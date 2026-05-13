"""Chat-style main screen. Replaces the three-pane MainScreen."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import Footer, Header, Static

from ...core import store
from ..widgets.chat_composer import ChatComposer
from ..widgets.chat_stream import ChatStream
from ..widgets.log_viewer import LogViewer
from ..widgets.peer_tabs import PeerTabs


class ChatScreen(Screen):
    BINDINGS = [
        ("q", "app.quit", "Quit"),
        ("f1", "help", "Help"),
        ("ctrl+r", "refresh", "Refresh"),
        ("f6", "toggle_logs", "Logs"),
        ("f", "find_message", "Find"),
        ("ctrl+p", "open_peers", "Peers"),
        ("s", "switch_acting_as", "Switch acting-as"),
        ("left,h", "prev_tab", "Prev member"),
        ("right,l", "next_tab", "Next member"),
    ]

    acting_as: reactive[str | None] = reactive(None)
    active_peer: reactive[str | None] = reactive(None)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._updating: bool = False  # guard against re-entrant populate calls

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Vertical(id="chat-root"):
            yield Static("", id="acting-as-chip")
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
            # Grouped parent → only peers sharing the same prefix
            members = [p.name for p in all_peers if p.name.startswith(prefix)]
        else:
            # Ungrouped parent (no '-') → only other ungrouped peers
            members = [p.name for p in all_peers if "-" not in p.name]
        # The parent shouldn't have a tab to talk to itself
        return [name for name in members if name != self.acting_as]

    def _populate_acting_as(self) -> None:
        parents = [p for p in store.list_peers() if p.role == "parent"]
        parent_names = {p.name for p in parents}
        if self.acting_as not in parent_names:
            self.acting_as = parents[0].name if parents else None
        chip = self.query_one("#acting-as-chip", Static)
        if self.acting_as:
            chip.update(
                f"[b]Acting as:[/b] {self.acting_as}   "
                f"[dim]s to switch[/dim]"
            )
        else:
            chip.update("[dim]No parents registered — press Ctrl+P to add one[/dim]")

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
        # Per-bubble mark-read is handled by ChatStream._mark_focused_read
        # (called automatically on refresh and on cursor move). We do NOT bulk
        # mark-read everything on tab open — that's too aggressive.

    # ---------------- handlers ----------------

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

    def on_chat_composer_broadcast(self, event) -> None:
        if not self.acting_as:
            self.notify("Pick a parent first", severity="warning")
            return
        members = [n for n in self._group_members() if n != self.acting_as]
        if not members:
            self.notify("No group members to broadcast to", severity="warning")
            return
        subject = event.text.splitlines()[0][:60] if event.text else "msg"
        bc = store.broadcast(from_peer=self.acting_as, to_peers=members,
                             subject=subject, body=event.text)
        self.notify(f"Broadcast {bc.id} sent to {len(members)} peers", timeout=4)
        self._refresh_thread()

    # ---------------- bindings ----------------

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

    def on_chat_stream_message_opened(self, event) -> None:
        from .message_detail import MessageDetailScreen
        async def after(_):
            await self.action_refresh()
        self.app.push_screen(MessageDetailScreen(event.msg_id), after)

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

    def action_open_peers(self) -> None:
        from .peers import PeersScreen
        def after(_):
            self.action_refresh()
        self.app.push_screen(PeersScreen(), after)

    def action_switch_acting_as(self) -> None:
        from ..widgets.switch_acting_as import SwitchActingAsModal
        def after(name):
            if name is None or name == self.acting_as:
                return
            self.acting_as = name
            self._populate_acting_as()
            self.call_after_refresh(self._populate_tabs_and_refresh)
        self.app.push_screen(SwitchActingAsModal(self.acting_as), after)

    async def _populate_tabs_and_refresh(self) -> None:
        await self._populate_tabs()
        self._refresh_thread()

    async def on_store_changed(self, event) -> None:
        await self.action_refresh()
