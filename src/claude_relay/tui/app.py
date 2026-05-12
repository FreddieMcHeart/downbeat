"""RelayApp — root Textual application."""
from __future__ import annotations

import logging
from textual.app import App

from ..core import logging as relay_logging
from .screens.main import MainScreen


class RelayApp(App):
    CSS_PATH = "theme.tcss"
    TITLE = "claude-relay"
    SUB_TITLE = "local relay TUI"

    def on_mount(self) -> None:
        relay_logging.setup(level="INFO")
        logging.getLogger("claude_relay.tui").info("app mounted")
        self.push_screen(MainScreen())
