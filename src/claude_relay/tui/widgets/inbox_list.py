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
        self.show_archived: bool = False
        self._current_peer: str | None = None

    def on_mount(self):
        self.add_columns("S", "time", "from", "subject")
        cols = list(self.columns.values())
        cols[0].width = 1
        cols[1].width = 5
        cols[2].width = 18

    def refresh_for_peer(self, peer_name: str | None) -> None:
        # Capture selected message id before clearing
        prev_msg = self.selected_message()
        prev_id = prev_msg.id if prev_msg else None

        self.clear()
        self._current_peer = peer_name
        if not peer_name:
            self._messages = []
            return
        self._messages = store.list_inbox(peer_name, include_archived=self.show_archived)
        target_row = 0
        for idx, m in enumerate(self._messages):
            flag = {"new": "•", "read": " ", "archived": "·"}[m.state.value]
            time_str = m.created_at[11:16] if len(m.created_at) >= 16 else ""
            self.add_row(flag, time_str, m.from_peer, m.subject)
            if prev_id is not None and m.id == prev_id:
                target_row = idx
        # Restore cursor — if the previously-selected message still exists, jump
        # there; otherwise stay at row 0.
        if self._messages:
            self.move_cursor(row=target_row)

    def subjects(self) -> list[str]:
        return [m.subject for m in self._messages]

    def toggle_archived(self) -> None:
        self.show_archived = not self.show_archived
        self.refresh_for_peer(self._current_peer)

    def selected_message(self) -> Message | None:
        row = self.cursor_row
        if row is None or row >= len(self._messages):
            return None
        return self._messages[row]
