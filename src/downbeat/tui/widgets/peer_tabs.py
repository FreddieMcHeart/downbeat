"""Tab bar listing peers in the current group with unread badges."""
from __future__ import annotations

import re

from textual.css.query import NoMatches
from textual.message import Message as TextualMessage
from textual.widgets import Tab, Tabs

from ...core import store

# Sentinel id for the synthetic "own inbox" tab.  Imported by chat.py and
# chat_stream.py — defined here (peer_tabs) to avoid circular imports.
OWN_INBOX_ID = "__own_inbox__"
OWN_INBOX_LABEL = "📥 inbox"


class PeerTabs(Tabs):
    class PeerSelected(TextualMessage):
        def __init__(self, peer_name: str):
            super().__init__()
            self.peer_name = peer_name

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._members: list[str] = []
        self._populating: bool = False
        self.can_focus = False
        self.can_focus_children = False

    async def populate(self, members: list[str], acting_as: str | None = None) -> None:
        """Replace tabs with new member set, preserving active when possible.

        Always prepends an own-inbox tab (OWN_INBOX_ID) before member tabs so
        that standalone/sink peers with no group members can still read their
        inbox.

        Re-entrant calls while a populate is in progress are skipped to avoid
        DuplicateIds from concurrent watcher + callback refreshes.
        """
        if self._populating:
            return
        self._populating = True
        try:
            new_members = [OWN_INBOX_ID] + list(members)
            # Membership unchanged: update labels on the EXISTING Tab
            # widgets in place, no clear()/add_tab(). A watcher-driven
            # refresh from a new message never adds or removes a peer, so
            # this is the overwhelmingly common call -- and clear()+add_tab
            # (mount, then Textual's own add_tab->refresh_active setting
            # .active once the mount completes) is exactly the sequence
            # whose timing produced a ValueError: No Tab with id '...'
            # under real, uncontrolled cross-thread scheduling (#118,
            # established: not reproducible via same-thread scheduling of
            # any shape tried, only via the real watcher; root Textual-
            # internal mechanism not established, only the trigger shape).
            # This does not narrow that window, it removes the only path
            # into it for this case -- clear()/add_tab() are simply never
            # called, so the race cannot occur here regardless of timing.
            # The window still exists when membership genuinely changes;
            # that residual case is Textual's own clear()/add_tab()
            # sequencing, not addressed here.
            if new_members == self._members and self.tab_count == len(new_members):
                self._relabel(OWN_INBOX_ID,
                              self._inbox_label(acting_as))
                for name in members:
                    self._relabel(name, self._member_label(name))
                return
            active_name = self._current_peer_name()
            await self.clear()
            # _members tracks own-inbox sentinel + real members for _current_peer_name
            self._members = new_members

            # --- Own-inbox tab (always first) ---
            await self.add_tab(Tab(self._inbox_label(acting_as),
                                    id=f"tab-{self._safe_id(OWN_INBOX_ID)}"))

            # --- Member tabs ---
            for name in members:
                await self.add_tab(Tab(self._member_label(name),
                                        id=f"tab-{self._safe_id(name)}"))

            # Restore previously active tab if still present; else own-inbox.
            if active_name and active_name in self._members:
                self.active = f"tab-{self._safe_id(active_name)}"
            else:
                self.active = f"tab-{self._safe_id(OWN_INBOX_ID)}"
        finally:
            self._populating = False

    def _inbox_label(self, acting_as: str | None) -> str:
        inbox_unread = 0
        if acting_as:
            inbox_unread, _ = store.inbox_summary(acting_as)
        return (OWN_INBOX_LABEL if inbox_unread == 0
                else f"{OWN_INBOX_LABEL}  ●{inbox_unread}")

    def _member_label(self, name: str) -> str:
        unread, _ = store.inbox_summary(name)
        return name if unread == 0 else f"{name}  ●{unread}"

    def _relabel(self, name: str, label: str) -> None:
        tab_id = f"tab-{self._safe_id(name)}"
        try:
            tab = self.query_one(f"#tabs-list > #{tab_id}", Tab)
        except NoMatches:
            return
        tab.label = label

    def _safe_id(self, name: str) -> str:
        # Textual widget ids allow only letters, numbers, underscores, hyphens.
        # Peer names are free-form (spaces, dots, emoji, etc.) so anything
        # outside that set must be sanitized, not just the historically-seen "-"/".".
        return re.sub(r"[^A-Za-z0-9_-]", "_", name)

    def _current_peer_name(self) -> str | None:
        if not self.active or not self._members:
            return None
        for name in self._members:
            if f"tab-{self._safe_id(name)}" == self.active:
                return name
        return None

    def on_tabs_tab_activated(self, event: Tabs.TabActivated) -> None:
        # populate() rebuilds the tab set (clear + re-add), and Textual
        # auto-activates the first tab added -- own-inbox -- before we restore
        # the tab the user was actually on. Those activations are rebuild
        # churn, not a user selection: reporting them phantom-switches the
        # screen's peer (UM -> own-inbox -> UM on a single refresh), which
        # emptied the thread. See #16. populate() owns the active tab while
        # it runs; the screen's own _populate_tabs() reconciles active_peer.
        if self._populating:
            return
        name = self._current_peer_name()
        if name:
            self.post_message(self.PeerSelected(name))
