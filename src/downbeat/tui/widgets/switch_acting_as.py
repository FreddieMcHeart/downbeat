"""Modal for switching the acting-as parent."""
from __future__ import annotations

from dataclasses import dataclass

from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.timer import Timer
from textual.widgets import Label, ListItem, ListView, Static

from ...core import store
from ..messages import StoreChanged

_SORT_MODES = ("recent", "name", "added")

# DECISION (#118): kept deliberately, not dead weight. watcher.py's
# on_any_event fires once per matched filesystem event with no coalescing
# of its own, so a real broadcast that writes N message files still posts N
# separate StoreChanged messages here. This debounce coalesces that burst
# into a single re-read. Each new event during the window EXTENDS it rather
# than being dropped -- see on_store_changed. If source-level coalescing is
# ever added (deferred to #120; not built in this PR), re-check whether
# this becomes a second, redundant delay stacked on top of it.
_REFRESH_DEBOUNCE_SECONDS = 0.15


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
        self._refresh_timer: Timer | None = None

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
        self._sorted = self._sorted_rows()
        self._render_rows(target=None)

    def on_unmount(self) -> None:
        if self._refresh_timer is not None:
            self._refresh_timer.stop()
            self._refresh_timer = None

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

    def _current_highlighted_name(self) -> str | None:
        """The peer under the cursor right now, read from the OUTGOING
        `self._sorted` before a render replaces it. A re-render (resort or
        live refresh) keeps the cursor on this same PEER rather than
        snapping back to `self.current` or drifting to a new index."""
        if self._listview is None or self._listview.index is None:
            return None
        if not (0 <= self._listview.index < len(self._sorted)):
            return None
        return self._sorted[self._listview.index].name

    def _render_rows(self, *, target: str | None) -> None:
        """Rebuild the ListView from the CURRENT `self._sorted` (callers own
        whether/how it was resorted before this runs) and reselect `target`
        if it's still present, falling back to `self.current`. `target` must
        be captured by the caller via `_current_highlighted_name()` BEFORE
        `self._sorted` is reassigned -- capturing it in here would read the
        old index against the already-replaced list and pick the wrong row."""
        self._listview.clear()
        for row in self._sorted:
            marker = "[b yellow]▶[/b yellow]" if row.name == self.current else " "
            badge = f"  ●{row.unread}" if row.unread > 0 else ""
            self._listview.append(ListItem(Static(f"{marker} {row.name}{badge}")))
        names = [r.name for r in self._sorted]
        pick = target if target in names else (
            self.current if self.current in names else None
        )
        if pick is not None:
            self._listview.index = names.index(pick)
        self._hint.update(self._hint_text())

    def action_cycle_sort(self) -> None:
        target = self._current_highlighted_name()
        self._sort_index = (self._sort_index + 1) % len(_SORT_MODES)
        self._sorted = self._sorted_rows()
        self._render_rows(target=target)

    def on_store_changed(self, event: StoreChanged) -> None:
        # Debounce: coalesce a burst into one re-read. Each new event
        # cancels and reschedules -- it EXTENDS the window rather than being
        # dropped, so the refresh always eventually runs once the burst
        # settles, never silently skipping the event that triggered it.
        if self._refresh_timer is not None:
            self._refresh_timer.stop()
        self._refresh_timer = self.set_timer(_REFRESH_DEBOUNCE_SECONDS, self._refresh_counts)

    def _refresh_counts(self) -> None:
        self._refresh_timer = None
        target = self._current_highlighted_name()
        # Re-read counts in place; deliberately do NOT re-sort while the
        # modal is open -- a row moving under the cursor between an arrow
        # key and Enter would select the wrong peer. `s` (action_cycle_sort)
        # remains the only thing that re-sorts, against these fresh counts.
        live_names: set[str] = set()
        existing_names = {row.name for row in self._rows}
        for peer in store.acting_as_candidates():
            live_names.add(peer.name)
            if peer.name not in existing_names:
                # Appeared while the modal was open -- appended at the end
                # of both lists, never spliced into the frozen sort order.
                unread, newest = store.inbox_summary(peer.name)
                new_row = _Row(peer.name, unread, newest, peer.registered_at)
                self._rows.append(new_row)
                self._sorted.append(new_row)
        for row in self._rows:
            if row.name in live_names:
                row.unread, row.newest = store.inbox_summary(row.name)
            # else: peer vanished mid-open -- leave its last known count in
            # place rather than removing the row from under the cursor.
        self._render_rows(target=target)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        idx = self._listview.index
        if idx is None or idx >= len(self._sorted):
            self.dismiss(None)
            return
        self.dismiss(self._sorted[idx].name)

    def action_cancel(self) -> None:
        self.dismiss(None)
