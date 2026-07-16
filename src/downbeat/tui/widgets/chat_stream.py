"""Scrollable list of message bubbles between two peers."""
from __future__ import annotations

from rich.markup import escape as _rich_escape
from rich.text import Text
from textual.containers import VerticalScroll
from textual.message import Message as TextualMessage
from textual.widgets import Static

from ...core import store
from ...core.models import Message, MessageState
from .peer_tabs import OWN_INBOX_ID


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
        # id -> bubble, maintained SYNCHRONOUSLY as we mount and remove. It is
        # the source of truth for "what is rendered", NOT self.children --
        # Textual's mount()/remove() are deferred, so self.children lags a
        # tick behind our intent. Two refresh_thread calls in one tick (a
        # peer change followed immediately by another) used to read that
        # stale tree, conclude the new thread's messages were already
        # rendered, mount nothing, and then let the pending removal wipe
        # everything -- an empty thread over non-empty data. See #21.
        self._bubbles: dict[str, Static] = {}
        self._cursor: int = 0  # index into _messages; the "focused" bubble
        self._me: str | None = None
        self._peer: str | None = None
        # Own-inbox archived toggle: when False (default) only pending
        # (inbox/ + delivered/) mail shows; when True the full received
        # history (processed/ + quarantine/) is included too. Only meaningful
        # on the OWN_INBOX_ID tab — see refresh_thread.
        self._show_archived: bool = False

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
        if me and peer:
            if peer == OWN_INBOX_ID:
                # Own-inbox tab: all messages addressed to me, any sender,
                # sorted oldest→newest (list_inbox returns newest-first, so reverse).
                # When _show_archived is on, include processed/ + quarantine/ so a
                # sink peer can see its full received history, not just pending.
                new_messages = list(reversed(
                    store.list_inbox(me, include_archived=self._show_archived)
                ))
            else:
                new_messages = store.list_thread(me, peer)
        else:
            new_messages = []

        # --- Full rebuild when the thread itself changes (different peer pair) ---
        full_rebuild = peer_changed
        if full_rebuild:
            self.remove_children()
            self._bubbles.clear()   # forget them NOW, not a tick from now
            self._messages = []

        self._me = new_me
        self._peer = new_peer

        if not new_messages:
            self._bubbles.clear()
            self.remove_children()
            self._messages = []
            return

        # Build id → message map for new messages (used in steps 1–3)
        new_by_id: dict[str, Message] = {m.id: m for m in new_messages}

        # --- 1. Remove bubbles whose id is no longer present ---
        for mid, bubble in list(self._bubbles.items()):
            if mid not in new_by_id:
                bubble.remove()
                del self._bubbles[mid]

        # --- 2. Update bubbles that exist in both sets but whose state changed ---
        for mid, bubble in self._bubbles.items():
            new_version = new_by_id[mid]  # membership guaranteed by step 1
            old = getattr(bubble, "_msg", None)
            if old is not None and (
                new_version.state != old.state
                or new_version.body != old.body
                or new_version.subject != old.subject
                or new_version.read_at != old.read_at
            ):
                bubble._msg = new_version
                self._render_bubble_into(bubble, new_version, new_me, is_selected=False)

        # --- 3. Mount bubbles for ids that are new (preserving order) ---
        prev_widget: Static | None = None
        for idx, m in enumerate(new_messages):
            existing = self._bubbles.get(m.id)
            if existing is not None:
                prev_widget = existing
                continue
            bubble = self._render_bubble(m, new_me, idx)
            if prev_widget is not None:
                self.mount(bubble, after=prev_widget)
            elif self._bubbles:
                # New oldest message ahead of ones we already track.
                self.mount(bubble, before=next(iter(self._bubbles.values())))
            else:
                self.mount(bubble)
            self._bubbles[m.id] = bubble
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

    def toggle_archived(self) -> bool:
        """Flip the own-inbox archived view and re-render. Returns the new state.

        Only the OWN_INBOX_ID tab varies its message set on this flag; on a
        member-peer thread list_thread already includes archived, so the flag
        is harmless there. Re-uses refresh_thread's differential update, which
        mounts/removes archived bubbles cleanly without a full rebuild."""
        self._show_archived = not self._show_archived
        self.refresh_thread(self._me, self._peer)
        return self._show_archived

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
        # Escape peer names for the header — header IS parsed as markup.
        from_safe = _rich_escape(msg.from_peer)
        to_safe = _rich_escape(msg.to_peer)
        direction = f"you → {to_safe}" if is_self else f"{from_safe} → you"
        time = msg.created_at[11:16] if len(msg.created_at) >= 16 else ""
        state_marker = {
            "new":         "[yellow]●[/yellow] ",
            "read":        "[green]✓[/green] ",
            "delivered":   "[cyan]⏳[/cyan] ",
            "archived":    "[dim]·[/dim] ",
            "quarantined": "[red]!![/red] ",
        }.get(msg.state.value, "")
        cursor_slot = "[b yellow]▶[/b yellow] " if is_selected else "  "
        header = (
            f"{cursor_slot}{state_marker}[b]{direction}[/b]"
            f"  [dim]{time}  id {msg.id}[/dim]"
        )
        body_raw = msg.body or ""
        if len(body_raw) > 600:
            body_text = body_raw[:600] + "\n… (truncated, press Enter to view full)"
        else:
            body_text = body_raw

        # Compose Text: header parsed as markup, body appended as LITERAL text
        # (no markup parser ever sees the body's brackets).
        rendered = Text.from_markup(header)
        rendered.append("\n")
        rendered.append(body_text)   # literal — Textual's parser does NOT touch this

        child.update(rendered)
        child.set_class(is_self, "bubble-self")
        child.set_class(not is_self, "bubble-other")
        child.set_class(is_selected, "bubble-selected")

    def _highlight_cursor(self) -> None:
        """Full re-render of all bubbles (kept for compatibility; prefer _highlight_cursor_diff)."""
        self._highlight_cursor_diff(None)

    def _highlight_cursor_diff(self, old_idx: int | None) -> None:
        """Update bubble styling for ONLY the cursor positions that changed."""
        # Ordered by message, from our synchronous bubble map -- NOT
        # self.children, which lags mounts by a tick (see #21). _cursor
        # indexes into _messages, so this list must be in the same order.
        children_list = [
            self._bubbles[m.id] for m in self._messages if m.id in self._bubbles
        ]
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
