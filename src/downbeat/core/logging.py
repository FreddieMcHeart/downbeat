"""Centralized logging config for downbeat.

Three loggers — downbeat.core, downbeat.tui, downbeat.watcher —
all attach to a single rotating handler on ~/.claude/relay/logs/downbeat.log."""
from __future__ import annotations

import logging
import time
from logging.handlers import RotatingFileHandler

from . import paths

_FORMAT = "%(asctime)sZ [%(levelname)-5s] %(name)-22s %(message)s"
_DATEFMT = "%Y-%m-%dT%H:%M:%S"
_ROOT_LOGGER = "downbeat"


def setup(level: str = "INFO") -> None:
    """Configure rotating handler on the package root logger.

    Idempotent: repeated calls do not add duplicate handlers.
    When the log path changes (e.g. in tests), old handlers are replaced."""
    from pathlib import Path

    paths.ensure_dirs()
    root = logging.getLogger(_ROOT_LOGGER)
    root.setLevel(level)
    target = Path(paths.LOG_FILE)
    # Check if already configured for this exact path
    for h in root.handlers:
        if isinstance(h, RotatingFileHandler) and Path(h.baseFilename) == target:
            return
    # Remove stale RotatingFileHandlers (e.g. from a previous relay_dir)
    for h in list(root.handlers):
        if isinstance(h, RotatingFileHandler):
            h.close()
            root.removeHandler(h)
    handler = RotatingFileHandler(
        target, maxBytes=1_048_576, backupCount=7, encoding="utf-8"
    )
    formatter = logging.Formatter(_FORMAT, datefmt=_DATEFMT)
    formatter.converter = time.gmtime
    handler.setFormatter(formatter)
    root.addHandler(handler)
    root.propagate = False