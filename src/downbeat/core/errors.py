class RelayError(Exception):
    """Base error for relay operations."""


class PeerNotFound(RelayError):
    """Raised when send/reply targets an unregistered peer."""


class MessageNotFound(RelayError):
    """Raised when an operation references an unknown message id."""


class PeerNameCollision(RelayError):
    """Raised when renaming a peer to a name that is already registered."""


class PeerReparentConflict(RelayError):
    """Raised by register_peer when an explicit --parent differs from an
    already-registered peer's stored parent (issue #70, option (b)). Names
    stay globally unique, so a reused name is presumed to be the SAME peer
    reattaching -- but silently carrying over identity while overwriting
    `parent` re-homes it without warning. Refusing turns that into an
    explicit decision: reattach with no --parent, or move it on purpose via
    `downbeat peers set-parent`."""


class InvalidPeerName(RelayError):
    """Raised when a peer name is empty or whitespace-only."""


class MessageLocked(RelayError):
    """Raised when an edit is attempted on a message past its NEW state."""


class StoreCorrupt(RelayError):
    """Raised when sessions.json or a message file fails to parse."""


class AmbiguousParent(RelayError):
    """Raised registering a child with no --parent when multiple role=parent peers exist."""


class InvalidParent(RelayError):
    """Raised when --parent names a peer that doesn't exist, or the
    assignment would be invalid for another reason (see CycleDetected)."""


class CycleDetected(InvalidParent):
    """Raised when a --parent assignment would create a cycle in the peer
    tree (including self-parenting, the degenerate 1-cycle). Subclasses
    InvalidParent so existing catch sites (cli/commands/relay_cmds.py,
    tui/widgets/add_peer_modal.py) need no new wiring."""
