"""Single-key y/n confirm modal + programmatic perform_delete helper."""
from __future__ import annotations

from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Label

from ...core import store


def perform_delete(msg_id: str) -> None:
    store.delete_message(msg_id)


class ConfirmDelete(ModalScreen):
    BINDINGS = [
        ("y", "confirm", "Yes"),
        ("n", "cancel", "No"),
        ("escape", "cancel", "Cancel"),
    ]

    def __init__(self, prompt: str):
        super().__init__()
        self.prompt = prompt

    def compose(self):
        with Vertical(classes="pane"):
            yield Label(self.prompt)
            yield Label("[y]es / [n]o")

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)
