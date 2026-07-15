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
    return datetime.now(UTC).isoformat(timespec="microseconds")


def new_id() -> str:
    return uuid.uuid4().hex[:12]


class MessageState(StrEnum):
    NEW = "new"
    READ = "read"
    DELIVERED = "delivered"     # in delivered/, awaiting ack
    QUARANTINED = "quarantined" # in quarantine/, manual recovery needed
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
    # --- Phase 0 schema additions ---
    delivered_at: str | None = None
    delivered_to_session_id: str | None = None
    redelivery_count: int = 0
    delivery_ack_at: str | None = None
    in_reply_to: str | None = None
    quarantined_at: str | None = None
    quarantine_reason: str | None = None
    # --- Phase 2 schema additions ---
    # Open string, NOT a StrEnum: "task" (default) | "backflow-ready" | future
    # Phase-3 kinds ("workflow-request"/"workflow-result") need zero migration.
    kind: str = "task"

    @property
    def state(self) -> MessageState:
        if self.quarantined_at is not None:
            return MessageState.QUARANTINED
        if self.archived:
            return MessageState.ARCHIVED
        if self.delivered_at is not None and self.delivery_ack_at is None:
            return MessageState.DELIVERED
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
            "delivered_at": self.delivered_at,
            "delivered_to_session_id": self.delivered_to_session_id,
            "redelivery_count": self.redelivery_count,
            "delivery_ack_at": self.delivery_ack_at,
            "in_reply_to": self.in_reply_to,
            "quarantined_at": self.quarantined_at,
            "quarantine_reason": self.quarantine_reason,
            "kind": self.kind,
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
            delivered_at=d.get("delivered_at"),
            delivered_to_session_id=d.get("delivered_to_session_id"),
            redelivery_count=d.get("redelivery_count", 0),
            delivery_ack_at=d.get("delivery_ack_at"),
            in_reply_to=d.get("in_reply_to"),
            quarantined_at=d.get("quarantined_at"),
            quarantine_reason=d.get("quarantine_reason"),
            kind=d.get("kind", "task"),
        )

    @classmethod
    def from_json(cls, s: str) -> Message:
        return cls.from_dict(json.loads(s))


@dataclass
class Peer:
    name: str
    session_id: str
    cwd: str
    role: str   # "parent" | "child" -- the /relay-monitor autonomy DEFAULT
                # only (auto-execute vs surface-and-ask). NOT structural
                # position: a peer can be role="child" and still have its
                # own children -- gaining/losing children never changes
                # this field. See docs/superpowers/specs/
                # 2026-07-15-general-peer-tree-design.md.
    registered_at: str
    last_seen: str
    # --- rebind identity ---
    claude_pid: int | None = None
    claude_pid_start: str | None = None         # ISO-8601 normalized
    session_id_history: list[str] = field(default_factory=list)
    last_rebind_at: str | None = None
    # --- explicit pairing (replaces name-prefix inference) ---
    parent: str | None = None   # name of the role="parent" peer this child joined; None for parents

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> Peer:
        return cls(
            name=d["name"],
            session_id=d["session_id"],
            cwd=d.get("cwd", ""),
            role=d.get("role", "child"),
            registered_at=d.get("registered_at", ""),
            last_seen=d.get("last_seen", ""),
            claude_pid=d.get("claude_pid"),
            claude_pid_start=d.get("claude_pid_start"),
            session_id_history=d.get("session_id_history", []),
            last_rebind_at=d.get("last_rebind_at"),
            parent=d.get("parent"),
        )


@dataclass
class Broadcast:
    id: str
    subject: str
    body: str
    from_peer: str
    to_peers: list[str]
    created_at: str
    message_ids: list[str] = field(default_factory=list)
