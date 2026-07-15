#!/usr/bin/env python3
"""Staleness check — warns when the downbeat CLI is older than this plugin.

Wired into:
  SessionStart  — startup|resume

Why this exists:
  The plugin and the `downbeat` CLI are two separate artifacts with two
  separate update paths, and Claude Code plugins fundamentally cannot ship a
  terminal command (plugin `bin/` is on the Bash *tool's* PATH, not the
  user's shell). So `claude plugin update` moves one and not the other, and
  nothing announces the drift. A real session ran a TUI several releases
  stale for hours while the plugin reported itself up to date, and a bug got
  filed against the version `--version` printed rather than the code that ran.

  This hook closes that specific hole: the next session start after the two
  diverge, it says so and gives the one command that fixes it.

Deliberately:
  - Asks the `downbeat` on the user's PATH, via subprocess, rather than
    importing downbeat here. The hook runs under Claude Code's interpreter;
    the CLI usually lives in its own venv (uv tool). Importing would report
    on the wrong installation, which is the exact class of bug this hook is
    supposed to catch.
  - Says nothing when the versions agree. A hook that speaks every session
    gets tuned out, and then it is worthless on the one session that matters.
  - Says nothing on an editable install beyond naming it: there the version
    is stamped at install time and the code is read live from a working tree,
    so "0.7.1 != 0.9.2" would be noise, not news.
  - Never raises and never blocks. It runs on EVERY session start, so any
    failure -- weird install, hostile binary on PATH, unreadable manifest --
    must degrade to silence, not to an error banner or a stall.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys

# rich_argparse renders --version through the help formatter and emits colour
# even into a pipe, so the real output is '\x1b[39mdownbeat 0.9.2\x1b[0m'.
# We ask for plain text via NO_COLOR *and* strip ANSI anyway: relying on
# either alone once made this hook silently unable to fire at all.
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
# No \b before 'downbeat': the char before it is 'm' (end of an ANSI escape)
# whenever stripping is bypassed, and word-char->word-char is not a boundary,
# which is precisely how this regex used to never match.
_VERSION_RE = re.compile(r"downbeat\s+(\d+\.\d+\.\d+(?:[.\w+-]*)?)")

# --version prints ~100 bytes. Anything beyond this is a broken or hostile
# binary and we want none of it in memory: an unbounded capture of a
# `yes`-style flooder was measured allocating 13 GB before its timeout fired.
_MAX_OUTPUT = 64 * 1024
_SUBPROCESS_TIMEOUT = 5


def plugin_version() -> str | None:
    root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if not root:
        return None
    try:
        with open(os.path.join(root, ".claude-plugin", "plugin.json")) as f:
            data = json.load(f)
        # Valid JSON that isn't an object is still garbage to us.
        return data.get("version") if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def cli_report() -> tuple[str | None, bool]:
    """(version, is_editable) for the `downbeat` on PATH.

    (None, False) when there is no downbeat to ask, or it can't be parsed --
    both mean "no opinion", never a warning. A hook that guesses wrong is
    worse than a hook that stays quiet.
    """
    exe = shutil.which("downbeat")
    if not exe:
        return None, False

    text = _run_version(exe)
    if text is None:
        return None, False
    m = _VERSION_RE.search(text)
    # Match 'editable' only against our own version line, not arbitrary
    # stderr, so an unrelated warning mentioning the word can't silence us.
    return (m.group(1) if m else None), ("editable" in text)


def _run_version(exe: str) -> str | None:
    """`<exe> --version`, bounded in both time and memory, or None.

    Reads nothing until the child exits: a flooder blocks on a full pipe
    buffer (~64KB) instead of ballooning this process, and then dies on the
    timeout. subprocess.run(capture_output=True) buffers without limit and
    does not bound this -- it was measured hitting 18GB RSS.
    """
    try:
        proc = subprocess.Popen(
            [exe, "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,  # never let a child eat OUR stdin
            text=True,
            env={**os.environ, "NO_COLOR": "1"},
        )
    except (OSError, subprocess.SubprocessError):
        return None

    try:
        try:
            proc.wait(timeout=_SUBPROCESS_TIMEOUT)
        except subprocess.TimeoutExpired:
            return None
        return _ANSI_RE.sub("", proc.stdout.read(_MAX_OUTPUT) if proc.stdout else "")
    except (OSError, ValueError):
        return None
    finally:
        if proc.poll() is None:
            proc.kill()
        try:
            if proc.stdout:
                proc.stdout.close()
        except OSError:
            pass
        proc.wait()


def main() -> int:
    # Claude Code always supplies stdin, but a closed fd 0 makes sys.stdin
    # None and a tty makes read() block to EOF -- burning the hook's whole
    # timeout on every session start. The sibling relay-inbox.py already
    # guards this; don't relearn it.
    if sys.stdin is not None and not sys.stdin.isatty():
        try:
            sys.stdin.read()
        except (OSError, ValueError):
            pass

    want = plugin_version()
    have, editable = cli_report()
    if not want or not have:
        return 0

    if editable:
        # The number is a fossil; comparing it would cry wolf every session.
        return 0
    if have == want:
        return 0

    sys.stdout.write(json.dumps({
        "systemMessage": (
            f"**downbeat: your CLI is out of step with the plugin.**\n\n"
            f"- plugin: `{want}`\n"
            f"- `downbeat` on your PATH: `{have}`\n\n"
            f"The two update separately — a Claude Code plugin can't ship a "
            f"terminal command, so `claude plugin update` moves the plugin "
            f"only. Bring both in line with one command:\n\n"
            f"    /downbeat:update\n\n"
            f"Until then the TUI you launch runs `{have}`, whatever this "
            f"plugin's hooks and commands say."
        )
    }) + "\n")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        # Last resort. A non-zero exit surfaces a "hook error" banner plus a
        # stderr line in the transcript on every single session start; a
        # version check is never worth that.
        sys.exit(0)
