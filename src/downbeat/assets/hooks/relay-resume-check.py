#!/usr/bin/env python3
"""Relay resume-identity check — warns at SessionStart when a resumed
session's relay identity cannot be determined, instead of leaving it to
fail silently at the first `send` (issue #71).

Wired into:
  SessionStart  — matcher "resume" only

Why this exists:
  Resume assigns Claude Code a brand-new session_id. `session_id_history`
  (PR #77) self-heals the common case — the new id was previously live for
  some peer, recorded in that peer's history — but issue #71's correction
  comment established there is a real, reported case where NO such lineage
  exists: the new id was never registered anywhere, so
  `find_peer_by_session_history` returns nothing and the self-heal falls
  straight through to a refusal. Before this hook, that refusal only
  surfaced at the moment a message was worth sending. This hook surfaces it
  at resume instead.

  It does NOT guess an identity and rebind automatically — issue #71 argues
  at length that a guess (name, cwd, "the only peer with a stale binding")
  is worse than a refusal, because it can bind a session to the wrong
  identity. This hook only ever *reports*; `downbeat rebind` stays a human
  decision.

Predicate (see find_stale_binding — deliberately narrow, to never nag a
session that was never a peer at all):
  - only considers source == "resume" (a brand-new "startup" session was
    never anyone's identity; nothing to warn about)
  - silent when this session_id is already some peer's current session_id
    (nothing wrong)
  - silent when this session_id is in ANY peer's session_id_history — that
    case self-heals silently on the next relay command (PR #77); warning
    about it too would be noise about something that already resolves
    itself
  - silent unless the resumed cwd matches EXACTLY ONE registered peer's cwd
    — that is the one piece of evidence available (this machine's registry
    previously bound a peer to this exact working directory). Zero matches
    means a genuinely fresh session — stay silent. More than one match is
    ambiguous — stay silent rather than guess which one.

Fails open: any exception, missing/unreadable registry, or unexpected
payload shape → silence + exit 0. This runs on EVERY session start; it must
never raise, never block startup, and never write to the registry.
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from pathlib import Path


def _relay_dir() -> Path:
    return Path(os.environ.get(
        "CLAUDE_RELAY_DIR", str(Path.home() / ".claude" / "relay")
    ))


def find_stale_binding(session_id, cwd, sessions):
    """Return (peer_name, peer_meta) if there is unambiguous evidence this
    resumed session is a stale-bound peer, else None. Pure and read-only —
    never touches the registry.
    """
    if not session_id or not cwd or not isinstance(sessions, dict):
        return None

    for meta in sessions.values():
        if not isinstance(meta, dict):
            continue
        if meta.get("session_id") == session_id:
            return None  # already correctly bound

    for meta in sessions.values():
        if not isinstance(meta, dict):
            continue
        if session_id in (meta.get("session_id_history") or []):
            return None  # self-heal (PR #77) already covers this

    candidates = [
        (name, meta) for name, meta in sessions.items()
        if isinstance(meta, dict) and meta.get("cwd") and meta["cwd"] == cwd
    ]
    if len(candidates) != 1:
        return None  # no evidence, or ambiguous -- never guess

    return candidates[0]


def render_message(peer_name, stale_session_id, session_id, cwd):
    stale_short = stale_session_id[:8] if stale_session_id else "?"
    sid_short = session_id[:8] if session_id else "?"
    return (
        "**downbeat: this session's relay identity looks stale.**\n\n"
        f"This session (`{sid_short}`) resumed in `{cwd}`, which downbeat's "
        f"registry binds to peer `{peer_name}` — but `{peer_name}` is still "
        f"pointed at a different, no-longer-current session "
        f"(`{stale_short}`). Until this is corrected, `{peer_name}` cannot "
        "send or receive relay messages as this session: `downbeat send` / "
        "`whoami` will refuse with \"session not registered\".\n\n"
        "Fix it:\n\n"
        f"    downbeat rebind {peer_name} --session-id {session_id}\n\n"
        f"If this session is not actually `{peer_name}`, ignore this and "
        "register under the correct name instead."
    )


def emit(message):
    sys.stdout.write(json.dumps({"systemMessage": message}) + "\n")
    sys.stdout.flush()


def main():
    raw = ""
    if sys.stdin is not None and not sys.stdin.isatty():
        raw = sys.stdin.read()
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except Exception:
        return
    if not isinstance(payload, dict):
        return

    if payload.get("source") != "resume":
        return

    session_id = payload.get("session_id")
    cwd = payload.get("cwd")
    if not session_id or not cwd:
        return

    sessions_file = _relay_dir() / "sessions.json"
    if not sessions_file.exists():
        return

    try:
        sessions = json.loads(sessions_file.read_text())
    except Exception:
        return

    hit = find_stale_binding(session_id, cwd, sessions)
    if hit is None:
        return

    name, meta = hit
    emit(render_message(name, meta.get("session_id", ""), session_id, cwd))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc(file=sys.stderr)
    sys.exit(0)
