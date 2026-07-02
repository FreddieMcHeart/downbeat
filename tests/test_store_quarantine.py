"""Tests for list_quarantined / requeue_quarantined / purge_quarantined."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta

import pytest


def _peers(store, *names):
    for n in names:
        store.register_peer(name=n, session_id=f"s-{n}", cwd="/tmp", role="parent")


def _quarantine_msg(relay_dir, store, peer="c", from_peer="p"):
    """Helper: send a message, deliver it, then force-quarantine via reconcile."""
    msg = store.send_message(from_peer=from_peer, to_peer=peer,
                             subject="hello", body="world")
    store.deliver_messages(peer_name=peer, session_id="sess-1")
    # Backdate delivered_at and set redelivery_count=3 so reconcile quarantines
    delivered_file = relay_dir / "delivered" / peer / f"{msg.id}.json"
    d = json.loads(delivered_file.read_text())
    d["delivered_at"] = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    d["redelivery_count"] = 3
    delivered_file.write_text(json.dumps(d))
    store.reconcile(window_minutes=30, max_redelivery=3)
    return msg


# ── list_quarantined ─────────────────────────────────────────────────────────

def test_list_quarantined_returns_quarantined_messages(relay_dir):
    from downbeat.core import store
    _peers(store, "p", "c")
    msg = _quarantine_msg(relay_dir, store)
    found = store.list_quarantined("c")
    assert len(found) == 1
    assert found[0].id == msg.id
    assert found[0].quarantined_at is not None


def test_list_quarantined_empty_for_clean_peer(relay_dir):
    from downbeat.core import store
    _peers(store, "p", "c")
    assert store.list_quarantined("c") == []


def test_list_quarantined_multiple_newest_first(relay_dir):
    from downbeat.core import store
    _peers(store, "p", "c")
    msg1 = _quarantine_msg(relay_dir, store)
    msg2 = _quarantine_msg(relay_dir, store)
    found = store.list_quarantined("c")
    assert len(found) == 2
    # newest-first: msg2 created after msg1
    assert found[0].id == msg2.id
    assert found[1].id == msg1.id


# ── requeue_quarantined ──────────────────────────────────────────────────────

def test_requeue_quarantined_moves_to_inbox(relay_dir):
    from downbeat.core import store
    from downbeat.core.models import MessageState
    _peers(store, "p", "c")
    msg = _quarantine_msg(relay_dir, store)
    count = store.requeue_quarantined("c")
    assert count == 1
    # Gone from quarantine
    assert store.list_quarantined("c") == []
    # Back in inbox with reset fields
    fetched = store.get_message(msg.id)
    assert fetched.quarantined_at is None
    assert fetched.quarantine_reason is None
    assert fetched.delivered_at is None
    assert fetched.delivered_to_session_id is None
    assert fetched.redelivery_count == 0
    assert fetched.state == MessageState.NEW


def test_requeue_quarantined_all_when_ids_none(relay_dir):
    from downbeat.core import store
    _peers(store, "p", "c")
    _quarantine_msg(relay_dir, store)
    _quarantine_msg(relay_dir, store)
    count = store.requeue_quarantined("c", ids=None)
    assert count == 2
    assert store.list_quarantined("c") == []


def test_requeue_quarantined_selective_by_id(relay_dir):
    from downbeat.core import store
    _peers(store, "p", "c")
    msg1 = _quarantine_msg(relay_dir, store)
    msg2 = _quarantine_msg(relay_dir, store)
    count = store.requeue_quarantined("c", ids=[msg1.id])
    assert count == 1
    # Only msg1 moved; msg2 still in quarantine
    remaining = store.list_quarantined("c")
    assert len(remaining) == 1
    assert remaining[0].id == msg2.id


def test_requeue_quarantined_nonexistent_peer_returns_zero(relay_dir):
    from downbeat.core import store
    assert store.requeue_quarantined("no-such-peer") == 0


# ── purge_quarantined ────────────────────────────────────────────────────────

def test_purge_quarantined_deletes_message(relay_dir):
    from downbeat.core import store
    from downbeat.core.errors import MessageNotFound
    _peers(store, "p", "c")
    msg = _quarantine_msg(relay_dir, store)
    count = store.purge_quarantined("c")
    assert count == 1
    assert store.list_quarantined("c") == []
    with pytest.raises(MessageNotFound):
        store.get_message(msg.id)


def test_purge_quarantined_selective_by_id(relay_dir):
    from downbeat.core import store
    _peers(store, "p", "c")
    msg1 = _quarantine_msg(relay_dir, store)
    msg2 = _quarantine_msg(relay_dir, store)
    count = store.purge_quarantined("c", ids=[msg1.id])
    assert count == 1
    remaining = store.list_quarantined("c")
    assert len(remaining) == 1
    assert remaining[0].id == msg2.id


def test_purge_quarantined_nonexistent_peer_returns_zero(relay_dir):
    from downbeat.core import store
    assert store.purge_quarantined("no-such-peer") == 0


# ── CLI integration ──────────────────────────────────────────────────────────

def test_cli_quarantine_list_exits_zero(relay_dir, capsys, monkeypatch):
    from downbeat.cli.__main__ import main
    from downbeat.core import store
    _peers(store, "p", "c")
    _quarantine_msg(relay_dir, store)
    monkeypatch.setattr(sys, "argv",
                        ["downbeat", "quarantine", "--peer", "c", "list"])
    rc = main()
    assert rc == 0
    out = capsys.readouterr().out
    assert "hello" in out


def test_cli_quarantine_list_empty_exits_zero(relay_dir, capsys, monkeypatch):
    from downbeat.cli.__main__ import main
    from downbeat.core import store
    _peers(store, "p", "c")
    monkeypatch.setattr(sys, "argv",
                        ["downbeat", "quarantine", "--peer", "c", "list"])
    rc = main()
    assert rc == 0
    assert "no quarantined" in capsys.readouterr().out


def test_cli_quarantine_purge_empties_quarantine(relay_dir, capsys, monkeypatch):
    from downbeat.cli.__main__ import main
    from downbeat.core import store
    _peers(store, "p", "c")
    _quarantine_msg(relay_dir, store)
    monkeypatch.setattr(sys, "argv",
                        ["downbeat", "quarantine", "--peer", "c", "purge"])
    rc = main()
    assert rc == 0
    assert store.list_quarantined("c") == []
    assert "purged 1" in capsys.readouterr().out


def test_cli_quarantine_requeue_moves_to_inbox(relay_dir, capsys, monkeypatch):
    from downbeat.cli.__main__ import main
    from downbeat.core import store
    _peers(store, "p", "c")
    msg = _quarantine_msg(relay_dir, store)
    monkeypatch.setattr(sys, "argv",
                        ["downbeat", "quarantine", "--peer", "c", "requeue"])
    rc = main()
    assert rc == 0
    assert store.list_quarantined("c") == []
    fetched = store.get_message(msg.id)
    assert fetched.redelivery_count == 0
    assert "requeued 1" in capsys.readouterr().out
