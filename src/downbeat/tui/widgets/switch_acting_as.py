"""Modal for switching the acting-as parent."""
from __future__ import annotations

from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Label, ListItem, ListView, Static

from ...core import store


class SwitchActingAsModal(ModalScreen):
    BINDINGS = [
        ("escape,q", "cancel", "Cancel"),
    ]

    def __init__(self, current: str | None):
        super().__init__()
        self.current = current
        self._listview: ListView | None = None
        self._parents: list[str] = []

    def compose(self):
        with Vertical(classes="pane"):
            yield Label("[b]Switch acting-as parent[/b]")
            yield Static("[dim]↑/↓ navigate · Enter select · Esc cancel[/dim]")
            self._listview = ListView(id="switch-listview")
            yield self._listview

    def on_mount(self) -> None:
        self._parents = [p.name for p in store.acting_as_candidates()]
        for name in self._parents:
            marker = "[b yellow]▶[/b yellow]" if name == self.current else " "
            self._listview.append(ListItem(Static(f"{marker} {name}")))
        # Preselect the current acting-as row
        if self.current in self._parents:
            self._listview.index = self._parents.index(self.current)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        idx = self._listview.index
        if idx is None or idx >= len(self._parents):
            self.dismiss(None)
            return
        self.dismiss(self._parents[idx])

    def action_cancel(self) -> None:
        self.dismiss(None)
