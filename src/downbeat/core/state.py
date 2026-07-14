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


def get_last_seen_rebind_at() -> str | None:
    return _load().get("last_seen_rebind_at")


def set_last_seen_rebind_at(when: str | None) -> None:
    data = _load()
    if when is None:
        data.pop("last_seen_rebind_at", None)
    else:
        data["last_seen_rebind_at"] = when
    _save(data)


def get_watcher_heartbeat_at() -> str | None:
    """Global fact: is a TUI resident FsWatcher alive right now. Written by
    tui/app.py on mount and refreshed periodically; read by the headless
    relay-poll-offer.py hook (via its own self-contained duplicate of this
    file, not this function — see docs/superpowers/specs/
    2026-07-14-tui-hosted-relay-notify-design.md) to avoid double-firing a
    notification when a TUI is already watching."""
    return _load().get("watcher_heartbeat_at")


def set_watcher_heartbeat_at(when: str | None) -> None:
    data = _load()
    if when is None:
        data.pop("watcher_heartbeat_at", None)
    else:
        data["watcher_heartbeat_at"] = when
    _save(data)


def get_notify_last_sent(peer_name: str) -> str | None:
    """Per-recipient cooldown timestamp for the idle-recipient notify,
    shared by the TUI path (this function) and the headless hook's own
    duplicate implementation, so cooldown is coherent regardless of which
    path fired last."""
    return _load().get("notify_last_sent", {}).get(peer_name)


def set_notify_last_sent(peer_name: str, when: str) -> None:
    data = _load()
    sent = data.setdefault("notify_last_sent", {})
    sent[peer_name] = when
    _save(data)


def now_iso() -> str:
    from .models import now_iso as _ni
    return _ni()
