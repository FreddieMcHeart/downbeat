"""Modal composer for new messages, replies, and broadcasts."""
from __future__ import annotations

from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static, TextArea

from ...core import store
from ...core.errors import PeerNotFound


class Composer(ModalScreen):
    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, sender: str, reply_to: str | None = None,
                 prefill_to: str | None = None):
        super().__init__()
        self.sender = sender
        self.reply_to = reply_to
        self.prefill_to = prefill_to or ""
        self.to_field: str = self.prefill_to
        self.subject_field: str = ""
        self.body_field: str = ""
        self.broadcast: bool = False
        self._to_input: Input | None = None
        self._subj_input: Input | None = None
        self._body_input: TextArea | None = None
        self._broadcast_label: Static | None = None

    def compose(self):
        with Vertical(classes="pane"):
            yield Label(f"From: {self.sender}")
            self._to_input = Input(value=self.to_field,
                                   placeholder="to (comma-separated for broadcast)",
                                   id="composer-to")
            yield self._to_input
            self._subj_input = Input(placeholder="subject", id="composer-subj")
            yield self._subj_input
            self._body_input = TextArea(text="", id="composer-body")
            yield self._body_input
            self._broadcast_label = Static(self._broadcast_text(),
                                           id="composer-bcast")
            yield self._broadcast_label
            yield Button("Send", id="composer-send", variant="primary")

    def _broadcast_text(self) -> str:
        return ("[b]broadcast: ON[/b]  (b to toggle)" if self.broadcast
                else "broadcast: off  (b to toggle)")

    def on_key(self, event) -> None:
        if event.key == "b" and not isinstance(self.focused, (Input, TextArea)):
            self.broadcast = not self.broadcast
            self._broadcast_label.update(self._broadcast_text())
            event.stop()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "composer-send":
            # Pull current values from widgets
            self.to_field = self._to_input.value
            self.subject_field = self._subj_input.value
            self.body_field = self._body_input.text
            self.submit()

    def submit(self) -> None:
        targets = [t.strip() for t in self.to_field.split(",") if t.strip()]
        if not targets:
            self.app.bell()
            return
        try:
            if self.broadcast or len(targets) > 1:
                store.broadcast(from_peer=self.sender, to_peers=targets,
                                subject=self.subject_field, body=self.body_field)
            elif self.reply_to:
                store.reply_to(self.reply_to, body=self.body_field,
                               from_peer=self.sender)
            else:
                store.send_message(from_peer=self.sender, to_peer=targets[0],
                                   subject=self.subject_field,
                                   body=self.body_field)
        except PeerNotFound as e:
            self.app.bell()
            self.notify(f"Unknown peer: {e}", severity="error")
            return
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)
