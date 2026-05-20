"""F1 help: keybinding cheat sheet."""
from __future__ import annotations

from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Label

HELP_TEXT = """\
[b]claude-relay TUI — Chat view[/b]

[b]Navigation[/b]
  Tab / Shift+Tab   cycle focus: Messages → Composer
  ← / →             prev / next group member
  ↑ / ↓             scroll within focused region (messages, composer)
  s                 switch acting-as parent
  Click a tab       switch peer

[b]Compose[/b]
  Enter           send to active peer
  Shift+Enter     newline in composer
  Ctrl+B          broadcast to all group children
  Ctrl+E          open $EDITOR on composer buffer

[b]Actions on focused bubble[/b]
  Enter           open focused message in detail view
                  (Edit / Reply / Delete / Broadcast status / Copy id)

[b]Peer management[/b]
  Ctrl+P          open Peers screen (add / remove / gc)

[b]System[/b]
  f               find message by id across all inboxes
  ? / F1          this help
  Ctrl+R          refresh
  Ctrl+L / F6     toggle log viewer
  q               quit

[b]Message detail — scroll[/b]
  ↑ / k           scroll up one line
  ↓ / j           scroll down one line
  Ctrl+B / PgUp   page up
  Ctrl+F / PgDn   page down
"""


class HelpScreen(ModalScreen):
    BINDINGS = [
        ("escape", "close", "Close"),
        ("question_mark,f1", "close", "Close"),
        ("q", "close", "Close"),
    ]

    def compose(self):
        with Vertical(classes="pane"):
            yield Label(HELP_TEXT)

    def action_close(self) -> None:
        self.dismiss(None)
