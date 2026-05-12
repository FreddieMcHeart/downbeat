"""Three-pane main screen: Peers | Inbox | Message."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import Footer, Header

from ..widgets.inbox_list import InboxList
from ..widgets.message_view import MessageView
from ..widgets.peer_list import PeerList


class MainScreen(Screen):
    BINDINGS = [
        ("q", "app.quit", "Quit"),
        ("f1", "help", "Help"),
        ("f5", "refresh", "Refresh"),
        ("f6", "toggle_logs", "Logs"),
        ("ctrl+t", "toggle_dark", "Theme"),
        ("enter", "open_message", "Open"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Horizontal(id="three-pane"):
            yield PeerList(id="peers-pane", classes="pane")
            yield InboxList(id="inbox-pane", classes="pane")
            yield MessageView(id="message-pane", classes="pane")
        yield Footer()

    def on_mount(self) -> None:
        peers = self.query_one(PeerList)
        if peers.acting_as:
            self.query_one(InboxList).refresh_for_peer(peers.acting_as)

    def on_peer_list_acting_as_changed(self, event) -> None:
        self.query_one(InboxList).refresh_for_peer(event.peer)

    def action_help(self) -> None:
        self.app.bell()  # placeholder until Task 20

    def action_refresh(self) -> None:
        self.query_one(PeerList).refresh_from_store()

    def action_toggle_logs(self) -> None:
        self.app.bell()  # placeholder until Task 19

    def action_toggle_dark(self) -> None:
        self.app.dark = not self.app.dark

    def action_open_message(self) -> None:
        msg = self.query_one(InboxList).selected_message()
        if msg:
            self.query_one(MessageView).show(msg.id)
            self.query_one(PeerList).refresh_from_store()  # update unread counts
