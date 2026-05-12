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
        unread_mark = f"[b]{row.unread}[/b]" if row.unread else "0"
        return f"{row.peer_name:<18} [dim]{row.role}[/dim]  {unread_mark}"


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
        self._listview = ListView(id="peer-listview")
        yield self._listview

    def on_mount(self):
        self.refresh_from_store()

    def refresh_from_store(self) -> None:
        peers = store.list_peers()
        self.items = []
        for p in peers:
            unread = len([m for m in store.list_inbox(p.name)
                          if m.state.value == "new"])
            row = PeerRow(peer_name=p.name, role=p.role, unread=unread)
            self.items.append(_PeerListItem(row))
        self._listview.clear()
        for it in self.items:
            self._listview.append(it)
        options = [(p.name, p.name) for p in peers]
        self._select.set_options(options)
        if self.acting_as is None:
            parents = [p for p in peers if p.role == "parent"]
            self.acting_as = parents[0].name if parents else (peers[0].name if peers else None)
        if self.acting_as:
            self._select.value = self.acting_as

    @on(Select.Changed, "#acting-as-select")
    def _on_select(self, event: Select.Changed) -> None:
        if event.value and event.value != Select.BLANK:
            self.acting_as = str(event.value)
            self.post_message(self.ActingAsChanged(self.acting_as))
