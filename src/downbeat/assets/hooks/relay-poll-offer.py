#!/usr/bin/env python3
"""Relay poll-offer hook — PostToolUse on Bash.

After a `send` or `reply` via the relay CLI, inject a one-time system reminder
asking Claude to consider offering the user a `/loop 3m` inbox-poll setup.

State file: ~/.claude/relay/loop_offer_state.json
  Keyed by session_id; each entry has {"hinted_at": ISO, "decided": bool}.

Fails open: any exception → stderr + exit 0, never blocks.
"""

import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
import traceback
from datetime import UTC, datetime, timedelta
from pathlib import Path

STATE_FILE = Path.home() / ".claude" / "relay" / "loop_offer_state.json"

# --- Idle-recipient staleness notify -----------------------------------
# Self-contained: this hook has NO downbeat package import available (see
# docs/superpowers/specs/2026-07-14-tui-hosted-relay-notify-design.md,
# "Implementation constraint") — every helper below duplicates, rather than
# imports, the equivalent logic in core/store.py, core/state.py, and
# core/notify.py.

_STALE_THRESHOLD_MINUTES = 10


def _relay_dir() -> Path:
    return Path(os.environ.get("CLAUDE_RELAY_DIR",
                               str(Path.home() / ".claude" / "relay")))


def _is_fresh(iso_ts: str | None, threshold_minutes: int) -> bool:
    if not iso_ts:
        return False
    try:
        ts = datetime.fromisoformat(iso_ts)
    except ValueError:
        return False
    return ts >= datetime.now(UTC) - timedelta(minutes=threshold_minutes)


def _is_stale(iso_ts: str | None, threshold_minutes: int) -> bool:
    """Mirrors core/store.py's _is_timestamp_stale contract exactly: missing
    or malformed timestamp -> False (not stale), never raises."""
    if not iso_ts:
        return False
    try:
        ts = datetime.fromisoformat(iso_ts)
    except ValueError:
        return False
    return ts < datetime.now(UTC) - timedelta(minutes=threshold_minutes)


def _is_recipient_stale(peer_name: str,
                        threshold_minutes: int = _STALE_THRESHOLD_MINUTES) -> bool:
    sessions_file = _relay_dir() / "sessions.json"
    if not sessions_file.exists():
        return False
    try:
        sessions = json.loads(sessions_file.read_text() or "{}")
    except Exception:
        return False
    peer = sessions.get(peer_name)
    if not peer:
        return False
    return _is_stale(peer.get("last_seen"), threshold_minutes)


def _escape_applescript(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _notify(title: str, message: str) -> None:
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
    except Exception:
        pass


def _read_tui_state() -> dict:
    tui_state_file = _relay_dir() / "tui_state.json"
    if not tui_state_file.exists():
        return {}
    try:
        return json.loads(tui_state_file.read_text() or "{}")
    except Exception:
        return {}


def _write_tui_state(data: dict) -> None:
    tui_state_file = _relay_dir() / "tui_state.json"
    tui_state_file.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(tui_state_file.parent), prefix=".tmp-", text=True)
    try:
        with os.fdopen(fd, "w") as f:
            f.write(json.dumps(data, indent=2))
        os.replace(tmp, tui_state_file)
    except Exception:
        Path(tmp).unlink(missing_ok=True)
        raise


def _lookup_original_sender(msg_id: str) -> str | None:
    for sub in ("inbox", "delivered", "processed"):
        base = _relay_dir() / sub
        if not base.exists():
            continue
        for match in base.glob(f"*/{msg_id}.json"):
            try:
                data = json.loads(match.read_text())
            except Exception:
                continue
            return data.get("from_peer")
    return None


def _resolve_recipient(command: str) -> str | None:
    try:
        tokens = shlex.split(command)
    except ValueError:
        return None
    for i, tok in enumerate(tokens):
        if tok in ("send", "reply") and i + 1 < len(tokens):
            arg = tokens[i + 1]
            if tok == "send":
                return arg
            return _lookup_original_sender(arg)
    return None


