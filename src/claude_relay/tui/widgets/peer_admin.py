"""Confirm-and-delete a peer, and GC-stale dialog with dry-run preview."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Input, Label

from ...core import store


def perform_remove_peer(name: str) -> None:
    store.remove_peer(name)


class RemovePeerConfirm(ModalScreen):
    BINDINGS = [("escape", "cancel", "Cancel"),
                ("y", "yes", "Yes"),
                ("n", "cancel", "No")]

    def __init__(self, peer_name: str):
        super().__init__()
        self.peer_name = peer_name

    def compose(self):
        with Vertical(classes="pane"):
            yield Label(f"[b]Remove peer[/b] {self.peer_name}?")
            yield Label("[dim]Inbox / processed message files are left untouched.[/dim]")
            yield Label("Press [b]y[/b] to confirm, [b]n[/b] to cancel")

    def action_yes(self) -> None:
        perform_remove_peer(self.peer_name)
        self.dismiss(self.peer_name)

    def action_cancel(self) -> None:
        self.dismiss(None)


class GcStaleModal(ModalScreen):
    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self):
        super().__init__()
        self._days: Input | None = None
        self._table: DataTable | None = None

    def compose(self):
        with Vertical(classes="pane"):
            yield Label("[b]GC stale peers[/b]")
            self._days = Input(value="14", placeholder="days threshold",
                               id="gc-days")
            yield self._days
            self._table = DataTable(id="gc-preview")
            self._table.add_columns("peer", "last_seen", "age (days)")
            yield self._table
            yield Button("Preview", id="gc-preview-btn")
            yield Button("Prune now", id="gc-prune", variant="error")

    def on_mount(self) -> None:
        self._refresh_preview()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "gc-days":
            self._refresh_preview()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "gc-preview-btn":
            self._refresh_preview()
        elif event.button.id == "gc-prune":
            pruned = self._prune()
            self.notify(f"Pruned {len(pruned)} stale peers",
                        timeout=3)
            self.dismiss(pruned)

    def _threshold(self) -> datetime:
        try:
            days = int(self._days.value or "14")
        except ValueError:
            days = 14
        return datetime.now(UTC) - timedelta(days=days)

    def _stale_peers(self) -> list[tuple[str, str, float]]:
        threshold = self._threshold()
        now = datetime.now(UTC)
        out: list[tuple[str, str, float]] = []
        for p in store.list_peers():
            try:
                ls = datetime.fromisoformat(p.last_seen)
            except ValueError:
                continue
            if ls < threshold:
                age = (now - ls).total_seconds() / 86400.0
                out.append((p.name, p.last_seen, age))
        return out

    def _refresh_preview(self) -> None:
        self._table.clear()
        for name, last_seen, age in self._stale_peers():
            self._table.add_row(name, last_seen[:19], f"{age:.1f}")

    def _prune(self) -> list[str]:
        pruned: list[str] = []
        for name, _, _ in self._stale_peers():
            store.remove_peer(name)
            pruned.append(name)
        return pruned

    def action_cancel(self) -> None:
        self.dismiss(None)
