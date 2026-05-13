"""F1 help: keybinding cheat sheet."""
from __future__ import annotations

from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Label

HELP_TEXT = """\
[b]claude-relay TUI — Chat view[/b]

[b]Navigation[/b]
  Tab / Shift+Tab   cycle focus: Acting-as → Messages → Composer
  ← / →             prev / next peer tab
  ↑ / ↓             scroll within focused region (dropdown, messages, composer)
  Click a tab       switch peer

[b]Compose[/b]
  Enter           send to active peer
  Shift+Enter     newline in composer
  Ctrl+B          broadcast to all group children
  Ctrl+E          open $EDITOR on composer buffer

[b]Actions on focused bubble[/b]
  e               edit (only on your unread sent messages)
  d               delete (with confirm)
  v               toast full body of focused message
  Shift+B         broadcast status (when applicable)

[b]Peer management[/b]
  Ctrl+P          open Peers screen (add / remove / gc)

[b]System[/b]
  f               find message by id across all inboxes
  F1              this help
  F5              refresh
  F6              toggle log viewer
  q               quit
"""


class HelpScreen(ModalScreen):
    BINDINGS = [
        ("escape", "close", "Close"),
        ("f1", "close", "Close"),
        ("q", "close", "Close"),
    ]

    def compose(self):
        with Vertical(classes="pane"):
            yield Label(HELP_TEXT)

    def action_close(self) -> None:
        self.dismiss(None)
