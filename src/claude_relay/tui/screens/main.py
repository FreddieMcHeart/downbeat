"""Three-pane main screen: Peers | Inbox | Message."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import Footer, Header, Static

from ..widgets.peer_list import PeerList


class MainScreen(Screen):
    BINDINGS = [
        ("q", "app.quit", "Quit"),
        ("f1", "help", "Help"),
        ("f5", "refresh", "Refresh"),
        ("f6", "toggle_logs", "Logs"),
        ("ctrl+t", "toggle_dark", "Theme"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Horizontal(id="three-pane"):
            yield PeerList(id="peers-pane", classes="pane")
            yield Static("Inbox", id="inbox-pane", classes="pane")
            yield Static("Message", id="message-pane", classes="pane")
        yield Footer()

    def action_help(self) -> None:
        self.app.bell()  # placeholder until Task 20

    def action_refresh(self) -> None:
        self.query_one(PeerList).refresh_from_store()

    def action_toggle_logs(self) -> None:
        self.app.bell()  # placeholder until Task 19

    def action_toggle_dark(self) -> None:
        self.app.dark = not self.app.dark
