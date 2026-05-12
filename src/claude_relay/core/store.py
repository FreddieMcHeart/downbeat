"""Filesystem-backed relay store: sessions.json + inbox/ + processed/.

All write operations are atomic via os.replace(). Read operations tolerate
missing files and return empty containers."""
from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path

from . import paths
from .errors import MessageLocked, MessageNotFound, PeerNotFound, StoreCorrupt
from .models import Broadcast, Message, MessageState, Peer, new_id, now_iso

_log = logging.getLogger("claude_relay.core")


def _atomic_write_text(target: Path, text: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(target.parent), prefix=".tmp-", text=True)
    try:
        with os.fdopen(fd, "w") as f:
            f.write(text)
        os.replace(tmp, target)
    except Exception:
        Path(tmp).unlink(missing_ok=True)
        raise


def _load_sessions() -> dict[str, dict]:
    if not paths.SESSIONS_FILE.exists():
        return {}
    try:
        return json.loads(paths.SESSIONS_FILE.read_text() or "{}")
    except json.JSONDecodeError as e:
        raise StoreCorrupt(f"{paths.SESSIONS_FILE} is not valid JSON: {e}") from e


def _save_sessions(data: dict[str, dict]) -> None:
    _atomic_write_text(paths.SESSIONS_FILE, json.dumps(data, indent=2))


def register_peer(name: str, session_id: str, cwd: str, role: str) -> Peer:
    sessions = _load_sessions()
    existing = sessions.get(name)
    registered_at = existing["registered_at"] if existing else now_iso()
    peer = Peer(name=name, session_id=session_id, cwd=cwd, role=role,
                registered_at=registered_at, last_seen=now_iso())
    sessions[name] = peer.to_dict()
    _save_sessions(sessions)
    _log.info("register peer=%s session=%s role=%s", name, session_id, role)
    return peer


def list_peers() -> list[Peer]:
    return [Peer.from_dict(d) for d in _load_sessions().values()]


def get_peer(name: str) -> Peer:
    sessions = _load_sessions()
    if name not in sessions:
        raise PeerNotFound(name)
    return Peer.from_dict(sessions[name])


def remove_peer(name: str) -> None:
    sessions = _load_sessions()
    sessions.pop(name, None)
    _save_sessions(sessions)


def touch_peer(name: str) -> None:
    sessions = _load_sessions()
    if name not in sessions:
        raise PeerNotFound(name)
    sessions[name]["last_seen"] = now_iso()
    _save_sessions(sessions)


def _message_path(msg: Message) -> Path:
    base = paths.PROCESSED_DIR if msg.archived else paths.INBOX_DIR
    return base / msg.to_peer / f"{msg.id}.json"


def _find_message_path(msg_id: str) -> Path:
    for base in (paths.INBOX_DIR, paths.PROCESSED_DIR):
        if not base.exists():
            continue
        for peer_dir in base.iterdir():
            candidate = peer_dir / f"{msg_id}.json"
            if candidate.exists():
                return candidate
    raise MessageNotFound(msg_id)


def _write_message(msg: Message) -> None:
    path = _message_path(msg)
    _atomic_write_text(path, msg.to_json())


def _read_message_at(path: Path) -> Message:
    try:
        return Message.from_json(path.read_text())
    except (json.JSONDecodeError, KeyError) as e:
        raise StoreCorrupt(f"{path} is not a valid message: {e}") from e


def get_message(msg_id: str) -> Message:
    return _read_message_at(_find_message_path(msg_id))


def send_message(from_peer: str, to_peer: str, subject: str, body: str,
                 broadcast_id: str | None = None) -> Message:
    # Sender doesn't need to be registered (CLI may send before its own
    # register completes); recipient must exist.
    get_peer(to_peer)
    msg = Message(
        id=new_id(),
        from_peer=from_peer,
        to_peer=to_peer,
        subject=subject,
        body=body,
        created_at=now_iso(),
        broadcast_id=broadcast_id,
    )
    _write_message(msg)
    _log.info("send from=%s to=%s msg=%s broadcast=%s bytes=%d",
              from_peer, to_peer, msg.id, broadcast_id, len(body))
    return msg


def mark_read(msg_id: str) -> Message:
    msg = get_message(msg_id)
    if msg.state != MessageState.NEW:
        return msg
    d = msg.to_dict()
    d["read_at"] = now_iso()
    updated = Message.from_dict(d)
    _write_message(updated)
    _log.info("read msg=%s", msg_id)
    return updated


