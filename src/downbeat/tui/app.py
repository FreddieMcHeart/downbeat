"""RelayApp — root Textual application."""
from __future__ import annotations

import json
import logging

from textual.app import App

from ..core import logging as relay_logging
from ..core import store, watcher
from .messages import StoreChanged
from .screens.chat import ChatScreen


class RelayApp(App):
    CSS_PATH = "theme.tcss"
    TITLE = "downbeat"
    SUB_TITLE = "local relay TUI"
    ENABLE_COMMAND_PALETTE = False
    # Mouse / trackpad scroll is enabled by default; affirming here for clarity:
    # Textual's terminal layer emits mouse wheel as MouseScrollUp/MouseScrollDown.
    # Scroll-container widgets (VerticalScroll, RichLog, DataTable) handle them
    # natively when their content exceeds viewport.

    def __init__(self):
        super().__init__()
        self._watcher = None

    def on_mount(self) -> None:
        relay_logging.setup(level="INFO")
        try:
            counts = store.reconcile()
            if counts["quarantined"] > 0:
                logging.getLogger("downbeat.tui").warning(
                    "reconcile at startup: %s", counts
                )
        except Exception:
            logging.getLogger("downbeat.tui").exception("reconcile failed at startup")

        # Check for unseen rebind events and surface as toasts
        try:
            unseen = self._unseen_rebinds()
            if unseen:
                for event in unseen:
                    self.notify(
                        f"{event['peer']} rebound after /clear: "
                        f"session {event['old_session_id'][:8]}→"
                        f"{event['new_session_id'][:8]}",
                        timeout=5,
                    )
                self._mark_rebinds_seen()
        except Exception:
            logging.getLogger("downbeat.tui").exception("rebind notification failed")

        logging.getLogger("downbeat.tui").info("app mounted")
        self.push_screen(ChatScreen())
        self._watcher = watcher.make_watcher(
            on_change=lambda: self.call_from_thread(self._on_change)
        )
        self._watcher.start()

    def _unseen_rebinds(self) -> list[dict]:
        """Return rebind events newer than the last-seen timestamp in tui_state."""
        from ..core import paths, state
        if not paths.REBIND_LOG.exists():
            return []
        last_seen = state.get_last_seen_rebind_at()
        events: list[dict] = []
        with paths.REBIND_LOG.open() as f:
            for line in f:
                try:
                    event = json.loads(line)
                except Exception:
                    continue
                ts = event.get("at", "")
                if last_seen is None or ts > last_seen:
                    events.append(event)
        return events

    def _mark_rebinds_seen(self) -> None:
        from ..core import state
        state.set_last_seen_rebind_at(state.now_iso())

    def on_unmount(self) -> None:
        if self._watcher:
            self._watcher.stop()

    def _on_change(self) -> None:
        self.post_message(StoreChanged())
