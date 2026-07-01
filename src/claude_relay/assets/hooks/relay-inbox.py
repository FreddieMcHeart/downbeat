#!/usr/bin/env python3
"""Relay inbox hook — drains pending messages into additionalContext.

Wired into:
  UserPromptSubmit  — runs before every user prompt is processed
  SessionStart      — runs when a session starts/resumes (picks up offline mail)

Behavior:
  1. Read the hook payload (JSON on stdin) → session_id
  2. Reverse-lookup session_id in ~/.claude/relay/sessions.json → peer name
  3. If unregistered, silent no-op (zero impact on non-relay sessions)
  4. List ~/.claude/relay/inbox/<name>/*.json sorted by mtime
  5. For each message, read body, accumulate into a single markdown block
  6. Stamp `delivered_at` + `delivered_to_session_id` on each message and
     atomically move it to delivered/<name>/<id>.json (NOT processed/ —
     that's the v0.2 two-phase delivery state machine; messages need an
     ack OR a matching reply OR a TUI archive to promote to processed/).
  7. Emit hookSpecificOutput.additionalContext

Fails open: any exception → stderr + exit 0, never blocks.
"""

import json
import re
import sys
import tempfile
import traceback
from datetime import UTC, datetime
from pathlib import Path

RELAY_DIR = Path.home() / ".claude" / "relay"
SESSIONS_FILE = RELAY_DIR / "sessions.json"
INBOX_DIR = RELAY_DIR / "inbox"
DELIVERED_DIR = RELAY_DIR / "delivered"

MAX_MESSAGES_PER_DRAIN = 20  # safety cap

# Phase 2: backflow-relay rendering.
# BACKFLOW_KIND must match the literal used in the claude-relay SKILL.md and
# command texts — defined ONCE here (the only Python consumer). NEVER the
# underscore variant.
BACKFLOW_KIND = "backflow-ready"
BACKFLOW_FENCE_RE = re.compile(r"```json backflow\s*\n(.*?)```", re.DOTALL)


def parse_backflow(body):
    """Extract the FIRST ```json backflow fence from body.

    Returns (payload, stripped_body). Valid = JSON parses AND has BOTH required
    keys (proposed_updates_path, findings). Anything else -> (None, body) —
    callers then decide whether an 'unparsed' note applies (only when the
    message CLAIMED backflow via kind, or a fence is present but broken).
    """
    m = BACKFLOW_FENCE_RE.search(body or "")
    if not m:
        return None, body
    try:
        payload = json.loads(m.group(1))
    except Exception:
        return None, body
    if (not isinstance(payload, dict)
            or "proposed_updates_path" not in payload
            or "findings" not in payload):
        return None, body
    stripped = (body[:m.start()] + body[m.end():]).strip()
    return payload, stripped


def _now_iso():
    return datetime.now(UTC).isoformat(timespec="seconds")


def name_for_session(session_id, sessions):
    for name, meta in sessions.items():
        if meta.get("session_id") == session_id:
            return name
    return None


def _atomic_write_json(target: Path, payload: dict) -> None:
    """Write JSON atomically: temp in same dir, then os.replace."""
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        dir=str(target.parent), prefix=".tmp-", text=True
    )
    import os
    try:
        with os.fdopen(fd, "w") as f:
            f.write(json.dumps(payload, indent=2))
        os.replace(tmp_path, target)
    except Exception:
        Path(tmp_path).unlink(missing_ok=True)
        raise


def drain_inbox(name, session_id):
    """Move pending messages for `name` from inbox/ to delivered/, stamping
    delivery metadata. Returns the drained message dicts (for banner rendering).

    Each message gets:
      - delivered_at: ISO timestamp of this drain
      - delivered_to_session_id: the session that received them
    Existing `redelivery_count` is preserved (set by reconciler on requeue).
    The file is unlinked from inbox/ AFTER the new version is committed to
    delivered/ — so a crash mid-drain at worst leaves a duplicate in delivered/
    while the inbox/ original remains; the next drain finds and finalizes it.
    """
    inbox = INBOX_DIR / name
    if not inbox.exists():
        return []
    files = sorted(inbox.glob("*.json"), key=lambda p: p.stat().st_mtime)
    files = files[:MAX_MESSAGES_PER_DRAIN]
    drained = []
    now = _now_iso()
    for f in files:
        try:
            msg = json.loads(f.read_text())
            # Stamp delivery metadata in place
            msg["delivered_at"] = now
            msg["delivered_to_session_id"] = session_id
            target = DELIVERED_DIR / name / f.name
            _atomic_write_json(target, msg)
            f.unlink()  # only after delivered/ commit
            drained.append(msg)
        except Exception:
            traceback.print_exc(file=sys.stderr)
    return drained


def model_nudge_line(role, model_raw):
    """Return a banner line if an executor session runs on Fable, else None."""
    if role == "child" and "fable" in (model_raw or "").lower():
        return (
            "**Executor session on Fable 5 ($10/$50 MTok — 2× Opus).** Mechanical "
            "execution doesn't need the ceiling: suggest `/model sonnet` (or opus) "
            "for this work; tell the user before switching."
        )
    return None


