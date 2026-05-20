"""Persisted session state for the TUI (last-used acting-as, active peer).

Stored separately from sessions.json (peer registry) because state is
ephemeral session memory, not user-managed peer config."""
from __future__ import annotations

import json
from typing import Any

from . import paths
from .store import _atomic_write_text

_STATE_FILE = paths.RELAY_DIR / "tui_state.json"


def _load() -> dict[str, Any]:
    if not _STATE_FILE.exists():
        return {}
    try:
        return json.loads(_STATE_FILE.read_text() or "{}")
    except json.JSONDecodeError:
        return {}


def _save(data: dict[str, Any]) -> None:
    _atomic_write_text(_STATE_FILE, json.dumps(data, indent=2))


def get_last_acting_as() -> str | None:
    return _load().get("last_acting_as")


def set_last_acting_as(name: str | None) -> None:
    data = _load()
    if name is None:
        data.pop("last_acting_as", None)
    else:
        data["last_acting_as"] = name
    _save(data)


def get_last_active_peer() -> str | None:
    return _load().get("last_active_peer")


def set_last_active_peer(name: str | None) -> None:
    data = _load()
    if name is None:
        data.pop("last_active_peer", None)
    else:
        data["last_active_peer"] = name
    _save(data)
