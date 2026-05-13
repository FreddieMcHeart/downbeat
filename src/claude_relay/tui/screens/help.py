"""F1 help: keybinding cheat sheet."""
from __future__ import annotations

from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Label

HELP_TEXT = """\
[b]claude-relay TUI — Chat view[/b]

[b]Navigation[/b]
  ↑/↓             move cursor through message bubbles
  Tab / Shift+Tab cycle peer tabs
  Click a tab     switch peer

[b]Compose[/b]
  Type in the bottom input, [b]Enter[/b] to send to active peer.

[b]Actions on focused bubble[/b]
  e               edit (only on your unread sent messages)
  d               delete (with confirm)
  v               toast full body of focused message
  Shift+B         broadcast status (when applicable)

[b]Peer management[/b]
  P  add peer    X  remove active peer    G  GC stale

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
