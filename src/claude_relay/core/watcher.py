"""Filesystem watchers for the inbox.

Two implementations:
  - FsWatcher: uses watchdog (inotify/FSEvents) for sub-100ms updates.
  - PollWatcher: timer-based, used as fallback on filesystems where
    watchdog can't get reliable events (NFS, SMB)."""
from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Callable, Protocol

from . import paths

_log = logging.getLogger("claude_relay.watcher")


class Watcher(Protocol):
    def start(self) -> None: ...
    def stop(self) -> None: ...


class PollWatcher:
    def __init__(self, interval: float, on_change: Callable[[], None]):
        self._interval = interval
        self._on_change = on_change
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._snapshot: set[tuple[str, float]] = set()

    def _scan(self) -> set[tuple[str, float]]:
        snap: set[tuple[str, float]] = set()
        for base in (paths.INBOX_DIR, paths.PROCESSED_DIR):
            if not base.exists():
                continue
            for p in base.rglob("*.json"):
                try:
                    snap.add((str(p), p.stat().st_mtime))
                except FileNotFoundError:
                    continue
        return snap

    def _run(self):
        self._snapshot = self._scan()
        while not self._stop.wait(self._interval):
            current = self._scan()
            if current != self._snapshot:
                self._snapshot = current
                try:
                    self._on_change()
                except Exception:
                    _log.exception("on_change callback raised")

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        _log.debug("PollWatcher started interval=%s", self._interval)

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
        _log.debug("PollWatcher stopped")


class FsWatcher:
    def __init__(self, on_change: Callable[[], None]):
        from watchdog.events import FileSystemEventHandler
        from watchdog.observers import Observer

        self._on_change = on_change
        self._observer = Observer()
        self._handler_class = FileSystemEventHandler

        class _Handler(FileSystemEventHandler):
            def on_any_event(handler_self, event):
                if event.src_path.endswith(".json"):
                    try:
                        on_change()
                    except Exception:
                        _log.exception("on_change callback raised")

        self._handler = _Handler()

    def start(self) -> None:
        paths.ensure_dirs()
        self._observer.schedule(self._handler, str(paths.INBOX_DIR),
                                recursive=True)
        self._observer.schedule(self._handler, str(paths.PROCESSED_DIR),
                                recursive=True)
        self._observer.start()
        _log.debug("FsWatcher started")

    def stop(self) -> None:
        self._observer.stop()
        self._observer.join(timeout=2)
        _log.debug("FsWatcher stopped")


def make_watcher(on_change: Callable[[], None],
                 prefer: str = "auto",
                 poll_interval: float = 2.0) -> Watcher:
    """Return the best available watcher. prefer='auto' tries FsWatcher,
    falls back to PollWatcher on failure or when prefer='poll'."""
    if prefer == "poll":
        return PollWatcher(interval=poll_interval, on_change=on_change)
    try:
        return FsWatcher(on_change=on_change)
    except Exception as e:
        _log.warning("FsWatcher unavailable (%s); falling back to PollWatcher", e)
        return PollWatcher(interval=poll_interval, on_change=on_change)
