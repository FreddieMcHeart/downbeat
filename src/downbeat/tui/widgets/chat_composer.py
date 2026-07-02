"""Multi-line composer pinned to the bottom of the chat view.

- Enter (no shift) sends the message.
- Shift+Enter inserts a newline.
- Ctrl+E opens $EDITOR on a tempfile, reads result back when the editor exits.
- Ctrl+B broadcasts the message to all group children.
"""
from __future__ import annotations

import os
import subprocess
import tempfile

from textual.message import Message as TextualMessage
from textual.widgets import TextArea


class ChatComposer(TextArea):
    DEFAULT_CSS = """
    ChatComposer {
        dock: bottom;
        height: 5;
        border: solid $primary;
    }
    """

    class Send(TextualMessage):
        def __init__(self, text: str):
            super().__init__()
            self.text = text

    class Broadcast(TextualMessage):
        def __init__(self, text: str):
            super().__init__()
            self.text = text

    def __init__(self, **kwargs):
        super().__init__(
            text="",
            soft_wrap=True,
            show_line_numbers=False,
            **kwargs,
        )

    def on_key(self, event) -> None:
        # Enter without shift => send. Shift+Enter falls through to default
        # (which inserts a newline). Ctrl+E opens external editor. Ctrl+B broadcasts.
        if event.key == "enter":
            self._send()
            event.stop()
            event.prevent_default()
            return
        if event.key == "ctrl+e":
            self._open_external_editor()
            event.stop()
            event.prevent_default()
            return
        if event.key == "ctrl+b":
            self._send_broadcast()
            event.stop()
            event.prevent_default()
            return
        # Default TextArea behavior (shift+enter goes here — inserts a newline)

    def _send(self) -> None:
        text = self.text.strip()
        if not text:
            return
        self.text = ""
        self.post_message(self.Send(text))

    def _send_broadcast(self) -> None:
        text = self.text.strip()
        if not text:
            return
        self.text = ""
        self.post_message(self.Broadcast(text))

    def _open_external_editor(self) -> None:
        if not hasattr(self.app, "suspend"):
            self.app.notify("External editor not supported in this Textual version",
                            severity="warning")
            return
        editor = os.environ.get("EDITOR", "nano")
        # Write current buffer to a tempfile so the user picks up where they were
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False,
                                         encoding="utf-8") as fh:
            fh.write(self.text)
            path = fh.name
        try:
            # The TUI app needs to suspend so the editor takes over the terminal.
            with self.app.suspend():
                subprocess.run([editor, path], check=False)
            with open(path, encoding="utf-8") as fh:
                new_text = fh.read()
            self.text = new_text.rstrip("\n")
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass
