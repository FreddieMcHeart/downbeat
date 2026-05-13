"""Scrollable list of message bubbles between two peers."""
from __future__ import annotations

from textual.containers import VerticalScroll
from textual.widgets import Static

from ...core import store
from ...core.models import Message, MessageState


class ChatStream(VerticalScroll):
    DEFAULT_CSS = """
    ChatStream { padding: 1 1; height: 1fr; }
    ChatStream > .bubble {
        padding: 0 1;
        margin: 0 0 1 0;
        border-left: thick transparent;
    }
    ChatStream > .bubble-self {
        border-left: thick $accent;
        color: $text;
    }
    ChatStream > .bubble-other {
        margin-left: 8;
        border-left: thick $primary-darken-2;
        color: $text-muted;
    }
    ChatStream > .bubble-selected {
        background: $accent 30%;
        border-left: thick $warning;
        text-style: bold;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._messages: list[Message] = []
        self._cursor: int = 0  # index into _messages; the "focused" bubble
        self._me: str | None = None
        self._peer: str | None = None

    def refresh_thread(self, me: str | None, peer: str | None) -> None:
        self._me = me
        self._peer = peer
        self.remove_children()
        if not me or not peer:
            self._messages = []
            return
        self._messages = store.list_thread(me, peer)
        for idx, m in enumerate(self._messages):
            self.mount(self._render_bubble(m, me, idx))
        if self._messages:
            # Always land cursor at the bottom (newest message) on thread load
            self._cursor = len(self._messages) - 1
            self._highlight_cursor()
            # Scroll to bottom (newest)
            self.scroll_end(animate=False)
            # Mark the most-recent focused message as read on thread open
            self._mark_focused_read()
        else:
            self._cursor = 0

    def _render_bubble(self, msg: Message, me: str, idx: int) -> Static:
        is_self = (msg.from_peer == me)
        direction = f"you → {msg.to_peer}" if is_self else f"{msg.from_peer} → you"
        time = msg.created_at[11:16] if len(msg.created_at) >= 16 else ""
        state_marker = {
            "new":      "[yellow]●[/yellow] ",
            "read":     "[green]✓[/green] ",
            "archived": "[dim]·[/dim] ",
        }.get(msg.state.value, "")
        # Render with a placeholder cursor slot that _highlight_cursor will fill
        cursor_slot = "  "
        header = f"{cursor_slot}{state_marker}[b]{direction}[/b]  [dim]{time}  id {msg.id}[/dim]"
        body = msg.body or ""
        if len(body) > 600:
            body = body[:600] + "\n[dim]…[truncated, press v to view full][/dim]"
        text = f"{header}\n{body}"
        base_class = "bubble bubble-self" if is_self else "bubble bubble-other"
        bubble = Static(text, classes=base_class)
        bubble.data_idx = idx
        bubble._msg = msg  # keep ref so _highlight_cursor can re-render
        return bubble

    def _highlight_cursor(self) -> None:
        for idx, child in enumerate(self.children):
            is_selected = (idx == self._cursor)
            child.set_class(is_selected, "bubble-selected")
            # Re-render header text to include or remove the ▶ cursor arrow
            if hasattr(child, "_msg") and self._me is not None:
                msg = child._msg
                is_self = (msg.from_peer == self._me)
                direction = f"you → {msg.to_peer}" if is_self else f"{msg.from_peer} → you"
                time = msg.created_at[11:16] if len(msg.created_at) >= 16 else ""
                state_marker = {
                    "new":      "[yellow]●[/yellow] ",
                    "read":     "[green]✓[/green] ",
                    "archived": "[dim]·[/dim] ",
                }.get(msg.state.value, "")
                cursor_slot = "[b yellow]▶[/b yellow] " if is_selected else "  "
                header = (
                    f"{cursor_slot}{state_marker}[b]{direction}[/b]"
                    f"  [dim]{time}  id {msg.id}[/dim]"
                )
                body = msg.body or ""
                if len(body) > 600:
                    body = body[:600] + "\n[dim]…[truncated, press v to view full][/dim]"
                child.update(f"{header}\n{body}")

    def _mark_focused_read(self) -> None:
        msg = self.selected_message()
        if not msg:
            return
        if msg.state == MessageState.NEW and self._me and msg.to_peer == self._me:
            store.mark_read(msg.id)

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
        # Mark as read if it's a NEW message addressed to me
        self._mark_focused_read()

    def selected_message(self) -> Message | None:
        if not self._messages:
            return None
        if 0 <= self._cursor < len(self._messages):
            return self._messages[self._cursor]
        return None
