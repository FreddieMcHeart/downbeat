"""Chat-style main screen. Replaces the three-pane MainScreen."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import Footer, Header, Static

from ...core import state, store
from ..widgets.chat_composer import ChatComposer
from ..widgets.chat_stream import ChatStream
from ..widgets.log_viewer import LogViewer
from ..widgets.peer_tabs import OWN_INBOX_ID, PeerTabs


class ChatScreen(Screen):
    BINDINGS = [
        ("q", "app.quit", "Quit"),
        # priority=True: fires even while a text widget (composer, find, peer-name
        # input) has focus and would otherwise consume the key. "q" itself must
        # stay non-priority so it's still typeable in message bodies — ctrl+c is
        # the universal, always-works escape hatch users expect from any TUI.
        Binding("ctrl+c", "app.quit", "Quit", priority=True, show=False),
        ("question_mark,f1", "help", "Help"),
        ("ctrl+r", "refresh", "Refresh"),
        ("ctrl+l,f6", "toggle_logs", "Logs"),
        ("f", "find_message", "Find"),
        ("ctrl+p", "open_peers", "Peers"),
        ("a", "toggle_archived", "Archived"),
        ("c", "clear_inbox", "Clear inbox"),
        ("s", "switch_acting_as", "Switch acting-as"),
        Binding("left,h", "prev_tab", "Prev member", key_display="←"),
        Binding("right,l", "next_tab", "Next member", key_display="→"),
        ("Q,shift+q", "open_quarantine", "Quarantine"),
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

    def _group_members(self) -> list[str]:
        if not self.acting_as:
            return []
        # Every child explicitly paired with acting_as (Peer.parent), not
        # peers that merely share a name prefix. The parent shouldn't have
        # a tab to talk to itself.
        return [p.name for p in store.children_of(self.acting_as) if p.name != self.acting_as]

    def _populate_acting_as(self) -> None:
        candidates = store.acting_as_candidates()
        candidate_names = {p.name for p in candidates}
        # Prefer persisted last-acting-as if still valid
        if self.acting_as is None or self.acting_as not in candidate_names:
            last = state.get_last_acting_as()
            if last in candidate_names:
                self.acting_as = last
            else:
                self.acting_as = candidates[0].name if candidates else None
        chip = self.query_one("#acting-as-chip", Static)
        if self.acting_as:
            q_count = sum(
                1 for m in store.list_inbox(self.acting_as, include_archived=True)
                if m.state.value == "quarantined"
            )
            suffix = f"   [red]⚠ {q_count} quarantined[/red]" if q_count else ""
            chip.update(
                f"[b]Acting as:[/b] {self.acting_as}   "
                f"[dim]s to switch[/dim]{suffix}"
            )
        else:
            chip.update("[dim]No parents registered — press Ctrl+P to add one[/dim]")

    async def _populate_tabs(self) -> None:
        tabs = self.query_one("#peer-tabs", PeerTabs)
        members = self._group_members()
        await tabs.populate(members, acting_as=self.acting_as)
        # Build the full tab order: own-inbox first, then members
        all_tabs = [OWN_INBOX_ID] + members
        # Prefer persisted last_active_peer if it's still a valid tab; else own-inbox
        if self.active_peer not in all_tabs:
            last = state.get_last_active_peer()
            if last in all_tabs:
                self.active_peer = last
            else:
                self.active_peer = OWN_INBOX_ID

    def _refresh_thread(self) -> None:
        stream = self.query_one("#chat-stream", ChatStream)
        stream.refresh_thread(self.acting_as, self.active_peer)
        # Per-bubble mark-read is handled by ChatStream._mark_focused_read
        # (called automatically on refresh and on cursor move). We do NOT bulk
        # mark-read everything on tab open — that's too aggressive.

    # ---------------- handlers ----------------

    async def on_peer_tabs_peer_selected(self, event) -> None:
        self.active_peer = event.peer_name
        # Don't persist the sentinel — it would corrupt last_active_peer state
        if event.peer_name != OWN_INBOX_ID:
            state.set_last_active_peer(event.peer_name)
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
        all_tabs = [OWN_INBOX_ID] + members
        if not all_tabs or not self.active_peer:
            return
        idx = all_tabs.index(self.active_peer) if self.active_peer in all_tabs else -1
        self.active_peer = all_tabs[(idx + 1) % len(all_tabs)]
        if self.active_peer != OWN_INBOX_ID:
            state.set_last_active_peer(self.active_peer)
        # Reflect on Tabs widget (active is a reactive, not an await)
        tabs = self.query_one("#peer-tabs", PeerTabs)
        tabs.active = f"tab-{tabs._safe_id(self.active_peer)}"
        self._refresh_thread()

    def action_prev_tab(self) -> None:
        members = self._group_members()
        all_tabs = [OWN_INBOX_ID] + members
        if not all_tabs or not self.active_peer:
            return
        idx = all_tabs.index(self.active_peer) if self.active_peer in all_tabs else 1
        self.active_peer = all_tabs[(idx - 1) % len(all_tabs)]
        if self.active_peer != OWN_INBOX_ID:
            state.set_last_active_peer(self.active_peer)
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
            candidate_names = {p.name for p in store.acting_as_candidates()}
            target_acting = msg.to_peer if msg.to_peer in candidate_names else msg.from_peer
            other = msg.from_peer if target_acting == msg.to_peer else msg.to_peer
            if target_acting in candidate_names:
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

    def action_open_quarantine(self) -> None:
        if not self.acting_as:
            return
        from .quarantine import QuarantineScreen
        def after(_):
            self.action_refresh()
        self.app.push_screen(QuarantineScreen(self.acting_as), after)

    def action_toggle_archived(self) -> None:
        # Archived view only applies to the own-inbox tab (a sink peer seeing
        # its full received history). On a member-peer thread it's a no-op.
        from ..widgets.chat_stream import ChatStream
        if self.active_peer != OWN_INBOX_ID:
            self.notify("Archived view applies to your inbox tab (←/→ to it)",
                        severity="warning", timeout=3)
            return
        stream = self.query_one("#chat-stream", ChatStream)
        showing = stream.toggle_archived()
        self.notify(
            "📥 inbox: showing full history (incl. archived)" if showing
            else "📥 inbox: showing pending only",
            timeout=3,
        )

    def action_clear_inbox(self) -> None:
        # Archive the current peer's absorbed report-backlog (everything pending
        # in its inbox+delivered) → processed/. Recoverable, not deleted. Only on
        # the own-inbox tab. Role-aware: a CHILD inbox holds parent→child TASKS,
        # so clearing it is the dangerous direction — warn loudly.
        from ..widgets.confirm import ConfirmDelete
        if self.active_peer != OWN_INBOX_ID:
            self.notify("Clear-inbox applies to your 📥 inbox tab (←/→ to it)",
                        severity="warning", timeout=3)
            return
        if not self.acting_as:
            return
        ids = [m.id for m in store.list_inbox(self.acting_as)]  # inbox + delivered
        if not ids:
            self.notify("Inbox already clear — nothing to archive", timeout=3)
            return
        peers = {p.name: p for p in store.list_peers()}
        role = peers[self.acting_as].role if self.acting_as in peers else "parent"
        if role == "child":
            prompt = (f"⚠ {self.acting_as} is a CHILD — its inbox holds parent→child "
                      f"TASKS, not reports. Archiving {len(ids)} message(s) marks them "
                      f"consumed (may lose unstarted work). Continue?")
        else:
            prompt = (f"Archive {len(ids)} absorbed message(s) for {self.acting_as} "
                      f"→ processed/? Recoverable, not deleted.")

        def after(confirmed: bool) -> None:
            if not confirmed:
                return
            res = store.archive_messages(ids)
            ok = sum(1 for v in res.values() if v)
            self.notify(f"Archived {ok}/{len(ids)} → processed/", timeout=4)
            self._populate_acting_as()
            self.call_after_refresh(self._populate_tabs_and_refresh)

        self.app.push_screen(ConfirmDelete(prompt), after)

    def action_switch_acting_as(self) -> None:
        from ..widgets.switch_acting_as import SwitchActingAsModal
        def after(name):
            if name is None or name == self.acting_as:
                return
            self.acting_as = name
            state.set_last_acting_as(name)
            # Clear active_peer so _populate_tabs picks default for new group
            self.active_peer = None
            self._populate_acting_as()
            self.call_after_refresh(self._populate_tabs_and_refresh)
        self.app.push_screen(SwitchActingAsModal(self.acting_as), after)

    async def _populate_tabs_and_refresh(self) -> None:
        await self._populate_tabs()
        self._refresh_thread()

    async def on_store_changed(self, event) -> None:
        await self.action_refresh()
