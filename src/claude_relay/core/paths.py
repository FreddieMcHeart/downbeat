"""Filesystem path constants for the relay store.

Override the relay root with the CLAUDE_RELAY_DIR environment variable
(used in tests so we don't touch the real ~/.claude/relay/).
"""
import os
from pathlib import Path

RELAY_DIR = Path(os.environ.get("CLAUDE_RELAY_DIR", str(Path.home() / ".claude" / "relay")))
INBOX_DIR = RELAY_DIR / "inbox"
PROCESSED_DIR = RELAY_DIR / "processed"
DELIVERED_DIR = RELAY_DIR / "delivered"
QUARANTINE_DIR = RELAY_DIR / "quarantine"
LOG_DIR = RELAY_DIR / "logs"
SESSIONS_FILE = RELAY_DIR / "sessions.json"
GROUPS_FILE = RELAY_DIR / "groups.json"
CONFIG_FILE = RELAY_DIR / "config.toml"
LOG_FILE = LOG_DIR / "claude-relay.log"
DELIVERY_LOG = RELAY_DIR / "delivery_log.jsonl"
REBIND_LOG = RELAY_DIR / "rebind_log.jsonl"


def ensure_dirs() -> None:
    """Create all relay subdirectories if they don't exist (idempotent)."""
    for d in (RELAY_DIR, INBOX_DIR, PROCESSED_DIR, DELIVERED_DIR,
              QUARANTINE_DIR, LOG_DIR):
        d.mkdir(parents=True, exist_ok=True)
