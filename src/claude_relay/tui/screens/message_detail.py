"""Dedicated single-message view with per-message actions."""
from __future__ import annotations

from rich.markup import escape as _rich_escape
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Footer, Header, Label, Markdown, Static

from ...core import store


class MessageDetailScreen(Screen):
    DEFAULT_CSS = """
    MessageDetailScreen {
        layout: vertical;
        overflow-y: auto;
        overflow-x: hidden;
    }
    #msg-title { padding: 1 2 0 2; }
    #msg-meta  { padding: 0 2 1 2; color: $text-muted; }
    #msg-body  { padding: 0 2 2 2; }
    """

    BINDINGS = [
        ("escape,q", "app.pop_screen", "Back"),
        ("e", "edit", "Edit"),
        ("r", "reply", "Reply"),
        ("d", "delete", "Delete"),
        ("B,shift+b", "broadcast_status", "Bcast"),
        ("y", "yank_body", "Yank body"),
        ("c", "copy_id", "Copy id"),
        ("up,k", "scroll_up", "Up"),
        ("down,j", "scroll_down", "Down"),
        ("ctrl+b,pageup", "page_up", "PgUp"),
        ("ctrl+f,pagedown", "page_down", "PgDn"),
    ]

    def __init__(self, msg_id: str):
        super().__init__()
        self.msg_id = msg_id
        self._meta: Static | None = None
        self._body: Markdown | None = None
        self._title: Label | None = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        self._title = Label("", id="msg-title")
        yield self._title
        self._meta = Static("", id="msg-meta")
        yield self._meta
        self._body = Markdown("", id="msg-body")
        yield self._body
        yield Footer()

    def on_mount(self) -> None:
        self._render_content_safe()

    def _render_content_safe(self) -> None:
        try:
            msg = store.get_message(self.msg_id)
        except Exception as e:
            self._title.update(
                f"[red]Error loading {self.msg_id}: {_rich_escape(str(e))}[/red]"
            )
            return
        self._title.update(
            f"[b]{_rich_escape(msg.subject)}[/b]   "
            f"[dim]({msg.state.value})[/dim]"
        )
        meta_lines = [
            f"id:        {msg.id}",
            f"from:      {_rich_escape(msg.from_peer)}",
            f"to:        {_rich_escape(msg.to_peer)}",
            f"created:   {msg.created_at}",
        ]
        if msg.read_at:
            meta_lines.append(f"read:      {msg.read_at}")
        if msg.edited_at:
            meta_lines.append(f"edited:    {msg.edited_at}")
        if msg.broadcast_id:
            meta_lines.append(f"broadcast: {msg.broadcast_id}")
        if msg.archived:
            meta_lines.append("[dim]archived[/dim]")
        self._meta.update("\n".join(meta_lines))
        # Markdown widget parses markdown, not Rich markup — no escaping needed.
        self._body.update(msg.body or "*(empty body)*")

    def action_edit(self) -> None:
        msg = store.get_message(self.msg_id)
        if msg.state.value != "new":
            self.notify(f"message is {msg.state.value} — edit blocked",
                        severity="warning")
            return
        from ..widgets.edit_modal import EditModal
        def after(result):
            if result:
                # Edit succeeded — return to chat where the change is visible
                self.app.pop_screen()
            else:
                # Edit cancelled — re-render in place
                self._render_content_safe()
        self.app.push_screen(EditModal(self.msg_id), after)

    def action_reply(self) -> None:
        msg = store.get_message(self.msg_id)
        from ..widgets.composer import Composer
        def after(_):
            self.app.pop_screen()
        self.app.push_screen(
            Composer(sender=msg.to_peer, reply_to=msg.id, prefill_to=msg.from_peer),
            after,
        )

    def action_delete(self) -> None:
        from ..widgets.confirm import ConfirmDelete, perform_delete
        def after(confirmed):
            if confirmed:
                perform_delete(self.msg_id)
                self.app.pop_screen()
        self.app.push_screen(
            ConfirmDelete(f"Delete message {self.msg_id}?"), after
        )

    def action_broadcast_status(self) -> None:
        msg = store.get_message(self.msg_id)
        if not msg.broadcast_id:
            self.notify("Not part of a broadcast", severity="warning")
            return
        from .broadcast_status import BroadcastStatusScreen
        self.app.push_screen(BroadcastStatusScreen(msg.broadcast_id))

    SCROLL_STEP = 3  # lines per mouse-wheel event

    def on_mouse_scroll_up(self, event) -> None:
        self.scroll_relative(y=-self.SCROLL_STEP, animate=False)
        event.stop()

    def on_mouse_scroll_down(self, event) -> None:
        self.scroll_relative(y=+self.SCROLL_STEP, animate=False)
        event.stop()

    def action_yank_body(self) -> None:
        from ..widgets.clipboard import copy_to_clipboard
        msg = store.get_message(self.msg_id)
        ok = copy_to_clipboard(msg.body or "")
        if ok:
            self.notify(f"Copied body ({len(msg.body or '')} chars)", timeout=2)
        else:
            self.notify(
                "Clipboard tool not available — install pyperclip or use pbcopy/xclip.",
                severity="error", timeout=4,
            )

    def action_copy_id(self) -> None:
        from ..widgets.clipboard import copy_to_clipboard
        if copy_to_clipboard(self.msg_id):
            self.notify(f"Copied id {self.msg_id} to clipboard", timeout=2)
        else:
            self.notify(f"id: {self.msg_id}", timeout=5)
