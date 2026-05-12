"""Modal editor for unread messages (and a programmatic perform_edit helper)."""
from __future__ import annotations

from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, TextArea

from ...core import store
from ...core.errors import MessageLocked


def perform_edit(msg_id: str, new_body: str | None = None,
                 new_subject: str | None = None) -> None:
    """Direct call into the store. Raises MessageLocked if past NEW state."""
    store.edit_message(msg_id, new_body=new_body, new_subject=new_subject)


class EditModal(ModalScreen):
    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, msg_id: str):
        super().__init__()
        self.msg_id = msg_id
        self._subj: Input | None = None
        self._body: TextArea | None = None

    def compose(self):
        msg = store.get_message(self.msg_id)
        with Vertical(classes="pane"):
            yield Label(f"Editing {self.msg_id}")
            self._subj = Input(value=msg.subject, id="edit-subj")
            yield self._subj
            self._body = TextArea(text=msg.body, id="edit-body")
            yield self._body
            yield Button("Save", id="edit-save", variant="primary")

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "edit-save":
            try:
                perform_edit(self.msg_id,
                             new_body=self._body.text,
                             new_subject=self._subj.value)
            except MessageLocked as e:
                self.notify(str(e), severity="error")
                return
            self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)
