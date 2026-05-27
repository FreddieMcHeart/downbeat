"""Right pane: render the selected message body."""
from __future__ import annotations

from rich.text import Text
from textual.containers import Vertical
from textual.widgets import Markdown, Static

from ...core import store


class MessageView(Vertical):
    @staticmethod
    def _empty_hint() -> str:
        return (
            "[b]No message selected[/b]\n\n"
            "Use [b]↑/↓[/b] to navigate, [b]Enter[/b] to open.\n\n"
            "[b]n[/b] new   [b]r[/b] reply   [b]e[/b] edit   [b]d[/b] delete\n"
            "[b]F1[/b] full help   [b]q[/b] quit"
        )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.body_text: str = ""
        self._meta = Static(self._empty_hint(), id="msg-meta")
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
        # Compose meta as Text: markup-parsed brackets, user content appended literal.
        meta = Text.from_markup("[b]")
        meta.append(msg.subject)   # literal
        meta.append_text(Text.from_markup("[/b]\n"))
        meta.append("id: ")
        meta.append(msg.id)
        meta.append("   from: ")
        meta.append(msg.from_peer)
        meta.append("   to: ")
        meta.append(msg.to_peer)
        meta.append("\n")
        meta.append_text(Text.from_markup(f"state: [cyan]{msg.state.value}[/cyan]   "))
        meta.append(f"created: {msg.created_at}")
        self._meta.update(meta)
        self._body.update(msg.body)

    def current_id(self) -> str | None:
        return self._current_id

    def clear(self) -> None:
        self._current_id = None
        self.body_text = ""
        self._meta.update(self._empty_hint())
        self._body.update("")
