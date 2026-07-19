"""Modal for finding a message across every peer's inbox and processed dirs."""
from __future__ import annotations

from rich.markup import escape as _rich_escape
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import DataTable, Input, Label

from ...core import store


class FindMessageModal(ModalScreen):
    BINDINGS = [("escape", "cancel", "Cancel"),
                ("down", "focus_results", "Results"),
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

    def on_mount(self) -> None:
        # Start in the search box so typing works immediately.
        if self._input is not None:
            self._input.focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "fm-input":
            self._refresh_results(event.value)

    def action_focus_results(self) -> None:
        # Hand keyboard focus from the search box down into the results table.
        # Only fires from the Input — once the table is focused it consumes
        # Down itself (row navigation), so this never hijacks browsing.
        if self._results and self.focused is self._input and self._table is not None:
            self._table.focus()
            self._table.move_cursor(row=0)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        # Enter in the search box opens the top match directly (the common
        # single-hit case). Down first to browse and pick another row.
        if event.input.id == "fm-input" and self._results and self._table is not None:
            self._table.move_cursor(row=0)
            self.action_open_selected()

    def _refresh_results(self, prefix: str) -> None:
        self._table.clear()
        self._results = store.find_message_by_id_prefix(prefix)
        for msg, location in self._results:
            self._table.add_row(
                msg.id, location,
                _rich_escape(msg.to_peer),
                _rich_escape(msg.from_peer),
                _rich_escape(msg.subject),
            )

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        # Enter on a focused table row: the DataTable consumes Enter and posts
        # this instead of firing the modal's binding, so open from here.
        self.action_open_selected()

    def action_open_selected(self) -> None:
        row = self._table.cursor_row
        if row is None or row >= len(self._results):
            self.dismiss(None)
            return
        msg, location = self._results[row]
        self.dismiss(msg)

    def action_cancel(self) -> None:
        self.dismiss(None)
