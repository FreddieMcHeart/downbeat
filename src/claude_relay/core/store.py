"""Filesystem-backed relay store: sessions.json + inbox/ + processed/.

All write operations are atomic via os.replace(). Read operations tolerate
missing files and return empty containers."""
from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import UTC
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


def _append_delivery_log(event: dict) -> None:
    paths.RELAY_DIR.mkdir(parents=True, exist_ok=True)
    line = json.dumps({**event, "at": now_iso()})
    with paths.DELIVERY_LOG.open("a") as f:
        f.write(line + "\n")


def _load_sessions() -> dict[str, dict]:
    if not paths.SESSIONS_FILE.exists():
        return {}
    try:
        raw = json.loads(paths.SESSIONS_FILE.read_text() or "{}")
    except json.JSONDecodeError as e:
        raise StoreCorrupt(f"{paths.SESSIONS_FILE} is not valid JSON: {e}") from e
    # Backfill missing `name` from the dict key (legacy relay.py compat)
    for key, value in raw.items():
        if "name" not in value:
            value["name"] = key
    return raw


def _save_sessions(data: dict[str, dict]) -> None:
    _atomic_write_text(paths.SESSIONS_FILE, json.dumps(data, indent=2))


def register_peer(name: str, session_id: str, cwd: str, role: str,
                  claude_pid: int | None = None,
                  claude_pid_start: str | None = None) -> Peer:
    sessions = _load_sessions()
    existing = sessions.get(name)
    registered_at = existing["registered_at"] if existing else now_iso()
    history = list(existing.get("session_id_history", [])) if existing else []
    if existing and existing.get("session_id") and existing["session_id"] != session_id:
        if existing["session_id"] not in history:
            history.append(existing["session_id"])
    peer = Peer(
        name=name, session_id=session_id, cwd=cwd, role=role,
        registered_at=registered_at, last_seen=now_iso(),
        claude_pid=claude_pid,
        claude_pid_start=claude_pid_start,
        session_id_history=history,
    )
    sessions[name] = peer.to_dict()
    _save_sessions(sessions)
    _log.info("register peer=%s session=%s role=%s claude_pid=%s",
              name, session_id, role, claude_pid)
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
    if msg.quarantined_at is not None:
        base = paths.QUARANTINE_DIR
    elif msg.archived:
        base = paths.PROCESSED_DIR
    elif msg.delivered_at is not None and msg.delivery_ack_at is None:
        base = paths.DELIVERED_DIR
    else:
        base = paths.INBOX_DIR
    return base / msg.to_peer / f"{msg.id}.json"


def _find_message_in(base: Path, msg_id: str) -> Path | None:
    if not base.exists():
        return None
    for peer_dir in base.iterdir():
        candidate = peer_dir / f"{msg_id}.json"
        if candidate.exists():
            return candidate
    return None


def _find_message_path(msg_id: str) -> Path:
    for base in (paths.INBOX_DIR, paths.DELIVERED_DIR, paths.PROCESSED_DIR,
                 paths.QUARANTINE_DIR):
        p = _find_message_in(base, msg_id)
        if p is not None:
            return p
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
                 broadcast_id: str | None = None,
                 in_reply_to: str | None = None,
                 kind: str = "task") -> Message:
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
        in_reply_to=in_reply_to,
        kind=kind,
    )
    _write_message(msg)
    _log.info("send from=%s to=%s msg=%s kind=%s broadcast=%s in_reply_to=%s bytes=%d",
              from_peer, to_peer, msg.id, kind, broadcast_id, in_reply_to, len(body))
    return msg


def deliver_messages(peer_name: str, session_id: str,
                     max: int = 20) -> list[Message]:
    """Move up to max messages from inbox/<peer>/ to delivered/<peer>/,
    stamping delivered_at + delivered_to_session_id."""
    inbox_dir = paths.INBOX_DIR / peer_name
    if not inbox_dir.exists():
        return []
    delivered_dir = paths.DELIVERED_DIR / peer_name
    delivered_dir.mkdir(parents=True, exist_ok=True)
    paths_sorted = sorted(inbox_dir.glob("*.json"),
                          key=lambda p: p.stat().st_mtime)[:max]
    out: list[Message] = []
    for p in paths_sorted:
        try:
            msg = _read_message_at(p)
        except StoreCorrupt:
            continue
        d = msg.to_dict()
        d["delivered_at"] = now_iso()
        d["delivered_to_session_id"] = session_id
        updated = Message.from_dict(d)
        target = delivered_dir / p.name
        _atomic_write_text(target, updated.to_json())
        p.unlink()
        out.append(updated)
        _log.info("deliver msg=%s peer=%s to_session=%s redelivery=%d",
                  msg.id, peer_name, session_id, msg.redelivery_count)
        _append_delivery_log({"event": "deliver", "msg_id": msg.id,
                              "peer": peer_name, "session_id": session_id,
                              "redelivery_count": msg.redelivery_count})
    return out


