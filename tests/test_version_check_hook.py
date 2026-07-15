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


# --- the tests that would have caught the ANSI bug ---------------------------
#
# Everything above fakes the CLI with `echo`. That is exactly how a hook that
# could never fire shipped: rich_argparse renders --version through the help
# formatter and emits ANSI even into a pipe, so the real bytes are
# '\x1b[39mdownbeat 0.9.2\x1b[0m' -- and the regex's leading \b could not match
# after the escape's trailing 'm'. A plain-text fixture proved nothing about
# the real thing. These tests use the real code path instead.

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


def _hook_parses(text):
    """Run the hook's own parsing over `text`, as if the CLI had printed it."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("_vc", HOOK)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    stripped = mod._ANSI_RE.sub("", text)
    m = mod._VERSION_RE.search(stripped)
    return (m.group(1) if m else None), ("editable" in stripped)


def test_hook_parses_the_real_release_version_output(monkeypatch):
    from downbeat.core.provenance import Provenance
    text = _real_version_output(monkeypatch, Provenance(version="0.9.2"))
    assert "downbeat 0.9.2" in mod_strip(text)
    version, editable = _hook_parses(text)
    assert version == "0.9.2", (
        f"hook cannot parse what the CLI actually prints: {text!r}"
    )
    assert editable is False


def test_hook_parses_the_real_editable_version_output(monkeypatch):
    from downbeat.core.provenance import Provenance
    text = _real_version_output(monkeypatch, Provenance(
        version="0.7.1", editable=True, editable_path="/Users/me/mama/downbeat"))
    version, editable = _hook_parses(text)
    assert version == "0.7.1"
    assert editable is True, "editable must be detected or we'd cry wolf forever"


def test_the_real_output_actually_contains_ansi(monkeypatch):
    """Guards the guard: if rich_argparse ever stops colourising, the ANSI
    stripping becomes untested dead weight and this test says so out loud."""
    from downbeat.core.provenance import Provenance
    text = _real_version_output(monkeypatch, Provenance(version="0.9.2"))
    assert "\x1b[" in text, (
        "the real --version no longer emits ANSI — the hook's stripping is now "
        "belt-without-braces; re-check whether it's still needed"
    )


def mod_strip(text):
    import re
    return re.sub(r"\x1b\[[0-9;]*m", "", text)
