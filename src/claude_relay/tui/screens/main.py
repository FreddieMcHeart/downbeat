"""Three-pane main screen: Peers | Inbox | Message."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header

from ...core import store
from ..messages import StoreChanged
from ..widgets.composer import Composer
from ..widgets.confirm import ConfirmDelete, perform_delete
from ..widgets.edit_modal import EditModal
from ..widgets.inbox_list import InboxList
from ..widgets.log_viewer import LogViewer
from ..widgets.message_view import MessageView
from ..widgets.peer_list import PeerList
from .broadcast_status import BroadcastStatusScreen
from .help import HelpScreen


class MainScreen(Screen):
    BINDINGS = [
        ("q", "app.quit", "Quit"),
        ("f1", "help", "Help"),
        ("f5", "refresh", "Refresh"),
        ("f6", "toggle_logs", "Logs"),
        ("ctrl+t", "toggle_dark", "Theme"),
        ("enter", "open_message", "Open"),
        ("n", "new_message", "New"),
        ("r", "reply", "Reply"),
        ("e", "edit", "Edit"),
        ("d", "delete", "Delete"),
        ("a", "toggle_archived", "Show/hide archived"),
        ("B,shift+b", "broadcast_status", "Bcast status"),
        ("P,shift+p", "add_peer", "Add peer"),
        ("X,shift+x", "remove_peer", "Remove peer"),
        ("G,shift+g", "gc_stale", "GC stale"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Horizontal(id="three-pane"):
            yield PeerList(id="peers-pane", classes="pane")
            yield InboxList(id="inbox-pane", classes="pane")
            yield MessageView(id="message-pane", classes="pane")
        yield Footer()
        yield LogViewer(id="logs")

    def on_mount(self) -> None:
        peers = self.query_one(PeerList)
        if peers.acting_as:
            inbox = self.query_one(InboxList)
            inbox.refresh_for_peer(peers.acting_as)
            if inbox.row_count > 0:
                inbox.focus()

    def on_peer_list_acting_as_changed(self, event) -> None:
        inbox = self.query_one(InboxList)
        inbox.refresh_for_peer(event.peer)
        inbox.focus()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        # Only react to InboxList selections; other DataTables live on
        # different screens so their RowSelected won't reach MainScreen.
        if isinstance(event.data_table, InboxList):
            self.action_open_message()
            event.stop()

    def on_store_changed(self, event: StoreChanged) -> None:
        self.action_refresh()
        sender = self.query_one(PeerList).acting_as
        if sender:
            self.query_one(InboxList).refresh_for_peer(sender)

    def action_help(self) -> None:
        self.app.push_screen(HelpScreen())

    def action_refresh(self) -> None:
        self.query_one(PeerList).refresh_from_store()

    def action_toggle_logs(self) -> None:
        self.query_one(LogViewer).toggle()

    def action_toggle_dark(self) -> None:
        self.app.dark = not self.app.dark

    def action_open_message(self) -> None:
        msg = self.query_one(InboxList).selected_message()
        if msg:
            self.query_one(MessageView).show(msg.id)
            self.query_one(PeerList).refresh_from_store()  # update unread counts

    def action_new_message(self) -> None:
        sender = self.query_one(PeerList).acting_as
        if not sender:
            self.app.bell()
            return
        def _after(_): self.query_one(InboxList).refresh_for_peer(sender)
        self.app.push_screen(Composer(sender=sender), _after)

    def action_reply(self) -> None:
        sender = self.query_one(PeerList).acting_as
        msg = self.query_one(InboxList).selected_message()
        if not (sender and msg):
            self.app.bell()
            return
        def _after(_): self.query_one(InboxList).refresh_for_peer(sender)
        self.app.push_screen(
            Composer(sender=sender, reply_to=msg.id, prefill_to=msg.from_peer),
            _after,
        )

    def action_edit(self) -> None:
        msg = self.query_one(InboxList).selected_message()
        if not msg:
            return
        if msg.state.value != "new":
            self.notify(f"message is {msg.state.value} — edit blocked",
                        severity="warning")
            return
        sender = self.query_one(PeerList).acting_as
        def _after(_): self.query_one(InboxList).refresh_for_peer(sender)
        self.app.push_screen(EditModal(msg.id), _after)

    def action_delete(self) -> None:
        msg = self.query_one(InboxList).selected_message()
        if not msg:
            return
        sender = self.query_one(PeerList).acting_as
        def _after(confirmed):
            if confirmed:
                perform_delete(msg.id)
                self.query_one(InboxList).refresh_for_peer(sender)
                self.query_one(PeerList).refresh_from_store()
        self.app.push_screen(
            ConfirmDelete(f"Delete message {msg.id} from {msg.from_peer}?"),
            _after,
        )

    def action_toggle_archived(self) -> None:
        inbox = self.query_one(InboxList)
        inbox.toggle_archived()
        state = "shown" if inbox.show_archived else "hidden"
        self.notify(f"Archived messages {state}", timeout=2)

    def action_add_peer(self) -> None:
        from ..widgets.add_peer_modal import AddPeerModal
        def after(name):
            peer_list = self.query_one(PeerList)
            peer_list.refresh_from_store()
            if name:
                self.notify(f"Registered peer {name}", timeout=2)
        self.app.push_screen(AddPeerModal(), after)

    def action_remove_peer(self) -> None:
        from ..widgets.peer_admin import RemovePeerConfirm
        peer_list = self.query_one(PeerList)
        target = peer_list.selected_peer_name() or peer_list.acting_as
        if not target:
            self.notify("No peer to remove", severity="warning")
            return
        def after(removed):
            peer_list.refresh_from_store()
            if removed:
                self.notify(f"Removed peer {removed}", timeout=2)
                inbox = self.query_one(InboxList)
                if peer_list.acting_as not in {p.name for p in store.list_peers()}:
                    inbox.refresh_for_peer(None)
        self.app.push_screen(RemovePeerConfirm(target), after)

    def action_gc_stale(self) -> None:
        from ..widgets.peer_admin import GcStaleModal
        def after(pruned):
            self.query_one(PeerList).refresh_from_store()
        self.app.push_screen(GcStaleModal(), after)

    def action_broadcast_status(self) -> None:
        msg = self.query_one(InboxList).selected_message()
        if not msg:
            self.notify("Select a message first", severity="warning", timeout=3)
            return
        if not msg.broadcast_id:
            self.notify(
                f"Message {msg.id} is not part of a broadcast — "
                "broadcast status is only meaningful for fan-out messages.",
                severity="warning",
                timeout=5,
            )
            return
        self.app.push_screen(BroadcastStatusScreen(msg.broadcast_id))
