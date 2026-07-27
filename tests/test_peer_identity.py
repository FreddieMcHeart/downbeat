"""Stable peer identity, separate from display name (issue #40, Option A).

`peer_id` is assigned once and never reassigned; `name` becomes a display
alias. Messages carry both: `from`/`to` keep the name *at send time* (useful
history, and what the TUI renders), `from_peer_id`/`to_peer_id` carry identity.
"""
from __future__ import annotations

import json
import sys


def _peers(store, *names):
    for n in names:
        store.register_peer(name=n, session_id=f"s-{n}", cwd="/tmp", role="parent")


# ── the id itself ────────────────────────────────────────────────────────────

def test_register_peer_assigns_a_peer_id(relay_dir):
    from downbeat.core import store
    _peers(store, "a")

    assert store.get_peer("a").peer_id


def test_two_peers_get_different_ids(relay_dir):
    from downbeat.core import store
    _peers(store, "a", "b")

    assert store.get_peer("a").peer_id != store.get_peer("b").peer_id


def test_peer_id_survives_re_registration(relay_dir):
    """A session restarting under the same name is the same peer."""
    from downbeat.core import store
    _peers(store, "a")
    original = store.get_peer("a").peer_id

    store.register_peer(name="a", session_id="s-new", cwd="/tmp", role="parent")

    assert store.get_peer("a").peer_id == original


def test_peer_id_survives_rename(relay_dir):
    from downbeat.core import store
    _peers(store, "a")
    original = store.get_peer("a").peer_id

    store.rename_peer("a", "a2")

    assert store.get_peer("a2").peer_id == original


def test_legacy_peer_without_id_resolves_deterministically(relay_dir):
    """Two concurrent readers must derive the SAME id for a legacy entry —
    a random backfill would hand them different identities."""
    from downbeat.core import paths, store
    paths.SESSIONS_FILE.write_text(json.dumps({
        "legacy": {"name": "legacy", "session_id": "s-legacy", "cwd": "/tmp",
                   "role": "parent", "registered_at": "", "last_seen": ""}
    }))

    first = store.get_peer("legacy").peer_id
    second = store.get_peer("legacy").peer_id

    assert first
    assert first == second


# ── messages carry identity alongside the display name ───────────────────────

def test_send_message_stamps_both_name_and_id(relay_dir):
    from downbeat.core import store
    _peers(store, "a", "b")

    msg = store.send_message(from_peer="a", to_peer="b", subject="s", body="x")

    assert msg.from_peer == "a"                              # display, at send time
    assert msg.from_peer_id == store.get_peer("a").peer_id   # identity
    assert msg.to_peer_id == store.get_peer("b").peer_id


def test_v1_message_upgrades_with_null_ids(relay_dir):
    """The ladder is pure — it cannot read the peer registry, so it only
    makes room for the ids. Filling them is the store's job."""
    from downbeat.core import store
    from downbeat.core.models import CURRENT_SCHEMA_VERSION, Message
    _peers(store, "a", "b")
    msg = store.send_message(from_peer="a", to_peer="b", subject="s", body="x")
    v1 = msg.to_dict()
    v1["schema_version"] = 1
    del v1["from_peer_id"], v1["to_peer_id"]

    upgraded = Message.from_dict(v1)

    assert upgraded.schema_version == CURRENT_SCHEMA_VERSION
    assert upgraded.from_peer_id is None
    assert upgraded.to_peer_id is None
    assert upgraded.from_peer == "a"  # the display name is untouched


# ── the actual #40 bug: renaming must not punch a hole in history ────────────

def test_list_thread_survives_a_rename(relay_dir):
    from downbeat.core import store
    _peers(store, "a", "b")
    store.send_message(from_peer="a", to_peer="b", subject="one", body="x")
    store.send_message(from_peer="b", to_peer="a", subject="two", body="y")
    store.send_message(from_peer="a", to_peer="b", subject="three", body="z")
    before = [m.id for m in store.list_thread("a", "b")]
    assert len(before) == 3

    store.rename_peer("a", "a2")

    after = [m.id for m in store.list_thread("a2", "b")]
    assert after == before


