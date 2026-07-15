"""Tab bar listing peers in the current group with unread badges."""
from __future__ import annotations

import re

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
            active_name = self._current_peer_name()
            await self.clear()
            # _members tracks own-inbox sentinel + real members for _current_peer_name
            self._members = [OWN_INBOX_ID] + list(members)

            # --- Own-inbox tab (always first) ---
            inbox_unread = 0
            if acting_as:
                inbox_unread = len([
                    m for m in store.list_inbox(acting_as)
                    if m.state.value == "new"
                ])
            inbox_label = (
                OWN_INBOX_LABEL if inbox_unread == 0
                else f"{OWN_INBOX_LABEL}  ●{inbox_unread}"
            )
            await self.add_tab(Tab(inbox_label, id=f"tab-{self._safe_id(OWN_INBOX_ID)}"))

            # --- Member tabs ---
            for name in members:
                unread = len([m for m in store.list_inbox(name)
                              if m.state.value == "new"])
                label = name if unread == 0 else f"{name}  ●{unread}"
                await self.add_tab(Tab(label, id=f"tab-{self._safe_id(name)}"))

            # Restore previously active tab if still present; else own-inbox.
            if active_name and active_name in self._members:
                self.active = f"tab-{self._safe_id(active_name)}"
            else:
                self.active = f"tab-{self._safe_id(OWN_INBOX_ID)}"
        finally:
            self._populating = False

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
