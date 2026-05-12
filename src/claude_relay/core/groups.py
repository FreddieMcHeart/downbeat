"""Peer groups, stored alongside sessions.json as groups.json."""
from __future__ import annotations

import json
from pathlib import Path

from . import paths


def _load() -> dict[str, list[str]]:
    if not paths.GROUPS_FILE.exists():
        return {}
    return json.loads(paths.GROUPS_FILE.read_text() or "{}")


def _save(data: dict[str, list[str]]) -> None:
    paths.GROUPS_FILE.parent.mkdir(parents=True, exist_ok=True)
    paths.GROUPS_FILE.write_text(json.dumps(data, indent=2))


def list_groups() -> dict[str, list[str]]:
    return _load()


def save_group(name: str, members: list[str]) -> None:
    data = _load()
    data[name] = list(members)
    _save(data)


def get_group(name: str) -> list[str]:
    return _load().get(name, [])


def delete_group(name: str) -> None:
    data = _load()
    data.pop(name, None)
    _save(data)
