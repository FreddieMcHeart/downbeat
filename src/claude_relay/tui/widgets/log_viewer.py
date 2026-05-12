"""F6 pane: live tail of the rotating log file + inline grep filter."""
from __future__ import annotations

import asyncio
from pathlib import Path

from textual.containers import Vertical
from textual.widgets import Input, RichLog

from ...core import paths


class LogViewer(Vertical):
    DEFAULT_CSS = """
    LogViewer { height: 12; display: none; }
    LogViewer.-visible { display: block; }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._log = RichLog(highlight=True, markup=False, id="log-rich")
        self._grep = Input(placeholder="grep…", id="log-grep")
        self._task: asyncio.Task | None = None
        self._pos: int = 0

    def compose(self):
        yield self._grep
        yield self._log

    def toggle(self) -> None:
        if self.has_class("-visible"):
            self.remove_class("-visible")
            if self._task:
                self._task.cancel()
                self._task = None
        else:
            self.add_class("-visible")
            self._task = asyncio.create_task(self._tail())

    async def _tail(self) -> None:
        path = paths.LOG_FILE
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch(exist_ok=True)
        self._pos = path.stat().st_size
        try:
            while True:
                await asyncio.sleep(0.5)
                if not path.exists():
                    continue
                size = path.stat().st_size
                if size < self._pos:
                    # File was rotated
                    self._pos = 0
                if size > self._pos:
                    with path.open("r") as f:
                        f.seek(self._pos)
                        chunk = f.read()
                        self._pos = f.tell()
                    needle = self._grep.value.strip()
                    for line in chunk.splitlines():
                        if not needle or needle in line:
                            self._log.write(line)
        except asyncio.CancelledError:
            return
