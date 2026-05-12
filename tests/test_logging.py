import logging

from claude_relay.core import logging as relay_logging
from claude_relay.core import paths


def test_setup_creates_log_file_and_logs_at_info(relay_dir):
    relay_logging.setup(level="INFO")
    log = logging.getLogger("claude_relay.core")
    log.info("send peer=child msg=a1f2")
    # Flush handlers
    for h in logging.getLogger("claude_relay").handlers:
        h.flush()
    contents = paths.LOG_FILE.read_text()
    assert "send peer=child msg=a1f2" in contents
    assert "[INFO ] claude_relay.core" in contents


def test_setup_respects_debug_level(relay_dir):
    relay_logging.setup(level="DEBUG")
    log = logging.getLogger("claude_relay.watcher")
    log.debug("fs event=created")
    for h in logging.getLogger("claude_relay").handlers:
        h.flush()
    assert "fs event=created" in paths.LOG_FILE.read_text()


def test_setup_idempotent(relay_dir):
    relay_logging.setup(level="INFO")
    relay_logging.setup(level="INFO")
    handlers = logging.getLogger("claude_relay").handlers
    assert len(handlers) == 1
