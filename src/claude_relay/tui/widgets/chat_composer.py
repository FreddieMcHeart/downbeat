"""Single-line composer pinned to the bottom of the chat view."""
from __future__ import annotations

from textual.message import Message as TextualMessage
from textual.widgets import Input


class ChatComposer(Input):
    DEFAULT_CSS = """
    ChatComposer { dock: bottom; height: 3; }
    """

    class Send(TextualMessage):
        def __init__(self, text: str):
            super().__init__()
            self.text = text

    def __init__(self, **kwargs):
        super().__init__(placeholder="message…  (Enter to send)", **kwargs)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = self.value.strip()
        if not text:
            return
        self.value = ""
        self.post_message(self.Send(text))
