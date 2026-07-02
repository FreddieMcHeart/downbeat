"""Modal to rebind a peer's session_id."""
from __future__ import annotations

from rich.markup import escape as _rich_escape
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label

from ...core import session, store


class RebindSessionModal(ModalScreen):
    BINDINGS = [
        ("escape", "cancel", "Cancel"),
    ]

    def __init__(self, peer_name: str):
        super().__init__()
        self.peer_name = peer_name
        self._input: Input | None = None

    def compose(self):
        with Vertical(classes="pane"):
            yield Label(f"[b]Rebind session_id for {_rich_escape(self.peer_name)}[/b]")
            yield Label(
                "[dim]Paste the new session_id, or leave blank to auto-detect "
                "(only works when this TUI runs inside the target Claude Code "
                "session — usually it doesn't, so paste explicitly).[/dim]"
            )
            # Pre-fill with auto-detected value if available
            auto = session.detect_session_id() or ""
            self._input = Input(value=auto,
                                placeholder="new session_id (UUID)",
                                id="rebind-sid")
            yield self._input
            yield Button("Rebind", id="rebind-submit", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "rebind-submit":
            self._submit()

    def _submit(self) -> None:
        sid = self._input.value.strip() or None
        try:
            peer = store.rebind_session(self.peer_name, sid)
        except Exception as e:
            self.notify(f"Rebind failed: {e}", severity="error", timeout=5)
            return
        self.dismiss(peer.name)

    def action_cancel(self) -> None:
        self.dismiss(None)