def _maybe_notify_stale_recipient(command: str) -> None:
    """Best-effort native notification if the send/reply's recipient looks
    idle and no TUI is currently watching. Never raises."""
    try:
        to_peer = _resolve_recipient(command)
        if not to_peer:
            return
        if not _is_recipient_stale(to_peer):
            return
        tui_state = _read_tui_state()
        if _is_fresh(tui_state.get("watcher_heartbeat_at"),
                     _STALE_THRESHOLD_MINUTES):
            return  # a TUI is open and will notify itself — avoid double-fire
        last_sent = tui_state.get("notify_last_sent", {}).get(to_peer)
        if _is_fresh(last_sent, _STALE_THRESHOLD_MINUTES):
            return  # cooldown
        _notify("downbeat", f"New message for {to_peer}")
        tui_state.setdefault("notify_last_sent", {})[to_peer] = (
            datetime.now(UTC).isoformat(timespec="seconds")
        )
        _write_tui_state(tui_state)
    except Exception:
        traceback.print_exc(file=sys.stderr)

# Match either path-based shim or the global CLI binary.
SEND_REPLY_RE = re.compile(
    r"(?:relay\.py|downbeat)\s+(?:send|reply)\b"
)

HINT = (
    "The user just executed a relay `send`/`reply`. If they appear to be done "
    "with local work for now AND there is no relay `/loop` already running in "
    "this session, use AskUserQuestion to offer:\n\n"
    "> \"You just sent a relay message. Want me to check the inbox every 3 "
    "minutes for a reply and surface it when it arrives?\"\n\n"
    "Options:\n"
    "- Yes, poll every 3 min → invoke `/loop 3m Check the relay inbox via "
    "~/.claude/relay/relay.py inbox. If there are new messages for a "
    "registered peer, surface them concisely (sender, subject, id) and ask "
    "how to handle each. If empty, stay silent.`\n"
    "- Yes, poll every 5 min → same instruction with `/loop 5m`\n"
    "- No, I'll check manually\n\n"
    "If the user already has queued tasks or is actively working on something "
    "else, do NOT interrupt — skip the offer this turn. This hint will only "
    "fire ONCE per session."
)


def _load_state() -> dict:
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text() or "{}")
    except Exception:
        return {}


def _save_state(data: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(data, indent=2))


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        # No stdin / not JSON → silent no-op
        return

    tool_name = payload.get("tool_name") or payload.get("toolName") or ""
    if tool_name != "Bash":
        return

    tool_input = payload.get("tool_input") or payload.get("toolInput") or {}
    command = (tool_input.get("command") or "").strip()
    if not SEND_REPLY_RE.search(command):
        return

    # Tool result inspection: only fire if the command succeeded.
    tool_result = payload.get("tool_result") or payload.get("toolResult") or {}
    # Exit code field varies; treat absent as success (best-effort).
    exit_code = tool_result.get("exit_code")
    if exit_code is not None and exit_code != 0:
        return

    # Independent of the once-per-session /loop-offer gate below — fires
    # every send/reply that targets a currently-stale peer, subject to its
    # own per-recipient cooldown.
    _maybe_notify_stale_recipient(command)

    session_id = (
        payload.get("session_id")
        or payload.get("sessionId")
        or ""
    )
    if not session_id:
        # No session id → still emit the hint (better safe than silent), but
        # we can't dedupe by session.
        sys.stdout.write(json.dumps({"systemMessage": HINT}) + "\n")
        return

    state = _load_state()
    entry = state.get(session_id) or {}
    if entry.get("hinted_at"):
        # Already fired in this session — silent.
        return

    entry["hinted_at"] = datetime.now(UTC).isoformat(timespec="seconds")
    state[session_id] = entry
    try:
        _save_state(state)
    except Exception:
        traceback.print_exc(file=sys.stderr)

    sys.stdout.write(json.dumps({"systemMessage": HINT}) + "\n")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc(file=sys.stderr)
        # Never block tools
        sys.exit(0)
