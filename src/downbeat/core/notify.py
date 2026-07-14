"""Native OS notification helper — best-effort, fails open.

Used by the TUI's resident FsWatcher (tui/app.py) to alert the human when a
message arrives for a stale (idle) recipient while the TUI itself is
running. The headless case (no TUI open) is covered by a SEPARATE, private
implementation inside assets/hooks/relay-poll-offer.py — that hook cannot
import this module (see docs/superpowers/specs/
2026-07-14-tui-hosted-relay-notify-design.md, "Implementation constraint").
"""
from __future__ import annotations

import logging
import subprocess
import sys

_log = logging.getLogger("downbeat.notify")


def _escape_applescript(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def notify(title: str, message: str) -> None:
    """Fire a native OS notification. Never raises — logs and returns on
    any failure (missing binary, timeout, unsupported platform)."""
    try:
        if sys.platform == "darwin":
            script = (
                f'display notification "{_escape_applescript(message)}" '
                f'with title "{_escape_applescript(title)}"'
            )
            subprocess.run(["osascript", "-e", script], timeout=3,
                           capture_output=True, check=False)
        elif sys.platform.startswith("linux"):
            subprocess.run(["notify-send", title, message], timeout=3,
                           capture_output=True, check=False)
        else:
            _log.debug("notify: unsupported platform %s, skipping", sys.platform)
    except Exception:
        _log.exception("notify() failed")