def ack_messages(ids: list[str]) -> dict[str, bool]:
    """For each id, find the message in delivered/, set delivery_ack_at,
    move to processed/, archive=True. Returns map of id→success."""
    result: dict[str, bool] = {}
    for mid in ids:
        try:
            path = _find_message_in(paths.DELIVERED_DIR, mid)
            if path is None:
                # Maybe already processed; treat as not-found
                result[mid] = False
                continue
            msg = _read_message_at(path)
            d = msg.to_dict()
            d["delivery_ack_at"] = now_iso()
            d["archived"] = True
            updated = Message.from_dict(d)
            peer = path.parent.name
            target = paths.PROCESSED_DIR / peer / path.name
            _atomic_write_text(target, updated.to_json())
            path.unlink()
            _log.info("ack msg=%s peer=%s", mid, peer)
            _append_delivery_log({"event": "ack", "msg_id": mid, "peer": peer})
            result[mid] = True
        except Exception:
            _log.exception("ack failed for %s", mid)
            result[mid] = False
    return result


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
             subject_prefix: str = "Re: ", kind: str = "task") -> Message:
    original = get_message(msg_id)
    old_path = _find_message_path(msg_id)
    # Archive original + auto-ack if it was in delivered/
    d = original.to_dict()
    d["archived"] = True
    if original.delivered_at is not None and original.delivery_ack_at is None:
        d["delivery_ack_at"] = now_iso()
        _append_delivery_log({"event": "auto_ack_via_reply",
                              "msg_id": msg_id, "peer": original.to_peer})
    archived = Message.from_dict(d)
    old_path.unlink()
    _write_message(archived)
    # Send the reply with in_reply_to set.
    # Bypass peer check — the broadcaster (original.from_peer) may not be
    # registered in the peer registry (broadcast fan-out case).
    reply = Message(
        id=new_id(),
        from_peer=from_peer,
        to_peer=original.from_peer,
        subject=f"{subject_prefix}{original.subject}",
        body=body,
        created_at=now_iso(),
        broadcast_id=original.broadcast_id,
        in_reply_to=msg_id,
        kind=kind,
    )
    _write_message(reply)
    _log.info("reply original=%s reply=%s kind=%s", msg_id, reply.id, kind)
    return reply


def list_inbox(peer_name: str, include_archived: bool = False) -> list[Message]:
    out: list[Message] = []
    seen: set[str] = set()
    # Always include inbox/ and delivered/ (in-flight messages)
    bases = [paths.INBOX_DIR, paths.DELIVERED_DIR]
    if include_archived:
        bases.extend([paths.PROCESSED_DIR, paths.QUARANTINE_DIR])
    for base in bases:
        if not base.exists():
            continue
        peer_dir = base / peer_name
        if not peer_dir.exists():
            continue
        for p in sorted(peer_dir.glob("*.json")):
            try:
                msg = _read_message_at(p)
            except StoreCorrupt:
                continue
            if msg.id not in seen:
                out.append(msg)
                seen.add(msg.id)
    out.sort(key=lambda m: m.created_at, reverse=True)
    return out


