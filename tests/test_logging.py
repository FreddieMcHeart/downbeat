import logging
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


def test_log_timestamps_are_utc_not_local(relay_dir):
    """The format appends a literal 'Z' (UTC); the timestamp must actually be
    UTC, not local time wearing a UTC label. Regression for #30."""
    import os
    import time

    epoch = 1_700_000_000  # 2023-11-14T22:13:20Z
    old_tz = os.environ.get("TZ")
    os.environ["TZ"] = "America/New_York"  # never equal to UTC
    time.tzset()
    try:
        relay_logging.setup(level="INFO")
        handler = next(
            h for h in logging.getLogger("downbeat").handlers
            if isinstance(h, RotatingFileHandler)
        )
        record = logging.LogRecord(
            "downbeat.core", logging.INFO, __file__, 1, "msg", None, None
        )
        record.created = epoch
        rendered = handler.formatter.format(record)
        expected_utc = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(epoch)) + "Z"
        local_wrong = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(epoch)) + "Z"
        assert local_wrong != expected_utc, "TZ not applied — test is not meaningful"
        assert expected_utc in rendered, f"{expected_utc!r} not in {rendered!r}"
    finally:
        if old_tz is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = old_tz
        time.tzset()


def test_setup_idempotent(relay_dir):
    relay_logging.setup(level="INFO")
    relay_logging.setup(level="INFO")
    # setup()'s idempotency contract only covers the RotatingFileHandler it
    # manages (see logging.py) — pytest's own log-capture handlers can also
    # be attached to this logger by unrelated tests and aren't setup()'s to
    # clean up.
    handlers = [
        h for h in logging.getLogger("downbeat").handlers
        if isinstance(h, RotatingFileHandler)
    ]
    assert len(handlers) == 1
