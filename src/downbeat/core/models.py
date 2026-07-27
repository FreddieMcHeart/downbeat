"""Dataclasses for relay entities — Message, Peer, Broadcast — with
backward-compatible JSON serialization (legacy messages missing the
new fields still parse)."""
from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds")


def new_id() -> str:
    return uuid.uuid4().hex[:12]


# --- Message wire-format versioning (issue #42) ------------------------------
# Bump when the on-disk shape changes structurally (a key renamed, a value's
# meaning changed, a field split) — NOT for a new optional field, which
# from_dict's .get() defaults already absorb. Every bump needs a migration
# rung registered in _MIGRATIONS below plus a test for that rung.
CURRENT_SCHEMA_VERSION = 2


def _migrate_v0_to_v1(d: dict) -> dict:
    """v0 = any file written before versioning existed, detected by the
    absence of a "schema_version" key.

    Deliberately a no-op on content: v1 ships the ladder itself and nothing
    else, so the first structural migration lands on a mechanism that has
    already been exercised against real v0 files rather than on untested
    plumbing and a data-model change at once.
    """
    return d


def _migrate_v1_to_v2(d: dict) -> dict:
    """v2 adds from_peer_id/to_peer_id — stable identity beside the display
    name (issue #40).

    Only makes room for them. A rung is pure by contract, so it cannot read
    the peer registry to resolve a name to an id; store.migrate_store() does
    that backfill, and list_thread falls back to name comparison for messages
    it could not resolve.
    """
    d.setdefault("from_peer_id", None)
    d.setdefault("to_peer_id", None)
    return d


# Keyed by the version being migrated FROM. A rung must be pure (dict in,
# dict out) so it can express structural changes field-level defaults cannot.
_MIGRATIONS: dict[int, Callable[[dict], dict]] = {
    0: _migrate_v0_to_v1,
    1: _migrate_v1_to_v2,
}


def _apply_migrations(d: dict) -> dict:
    """Walk a raw message dict up to CURRENT_SCHEMA_VERSION.

    Raises KeyError on a version this build cannot handle — which
    _read_message_at already turns into StoreCorrupt, so there is no new
    catch site. Refusing a too-new file is deliberate: from_dict drops keys
    it does not know, so silently rewriting a file a newer downbeat wrote
    would destroy those fields.
    """
    version = d.get("schema_version", 0)
    if not isinstance(version, int) or version < 0:
        raise KeyError(f"schema_version {version!r} is not a valid version")
    if version > CURRENT_SCHEMA_VERSION:
        raise KeyError(
            f"schema_version {version} is newer than this downbeat supports "
            f"({CURRENT_SCHEMA_VERSION}); upgrade downbeat to read it"
        )
    while version < CURRENT_SCHEMA_VERSION:
        d = _MIGRATIONS[version](d)
        version += 1
    return d


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
    # --- Phase 3 schema additions ---
    # Always the current version in memory: from_dict runs the ladder before
    # constructing, so a Message that exists is by definition up to date.
    schema_version: int = CURRENT_SCHEMA_VERSION
    # Stable identity of the two ends (issue #40). from_peer/to_peer above stay
    # the display name *at send time* — real history, and what the TUI renders.
    # These are what identity comparisons must use. None means "not resolved":
    # a pre-v2 message whose sender is no longer a registered peer.
    from_peer_id: str | None = None
    to_peer_id: str | None = None

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
            "schema_version": self.schema_version,
            "from_peer_id": self.from_peer_id,
            "to_peer_id": self.to_peer_id,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, d: dict) -> Message:
        # The ladder runs before any field is read, so migration rungs are the
        # only code that ever needs to know about an older shape.
        d = _apply_migrations(d)
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
            schema_version=CURRENT_SCHEMA_VERSION,
            from_peer_id=d.get("from_peer_id"),
            to_peer_id=d.get("to_peer_id"),
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
    parent: str | None = None   # name of the peer this one is a child of; None for
                                # a tree root. Any registered peer is a valid target
                                # regardless of role -- a role="parent" peer can have
                                # its own parent (an interior node). See the role
                                # field's comment above.
    # --- stable identity (issue #40) ---
    # Assigned once and never reassigned -- not by rename, not by rebind, not
    # by re-registration. `name` is a display alias; `session_id` is the
    # volatile OS-process attachment (see rebind_session). This is the only
    # field that answers "which enduring peer is this". Empty only for a legacy
    # entry that _load_sessions has not backfilled yet.
    peer_id: str = ""

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
            peer_id=d.get("peer_id", ""),
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