def reconcile(window_minutes: int = 30, max_redelivery: int = 3) -> dict:
    """Scan delivered/. For each message with delivered_at older than
    window_minutes: requeue if redelivery_count < max_redelivery, else quarantine."""
    from datetime import datetime, timedelta
    now = datetime.now(UTC)
    threshold = now - timedelta(minutes=window_minutes)
    counts = {"promoted": 0, "requeued": 0, "quarantined": 0}
    if not paths.DELIVERED_DIR.exists():
        return counts
    for peer_dir in paths.DELIVERED_DIR.iterdir():
        if not peer_dir.is_dir():
            continue
        for p in list(peer_dir.glob("*.json")):
            try:
                msg = _read_message_at(p)
            except StoreCorrupt:
                continue
            if not msg.delivered_at:
                continue
            try:
                d_at = datetime.fromisoformat(msg.delivered_at)
            except ValueError:
                continue
            if d_at > threshold:
                continue  # still within window
            if msg.redelivery_count + 1 > max_redelivery:
                # Quarantine
                d = msg.to_dict()
                d["quarantined_at"] = now_iso()
                d["quarantine_reason"] = (
                    f"unacked after {max_redelivery} redeliveries"
                )
                quarantined = Message.from_dict(d)
                target = paths.QUARANTINE_DIR / peer_dir.name / p.name
                target.parent.mkdir(parents=True, exist_ok=True)
                _atomic_write_text(target, quarantined.to_json())
                p.unlink()
                counts["quarantined"] += 1
                _log.warning("quarantine msg=%s peer=%s reason=%s",
                             msg.id, peer_dir.name, d["quarantine_reason"])
                _append_delivery_log({"event": "quarantine",
                                      "msg_id": msg.id, "peer": peer_dir.name})
            else:
                # Requeue back to inbox/
                d = msg.to_dict()
                d["delivered_at"] = None
                d["delivered_to_session_id"] = None
                d["redelivery_count"] = msg.redelivery_count + 1
                requeued = Message.from_dict(d)
                target = paths.INBOX_DIR / peer_dir.name / p.name
                target.parent.mkdir(parents=True, exist_ok=True)
                _atomic_write_text(target, requeued.to_json())
                p.unlink()
                counts["requeued"] += 1
                _log.info("requeue msg=%s peer=%s attempt=%d",
                          msg.id, peer_dir.name, d["redelivery_count"])
                _append_delivery_log({"event": "requeue",
                                      "msg_id": msg.id, "peer": peer_dir.name,
                                      "redelivery_count": d["redelivery_count"]})
    return counts


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
    for base in (paths.INBOX_DIR, paths.DELIVERED_DIR, paths.PROCESSED_DIR,
                 paths.QUARANTINE_DIR):
        if not base.exists():
            continue
        for peer_dir in base.iterdir():
            if not peer_dir.is_dir():
                continue
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


def rebind_session(name: str, new_session_id: str | None = None) -> Peer:
    """Update only the session_id (and last_seen) for an existing peer.
    role, cwd, registered_at are preserved. If new_session_id is None, the
    function auto-detects via session.detect_session_id(); raises RelayError
    if no detection is possible.
    Also appends to rebind_log.jsonl and updates session_id_history."""
    from . import session as session_mod
    from .errors import RelayError

    sessions = _load_sessions()
    if name not in sessions:
        raise PeerNotFound(name)

    if new_session_id is None:
        new_session_id = session_mod.detect_session_id()
        if new_session_id is None:
            raise RelayError(
                "could not auto-detect a session id; pass --session-id explicitly"
            )

    entry = sessions[name]
    old_sid = entry.get("session_id")
    history = list(entry.get("session_id_history", []))
    if old_sid and old_sid != new_session_id and old_sid not in history:
        history.append(old_sid)
    entry["session_id"] = new_session_id
    entry["session_id_history"] = history
    entry["last_rebind_at"] = now_iso()
    entry["last_seen"] = now_iso()
    sessions[name] = entry
    _save_sessions(sessions)
    _log.info("rebind peer=%s old_session=%s new_session=%s",
              name, old_sid, new_session_id)
    # Append to rebind_log.jsonl
    _append_rebind_log({"peer": name, "old_session_id": old_sid,
                        "new_session_id": new_session_id})
    return Peer.from_dict(entry)


def _append_rebind_log(event: dict) -> None:
    paths.RELAY_DIR.mkdir(parents=True, exist_ok=True)
    line = json.dumps({**event, "at": now_iso()})
    with paths.REBIND_LOG.open("a") as f:
        f.write(line + "\n")


def find_peer_by_claude_pid(claude_pid: int,
                            claude_pid_start: str | None) -> list[Peer]:
    """Return peers whose claude_pid matches.
    If both stored and provided start times are non-None, require them to match.
    If either is None, accept the pid match alone."""
    out = []
    for p in list_peers():
        if p.claude_pid != claude_pid:
            continue
        # Strict start-time match when both sides have a value
        if p.claude_pid_start and claude_pid_start and p.claude_pid_start != claude_pid_start:
            continue
        out.append(p)
    return out


def list_quarantined(peer_name: str) -> list[Message]:
    """All quarantined messages for a peer, newest first."""
    out = []
    qdir = paths.QUARANTINE_DIR / peer_name
    if qdir.exists():
        for p in sorted(qdir.glob("*.json")):
            try:
                out.append(_read_message_at(p))
            except StoreCorrupt:
                continue
    out.sort(key=lambda m: m.created_at, reverse=True)
    return out


