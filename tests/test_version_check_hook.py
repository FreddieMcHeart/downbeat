"""The staleness hook is the thing that would have caught a real incident:
a session ran a TUI several releases behind for hours while the plugin
reported itself current. Its value is entirely in *when it stays quiet* --
a hook that talks every session gets ignored, and then it isn't there on the
one session that matters."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parents[1] / "hooks" / "version-check.py"


def _run(tmp_path, plugin_version, cli_stdout, on_path=True):
    """Run the hook with a fake `downbeat` on PATH.

    The fake is a shell script rather than a monkeypatch because the hook
    deliberately shells out -- it must report on the CLI the *user* would
    launch, not on whatever is importable in the hook's own interpreter.
    """
    plugin_root = tmp_path / "plugin"
    (plugin_root / ".claude-plugin").mkdir(parents=True)
    (plugin_root / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": "downbeat", "version": plugin_version})
    )

    bindir = tmp_path / "bin"
    bindir.mkdir()
    if on_path:
        fake = bindir / "downbeat"
        fake.write_text(f'#!/bin/sh\necho "{cli_stdout}"\n')
        fake.chmod(0o755)

    proc = subprocess.run(
        [sys.executable, str(HOOK)],
        input="{}",
        capture_output=True,
        text=True,
        timeout=20,
        env={
            "PATH": str(bindir),
            "CLAUDE_PLUGIN_ROOT": str(plugin_root),
            "HOME": str(tmp_path),
        },
    )
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.strip()


def test_warns_when_the_cli_lags_the_plugin(tmp_path):
    out = _run(tmp_path, plugin_version="0.9.2", cli_stdout="downbeat 0.7.1")
    assert out, "a lagging CLI must be reported -- this is the whole point"
    msg = json.loads(out)["systemMessage"]
    assert "0.9.2" in msg and "0.7.1" in msg
    assert "/downbeat:update" in msg, "a warning without the fix is just nagging"


def test_silent_when_versions_agree(tmp_path):
    assert _run(tmp_path, plugin_version="0.9.2", cli_stdout="downbeat 0.9.2") == ""


def test_silent_on_an_editable_install(tmp_path):
    """An editable install's version is stamped at install time while the code
    is read live from a working tree, so a mismatch there is expected and
    means nothing. Warning about it would cry wolf every single session."""
    out = _run(
        tmp_path,
        plugin_version="0.9.2",
        cli_stdout="downbeat 0.7.1 (editable -> /Users/me/mama/downbeat; ...)",
    )
    assert out == ""


def test_silent_when_no_downbeat_on_path(tmp_path):
    assert _run(tmp_path, plugin_version="0.9.2", cli_stdout="", on_path=False) == ""


def test_silent_when_the_cli_output_is_unparseable(tmp_path):
    """No opinion beats a wrong opinion."""
    assert _run(tmp_path, plugin_version="0.9.2", cli_stdout="weird output") == ""


@pytest.mark.parametrize("cli", ["downbeat 0.10.0", "downbeat 1.0.0"])
def test_warns_when_the_cli_is_ahead_too(tmp_path, cli):
    """Drift in either direction means the two artifacts disagree; the user
    should know regardless of which one moved."""
    assert _run(tmp_path, plugin_version="0.9.2", cli_stdout=cli) != ""


# --- against the real thing --------------------------------------------------
#
# Everything above fakes the CLI with `echo`. That is exactly how a hook that
# could never fire shipped: rich_argparse renders --version through the help
# formatter and emits ANSI even into a pipe, so the real bytes are
# '\x1b[39mdownbeat 0.9.2\x1b[0m' -- and the regex's leading \b could not match
# after the escape's trailing 'm'. A plain-text fixture proved nothing about
# the real thing.
#
# Nor did the first attempt at fixing that: it fed real output to a *copy* of
# the hook's two regexes, which is a restatement of the implementation, not a
# test of the chain. _run_version -- the part that actually talks to the CLI,
# and the part that then shipped an unbounded hang -- had no coverage at all.
# So these drive the real hook process against a real CLI on a real PATH.

def _real_version_output(monkeypatch, prov):
    """The exact string `downbeat --version` prints for a given provenance,
    rendered through the real argparse + rich_argparse path."""
    from downbeat.cli import __main__ as cli
    from downbeat.core import provenance as prov_mod

    monkeypatch.setattr(prov_mod, "detect", lambda: prov)
    parser = cli.build_parser()
    import contextlib
    import io
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.suppress(SystemExit):
        parser.parse_args(["--version"])
    return buf.getvalue()


def _hook_module():
    import importlib.util
    spec = importlib.util.spec_from_file_location("_vc_re", HOOK)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_version_regex_matches_colourised_output(monkeypatch):
    """The regex must handle a colourised version line. Colour is FORCED here
    rather than hoped for.

    rich_argparse renders --version to a *string*, so it decides on colour
    from the environment, not from isatty -- which is why the real CLI emits
    ANSI into a pipe on a developer's machine (TERM is set) and plain text in
    CI (it isn't). An earlier version of this test just asserted "the real
    output contains ANSI" and so encoded the author's own terminal: green
    locally, red on every CI runner, and testing nothing either way.

    That environment-dependence is also why the original bug was insidious --
    the inert regex only failed where someone had a TERM.
    """
    monkeypatch.setenv("FORCE_COLOR", "1")
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.delenv("TERM", raising=False)  # TERM=dumb defeats FORCE_COLOR

    from downbeat.core.provenance import Provenance
    text = _real_version_output(monkeypatch, Provenance(version="0.9.2"))
    assert "\x1b[" in text, "FORCE_COLOR no longer forces colour; test is moot"
    assert _hook_module()._VERSION_RE.search(text), (
        "the regex cannot match colourised output — this is the exact shape "
        "that shipped inert. Do not let NO_COLOR become the only defence."
    )


def test_no_color_is_what_the_hook_actually_relies_on(monkeypatch):
    """The companion fact: with NO_COLOR the CLI answers plain, which is why
    _ANSI_RE is dormant in production. Pinned so the two defences stay
    honestly labelled -- the stripping is the spare, not the engine."""
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.setenv("FORCE_COLOR", "1")  # NO_COLOR must still win

    from downbeat.core.provenance import Provenance
    text = _real_version_output(monkeypatch, Provenance(version="0.9.2"))
    assert "\x1b[" not in text, "NO_COLOR no longer wins; _ANSI_RE is now load-bearing"


# --- integration: the real hook, a real CLI, a real PATH ---------------------

def _rich_cli(tmp_path, version, editable=False, grandchild_sleep=None,
               ignores_no_color=False):
    """A `downbeat` on PATH whose --version goes through the REAL argparse +
    rich_argparse path -- ANSI and all -- rather than `echo`.

    The python goes in its own file rather than `sh -c '...'`: an earlier
    version inlined it and the paths, interpolated with !r, arrived
    single-quoted and closed the shell's own quote. The script then printed
    nothing and the test failed pointing at the hook. Nothing to quote,
    nothing to get wrong.
    """
    src = Path(__file__).resolve().parents[1] / "src"
    prov = (f'Provenance(version="{version}", editable=True, '
            f'editable_path="/w/tree")' if editable
            else f'Provenance(version="{version}")')
    # ignores_no_color: a CLI that colours its output regardless of what we
    # ask. That is the ONLY scenario in which _ANSI_RE earns its place -- with
    # a compliant CLI the hook's NO_COLOR request means the stripping never
    # runs, so without this the defence-in-depth is entirely untested and the
    # branch would rot unnoticed.
    force = ('import os\nos.environ["FORCE_COLOR"] = "1"\n'
             'os.environ.pop("NO_COLOR", None)\nos.environ.pop("TERM", None)\n'
             if ignores_no_color else "")
    pyfile = tmp_path / "fake_downbeat.py"
    pyfile.write_text(
        "import sys\n"
        + force
        + f'sys.path.insert(0, "{src}")\n'
        "from downbeat.core import provenance as p\n"
        "from downbeat.core.provenance import Provenance\n"
        f"p.detect = lambda: {prov}\n"
        "from downbeat.cli.__main__ import build_parser\n"
        'build_parser().parse_args(["--version"])\n'
    )

    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    script = bindir / "downbeat"
    lines = ["#!/bin/sh"]
    if grandchild_sleep:
        # Outlives the child and keeps the inherited pipe write-end open.
        lines.append(f"( sleep {grandchild_sleep} & )")
    lines.append(f'exec "{sys.executable}" "{pyfile}" "$@"')
    script.write_text("\n".join(lines) + "\n")
    script.chmod(0o755)
    return bindir


def _run_hook(tmp_path, bindir, plugin_version):
    plugin_root = tmp_path / "plugin"
    (plugin_root / ".claude-plugin").mkdir(parents=True, exist_ok=True)
    (plugin_root / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": "downbeat", "version": plugin_version}))
    proc = subprocess.run(
        [sys.executable, str(HOOK)], input="{}", capture_output=True,
        text=True, timeout=30,
        env={"PATH": f"{bindir}:/usr/bin:/bin", "CLAUDE_PLUGIN_ROOT": str(plugin_root),
             "HOME": str(tmp_path)},
    )
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.strip()


def test_end_to_end_warns_against_a_real_rich_argparse_cli(tmp_path):
    """The one that matters: real hook process, real CLI, real ANSI. This is
    the test whose absence let an inert hook ship."""
    bindir = _rich_cli(tmp_path, "0.7.1")
    out = _run_hook(tmp_path, bindir, plugin_version="0.9.2")
    assert out, "hook stayed silent against real drift — it is inert again"
    assert "0.7.1" in json.loads(out)["systemMessage"]


def test_end_to_end_silent_when_a_real_cli_matches(tmp_path):
    bindir = _rich_cli(tmp_path, "0.9.2")
    assert _run_hook(tmp_path, bindir, plugin_version="0.9.2") == ""


def test_end_to_end_silent_against_a_real_editable_cli(tmp_path):
    bindir = _rich_cli(tmp_path, "0.7.1", editable=True)
    assert _run_hook(tmp_path, bindir, plugin_version="0.9.2") == ""


def test_a_grandchild_holding_the_pipe_does_not_stall_session_start(tmp_path):
    """A child that exits fast but leaves a grandchild on the inherited pipe
    write-end yields no EOF. A blocking read waits out the grandchild's whole
    life -- measured at 20s for a 20s sleeper, and in production the 8s hook
    timeout then kills the hook, so the warning is never shown either. Both
    halves matter: it must be fast AND still report."""
    import time
    bindir = _rich_cli(tmp_path, "0.7.1", grandchild_sleep=10)
    start = time.monotonic()
    out = _run_hook(tmp_path, bindir, plugin_version="0.9.2")
    elapsed = time.monotonic() - start
    assert elapsed < 5, f"hook took {elapsed:.1f}s — it is waiting out the grandchild"
    assert out, "hook must still report the drift, not just return quickly"


def test_stderr_mentioning_editable_cannot_silence_the_hook(tmp_path):
    """`"editable" in <whole capture>` let any passing mention -- a uv/pip
    deprecation notice -- disable the check permanently and invisibly."""
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    script = bindir / "downbeat"
    script.write_text('#!/bin/sh\n'
                      'echo "note: editable installs are deprecated" >&2\n'
                      'echo "downbeat 0.7.1"\n')
    script.chmod(0o755)
    assert _run_hook(tmp_path, bindir, plugin_version="0.9.2") != ""


def test_end_to_end_against_a_cli_that_ignores_no_color(tmp_path):
    """The scenario _ANSI_RE exists for, and the one nothing covered until now.

    The hook asks for NO_COLOR and the real CLI complies, so every other test
    here -- including the "real CLI" ones -- goes down the plain-text path.
    That means the ANSI stripping, added precisely because a colourised line
    once made this hook permanently inert, had no test at all. A CLI that
    ignores NO_COLOR is exactly what the spare tyre is for.
    """
    bindir = _rich_cli(tmp_path, "0.7.1", ignores_no_color=True)
    out = _run_hook(tmp_path, bindir, plugin_version="0.9.2")
    assert out, "hook went silent against a colourised CLI — inert all over again"
    assert "0.7.1" in json.loads(out)["systemMessage"]


def test_end_to_end_editable_detected_even_when_colourised(tmp_path):
    """Same path, opposite expectation: the '(editable' sniff must survive the
    ANSI too, or an editable install gets nagged every session."""
    bindir = _rich_cli(tmp_path, "0.7.1", editable=True, ignores_no_color=True)
    assert _run_hook(tmp_path, bindir, plugin_version="0.9.2") == ""
