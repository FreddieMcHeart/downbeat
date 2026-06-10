"""Quarantine management screen — list / requeue / purge quarantined messages."""
from __future__ import annotations

from rich.markup import escape as _rich_escape
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen, Screen
from textual.widgets import DataTable, Footer, Header, Label

from ...core import store


class _ConfirmModal(ModalScreen):
    """Generic y/n confirmation modal used for requeue and purge."""

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("y", "yes", "Yes"),
        ("n", "cancel", "No"),
    ]

    def __init__(self, message: str):
        super().__init__()
        self._message = message

    def compose(self) -> ComposeResult:
        with Vertical(classes="pane"):
            yield Label(self._message)
            yield Label("Press [b]y[/b] to confirm, [b]n[/b] to cancel")

    def action_yes(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)


class QuarantineScreen(Screen):
    BINDINGS = [
        ("escape", "app.pop_screen", "Back"),
        ("q", "app.pop_screen", "Back"),
        ("r", "requeue_all", "Requeue all"),
        ("p", "purge_all", "Purge all"),
        ("ctrl+r", "refresh", "Refresh"),
    ]

    def __init__(self, peer_name: str):
        super().__init__()
        self.peer_name = peer_name
        self._msgs: list = []

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Vertical(id="quarantine-root"):
            yield Label(
                f"[b]Quarantine[/b]  peer=[b]{_rich_escape(self.peer_name)}[/b]   "
                "[dim]r requeue-all · p purge-all · Esc back[/dim]"
            )
            self._table = DataTable(id="quarantine-table")
            self._table.cursor_type = "row"
            self._table.add_columns("id", "from", "quarantined", "subject")
            yield self._table
        yield Footer()

    def on_mount(self) -> None:
        self._refresh()

    def _refresh(self) -> None:
        self._msgs = store.list_quarantined(self.peer_name)
        self._table.clear()
        for m in self._msgs:
            from rich.text import Text
            row_id = Text(m.id)
            row_from = Text(_rich_escape(m.from_peer))
            row_quarantined = Text((m.quarantined_at or "")[:19])
            row_subject = Text(_rich_escape(m.subject))
            self._table.add_row(row_id, row_from, row_quarantined, row_subject)

    def action_refresh(self) -> None:
        self._refresh()

    def action_requeue_all(self) -> None:
        count = len(self._msgs)
        if count == 0:
            self.notify("No quarantined messages", severity="information")
            return

        def after(confirmed: bool) -> None:
            if not confirmed:
                return
            moved = store.requeue_quarantined(self.peer_name)
            self._refresh()
            self.notify(f"Requeued {moved} message(s) to inbox", timeout=3)

        self.app.push_screen(
            _ConfirmModal(
                f"Requeue [b]{count}[/b] quarantined message(s) to inbox?"
            ),
            after,
        )

    def action_purge_all(self) -> None:
        count = len(self._msgs)
        if count == 0:
            self.notify("No quarantined messages", severity="information")
            return

        def after(confirmed: bool) -> None:
            if not confirmed:
                return
            deleted = store.purge_quarantined(self.peer_name)
            self._refresh()
            self.notify(f"Purged {deleted} message(s)", timeout=3)

        self.app.push_screen(
            _ConfirmModal(
                f"Permanently delete [b]{count}[/b] quarantined message(s)?"
            ),
            after,
        )
