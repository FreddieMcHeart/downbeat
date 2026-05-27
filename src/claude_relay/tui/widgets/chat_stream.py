"""Scrollable list of message bubbles between two peers."""
from __future__ import annotations

from rich.markup import escape as _rich_escape
from textual.containers import VerticalScroll
from textual.message import Message as TextualMessage
from textual.widgets import Static

from ...core import store
from ...core.models import Message, MessageState


class ChatStream(VerticalScroll):
    BINDINGS = [
        ("up,k", "cursor_up", "Up"),
        ("down,j", "cursor_down", "Down"),
        ("enter", "open_detail", "Open"),
        ("y", "yank_body", "Yank body"),
    ]
    can_focus = True

    class MessageOpened(TextualMessage):
        def __init__(self, msg_id: str):
            super().__init__()
            self.msg_id = msg_id

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
        # Capture scroll / peer state BEFORE any mutation so the UX guards
        # (scroll preservation, conditional mark-read) stay correct.
        peer_changed = (self._peer != peer)
        try:
            was_at_tail = self.scroll_offset.y >= max(0, self.max_scroll_y - 2)
        except Exception:
            was_at_tail = True
        prev_offset = self.scroll_offset.y

        new_me = me
        new_peer = peer
        new_messages = store.list_thread(me, peer) if me and peer else []

        # --- Full rebuild when the thread itself changes (different peer pair) ---
        full_rebuild = peer_changed
        if full_rebuild:
            self.remove_children()
            self._messages = []

        self._me = new_me
        self._peer = new_peer

        if not new_messages:
            self._messages = []
            return

        # Build id → message map for new messages (used in steps 1–3)
        new_by_id: dict[str, Message] = {m.id: m for m in new_messages}

        # --- 1. Remove bubbles whose id is no longer present ---
        for child in list(self.children):
            msg = getattr(child, "_msg", None)
            if msg is not None and msg.id not in new_by_id:
                child.remove()

        # --- 2. Update bubbles that exist in both sets but whose state changed ---
        for child in list(self.children):
            msg = getattr(child, "_msg", None)
            if msg is None:
                continue
            new_version = new_by_id.get(msg.id)
            if new_version is None:
                continue
            if (
                new_version.state != msg.state
                or new_version.body != msg.body
                or new_version.subject != msg.subject
                or new_version.read_at != msg.read_at
            ):
                child._msg = new_version
                self._render_bubble_into(child, new_version, new_me, is_selected=False)

        # --- 3. Mount bubbles for ids that are new (preserving order) ---
        children_by_id: dict[str, Static] = {
            c._msg.id: c
            for c in self.children
            if getattr(c, "_msg", None) is not None
        }
        prev_widget: Static | None = None
        for idx, m in enumerate(new_messages):
            if m.id in children_by_id:
                prev_widget = children_by_id[m.id]
                continue
            bubble = self._render_bubble(m, new_me, idx)
            if prev_widget is not None:
                self.mount(bubble, after=prev_widget)
            else:
                existing = list(self.children)
                if existing:
                    self.mount(bubble, before=existing[0])
                else:
                    self.mount(bubble)
            children_by_id[m.id] = bubble
            prev_widget = bubble

        # --- 4. Update internal message list ---
        self._messages = list(new_messages)

        # --- 5. Cursor / scroll / mark-read (preserving original UX guards) ---
        if self._messages:
            self._cursor = len(self._messages) - 1
            self._highlight_cursor_diff(None)
            # Follow-tail rule:
            # - Peer changed (new tab) → always show the newest message.
            # - User was at the bottom → keep them at the bottom on refresh.
            # - User had scrolled up → restore their previous scroll position
            #   so refresh doesn't yank them back to bottom.
            if peer_changed or was_at_tail:
                self.scroll_end(animate=False)
            else:
                # call_after_refresh ensures children are laid out before we
                # try to set scroll position
                self.call_after_refresh(self.scroll_to, 0, prev_offset, animate=False)
            # Only auto-mark-read on peer change (initial open of a thread),
            # not on every watcher-driven refresh — otherwise mark_read fires
            # for the bottom message constantly even when the user is reading older ones.
            if peer_changed:
                self._mark_focused_read()
        else:
            self._cursor = 0

    def _render_bubble(self, msg: Message, me: str, idx: int) -> Static:
        base_class = "bubble bubble-self" if (msg.from_peer == me) else "bubble bubble-other"
        bubble = Static("", classes=base_class)
        bubble.data_idx = idx
        bubble._msg = msg  # keep ref so cursor helpers can re-render
        self._render_bubble_into(bubble, msg, me, is_selected=False)
        return bubble

    def _render_bubble_into(
        self,
        child: Static,
        msg: Message,
        me: str | None,
        is_selected: bool = False,
    ) -> None:
        """Update an existing bubble's text + classes in place (no re-mount)."""
        is_self = (msg.from_peer == me) if me else False
        # Escape user-provided peer names so '[' in names doesn't break markup parsing.
        from_safe = _rich_escape(msg.from_peer)
        to_safe = _rich_escape(msg.to_peer)
        direction = f"you → {to_safe}" if is_self else f"{from_safe} → you"
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
        body_raw = msg.body or ""
        # Truncate first, then escape — keeps our own '[dim]…[/dim]' suffix as
        # real markup while brackets in user content get escaped.
        if len(body_raw) > 600:
            body_safe = (
                _rich_escape(body_raw[:600])
                + "\n[dim]… (truncated, press Enter to view full)[/dim]"
            )
        else:
            body_safe = _rich_escape(body_raw)
        child.update(f"{header}\n{body_safe}")
        child.set_class(is_self, "bubble-self")
        child.set_class(not is_self, "bubble-other")
        child.set_class(is_selected, "bubble-selected")

    def _highlight_cursor(self) -> None:
        """Full re-render of all bubbles (kept for compatibility; prefer _highlight_cursor_diff)."""
        self._highlight_cursor_diff(None)

    def _highlight_cursor_diff(self, old_idx: int | None) -> None:
        """Update bubble styling for ONLY the cursor positions that changed."""
        children_list = list(self.children)
        if not children_list or self._me is None:
            return

        new_idx = self._cursor
        # Touch the bubble that LOST the cursor (if it still exists and differs)
        if (
            old_idx is not None
            and 0 <= old_idx < len(children_list)
            and old_idx != new_idx
        ):
            child = children_list[old_idx]
            msg = getattr(child, "_msg", None)
            if msg is not None:
                self._render_bubble_into(child, msg, self._me, is_selected=False)
        # Touch the bubble that GAINED the cursor
        if 0 <= new_idx < len(children_list):
            child = children_list[new_idx]
            msg = getattr(child, "_msg", None)
            if msg is not None:
                self._render_bubble_into(child, msg, self._me, is_selected=True)
                self.scroll_to_widget(child, animate=False)

    def _mark_focused_read(self) -> None:
        msg = self.selected_message()
        if not msg:
            return
        if msg.state == MessageState.NEW and self._me and msg.to_peer == self._me:
            store.mark_read(msg.id)

    def move_cursor(self, delta: int) -> None:
        if not self._messages:
            return
        old_idx = self._cursor
        self._cursor = max(0, min(len(self._messages) - 1, self._cursor + delta))
        self._highlight_cursor_diff(old_idx)
        # Mark as read if it's a NEW message addressed to me
        self._mark_focused_read()

    def action_cursor_up(self) -> None:
        self.move_cursor(-1)

    def action_cursor_down(self) -> None:
        self.move_cursor(+1)

    SCROLL_STEP = 3  # lines per mouse-wheel event

    def on_mouse_scroll_up(self, event) -> None:
        self.scroll_relative(y=-self.SCROLL_STEP, animate=False)
        event.stop()

    def on_mouse_scroll_down(self, event) -> None:
        self.scroll_relative(y=+self.SCROLL_STEP, animate=False)
        event.stop()

    def selected_message(self) -> Message | None:
        if not self._messages:
            return None
        if 0 <= self._cursor < len(self._messages):
            return self._messages[self._cursor]
        return None

    def action_open_detail(self) -> None:
        msg = self.selected_message()
        if msg:
            self.post_message(self.MessageOpened(msg.id))

    def action_yank_body(self) -> None:
        msg = self.selected_message()
        if not msg:
            self.app.notify("No message focused", severity="warning", timeout=2)
            return
        from .clipboard import copy_to_clipboard
        ok = copy_to_clipboard(msg.body or "")
        if ok:
            self.app.notify(f"Copied body of {msg.id} ({len(msg.body or '')} chars)",
                            timeout=2)
        else:
            self.app.notify(
                "Clipboard tool not available — install pyperclip or use pbcopy/xclip.",
                severity="error", timeout=4,
            )
