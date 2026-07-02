import logging

from downbeat.core import logging as relay_logging
from downbeat.core import paths


def test_setup_creates_log_file_and_logs_at_info(relay_dir):
    relay_logging.setup(level="INFO")
    log = logging.getLogger("downbeat.core")
    log.info("send peer=child msg=a1f2")
    # Flush handlers
    for h in logging.getLogger("downbeat").handlers:
        h.flush()
    contents = paths.LOG_FILE.read_text()
    assert "send peer=child msg=a1f2" in contents
    assert "[INFO ] downbeat.core" in contents


def test_setup_respects_debug_level(relay_dir):
    relay_logging.setup(level="DEBUG")
    log = logging.getLogger("downbeat.watcher")
    log.debug("fs event=created")
    for h in logging.getLogger("downbeat").handlers:
        h.flush()
    assert "fs event=created" in paths.LOG_FILE.read_text()


def test_setup_idempotent(relay_dir):
    relay_logging.setup(level="INFO")
    relay_logging.setup(level="INFO")
    handlers = logging.getLogger("downbeat").handlers
    assert len(handlers) == 1
