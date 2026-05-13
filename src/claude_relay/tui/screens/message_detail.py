"""Dedicated single-message view with per-message actions."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Footer, Header, Label, Markdown, Static

from ...core import store


class MessageDetailScreen(Screen):
    BINDINGS = [
        ("escape,q", "app.pop_screen", "Back"),
        ("e", "edit", "Edit"),
        ("r", "reply", "Reply"),
        ("d", "delete", "Delete"),
        ("B,shift+b", "broadcast_status", "Bcast"),
        ("c", "copy_id", "Copy id"),
    ]

    def __init__(self, msg_id: str):
        super().__init__()
        self.msg_id = msg_id
        self._meta: Static | None = None
        self._body: Markdown | None = None
        self._title: Label | None = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Vertical(id="msg-detail-root"):
            self._title = Label("", id="msg-title")
            yield self._title
            self._meta = Static("", id="msg-meta", classes="pane")
            yield self._meta
            with VerticalScroll(id="msg-body-scroll", classes="pane"):
                self._body = Markdown("", id="msg-body")
                yield self._body
        yield Footer()

    def on_mount(self) -> None:
        self._render()

    def _render(self) -> None:
        msg = store.get_message(self.msg_id)
        self._title.update(f"[b]{msg.subject}[/b]   "
                            f"[dim]{msg.state.value}[/dim]")
        meta_lines = [
            f"id:        {msg.id}",
            f"from:      {msg.from_peer}",
            f"to:        {msg.to_peer}",
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
        self._body.update(msg.body or "[dim](empty body)[/dim]")

    def action_edit(self) -> None:
        msg = store.get_message(self.msg_id)
        if msg.state.value != "new":
            self.notify(f"message is {msg.state.value} — edit blocked",
                        severity="warning")
            return
        from ..widgets.edit_modal import EditModal
        def after(_):
            self._render()
        self.app.push_screen(EditModal(self.msg_id), after)

    def action_reply(self) -> None:
        msg = store.get_message(self.msg_id)
        from ..widgets.composer import Composer
        def after(_):
            # After replying, pop back to chat which will refresh
            self.app.pop_screen()
        # The reply Composer routes correctly: sender=msg.to_peer, reply_to=msg.id
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

    def action_copy_id(self) -> None:
        # Best-effort clipboard; fall back to notify-only if pyperclip isn't installed
        try:
            import pyperclip  # type: ignore
            pyperclip.copy(self.msg_id)
            self.notify(f"Copied id {self.msg_id} to clipboard", timeout=2)
        except Exception:
            self.notify(f"id: {self.msg_id}", timeout=5)
