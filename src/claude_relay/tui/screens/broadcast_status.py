"""Modal screen showing per-target reply state for a broadcast."""
from __future__ import annotations

from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import DataTable, Label

from ...core import store


class BroadcastStatusScreen(ModalScreen):
    BINDINGS = [("escape", "action_dismiss", "Close")]

    def __init__(self, broadcast_id: str):
        super().__init__()
        self.broadcast_id = broadcast_id

    def compose(self):
        with Vertical(classes="pane"):
            yield Label(f"Broadcast {self.broadcast_id}")
            table = DataTable(id="bc-table")
            table.add_columns("target", "state", "original", "replies")
            for row in store.broadcast_status(self.broadcast_id):
                table.add_row(row["target"], row["state"],
                              row["original_id"],
                              ", ".join(row["reply_ids"]) or "-")
            yield table

    def action_dismiss(self) -> None:
        self.dismiss(None)
