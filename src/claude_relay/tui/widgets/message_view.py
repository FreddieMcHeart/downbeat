"""Right pane: render the selected message body."""
from __future__ import annotations

from textual.containers import Vertical
from textual.widgets import Markdown, Static

from ...core import store


class MessageView(Vertical):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.body_text: str = ""
        self._meta = Static("Select a message", id="msg-meta")
        self._body = Markdown("", id="msg-body")
        self._current_id: str | None = None

    def compose(self):
        yield self._meta
        yield self._body

    def show(self, msg_id: str) -> None:
        msg = store.get_message(msg_id)
        if msg.state.value == "new":
            store.mark_read(msg_id)
            msg = store.get_message(msg_id)
        self._current_id = msg.id
        self.body_text = msg.body
        self._meta.update(
            f"[b]{msg.subject}[/b]\n"
            f"id: {msg.id}   from: {msg.from_peer}   to: {msg.to_peer}\n"
            f"state: [cyan]{msg.state.value}[/cyan]   "
            f"created: {msg.created_at}"
        )
        self._body.update(msg.body)

    def current_id(self) -> str | None:
        return self._current_id

    def clear(self) -> None:
        self._current_id = None
        self.body_text = ""
        self._meta.update("Select a message")
        self._body.update("")