def edit_message(msg_id: str, new_body: str | None = None,
                 new_subject: str | None = None) -> Message:
    msg = get_message(msg_id)
    if msg.state != MessageState.NEW:
        raise MessageLocked(
            f"message {msg_id} is in state {msg.state.value}; edit blocked"
        )
    d = msg.to_dict()
    if new_body is not None:
        d["body"] = new_body
    if new_subject is not None:
        d["subject"] = new_subject
    d["edited_at"] = now_iso()
    updated = Message.from_dict(d)
    _write_message(updated)
    _log.info("edit msg=%s new_body_bytes=%d", msg_id,
              len(new_body) if new_body else 0)
    return updated


def delete_message(msg_id: str) -> None:
    _find_message_path(msg_id).unlink()
    _log.info("delete msg=%s", msg_id)


def reply_to(msg_id: str, body: str, from_peer: str,
             subject_prefix: str = "Re: ") -> Message:
    original = get_message(msg_id)
    # Archive original
    d = original.to_dict()
    d["archived"] = True
    archived = Message.from_dict(d)
    # Move from inbox/ to processed/
    old_path = _find_message_path(msg_id)
    old_path.unlink()
    _write_message(archived)
    # Send the reply back to the original sender (bypass peer check — the
    # broadcaster may not be registered in the peer registry).
    reply = Message(
        id=new_id(),
        from_peer=from_peer,
        to_peer=original.from_peer,
        subject=f"{subject_prefix}{original.subject}",
        body=body,
        created_at=now_iso(),
        broadcast_id=original.broadcast_id,
    )
    _write_message(reply)
    _log.info("reply original=%s reply=%s", msg_id, reply.id)
    return reply


def list_inbox(peer_name: str, include_archived: bool = False) -> list[Message]:
    out: list[Message] = []
    inbox_dir = paths.INBOX_DIR / peer_name
    if inbox_dir.exists():
        for p in sorted(inbox_dir.glob("*.json")):
            out.append(_read_message_at(p))
    if include_archived:
        processed_dir = paths.PROCESSED_DIR / peer_name
        if processed_dir.exists():
            for p in sorted(processed_dir.glob("*.json")):
                out.append(_read_message_at(p))
    out.sort(key=lambda m: m.created_at, reverse=True)
    return out


def broadcast(from_peer: str, to_peers: list[str],
              subject: str, body: str) -> Broadcast:
    bc_id = new_id()
    bc = Broadcast(
        id=bc_id,
        subject=subject,
        body=body,
        from_peer=from_peer,
        to_peers=list(to_peers),
        created_at=now_iso(),
    )
    for target in to_peers:
        msg = send_message(from_peer=from_peer, to_peer=target,
                           subject=subject, body=body,
                           broadcast_id=bc_id)
        bc.message_ids.append(msg.id)
    _log.info("broadcast id=%s from=%s targets=%d",
              bc_id, from_peer, len(to_peers))
    return bc


def _scan_all_messages() -> list[Message]:
    out: list[Message] = []
    for base in (paths.INBOX_DIR, paths.PROCESSED_DIR):
        if not base.exists():
            continue
        for peer_dir in base.iterdir():
            for p in peer_dir.glob("*.json"):
                try:
                    out.append(_read_message_at(p))
                except StoreCorrupt:
                    continue
    return out


def broadcast_status(broadcast_id: str) -> list[dict]:
    """Return one row per original target. State derived from sibling messages
    and any reply messages that carry the same broadcast_id."""
    all_msgs = _scan_all_messages()
    siblings = [m for m in all_msgs if m.broadcast_id == broadcast_id]
    if not siblings:
        return []
    # The original fan-out: each target appears as a recipient of one sibling
    # with state != REPLY. A reply is a message FROM the target carrying the
    # same broadcast_id.
    originals = {m.to_peer: m for m in siblings
                 if m.from_peer != m.to_peer and not _is_reply(m, siblings)}
    rows: list[dict] = []
    for target, original in originals.items():
        replies = [m for m in siblings
                   if m.from_peer == target and m.id != original.id]
        if replies:
            state = "replied"
        elif original.state == MessageState.READ:
            state = "read"
        else:
            state = "pending"
        rows.append({"target": target, "state": state,
                     "original_id": original.id,
                     "reply_ids": [r.id for r in replies]})
    return rows


def _is_reply(msg: Message, siblings: list[Message]) -> bool:
    # A reply has both from_peer and to_peer flipped vs the original. We
    # treat any sibling where from_peer != "parent fan-out sender" as a reply.
    # Simpler heuristic: replies have subject starting with "Re: ".
    return msg.subject.startswith("Re: ")
