"""Modal for registering a new peer."""
from __future__ import annotations

from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Label, Select, Static

from ...core import store


class AddPeerModal(ModalScreen):
    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self):
        super().__init__()
        self._name: Input | None = None
        self._role: Select | None = None
        self._session_id: Input | None = None
        self._cwd: Input | None = None

    def compose(self):
        with Vertical(classes="pane"):
            yield Label("[b]Add peer[/b]")
            self._name = Input(placeholder="name (e.g. PLAT-3145-master)",
                               id="ap-name")
            yield self._name
            self._role = Select(
                [("parent", "parent"), ("child", "child")],
                prompt="role",
                value="child",
                id="ap-role",
            )
            yield self._role
            self._session_id = Input(placeholder="session_id (optional)",
                                     id="ap-session")
            yield self._session_id
            self._cwd = Input(placeholder="cwd (optional, defaults to $PWD)",
                              id="ap-cwd")
            yield self._cwd
            yield Static("[dim]Press Enter in any field to register, Esc to cancel[/dim]")

    def on_input_submitted(self, event) -> None:
        self.submit()

    def submit(self) -> None:
        import os
        name = self._name.value.strip()
        if not name:
            self.app.bell()
            self.notify("Name is required", severity="warning")
            return
        role = self._role.value if self._role.value != Select.BLANK else "child"
        sid = self._session_id.value.strip() or f"manual-{os.getpid()}"
        cwd = self._cwd.value.strip() or os.getcwd()
        store.register_peer(name=name, session_id=sid, cwd=cwd, role=role)
        self.dismiss(name)

    def action_cancel(self) -> None:
        self.dismiss(None)
