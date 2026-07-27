"""Tests for message-store schema versioning (issue #42).

Two halves of the mechanism, tested separately because either can regress
alone: tolerant-read (a v0 file upgrades through the ladder) and
stamp-on-write (the upgraded shape is what lands back on disk).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


def _peers(store, *names):
    for n in names:
        store.register_peer(name=n, session_id=f"s-{n}", cwd="/tmp", role="parent")


def _v0_dict(msg) -> dict:
    """Exactly what main produced before this change: the current wire shape
    with no schema_version key at all."""
    d = msg.to_dict()
    d.pop("schema_version", None)
    return d


def _write_v0_file(base_dir, peer: str, msg) -> Path:
    """Drop a real v0 JSON file into base_dir/peer/<id>.json."""
    target = base_dir / peer / f"{msg.id}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(_v0_dict(msg), indent=2))
    return target


# ── the model layer: ladder + stamping ───────────────────────────────────────

def test_new_message_carries_current_schema_version(relay_dir):
    from downbeat.core import store
    from downbeat.core.models import CURRENT_SCHEMA_VERSION
    _peers(store, "p", "c")
    msg = store.send_message(from_peer="p", to_peer="c", subject="s", body="b")

    assert msg.schema_version == CURRENT_SCHEMA_VERSION
    on_disk = json.loads((relay_dir / "inbox" / "c" / f"{msg.id}.json").read_text())
    assert on_disk["schema_version"] == CURRENT_SCHEMA_VERSION


def test_round_trip_through_dict_is_lossless(relay_dir):
    from downbeat.core import store
    from downbeat.core.models import Message
    _peers(store, "p", "c")
    msg = store.send_message(from_peer="p", to_peer="c", subject="s", body="b")

    assert Message.from_dict(msg.to_dict()) == msg


def test_v0_dict_upgrades_to_current_version(relay_dir):
    from downbeat.core import store
    from downbeat.core.models import CURRENT_SCHEMA_VERSION, Message
    _peers(store, "p", "c")
    msg = store.send_message(from_peer="p", to_peer="c", subject="s", body="b")

    upgraded = Message.from_dict(_v0_dict(msg))

    assert upgraded.schema_version == CURRENT_SCHEMA_VERSION
    assert upgraded == msg  # every other field survived the ladder


def test_schema_version_newer_than_supported_is_refused(relay_dir):
    """Silently downgrading a file a newer downbeat wrote would strip fields
    this version does not know about."""
    from downbeat.core import store
    from downbeat.core.models import CURRENT_SCHEMA_VERSION, Message
    _peers(store, "p", "c")
    msg = store.send_message(from_peer="p", to_peer="c", subject="s", body="b")
    d = msg.to_dict()
    d["schema_version"] = CURRENT_SCHEMA_VERSION + 1

    with pytest.raises(KeyError):
        Message.from_dict(d)


# ── the store choke points: real files, real _read_message_at ────────────────

def test_v0_file_on_disk_reads_without_corruption(relay_dir):
    from downbeat.core import paths, store
    from downbeat.core.models import CURRENT_SCHEMA_VERSION
    _peers(store, "p", "c")
    msg = store.send_message(from_peer="p", to_peer="c", subject="hello",
                             body="world")
    path = _write_v0_file(paths.INBOX_DIR, "c", msg)

    loaded = store._read_message_at(path)

    assert loaded.schema_version == CURRENT_SCHEMA_VERSION
    assert loaded.subject == "hello"
    assert loaded.body == "world"
    assert loaded.id == msg.id


def test_v0_file_self_heals_on_next_write(relay_dir):
    """Upgrade-on-read is only half the mechanism — the upgraded shape has to
    land back on disk."""
    from downbeat.core import paths, store
    from downbeat.core.models import CURRENT_SCHEMA_VERSION
    _peers(store, "p", "c")
    msg = store.send_message(from_peer="p", to_peer="c", subject="s", body="b")
    path = _write_v0_file(paths.INBOX_DIR, "c", msg)
    assert "schema_version" not in json.loads(path.read_text())

    store._write_message(store._read_message_at(path))

    raw = json.loads(path.read_text())  # raw JSON, not through the model
    assert raw["schema_version"] == CURRENT_SCHEMA_VERSION


def test_malformed_file_still_raises_store_corrupt(relay_dir):
    """The ladder must not swallow the existing corruption detection."""
    from downbeat.core import paths, store
    from downbeat.core.errors import StoreCorrupt
    _peers(store, "p", "c")
    bad = paths.INBOX_DIR / "c" / "broken.json"
    bad.parent.mkdir(parents=True, exist_ok=True)
    bad.write_text('{"id": "abc"}')  # no from/to

    with pytest.raises(StoreCorrupt):
        store._read_message_at(bad)


def test_invalid_json_still_raises_store_corrupt(relay_dir):
    from downbeat.core import paths, store
    from downbeat.core.errors import StoreCorrupt
    _peers(store, "p", "c")
    bad = paths.INBOX_DIR / "c" / "broken.json"
    bad.parent.mkdir(parents=True, exist_ok=True)
    bad.write_text("not json at all")

    with pytest.raises(StoreCorrupt):
        store._read_message_at(bad)


# ── migrate_store: the eager flush across all four directories ───────────────

def _seed_v0_across_dirs(relay_dir, store):
    """One v0 file in each of the four message directories."""
    from downbeat.core import paths
    msgs = []
    for base in (paths.INBOX_DIR, paths.DELIVERED_DIR,
                 paths.PROCESSED_DIR, paths.QUARANTINE_DIR):
        m = store.send_message(from_peer="p", to_peer="c",
                               subject=base.name, body="x")
        # send_message already wrote a current-version file into inbox/;
        # remove it so only the v0 copy under `base` remains.
        (paths.INBOX_DIR / "c" / f"{m.id}.json").unlink()
        _write_v0_file(base, "c", m)
        msgs.append(m)
    return msgs


def test_migrate_store_upgrades_every_directory(relay_dir):
    from downbeat.core import paths, store
    from downbeat.core.models import CURRENT_SCHEMA_VERSION
    _peers(store, "p", "c")
    _seed_v0_across_dirs(relay_dir, store)

    counts = store.migrate_store()

    assert counts["migrated"] == 4
    assert counts["current"] == 0
    assert counts["unreadable"] == 0
    for base in (paths.INBOX_DIR, paths.DELIVERED_DIR,
                 paths.PROCESSED_DIR, paths.QUARANTINE_DIR):
        for p in base.glob("*/*.json"):
            assert json.loads(p.read_text())["schema_version"] == \
                CURRENT_SCHEMA_VERSION


def test_migrate_store_counts_already_current_files_separately(relay_dir):
    from downbeat.core import store
    _peers(store, "p", "c")
    store.send_message(from_peer="p", to_peer="c", subject="s", body="b")

    counts = store.migrate_store()

    assert counts["migrated"] == 0
    assert counts["current"] == 1


def test_migrate_store_dry_run_writes_nothing(relay_dir):
    from downbeat.core import paths, store
    _peers(store, "p", "c")
    _seed_v0_across_dirs(relay_dir, store)
    before = {p: p.read_text()
              for p in paths.RELAY_DIR.glob("*/*/*.json")}

    counts = store.migrate_store(dry_run=True)

    assert counts["migrated"] == 4
    for p, text in before.items():
        assert p.read_text() == text, f"{p} was modified during a dry run"


def test_migrate_store_reports_unreadable_without_touching_it(relay_dir):
    from downbeat.core import paths, store
    _peers(store, "p", "c")
    bad = paths.INBOX_DIR / "c" / "broken.json"
    bad.parent.mkdir(parents=True, exist_ok=True)
    bad.write_text('{"id": "abc"}')

    counts = store.migrate_store()

    assert counts["unreadable"] == 1
    assert counts["migrated"] == 0
    assert json.loads(bad.read_text()) == {"id": "abc"}


def test_migrate_store_on_empty_relay_returns_zeros(relay_dir):
    from downbeat.core import store

    counts = store.migrate_store()

    assert counts == {"scanned": 0, "migrated": 0, "current": 0,
                      "unreadable": 0, "ids_backfilled": 0}


# ── CLI ──────────────────────────────────────────────────────────────────────

def test_cli_migrate_reports_counts(relay_dir, capsys, monkeypatch):
    from downbeat.cli.__main__ import main
    from downbeat.core import store
    _peers(store, "p", "c")
    _seed_v0_across_dirs(relay_dir, store)
    monkeypatch.setattr(sys, "argv", ["downbeat", "migrate"])

    rc = main()

    assert rc == 0
    assert "migrated 4" in capsys.readouterr().out


def test_cli_migrate_dry_run_says_nothing_was_written(relay_dir, capsys,
                                                      monkeypatch):
    from downbeat.cli.__main__ import main
    from downbeat.core import paths, store
    _peers(store, "p", "c")
    _seed_v0_across_dirs(relay_dir, store)
    before = {p: p.read_text() for p in paths.RELAY_DIR.glob("*/*/*.json")}
    monkeypatch.setattr(sys, "argv", ["downbeat", "migrate", "--dry-run"])

    rc = main()

    out = capsys.readouterr().out
    assert rc == 0
    assert "dry run" in out
    for p, text in before.items():
        assert p.read_text() == text
