"""Left pane: registered peers with unread counts + 'Acting as' selector."""
from __future__ import annotations

from dataclasses import dataclass

from textual import on
from textual.containers import Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import ListItem, ListView, Select, Static

from ...core import store


@dataclass
class PeerRow:
    peer_name: str
    role: str
    unread: int


class _PeerListItem(ListItem):
    def __init__(self, row: PeerRow):
        super().__init__(Static(self._format_row(row)))
        self.peer_name = row.peer_name
        self.unread = row.unread

    @staticmethod
    def _format_row(row: PeerRow) -> str:
        role_glyph = "P" if row.role == "parent" else "C"
        if row.unread:
            unread = f"[b]{row.unread}[/b]"
        else:
            unread = "[dim]0[/dim]"
        name = row.peer_name if len(row.peer_name) <= 18 else row.peer_name[:17] + "…"
        return f"{name}  [dim]{role_glyph}[/dim]  {unread}"


class PeerList(Vertical):
    DEFAULT_CSS = ""
    acting_as: reactive[str | None] = reactive(None)

    class ActingAsChanged(Message):
        def __init__(self, peer: str) -> None:
            super().__init__()
            self.peer = peer

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.items: list[_PeerListItem] = []
        self._select: Select | None = None
        self._listview: ListView | None = None

    def compose(self):
        self._select = Select[str]([], prompt="Acting as", id="acting-as-select")
        yield self._select
        yield Static("[dim]P=parent  C=child[/dim]")
        self._listview = ListView(id="peer-listview")
        yield self._listview

    def on_mount(self):
        self.refresh_from_store()

    def _related_prefix(self, parent_name: str) -> str:
        """Return the naming prefix used to find related children.
        For 'PLAT-3113-master' returns 'PLAT-3113-'; for 'parent' returns ''.
        Empty prefix means "fallback to all children"."""
        if "-" not in parent_name:
            return ""
        return parent_name.rsplit("-", 1)[0] + "-"

    def refresh_from_store(self) -> None:
        all_peers = store.list_peers()
        parents = [p for p in all_peers if p.role == "parent"]
        children = [p for p in all_peers if p.role == "child"]

        # Maintain or pick acting_as among PARENTS only.
        parent_names = {p.name for p in parents}
        if self.acting_as not in parent_names:
            self.acting_as = parents[0].name if parents else None

        # Filter children to those related to the acting-as parent.
        if self.acting_as:
            prefix = self._related_prefix(self.acting_as)
            if prefix:
                related = [c for c in children if c.name.startswith(prefix)]
            else:
                related = children
        else:
            related = []

        # Build list items
        self.items = []
        for p in related:
            unread = len([m for m in store.list_inbox(p.name)
                          if m.state.value == "new"])
            row = PeerRow(peer_name=p.name, role=p.role, unread=unread)
            self.items.append(_PeerListItem(row))

        self._listview.clear()
        for it in self.items:
            self._listview.append(it)

        # Dropdown options: PARENTS ONLY
        options = [(p.name, p.name) for p in parents]
        self._select.set_options(options)
        if self.acting_as:
            self._select.value = self.acting_as

    def selected_peer_name(self) -> str | None:
        if not self._listview:
            return None
        idx = self._listview.index
        if idx is None or idx >= len(self.items):
            return None
        return self.items[idx].peer_name

    def on_list_view_selected(self, event) -> None:
        name = self.selected_peer_name()
        if name:
            self.post_message(self.ActingAsChanged(name))
            event.stop()

    @on(Select.Changed, "#acting-as-select")
    def _on_select(self, event: Select.Changed) -> None:
        if event.value and event.value != Select.BLANK:
            self.acting_as = str(event.value)
            self.post_message(self.ActingAsChanged(self.acting_as))
