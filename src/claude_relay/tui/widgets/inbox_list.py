"""Middle pane: messages for the currently-selected peer."""
from __future__ import annotations

from textual.widgets import DataTable

from ...core import store
from ...core.models import Message


class InboxList(DataTable):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.cursor_type = "row"
        self._messages: list[Message] = []

    def on_mount(self):
        self.add_columns("S", "id", "from", "subject", "created")

    def refresh_for_peer(self, peer_name: str | None) -> None:
        self.clear()
        if not peer_name:
            self._messages = []
            return
        self._messages = store.list_inbox(peer_name, include_archived=True)
        for m in self._messages:
            flag = {"new": "•", "read": " ", "archived": "·"}[m.state.value]
            self.add_row(flag, m.id, m.from_peer, m.subject, m.created_at[:19])

    def subjects(self) -> list[str]:
        return [m.subject for m in self._messages]

    def selected_message(self) -> Message | None:
        row = self.cursor_row
        if row is None or row >= len(self._messages):
            return None
        return self._messages[row]
