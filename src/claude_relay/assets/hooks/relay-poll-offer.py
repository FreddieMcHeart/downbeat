#!/usr/bin/env python3
"""Relay poll-offer hook — PostToolUse on Bash.

After a `send` or `reply` via the relay CLI, inject a one-time system reminder
asking Claude to consider offering the user a `/loop 3m` inbox-poll setup.

State file: ~/.claude/relay/loop_offer_state.json
  Keyed by session_id; each entry has {"hinted_at": ISO, "decided": bool}.

Fails open: any exception → stderr + exit 0, never blocks.
"""

import json
import re
import sys
import traceback
from datetime import UTC, datetime
from pathlib import Path

STATE_FILE = Path.home() / ".claude" / "relay" / "loop_offer_state.json"

# Match either path-based shim or the global CLI binary.
SEND_REPLY_RE = re.compile(
    r"(?:relay\.py|claude-relay)\s+(?:send|reply)\b"
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
