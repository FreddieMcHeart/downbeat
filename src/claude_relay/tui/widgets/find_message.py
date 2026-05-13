"""Modal for finding a message across every peer's inbox and processed dirs."""
from __future__ import annotations

from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import DataTable, Input, Label

from ...core import store


class FindMessageModal(ModalScreen):
    BINDINGS = [("escape", "cancel", "Cancel"),
                ("enter", "open_selected", "Open")]

    def __init__(self):
        super().__init__()
        self._input: Input | None = None
        self._table: DataTable | None = None
        self._results: list[tuple[object, str]] = []  # (Message, location)

    def compose(self):
        with Vertical(classes="pane"):
            yield Label("[b]Find message by id prefix[/b]")
            self._input = Input(placeholder="paste a message id or prefix",
                                id="fm-input")
            yield self._input
            self._table = DataTable(id="fm-table")
            self._table.cursor_type = "row"
            self._table.add_columns("id", "where", "to", "from", "subject")
            yield self._table

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "fm-input":
            self._refresh_results(event.value)

    def _refresh_results(self, prefix: str) -> None:
        self._table.clear()
        self._results = store.find_message_by_id_prefix(prefix)
        for msg, location in self._results:
            self._table.add_row(msg.id, location, msg.to_peer,
                                 msg.from_peer, msg.subject)

    def action_open_selected(self) -> None:
        row = self._table.cursor_row
        if row is None or row >= len(self._results):
            self.dismiss(None)
            return
        msg, location = self._results[row]
        self.dismiss(msg)

    def action_cancel(self) -> None:
        self.dismiss(None)
