"""Shared TUI message types to avoid circular imports."""
from __future__ import annotations

from textual.message import Message


class StoreChanged(Message):
    """Posted when the filesystem store changes; drives reactive UI refresh."""
    pass
