"""Scrollable list of message bubbles between two peers."""
from __future__ import annotations

from textual.containers import VerticalScroll
from textual.widgets import Static

from ...core import store
from ...core.models import Message


class ChatStream(VerticalScroll):
    DEFAULT_CSS = """
    ChatStream { padding: 0 1; height: 1fr; }
    ChatStream > .bubble-self { color: $accent; padding: 0 0 1 0; }
    ChatStream > .bubble-other { padding: 0 0 1 8; }
    ChatStream > .bubble-selected { background: $boost; }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._messages: list[Message] = []
        self._cursor: int = 0  # index into _messages; the "focused" bubble

    def refresh_thread(self, me: str | None, peer: str | None) -> None:
        self.remove_children()
        if not me or not peer:
            self._messages = []
            return
        self._messages = store.list_thread(me, peer)
        for idx, m in enumerate(self._messages):
            self.mount(self._render_bubble(m, me, idx))
        if self._messages:
            self._cursor = min(self._cursor, len(self._messages) - 1)
            self._highlight_cursor()
            # Scroll to bottom (newest)
            self.scroll_end(animate=False)
        else:
            self._cursor = 0

    def _render_bubble(self, msg: Message, me: str, idx: int) -> Static:
        is_self = (msg.from_peer == me)
        direction = f"you → {msg.to_peer}" if is_self else f"{msg.from_peer} → you"
        time = msg.created_at[11:16] if len(msg.created_at) >= 16 else ""
        header = f"[b]{direction}[/b]  [dim]{time}  id {msg.id}[/dim]"
        body = msg.body or ""
        # Truncate very long body for the bubble view; full body on demand
        if len(body) > 600:
            body = body[:600] + "\n[dim]…[truncated, press v to view full][/dim]"
        text = f"{header}\n{body}"
        bubble = Static(text, classes="bubble-self" if is_self else "bubble-other")
        bubble.data_idx = idx  # custom attribute we use to find which bubble
        return bubble

    def _highlight_cursor(self) -> None:
        for idx, child in enumerate(self.children):
            child.set_class(idx == self._cursor, "bubble-selected")

    def move_cursor(self, delta: int) -> None:
        if not self._messages:
            return
        self._cursor = max(0, min(len(self._messages) - 1, self._cursor + delta))
        self._highlight_cursor()
        # Scroll selected child into view
        for idx, child in enumerate(self.children):
            if idx == self._cursor:
                self.scroll_to_widget(child, animate=False)
                break

    def selected_message(self) -> Message | None:
        if not self._messages:
            return None
        if 0 <= self._cursor < len(self._messages):
            return self._messages[self._cursor]
        return None