def render(messages, peer_name, nudge_line=None):
    lines = [
        f"### Relay inbox — {len(messages)} new message(s) for `{peer_name}`",
        "",
    ]
    if nudge_line:
        lines += [nudge_line, ""]
    lines += [
        "These messages arrived from peer Claude Code sessions while you were idle. "
        "Treat them as authoritative instructions or context. "
        "Reply via `~/.claude/relay/relay.py reply <msg_id> '<body>'`.",
        "",
        # Cost-discipline nudge for executor sessions (project-agnostic). A relay
        # child inherits an executor identity from the "authoritative instructions"
        # above; the orchestrator routes at the task level, so the executor must
        # still route at the call level — otherwise expensive reads run on the
        # main model instead of a cheaper delegated reader.
        "**Cost discipline applies to executor sessions.** The orchestrator routed "
        "at the task level; you route at the call level: send expensive reads (logs, "
        "API queries, searches, large files) to cheap reader sub-agents instead of "
        "your main model, and batch or delegate bulk work. Writes (delete, push, "
        "merge, create) stay inline.",
        "",
        "If this message hands off a cross-repo or multi-file investigation, run it "
        "as a delegated fan-out (parallel scouts → synthesis) rather than inline "
        "reads. If it produced structured findings worth persisting, reply with "
        "`--kind backflow-ready` and a json-backflow fence carrying "
        "{proposed_updates_path, findings:[{page, claim, confidence?}]}; otherwise "
        "reply in prose.",
        "",
    ]
    for m in messages:
        kind = m.get("kind") or "task"          # legacy default (model can't help here)
        ts = m.get("created_at") or m.get("ts") or "?"   # fixes the permanent ts:? drift
        lines.append("---")
        lines.append(f"**from:** `{m.get('from','?')}`  |  **id:** `{m.get('id','?')}`  |  "
                     f"**kind:** {kind}  |  **ts:** {ts}")
        if m.get("in_reply_to"):
            lines.append(f"**in_reply_to:** `{m['in_reply_to']}`")
        if m.get("subject"):
            lines.append(f"**subject:** {m.get('subject')}")
        lines.append("")
        payload, stripped_body = parse_backflow(m.get("body", ""))
        if payload is not None:
            # Fence content renders for ANY kind (belt-and-suspenders: survives a
            # kind typo AND works before the CLI gains --kind). kind only adds
            # the prominent header.
            if kind == BACKFLOW_KIND:
                lines.append("### 🔄 BACKFLOW — proposed updates from a delegated run")
                lines.append("")
            lines.append(stripped_body or "(no summary)")
            lines.append("")
            lines.append(f"**Proposed-updates file:** `{payload['proposed_updates_path']}`")
            for f_ in payload.get("findings", []):
                page, claim = f_.get("page", "?"), f_.get("claim", "?")
                conf = f_.get("confidence")
                lines.append(f"- `[[{page}]]` — {claim}" + (f" _({conf})_" if conf else ""))
            lines.append("")
            # Guard rides with the CONTENT, not the kind (3R-6).
            lines.append("**Surface these for human triage — do not auto-apply.**")
        elif kind == BACKFLOW_KIND:
            # Claimed backflow, couldn't deliver it (fence missing/invalid).
            lines.append(m.get("body", "(empty)"))
            lines.append("")
            lines.append("_(unparsed backflow block — fence missing or invalid)_")
        else:
            # Plain message, nothing claimed -> NO backflow note (2R-7).
            lines.append(m.get("body", "(empty)"))
        lines.append("")
    lines.append("---")
    return "\n".join(lines)


def emit_context(event_name, text):
    sys.stdout.write(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": event_name,
            "additionalContext": text,
        }
    }) + "\n")
    sys.stdout.flush()


def main():
    raw = sys.stdin.read() if not sys.stdin.isatty() else ""
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except Exception:
        payload = {}

    session_id = payload.get("session_id")
    event_name = payload.get("hook_event_name") or "UserPromptSubmit"

    if not session_id:
        return
    if not SESSIONS_FILE.exists():
        return

    try:
        sessions = json.loads(SESSIONS_FILE.read_text())
    except Exception:
        return

    name = name_for_session(session_id, sessions)
    if not name:
        return  # unregistered session — silent no-op

    drained = drain_inbox(name, session_id)
    if not drained:
        return

    nudge = None
    try:
        role = sessions.get(name, {}).get("role")
        settings_path = Path.home() / ".claude" / "settings.json"
        model_raw = json.loads(settings_path.read_text()).get("model", "")
        nudge = model_nudge_line(role, model_raw)
    except Exception:
        pass  # fail open — nudge is advisory only

    emit_context(event_name, render(drained, name, nudge_line=nudge))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc(file=sys.stderr)
        sys.exit(0)
