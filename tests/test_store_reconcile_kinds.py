"""Tests for kind-aware reconcile: terminal messages auto-ack instead of
churning through redeliveries into quarantine (issue #47)."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta


def _peers(store, *names):
    for n in names:
        store.register_peer(name=n, session_id=f"s-{n}", cwd="/tmp", role="parent")


def _deliver_and_age(relay_dir, store, msg, peer="c", redelivery_count=0,
                     minutes_ago=60):
    """Deliver a message to `peer`, then backdate delivered_at so the next
    reconcile() sees it as past the window."""
    store.deliver_messages(peer_name=peer, session_id="sess-1")
    delivered_file = relay_dir / "delivered" / peer / f"{msg.id}.json"
    d = json.loads(delivered_file.read_text())
    d["delivered_at"] = (
        datetime.now(UTC) - timedelta(minutes=minutes_ago)
    ).isoformat()
    d["redelivery_count"] = redelivery_count
    delivered_file.write_text(json.dumps(d))


# ── replies (in_reply_to) are terminal ───────────────────────────────────────

def test_reconcile_auto_acks_reply_instead_of_requeueing(relay_dir):
    """A reply has no ack path — the original sender absorbed it on arrival."""
    from downbeat.core import store
    from downbeat.core.models import MessageState
    _peers(store, "p", "c")
    original = store.send_message(from_peer="c", to_peer="p",
                                  subject="ask", body="?")
    reply = store.send_message(from_peer="p", to_peer="c", subject="Re: ask",
                               body="answer", in_reply_to=original.id)
    _deliver_and_age(relay_dir, store, reply)

    counts = store.reconcile(window_minutes=30, max_redelivery=3)

    assert counts["auto_acked"] == 1
    assert counts["requeued"] == 0
    assert counts["quarantined"] == 0
    fetched = store.get_message(reply.id)
    assert fetched.delivery_ack_at is not None
    assert fetched.state == MessageState.ARCHIVED
    assert fetched.redelivery_count == 0


def test_reconcile_auto_acks_reply_instead_of_quarantining(relay_dir):
    """The backlog case: a Re: chain stuck at redelivery_count 3 must be
    acked, not quarantined."""
    from downbeat.core import store
    _peers(store, "p", "c")
    original = store.send_message(from_peer="c", to_peer="p",
                                  subject="ask", body="?")
    reply = store.send_message(from_peer="p", to_peer="c", subject="Re: ask",
                               body="answer", in_reply_to=original.id)
    _deliver_and_age(relay_dir, store, reply, redelivery_count=3)

    counts = store.reconcile(window_minutes=30, max_redelivery=3)

    assert counts["auto_acked"] == 1
    assert counts["quarantined"] == 0
    assert store.list_quarantined("c") == []


# ── terminal kinds ───────────────────────────────────────────────────────────

def test_reconcile_auto_acks_backflow_ready_kind(relay_dir):
    from downbeat.core import store
    _peers(store, "p", "c")
    msg = store.send_message(from_peer="p", to_peer="c", subject="done",
                             body="results", kind="backflow-ready")
    _deliver_and_age(relay_dir, store, msg)

    counts = store.reconcile(window_minutes=30, max_redelivery=3)

    assert counts["auto_acked"] == 1
    assert counts["requeued"] == 0
    assert store.get_message(msg.id).delivery_ack_at is not None


def test_reconcile_auto_acks_status_kind(relay_dir):
    from downbeat.core import store
    _peers(store, "p", "c")
    msg = store.send_message(from_peer="p", to_peer="c", subject="fyi",
                             body="halfway", kind="status")
    _deliver_and_age(relay_dir, store, msg)

    counts = store.reconcile(window_minutes=30, max_redelivery=3)

    assert counts["auto_acked"] == 1
    assert counts["requeued"] == 0


# ── genuine tasks are untouched (regression guard) ───────────────────────────

def test_reconcile_still_requeues_genuine_task(relay_dir):
    from downbeat.core import store
    _peers(store, "p", "c")
    msg = store.send_message(from_peer="p", to_peer="c", subject="do it",
                             body="work")
    _deliver_and_age(relay_dir, store, msg)

    counts = store.reconcile(window_minutes=30, max_redelivery=3)

    assert counts["auto_acked"] == 0
    assert counts["requeued"] == 1
    assert store.get_message(msg.id).redelivery_count == 1


def test_reconcile_still_quarantines_exhausted_task(relay_dir):
    from downbeat.core import store
    _peers(store, "p", "c")
    msg = store.send_message(from_peer="p", to_peer="c", subject="do it",
                             body="work")
    _deliver_and_age(relay_dir, store, msg, redelivery_count=3)

    counts = store.reconcile(window_minutes=30, max_redelivery=3)

    assert counts["auto_acked"] == 0
    assert counts["quarantined"] == 1
    assert len(store.list_quarantined("c")) == 1


# ── the delivery window still governs ────────────────────────────────────────

def test_reconcile_leaves_fresh_terminal_message_alone(relay_dir):
    """A recipient that is awake still gets its normal chance to ack."""
    from downbeat.core import store
    from downbeat.core.models import MessageState
    _peers(store, "p", "c")
    original = store.send_message(from_peer="c", to_peer="p",
                                  subject="ask", body="?")
    reply = store.send_message(from_peer="p", to_peer="c", subject="Re: ask",
                               body="answer", in_reply_to=original.id)
    _deliver_and_age(relay_dir, store, reply, minutes_ago=1)

    counts = store.reconcile(window_minutes=30, max_redelivery=3)

    assert counts["auto_acked"] == 0
    assert store.get_message(reply.id).state == MessageState.DELIVERED


# ── CLI reports the new outcome ──────────────────────────────────────────────

def test_cli_reconcile_reports_auto_acked(relay_dir, capsys, monkeypatch):
    from downbeat.cli.__main__ import main
    from downbeat.core import store
    _peers(store, "p", "c")
    msg = store.send_message(from_peer="p", to_peer="c", subject="done",
                             body="results", kind="backflow-ready")
    _deliver_and_age(relay_dir, store, msg)
    monkeypatch.setattr(sys, "argv", ["downbeat", "reconcile"])

    rc = main()

    assert rc == 0
    assert "auto_acked=1" in capsys.readouterr().out