def test_list_thread_recovers_a_message_the_rename_sweep_missed(relay_dir):
    """`peers rename` (Option B) keeps history intact by rewriting `from`/`to`
    in every file. Any file the sweep does not reach — written concurrently
    with the rename, or sitting in a directory the walk missed — keeps the old
    name and silently drops out of the thread. Identity survives that; a name
    comparison cannot.
    """
    from downbeat.core import paths, store
    _peers(store, "a", "b")
    msg = store.send_message(from_peer="a", to_peer="b", subject="one", body="x")
    store.rename_peer("a", "a2")
    # Simulate the file the sweep missed: its `from` still says "a".
    path = paths.INBOX_DIR / "b" / f"{msg.id}.json"
    d = json.loads(path.read_text())
    d["from"] = "a"
    path.write_text(json.dumps(d))

    thread = store.list_thread("a2", "b")

    assert [m.id for m in thread] == [msg.id]


def test_list_thread_still_works_for_unmigrated_messages(relay_dir):
    """Messages whose ids were never backfilled still thread by name."""
    from downbeat.core import paths, store
    _peers(store, "a", "b")
    msg = store.send_message(from_peer="a", to_peer="b", subject="one", body="x")
    path = paths.INBOX_DIR / "b" / f"{msg.id}.json"
    d = json.loads(path.read_text())
    d["from_peer_id"] = None
    d["to_peer_id"] = None
    path.write_text(json.dumps(d))

    thread = store.list_thread("a", "b")

    assert [m.id for m in thread] == [msg.id]


# ── backfilling identity onto historical messages ────────────────────────────

def _strip_ids(path):
    d = json.loads(path.read_text())
    d["from_peer_id"] = None
    d["to_peer_id"] = None
    path.write_text(json.dumps(d))


def test_migrate_store_backfills_ids_from_the_registry(relay_dir):
    from downbeat.core import paths, store
    _peers(store, "a", "b")
    msg = store.send_message(from_peer="a", to_peer="b", subject="s", body="x")
    path = paths.INBOX_DIR / "b" / f"{msg.id}.json"
    _strip_ids(path)

    counts = store.migrate_store()

    assert counts["ids_backfilled"] == 1
    raw = json.loads(path.read_text())
    assert raw["from_peer_id"] == store.get_peer("a").peer_id
    assert raw["to_peer_id"] == store.get_peer("b").peer_id


def test_migrate_store_leaves_unknown_sender_unresolved(relay_dir):
    """A peer that no longer exists has no id to map to — leave it null and
    let the name-based fallback carry it, rather than inventing an identity."""
    from downbeat.core import paths, store
    _peers(store, "a", "b")
    msg = store.send_message(from_peer="a", to_peer="b", subject="s", body="x")
    path = paths.INBOX_DIR / "b" / f"{msg.id}.json"
    _strip_ids(path)
    store.remove_peer("a")

    counts = store.migrate_store()

    raw = json.loads(path.read_text())
    assert raw["from_peer_id"] is None
    assert raw["to_peer_id"] == store.get_peer("b").peer_id
    assert counts["ids_backfilled"] == 1


def test_migrate_store_is_idempotent_on_ids(relay_dir):
    from downbeat.core import paths, store
    _peers(store, "a", "b")
    msg = store.send_message(from_peer="a", to_peer="b", subject="s", body="x")
    _strip_ids(paths.INBOX_DIR / "b" / f"{msg.id}.json")
    store.migrate_store()

    counts = store.migrate_store()

    assert counts["ids_backfilled"] == 0
    assert counts["migrated"] == 0


# ── CLI ──────────────────────────────────────────────────────────────────────

def test_cli_migrate_reports_ids_backfilled(relay_dir, capsys, monkeypatch):
    from downbeat.cli.__main__ import main
    from downbeat.core import paths, store
    _peers(store, "a", "b")
    msg = store.send_message(from_peer="a", to_peer="b", subject="s", body="x")
    _strip_ids(paths.INBOX_DIR / "b" / f"{msg.id}.json")
    monkeypatch.setattr(sys, "argv", ["downbeat", "migrate"])

    rc = main()

    assert rc == 0
    assert "identity for 1 message" in capsys.readouterr().out


def test_cli_peers_shows_peer_id(relay_dir, capsys, monkeypatch):
    from downbeat.cli.__main__ import main
    from downbeat.core import store
    _peers(store, "a")
    monkeypatch.setattr(sys, "argv", ["downbeat", "peers"])

    rc = main()

    assert rc == 0
    assert store.get_peer("a").peer_id in capsys.readouterr().out
