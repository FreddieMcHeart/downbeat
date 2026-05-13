"""Tab bar listing peers in the current group with unread badges."""
from __future__ import annotations

from textual.message import Message as TextualMessage
from textual.widgets import Tab, Tabs

from ...core import store


class PeerTabs(Tabs):
    class PeerSelected(TextualMessage):
        def __init__(self, peer_name: str):
            super().__init__()
            self.peer_name = peer_name

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._members: list[str] = []
        self._populating: bool = False

    async def populate(self, members: list[str]) -> None:
        """Replace tabs with new member set, preserving active when possible.

        Re-entrant calls while a populate is in progress are skipped to avoid
        DuplicateIds from concurrent watcher + callback refreshes.
        """
        if self._populating:
            return
        self._populating = True
        try:
            active_name = self._current_peer_name()
            await self.clear()
            self._members = list(members)
            for name in members:
                unread = len([m for m in store.list_inbox(name)
                              if m.state.value == "new"])
                label = name if unread == 0 else f"{name}  ●{unread}"
                await self.add_tab(Tab(label, id=f"tab-{self._safe_id(name)}"))
            if active_name and active_name in members:
                self.active = f"tab-{self._safe_id(active_name)}"
            elif members:
                self.active = f"tab-{self._safe_id(members[0])}"
        finally:
            self._populating = False

    def _safe_id(self, name: str) -> str:
        return name.replace("-", "_").replace(".", "_")

    def _current_peer_name(self) -> str | None:
        if not self.active or not self._members:
            return None
        for name in self._members:
            if f"tab-{self._safe_id(name)}" == self.active:
                return name
        return None

    def on_tabs_tab_activated(self, event: Tabs.TabActivated) -> None:
        name = self._current_peer_name()
        if name:
            self.post_message(self.PeerSelected(name))
