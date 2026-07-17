import logging
import re
import time
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler

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
    # setup()'s idempotency contract only covers the RotatingFileHandler it
    # manages (see logging.py) — pytest's own log-capture handlers can also
    # be attached to this logger by unrelated tests and aren't setup()'s to
    # clean up.
    handlers = [
        h for h in logging.getLogger("downbeat").handlers if isinstance(h, RotatingFileHandler)
    ]
    assert len(handlers) == 1


def test_log_timestamps_use_utc_with_z_suffix(relay_dir):
    """%(asctime)sZ must be UTC, not local time with a literal Z (#30)."""
    relay_logging.setup(level="INFO")
    handlers = [
        h for h in logging.getLogger("downbeat").handlers if isinstance(h, RotatingFileHandler)
    ]
    assert len(handlers) == 1
    formatter = handlers[0].formatter
    assert formatter is not None
    assert formatter.converter is time.gmtime

    before = datetime.now(UTC).replace(microsecond=0)
    log = logging.getLogger("downbeat.core")
    log.info("utc-stamp-probe")
    for h in handlers:
        h.flush()
    after = datetime.now(UTC).replace(microsecond=0)

    contents = paths.LOG_FILE.read_text()
    match = re.search(
        r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})Z \[INFO \] downbeat\.core\s+utc-stamp-probe",
        contents,
    )
    assert match, contents
    stamped = datetime.strptime(match.group(1), "%Y-%m-%dT%H:%M:%S").replace(tzinfo=UTC)
    assert before <= stamped <= after
