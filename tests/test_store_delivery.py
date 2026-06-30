from datetime import UTC

from claude_relay.core import store
from claude_relay.core.models import MessageState


def _peers(*names):
    for n in names:
        store.register_peer(name=n, session_id=f"s-{n}", cwd="/tmp", role="parent")


def test_deliver_moves_inbox_to_delivered(relay_dir):
    _peers("p", "c")
    msg = store.send_message(from_peer="p", to_peer="c", subject="x", body="y")
    delivered = store.deliver_messages(peer_name="c", session_id="sess-1")
    assert len(delivered) == 1
    assert delivered[0].id == msg.id
    assert delivered[0].delivered_at is not None
    assert delivered[0].state == MessageState.DELIVERED


def test_ack_promotes_to_processed(relay_dir):
    _peers("p", "c")
    msg = store.send_message(from_peer="p", to_peer="c", subject="x", body="y")
    store.deliver_messages(peer_name="c", session_id="sess-1")
    results = store.ack_messages([msg.id])
    assert results[msg.id] is True
    fetched = store.get_message(msg.id)
    assert fetched.archived is True
    assert fetched.delivery_ack_at is not None
    assert fetched.state == MessageState.ARCHIVED


def test_reply_auto_acks_delivered_original(relay_dir):
    _peers("p", "c")
    msg = store.send_message(from_peer="p", to_peer="c", subject="x", body="y")
    store.deliver_messages(peer_name="c", session_id="sess-1")
    reply = store.reply_to(msg.id, body="ack", from_peer="c")
    fetched = store.get_message(msg.id)
    assert fetched.delivery_ack_at is not None
    assert fetched.archived is True
    assert reply.in_reply_to == msg.id


def test_archive_messages_clears_new_inbox_to_processed(relay_dir):
    """archive_messages must drain a NEW (never-delivered) inbox message to
    processed/ — the dead-peer report-backlog case the TUI clear button hits."""
    _peers("p", "c")
    msg = store.send_message(from_peer="p", to_peer="c", subject="report", body="done")
    # NEW, never delivered (dead peer scenario)
    assert store.get_message(msg.id).state == MessageState.NEW
    results = store.archive_messages([msg.id])
    assert results[msg.id] is True
    fetched = store.get_message(msg.id)
    assert fetched.archived is True
    assert fetched.state == MessageState.ARCHIVED
    # No longer counted as pending NEW in the badge set
    pending = [m for m in store.list_inbox("c") if m.state == MessageState.NEW]
    assert msg.id not in {m.id for m in pending}


def test_archive_messages_auto_acks_delivered(relay_dir):
    """A delivered-but-unacked message archived via the clear button gets its
    delivery_ack_at stamped (closes the delivery loop, not just hides it)."""
    _peers("p", "c")
    msg = store.send_message(from_peer="p", to_peer="c", subject="x", body="y")
    store.deliver_messages(peer_name="c", session_id="sess-1")
    assert store.get_message(msg.id).state == MessageState.DELIVERED
    store.archive_messages([msg.id])
    fetched = store.get_message(msg.id)
    assert fetched.archived is True
    assert fetched.delivery_ack_at is not None


def test_reconcile_requeues_stale_delivered(relay_dir, monkeypatch):
    from datetime import datetime, timedelta
    _peers("p", "c")
    msg = store.send_message(from_peer="p", to_peer="c", subject="x", body="y")
    store.deliver_messages(peer_name="c", session_id="sess-1")
    # Backdate delivered_at to 1 hour ago
    import json
    delivered_file = relay_dir / "delivered" / "c" / f"{msg.id}.json"
    d = json.loads(delivered_file.read_text())
    d["delivered_at"] = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    delivered_file.write_text(json.dumps(d))
    counts = store.reconcile(window_minutes=30, max_redelivery=3)
    assert counts["requeued"] == 1
    # Message is back in inbox/ with redelivery_count incremented
    fetched = store.get_message(msg.id)
    assert fetched.redelivery_count == 1
    assert fetched.delivered_at is None


def test_reconcile_quarantines_after_max_redelivery(relay_dir):
    from datetime import datetime, timedelta
    _peers("p", "c")
    msg = store.send_message(from_peer="p", to_peer="c", subject="x", body="y")
    # Simulate already-3-times-redelivered by writing directly
    import json
    store.deliver_messages(peer_name="c", session_id="sess-1")
    delivered_file = relay_dir / "delivered" / "c" / f"{msg.id}.json"
    d = json.loads(delivered_file.read_text())
    d["delivered_at"] = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    d["redelivery_count"] = 3
    delivered_file.write_text(json.dumps(d))
    counts = store.reconcile(window_minutes=30, max_redelivery=3)
    assert counts["quarantined"] == 1
    fetched = store.get_message(msg.id)
    assert fetched.state == MessageState.QUARANTINED
    assert fetched.quarantine_reason is not None


def test_list_inbox_includes_delivered_messages(relay_dir):
    _peers("p", "c")
    store.send_message(from_peer="p", to_peer="c", subject="a", body="x")
    store.deliver_messages(peer_name="c", session_id="sess-1")
    msgs = store.list_inbox("c")
    assert len(msgs) == 1
    assert msgs[0].state == MessageState.DELIVERED
