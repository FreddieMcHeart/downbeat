class RelayError(Exception):
    """Base error for relay operations."""


class PeerNotFound(RelayError):
    """Raised when send/reply targets an unregistered peer."""


class MessageNotFound(RelayError):
    """Raised when an operation references an unknown message id."""


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
