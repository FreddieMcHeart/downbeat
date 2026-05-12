"""Dataclasses for relay entities — Message, Peer, Broadcast — with
backward-compatible JSON serialization (legacy messages missing the
new fields still parse)."""
from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def new_id() -> str:
    return uuid.uuid4().hex[:12]


class MessageState(StrEnum):
    NEW = "new"
    READ = "read"
    ARCHIVED = "archived"


@dataclass(frozen=True)
class Message:
    id: str
    from_peer: str
    to_peer: str
    subject: str
    body: str
    created_at: str
    read_at: str | None = None
    edited_at: str | None = None
    broadcast_id: str | None = None
    archived: bool = False

    @property
    def state(self) -> MessageState:
        if self.archived:
            return MessageState.ARCHIVED
        if self.read_at is not None:
            return MessageState.READ
        return MessageState.NEW

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "from": self.from_peer,
            "to": self.to_peer,
            "subject": self.subject,
            "body": self.body,
            "created_at": self.created_at,
            "read_at": self.read_at,
            "edited_at": self.edited_at,
            "broadcast_id": self.broadcast_id,
            "archived": self.archived,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, d: dict) -> Message:
        return cls(
            id=d["id"],
            from_peer=d["from"],
            to_peer=d["to"],
            subject=d.get("subject", ""),
            body=d.get("body", ""),
            created_at=d.get("created_at") or d.get("ts") or "",
            read_at=d.get("read_at"),
            edited_at=d.get("edited_at"),
            broadcast_id=d.get("broadcast_id"),
            archived=d.get("archived", False),
        )

    @classmethod
    def from_json(cls, s: str) -> Message:
        return cls.from_dict(json.loads(s))


@dataclass
class Peer:
    name: str
    session_id: str
    cwd: str
    role: str   # "parent" | "child"
    registered_at: str
    last_seen: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> Peer:
        return cls(**d)


@dataclass
class Broadcast:
    id: str
    subject: str
    body: str
    from_peer: str
    to_peers: list[str]
    created_at: str
    message_ids: list[str] = field(default_factory=list)