def requeue_quarantined(peer_name: str, ids: list[str] | None = None) -> int:
    """Move quarantined messages back to inbox/ for a fresh delivery cycle.
    Resets quarantine + delivery fields and redelivery_count=0. If ids is None,
    requeue ALL for the peer. Returns count moved."""
    qdir = paths.QUARANTINE_DIR / peer_name
    if not qdir.exists():
        return 0
    moved = 0
    for p in sorted(qdir.glob("*.json")):
        try:
            msg = _read_message_at(p)
        except StoreCorrupt:
            continue
        if ids is not None and msg.id not in ids:
            continue
        d = msg.to_dict()
        d["quarantined_at"] = None
        d["quarantine_reason"] = None
        d["delivered_at"] = None
        d["delivered_to_session_id"] = None
        d["redelivery_count"] = 0
        requeued = Message.from_dict(d)
        target = paths.INBOX_DIR / peer_name / p.name
        target.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write_text(target, requeued.to_json())
        p.unlink()
        moved += 1
        _log.info("requeue-quarantined msg=%s peer=%s", msg.id, peer_name)
        _append_delivery_log({"event": "requeue_quarantined", "msg_id": msg.id,
                              "peer": peer_name})
    return moved


def purge_quarantined(peer_name: str, ids: list[str] | None = None) -> int:
    """Permanently delete quarantined messages. If ids is None, purge ALL for
    the peer. Returns count deleted."""
    qdir = paths.QUARANTINE_DIR / peer_name
    if not qdir.exists():
        return 0
    deleted = 0
    for p in sorted(qdir.glob("*.json")):
        try:
            msg = _read_message_at(p)
        except StoreCorrupt:
            # still allow purge of corrupt files
            p.unlink()
            deleted += 1
            continue
        if ids is not None and msg.id not in ids:
            continue
        p.unlink()
        deleted += 1
        _log.info("purge-quarantined msg=%s peer=%s", msg.id, peer_name)
        _append_delivery_log({"event": "purge_quarantined", "msg_id": msg.id,
                              "peer": peer_name})
    return deleted


def _is_reply(msg: Message, siblings: list[Message]) -> bool:
    # A reply has both from_peer and to_peer flipped vs the original. We
    # treat any sibling where from_peer != "parent fan-out sender" as a reply.
    # Simpler heuristic: replies have subject starting with "Re: ".
    return msg.subject.startswith("Re: ")


def poll_new(peer_name: str, seen: set[str]) -> tuple[list[Message], set[str]]:
    """Return (NEW messages whose id is not in seen, updated seen-set).

    Read-only — peeks inbox only, never drains or acks. Callers maintain
    the ``seen`` set across iterations to suppress already-announced messages.
    """
    current = [m for m in list_inbox(peer_name) if m.state == MessageState.NEW]
    new = [m for m in current if m.id not in seen]
    seen = seen | {m.id for m in current}
    return new, seen


def list_thread(peer_a: str, peer_b: str,
                include_archived: bool = True) -> list[Message]:
    """Return all messages between peer_a and peer_b (either direction),
    sorted oldest to newest. Used by the chat view."""
    out: list[Message] = []
    seen: set[str] = set()
    for owner, sender in ((peer_a, peer_b), (peer_b, peer_a)):
        for m in list_inbox(owner, include_archived=include_archived):
            if m.from_peer == sender and m.id not in seen:
                out.append(m)
                seen.add(m.id)
    out.sort(key=lambda m: m.created_at)
    return out


def find_message_by_id_prefix(id_prefix: str) -> list[tuple[Message, str]]:
    """Search every peer's inbox/, delivered/, processed/, and quarantine/ for
    messages whose id starts with id_prefix. Returns (message, location) tuples.
    Empty prefix returns nothing (avoid scanning the whole world)."""
    prefix = id_prefix.strip()
    if not prefix:
        return []
    out: list[tuple[Message, str]] = []
    for base, label in ((paths.INBOX_DIR, "inbox"),
                         (paths.DELIVERED_DIR, "delivered"),
                         (paths.PROCESSED_DIR, "processed"),
                         (paths.QUARANTINE_DIR, "quarantine")):
        if not base.exists():
            continue
        for peer_dir in base.iterdir():
            if not peer_dir.is_dir():
                continue
            for p in peer_dir.glob("*.json"):
                if not p.stem.startswith(prefix):
                    continue
                try:
                    out.append((_read_message_at(p), label))
                except StoreCorrupt:
                    continue
    return out
