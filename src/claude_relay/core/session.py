"""Session-id detection for Claude Code processes.

Claude Code's Bash tool runs without CLAUDE_SESSION_ID exported, so we
infer the session by walking up the process tree looking for marker
files written by the cost-discipline hook or by our own register
command."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

from . import paths

_ANCESTOR_HOPS = 10


def _walk_ancestors():
    pid = os.getpid()
    for _ in range(_ANCESTOR_HOPS):
        try:
            ppid = int(subprocess.check_output(
                ["ps", "-o", "ppid=", "-p", str(pid)],
                stderr=subprocess.DEVNULL,
            ).decode().strip())
        except Exception:
            return
        if ppid <= 1:
            return
        yield ppid
        pid = ppid


def detect_session_id() -> str | None:
    """Return the current Claude Code session_id, or None if not detectable."""
    for pid in _walk_ancestors():
        # 1) cost-discipline hook marker
        cd_marker = Path(f"/tmp/cc-session-by-pid-{pid}.txt")
        if cd_marker.exists():
            return cd_marker.read_text().strip()
        # 2) our own register backstop
        relay_marker = paths.RELAY_DIR / f".sid-{pid}"
        if relay_marker.exists():
            return relay_marker.read_text().strip()
    return None


def write_marker_for_self(session_id: str) -> None:
    paths.RELAY_DIR.mkdir(parents=True, exist_ok=True)
    marker = paths.RELAY_DIR / f".sid-{os.getpid()}"
    marker.write_text(session_id)
