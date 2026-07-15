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
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys

# `downbeat X.Y.Z ...` -- describe() may add provenance detail after it.
_VERSION_RE = re.compile(r"\bdownbeat\s+(\d+\.\d+\.\d+(?:[.\w+-]*)?)")


def plugin_version() -> str | None:
    root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if not root:
        return None
    try:
        with open(os.path.join(root, ".claude-plugin", "plugin.json")) as f:
            return json.load(f).get("version")
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
    try:
        out = subprocess.run(
            [exe, "--version"],
            capture_output=True, text=True, timeout=5, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None, False
    text = f"{out.stdout} {out.stderr}"
    m = _VERSION_RE.search(text)
    return (m.group(1) if m else None), ("editable" in text)


def main() -> int:
    sys.stdin.read()  # drain the payload; we don't need it

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
    sys.exit(main())
