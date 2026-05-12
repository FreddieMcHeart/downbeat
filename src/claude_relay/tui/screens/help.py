"""F1 help: keybinding cheat sheet."""
from __future__ import annotations

from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Label

HELP_TEXT = """\
[b]claude-relay TUI[/b]

[b]Navigation[/b]
  ↑/↓ or j/k        navigate within focused pane
  ←/→ or h/l        switch pane
  Enter             open / read message (marks read)

[b]Actions[/b]
  n                 new message
  r                 reply to selected
  e                 edit selected (only NEW)
  d                 delete (with confirm)
  b                 toggle broadcast in composer
  Shift+B           broadcast status for selected

[b]System[/b]
  /                 search
  F1                this help
  F5                refresh
  F6                toggle log viewer
  :                 command palette
  Ctrl+T            toggle dark/light theme
  q                 quit
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
