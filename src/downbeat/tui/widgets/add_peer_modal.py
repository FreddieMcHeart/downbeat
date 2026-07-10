"""Modal for registering a new peer."""
from __future__ import annotations

from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Label, Select, Static

from ...core import store
from ...core.errors import AmbiguousParent, InvalidParent


class AddPeerModal(ModalScreen):
    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, default_parent: str | None = None):
        super().__init__()
        self._default_parent = default_parent
        self._name: Input | None = None
        self._role: Select | None = None
        # Tracked via on_select_changed rather than read back from
        # self._role.value — Select's initial `value=` isn't guaranteed to
        # be committed synchronously by the time a fast programmatic
        # submit() runs.
        self._role_value: str = "child"
        # NOTE: do not name this `self._parent` — Widget already uses that
        # attribute internally for the DOM parent; clobbering it breaks
        # mount/attachment tracking with a confusing MountError.
        self._parent_input: Input | None = None
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
            self._parent_input = Input(
                placeholder="parent name (required for role=child if >1 parent exists)",
                value=self._default_parent or "",
                id="ap-parent",
            )
            yield self._parent_input
            self._session_id = Input(placeholder="session_id (optional)",
                                     id="ap-session")
            yield self._session_id
            self._cwd = Input(placeholder="cwd (optional, defaults to $PWD)",
                              id="ap-cwd")
            yield self._cwd
            yield Static("[dim]Press Enter in any field to register, Esc to cancel[/dim]")

    def on_select_changed(self, event: Select.Changed) -> None:
        # `Select.BLANK` is `False`, not the real "no selection" sentinel —
        # the actual blank value is `Select.NULL` (a NoSelection instance).
        if event.select is self._role and event.value is not Select.NULL:
            self._role_value = event.value

    def on_input_submitted(self, event) -> None:
        self.submit()

    def submit(self) -> None:
        import os
        name = self._name.value.strip()
        if not name:
            self.app.bell()
            self.notify("Name is required", severity="warning")
            return
        role = self._role_value
        parent = self._parent_input.value.strip() or None
        sid = self._session_id.value.strip() or f"manual-{os.getpid()}"
        cwd = self._cwd.value.strip() or os.getcwd()
        try:
            store.register_peer(name=name, session_id=sid, cwd=cwd, role=role, parent=parent)
        except (AmbiguousParent, InvalidParent) as e:
            self.app.bell()
            self.notify(str(e), severity="error")
            return
        self.dismiss(name)

    def action_cancel(self) -> None:
        self.dismiss(None)
