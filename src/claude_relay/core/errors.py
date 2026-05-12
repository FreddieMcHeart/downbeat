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
