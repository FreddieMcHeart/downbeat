"""Chat-style main screen. Replaces the three-pane MainScreen."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import Footer, Header, Select

from ...core import store
from ..widgets.chat_composer import ChatComposer
from ..widgets.chat_stream import ChatStream
from ..widgets.log_viewer import LogViewer
from ..widgets.peer_tabs import PeerTabs


class ChatScreen(Screen):
    BINDINGS = [
        ("q", "app.quit", "Quit"),
        ("f1", "help", "Help"),
        ("f5", "refresh", "Refresh"),
        ("f6", "toggle_logs", "Logs"),
        ("up", "cursor_up", "Up"),
        ("down", "cursor_down", "Down"),
        ("e", "edit", "Edit"),
        ("d", "delete", "Delete"),
        ("f", "find_message", "Find"),
        ("v", "view_full", "View full"),
        ("P,shift+p", "add_peer", "Add peer"),
        ("X,shift+x", "remove_peer", "Remove peer"),
        ("G,shift+g", "gc_stale", "GC stale"),
        ("B,shift+b", "broadcast_status", "Bcast"),
        ("tab", "next_tab", "Next peer"),
        ("shift+tab", "prev_tab", "Prev peer"),
    ]

    acting_as: reactive[str | None] = reactive(None)
    active_peer: reactive[str | None] = reactive(None)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._updating: bool = False  # guard against re-entrant populate calls

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Vertical(id="chat-root"):
            yield Select([], prompt="Acting as", id="acting-as-select")
            yield PeerTabs(id="peer-tabs")
            yield ChatStream(id="chat-stream")
            yield ChatComposer(id="chat-composer")
            yield LogViewer()
        yield Footer()

    # ---------------- lifecycle ----------------

    async def on_mount(self) -> None:
        self._populate_acting_as()
        await self._populate_tabs()
        self._refresh_thread()

    def _related_prefix(self, parent_name: str) -> str:
        if "-" not in parent_name:
            return ""
        return parent_name.rsplit("-", 1)[0] + "-"

    def _group_members(self) -> list[str]:
        if not self.acting_as:
            return []
        prefix = self._related_prefix(self.acting_as)
        all_peers = store.list_peers()
        if prefix:
            return [p.name for p in all_peers if p.name.startswith(prefix)]
        return [p.name for p in all_peers]

    def _populate_acting_as(self) -> None:
        sel = self.query_one("#acting-as-select", Select)
        parents = [p for p in store.list_peers() if p.role == "parent"]
        sel.set_options([(p.name, p.name) for p in parents])
        if self.acting_as not in {p.name for p in parents}:
            self.acting_as = parents[0].name if parents else None
        if self.acting_as:
            sel.value = self.acting_as

    async def _populate_tabs(self) -> None:
        tabs = self.query_one("#peer-tabs", PeerTabs)
        members = self._group_members()
        await tabs.populate(members)
        # When tabs.populate sets self.active, on_tabs_tab_activated will fire
        # and set self.active_peer. As a defensive default:
        if members and not self.active_peer:
            self.active_peer = members[0]

    def _refresh_thread(self) -> None:
        stream = self.query_one("#chat-stream", ChatStream)
        stream.refresh_thread(self.acting_as, self.active_peer)
        # Mark all unread messages from active_peer as read
        if self.acting_as and self.active_peer:
            for m in store.list_inbox(self.acting_as):
                if m.from_peer == self.active_peer and m.state.value == "new":
                    store.mark_read(m.id)

    # ---------------- handlers ----------------

    async def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "acting-as-select" and event.value not in (None, Select.BLANK):
            new_val = str(event.value)
            if new_val == self.acting_as:
                # Same value — already initialised by on_mount; skip re-populate
                return
            self.acting_as = new_val
            await self._populate_tabs()
            self._refresh_thread()

    async def on_peer_tabs_peer_selected(self, event) -> None:
        self.active_peer = event.peer_name
        self._refresh_thread()

    def on_chat_composer_send(self, event) -> None:
        if not self.acting_as or not self.active_peer:
            self.notify("Pick a peer first", severity="warning")
            return
        # Subject: first 60 chars of body, or "msg" if blank
        subject = event.text.splitlines()[0][:60] if event.text else "msg"
        store.send_message(from_peer=self.acting_as, to_peer=self.active_peer,
                           subject=subject, body=event.text)
        self._refresh_thread()

    # ---------------- bindings ----------------

    def action_cursor_up(self) -> None:
        self.query_one("#chat-stream", ChatStream).move_cursor(-1)

    def action_cursor_down(self) -> None:
        self.query_one("#chat-stream", ChatStream).move_cursor(+1)

    def action_next_tab(self) -> None:
        members = self._group_members()
        if not members or not self.active_peer:
            return
        idx = members.index(self.active_peer) if self.active_peer in members else -1
        self.active_peer = members[(idx + 1) % len(members)]
        # Reflect on Tabs widget (active is a reactive, not an await)
        tabs = self.query_one("#peer-tabs", PeerTabs)
        tabs.active = f"tab-{tabs._safe_id(self.active_peer)}"
        self._refresh_thread()

    def action_prev_tab(self) -> None:
        members = self._group_members()
        if not members or not self.active_peer:
            return
        idx = members.index(self.active_peer) if self.active_peer in members else 1
        self.active_peer = members[(idx - 1) % len(members)]
        tabs = self.query_one("#peer-tabs", PeerTabs)
        tabs.active = f"tab-{tabs._safe_id(self.active_peer)}"
        self._refresh_thread()

    async def action_refresh(self) -> None:
        self._populate_acting_as()
        await self._populate_tabs()
        self._refresh_thread()

    def action_help(self) -> None:
        from .help import HelpScreen
        self.app.push_screen(HelpScreen())

    def action_toggle_logs(self) -> None:
        self.query_one(LogViewer).toggle()

    def action_edit(self) -> None:
        from ..widgets.edit_modal import EditModal
        msg = self.query_one("#chat-stream", ChatStream).selected_message()
        if not msg:
            self.notify("No message focused", severity="warning")
            return
        if msg.state.value != "new":
            self.notify(f"message is {msg.state.value} — edit blocked", severity="warning")
            return
        async def after(_):
            self._refresh_thread()
        self.app.push_screen(EditModal(msg.id), after)

    def action_delete(self) -> None:
        from ..widgets.confirm import ConfirmDelete, perform_delete
        msg = self.query_one("#chat-stream", ChatStream).selected_message()
        if not msg:
            return
        def after(confirmed):
            if confirmed:
                perform_delete(msg.id)
                self._refresh_thread()
        self.app.push_screen(ConfirmDelete(
            f"Delete message {msg.id} from {msg.from_peer}?"), after)

    def action_find_message(self) -> None:
        from ..widgets.find_message import FindMessageModal
        async def after(msg):
            if msg is None:
                return
            # Switch acting-as and tab if needed
            peers = {p.name: p for p in store.list_peers()}
            is_parent = msg.to_peer in peers and peers[msg.to_peer].role == "parent"
            target_acting = msg.to_peer if is_parent else msg.from_peer
            other = msg.from_peer if target_acting == msg.to_peer else msg.to_peer
            if target_acting in peers and peers[target_acting].role == "parent":
                self.acting_as = target_acting
                await self._populate_tabs()
                self.active_peer = other
                tabs = self.query_one("#peer-tabs", PeerTabs)
                if other in self._group_members():
                    tabs.active = f"tab-{tabs._safe_id(other)}"
                self._refresh_thread()
        self.app.push_screen(FindMessageModal(), after)

    def action_view_full(self) -> None:
        # Could push a modal showing untruncated message body; for MVP, no-op + hint
        msg = self.query_one("#chat-stream", ChatStream).selected_message()
        if not msg:
            return
        self.notify(f"Full body of {msg.id}:\n{msg.body}", timeout=10)

    def action_add_peer(self) -> None:
        from ..widgets.add_peer_modal import AddPeerModal
        async def after(name):
            await self.action_refresh()
            if name:
                self.notify(f"Registered peer {name}", timeout=2)
        self.app.push_screen(AddPeerModal(), after)

    def action_remove_peer(self) -> None:
        from ..widgets.peer_admin import RemovePeerConfirm
        # Remove the currently active tab peer
        if not self.active_peer:
            self.notify("No peer to remove", severity="warning")
            return
        async def after(removed):
            await self.action_refresh()
            if removed:
                self.notify(f"Removed peer {removed}", timeout=2)
        self.app.push_screen(RemovePeerConfirm(self.active_peer), after)

    def action_gc_stale(self) -> None:
        from ..widgets.peer_admin import GcStaleModal
        async def after(pruned):
            await self.action_refresh()
        self.app.push_screen(GcStaleModal(), after)

    def action_broadcast_status(self) -> None:
        from .broadcast_status import BroadcastStatusScreen
        msg = self.query_one("#chat-stream", ChatStream).selected_message()
        if not msg:
            self.notify("Select a message first", severity="warning")
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

    async def on_store_changed(self, event) -> None:
        await self.action_refresh()
