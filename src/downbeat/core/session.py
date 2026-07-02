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


def _process_is_claude(pid: int) -> bool:
    """Return True if pid is a currently-running 'claude' process.
    Used to filter stale markers — a marker is only trustworthy if
    its owning PID is still alive AND still the claude that wrote it.
    PIDs get recycled, so 'alive' alone is not enough."""
    try:
        comm = subprocess.check_output(
            ["ps", "-o", "comm=", "-p", str(pid)],
            stderr=subprocess.DEVNULL,
        ).decode().strip().lower()
    except Exception:
        return False
    # `ps -o comm=` sometimes reports the full resolved binary path rather
    # than just the short process name — and where "claude" lands in that
    # path varies:
    #   - the real Claude Code install resolves to
    #     .../local/share/claude/versions/<version> — "claude" is a middle
    #     PATH SEGMENT, while the basename is just the version number
    #     (e.g. "2.1.197"). Basename-only matching false-negatives here.
    #   - a process invoked via `uv run` from a checkout directory named
    #     "downbeat" resolves to .../downbeat/.venv/bin/python3 —
    #     "claude" is a substring of an unrelated directory NAME
    #     ("downbeat"), not an exact segment. Whole-string substring
    #     matching false-positives here.
    # Matching an EXACT path segment (split on "/") handles both: it accepts
    # "claude" as a full segment anywhere in the path, but rejects a
    # look-alike segment like "downbeat".
    return "claude" in comm.split("/")


def detect_session_id() -> str | None:
    """Return the current Claude Code session_id, or None if not detectable.

    Only trusts markers whose owning PID is BOTH alive AND a claude
    process. Stale markers (PID dead, or PID recycled to a non-claude
    process) are skipped — they would otherwise misattribute messages
    to peers that no longer correspond to the calling session."""
    for pid in _walk_ancestors():
        if not _process_is_claude(pid):
            continue
        # 1) cost-discipline hook marker
        cd_marker = Path(f"/tmp/cc-session-by-pid-{pid}.txt")
        if cd_marker.exists():
            return cd_marker.read_text().strip()
        # 2) our own register backstop
        # Per-pid relay markers are written by `register`; the python CLI
        # process is short-lived so its PID rarely matches an ancestor.
        # Kept for backwards compat with older installs.
        relay_marker = paths.RELAY_DIR / f".sid-{pid}"
        if relay_marker.exists():
            return relay_marker.read_text().strip()
    return None


def gc_stale_markers() -> dict[str, int]:
    """Remove marker files whose owning PID is dead OR no longer a claude
    process. Returns counts of removed files per location."""
    removed = {"tmp": 0, "relay": 0}
    # Sweep /tmp/cc-session-by-pid-*.txt
    for p in Path("/tmp").glob("cc-session-by-pid-*.txt"):
        try:
            pid = int(p.stem.split("-")[-1])
        except ValueError:
            continue
        if not _process_is_claude(pid):
            try:
                p.unlink()
                removed["tmp"] += 1
            except OSError:
                pass
    # Sweep ~/.claude/relay/.sid-*
    if paths.RELAY_DIR.exists():
        for p in paths.RELAY_DIR.glob(".sid-*"):
            try:
                pid = int(p.name.removeprefix(".sid-"))
            except ValueError:
                continue
            if not _process_is_claude(pid):
                try:
                    p.unlink()
                    removed["relay"] += 1
                except OSError:
                    pass
    return removed


def write_marker_for_self(session_id: str) -> None:
    paths.RELAY_DIR.mkdir(parents=True, exist_ok=True)
    marker = paths.RELAY_DIR / f".sid-{os.getpid()}"
    marker.write_text(session_id)


def process_start_time(pid: int) -> str | None:
    """Return ISO-8601 normalized process start time, or None.
    macOS: `ps -o lstart=` returns 'Mon May 27 09:11:11 2026'.
    Linux: `ps -o lstart=` returns the same format on most distros.
    We parse and re-emit as ISO-8601 with second precision."""
    try:
        raw = subprocess.check_output(
            ["ps", "-o", "lstart=", "-p", str(pid)],
            stderr=subprocess.DEVNULL,
        ).decode().strip()
    except Exception:
        return None
    if not raw:
        return None
    try:
        from datetime import datetime
        dt = datetime.strptime(raw, "%a %b %d %H:%M:%S %Y")
        return dt.isoformat(timespec="seconds")
    except ValueError:
        return None


def detect_live_claude_pid() -> int | None:
    """Walk ancestors and return the first PID that is a live claude process."""
    for pid in _walk_ancestors():
        if _process_is_claude(pid):
            return pid
    return None
