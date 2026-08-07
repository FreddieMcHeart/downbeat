"""Modal for switching the acting-as parent."""
from __future__ import annotations

from dataclasses import dataclass

from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Label, ListItem, ListView, Static

from ...core import store

_SORT_MODES = ("recent", "name", "added")


@dataclass
class _Row:
    name: str
    unread: int
    newest: str | None
    registered_at: str


class SwitchActingAsModal(ModalScreen):
    BINDINGS = [
        ("escape,q", "cancel", "Cancel"),
        ("s", "cycle_sort", "Sort"),
    ]

    def __init__(self, current: str | None):
        super().__init__()
        self.current = current
        self._listview: ListView | None = None
        self._hint: Static | None = None
        self._rows: list[_Row] = []
        self._sorted: list[_Row] = []
        self._sort_index = 0

    def compose(self):
        with Vertical(classes="pane"):
            yield Label("[b]Switch acting-as parent[/b]")
            self._hint = Static(self._hint_text())
            yield self._hint
            self._listview = ListView(id="switch-listview")
            yield self._listview

    def on_mount(self) -> None:
        self._rows = []
        for peer in store.acting_as_candidates():
            unread, newest = store.inbox_summary(peer.name)
            self._rows.append(_Row(peer.name, unread, newest, peer.registered_at))
        self._render_rows()

    def _hint_text(self) -> str:
        mode = _SORT_MODES[self._sort_index]
        return f"[dim]↑/↓ navigate · Enter select · Esc cancel · s: sort ({mode})[/dim]"

    def _sorted_rows(self) -> list[_Row]:
        mode = _SORT_MODES[self._sort_index]
        if mode == "name":
            return sorted(self._rows, key=lambda r: r.name)
        if mode == "added":
            return sorted(self._rows, key=lambda r: r.registered_at, reverse=True)
        # "recent" (default): newest message first; peers with no messages
        # sort last rather than under a fabricated timestamp.
        with_messages = sorted(
            (r for r in self._rows if r.newest is not None),
            key=lambda r: r.newest or "",
            reverse=True,
        )
        without_messages = [r for r in self._rows if r.newest is None]
        return with_messages + without_messages

    def _render_rows(self) -> None:
        self._sorted = self._sorted_rows()
        self._listview.clear()
        for row in self._sorted:
            marker = "[b yellow]▶[/b yellow]" if row.name == self.current else " "
            badge = f"  ●{row.unread}" if row.unread > 0 else ""
            self._listview.append(ListItem(Static(f"{marker} {row.name}{badge}")))
        # Preselect the current acting-as row, recomputed against the NEW
        # order every time -- never carried over as a stale index.
        names = [r.name for r in self._sorted]
        if self.current in names:
            self._listview.index = names.index(self.current)
        self._hint.update(self._hint_text())

    def action_cycle_sort(self) -> None:
        self._sort_index = (self._sort_index + 1) % len(_SORT_MODES)
        self._render_rows()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        idx = self._listview.index
        if idx is None or idx >= len(self._sorted):
            self.dismiss(None)
            return
        self.dismiss(self._sorted[idx].name)

    def action_cancel(self) -> None:
        self.dismiss(None)
