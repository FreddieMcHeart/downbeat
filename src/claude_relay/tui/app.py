"""RelayApp — root Textual application."""
from __future__ import annotations

import logging
from textual.app import App

from ..core import logging as relay_logging
from ..core import watcher
from .messages import StoreChanged
from .screens.main import MainScreen


class RelayApp(App):
    CSS_PATH = "theme.tcss"
    TITLE = "claude-relay"
    SUB_TITLE = "local relay TUI"

    def __init__(self):
        super().__init__()
        self._watcher = None

    def on_mount(self) -> None:
        relay_logging.setup(level="INFO")
        logging.getLogger("claude_relay.tui").info("app mounted")
        self.push_screen(MainScreen())
        self._watcher = watcher.make_watcher(
            on_change=lambda: self.call_from_thread(self._on_change)
        )
        self._watcher.start()

    def on_unmount(self) -> None:
        if self._watcher:
            self._watcher.stop()

    def _on_change(self) -> None:
        self.post_message(StoreChanged())
