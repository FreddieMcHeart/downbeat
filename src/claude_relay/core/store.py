"""Filesystem-backed relay store: sessions.json + inbox/ + processed/.

All write operations are atomic via os.replace(). Read operations tolerate
missing files and return empty containers."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from . import paths
from .errors import MessageLocked, MessageNotFound, PeerNotFound, StoreCorrupt
from .models import Broadcast, Message, MessageState, Peer, new_id, now_iso


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
