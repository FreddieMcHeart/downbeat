import pytest

from downbeat.core import store
from downbeat.core.errors import MessageLocked, MessageNotFound, PeerNotFound
from downbeat.core.models import MessageState


def _peers(*names):
    for n in names:
        store.register_peer(name=n, session_id=f"s-{n}", cwd="/tmp", role="parent")


def test_send_writes_inbox_message(relay_dir):
    _peers("parent", "child")
    msg = store.send_message(from_peer="parent", to_peer="child",
                             subject="hi", body="do work")
    fetched = store.get_message(msg.id)
    assert fetched.subject == "hi"
    assert fetched.state == MessageState.NEW


def test_send_to_unknown_peer_raises(relay_dir):
    _peers("parent")
    with pytest.raises(PeerNotFound):
        store.send_message(from_peer="parent", to_peer="ghost",
                           subject="x", body="x")


def test_mark_read_sets_read_at(relay_dir):
    _peers("parent", "child")
    msg = store.send_message(from_peer="parent", to_peer="child",
                             subject="s", body="b")
    store.mark_read(msg.id)
    assert store.get_message(msg.id).state == MessageState.READ


def test_mark_read_is_idempotent(relay_dir):
    _peers("parent", "child")
    msg = store.send_message(from_peer="parent", to_peer="child",
                             subject="s", body="b")
    store.mark_read(msg.id)
    first = store.get_message(msg.id).read_at
    store.mark_read(msg.id)
    assert store.get_message(msg.id).read_at == first


def test_edit_allowed_while_new(relay_dir):
    _peers("parent", "child")
    msg = store.send_message(from_peer="parent", to_peer="child",
                             subject="s", body="b")
    store.edit_message(msg.id, new_body="b2")
    edited = store.get_message(msg.id)
    assert edited.body == "b2"
    assert edited.edited_at is not None


def test_edit_blocked_after_read(relay_dir):
    _peers("parent", "child")
    msg = store.send_message(from_peer="parent", to_peer="child",
                             subject="s", body="b")
    store.mark_read(msg.id)
    with pytest.raises(MessageLocked):
        store.edit_message(msg.id, new_body="b2")


def test_delete_removes_message(relay_dir):
    _peers("parent", "child")
    msg = store.send_message(from_peer="parent", to_peer="child",
                             subject="s", body="b")
    store.delete_message(msg.id)
    with pytest.raises(MessageNotFound):
        store.get_message(msg.id)


def test_delete_allowed_after_read(relay_dir):
    _peers("parent", "child")
    msg = store.send_message(from_peer="parent", to_peer="child",
                             subject="s", body="b")
    store.mark_read(msg.id)
    store.delete_message(msg.id)
    with pytest.raises(MessageNotFound):
        store.get_message(msg.id)


def test_reply_archives_original_and_creates_response(relay_dir):
    _peers("parent", "child")
    msg = store.send_message(from_peer="parent", to_peer="child",
                             subject="s", body="b")
    store.mark_read(msg.id)
    reply = store.reply_to(msg.id, body="reply-body", from_peer="child")
    # Original archived
    archived = store.get_message(msg.id)
    assert archived.state == MessageState.ARCHIVED
    # Reply is a new NEW message addressed back to parent
    assert reply.from_peer == "child"
    assert reply.to_peer == "parent"
    assert reply.state == MessageState.NEW


def test_list_inbox_for_peer(relay_dir):
    _peers("parent", "child")
    store.send_message(from_peer="parent", to_peer="child", subject="a", body="x")
    store.send_message(from_peer="parent", to_peer="child", subject="b", body="x")
    items = store.list_inbox("child")
    assert len(items) == 2
    assert {m.subject for m in items} == {"a", "b"}


def test_list_inbox_dedups_when_id_appears_in_both_dirs(relay_dir):
    """Defensive: legacy data sometimes has the same msg id in both inbox/
    and processed/. list_inbox should return it once."""
    import json
    _peers("parent", "child")
    msg = store.send_message(from_peer="parent", to_peer="child",
                             subject="s", body="b")
    # Manually plant a duplicate in processed/
    dup_dir = relay_dir / "processed" / "child"
    dup_dir.mkdir(parents=True, exist_ok=True)
    dup_path = dup_dir / f"{msg.id}.json"
    dup_path.write_text(json.dumps({**msg.to_dict(), "archived": True}))
    # With include_archived=True, must still see only one entry for this id
    items = store.list_inbox("child", include_archived=True)
    ids = [m.id for m in items]
    assert ids.count(msg.id) == 1


def test_find_message_by_id_prefix(relay_dir):
    _peers("parent", "child")
    a = store.send_message(from_peer="parent", to_peer="child",
                           subject="alpha", body="x")
    b = store.send_message(from_peer="parent", to_peer="child",
                           subject="beta", body="y")
    # Reply b — moves it to processed/
    store.mark_read(b.id)
    store.reply_to(b.id, body="reply", from_peer="child")
    # Search by short prefix of a
    matches = store.find_message_by_id_prefix(a.id[:6])
    ids = {m.id for m, _ in matches}
    assert a.id in ids

    # Search hits a message archived in processed/
    matches_b = store.find_message_by_id_prefix(b.id[:6])
    locations = {loc for _, loc in matches_b}
    assert "processed" in locations or "inbox" in locations  # one of them

    # Empty prefix returns nothing
    assert store.find_message_by_id_prefix("") == []
    assert store.find_message_by_id_prefix("   ") == []


def test_find_message_no_match_returns_empty(relay_dir):
    _peers("p", "c")
    store.send_message(from_peer="p", to_peer="c", subject="s", body="b")
    assert store.find_message_by_id_prefix("zzzzzzzz") == []


def test_list_thread_returns_both_directions_sorted(relay_dir):
    _peers("parent", "child")
    a = store.send_message(from_peer="parent", to_peer="child",
                           subject="q1", body="ask")
    # Simulate child replying
    store.mark_read(a.id)
    b = store.reply_to(a.id, body="answer", from_peer="child")
    # parent replies again
    c = store.send_message(from_peer="parent", to_peer="child",
                           subject="q2", body="follow up")
    thread = store.list_thread("parent", "child")
    ids = {m.id for m in thread}
    # All three messages should appear (both directions, including archived)
    assert ids == {a.id, b.id, c.id}
    # Verify sorted oldest-to-newest (created_at is ISO; same-second ties are stable
    # by sort stability but not guaranteed order — we only assert set membership here)
    assert all(thread[i].created_at <= thread[i + 1].created_at
               for i in range(len(thread) - 1))


def test_send_message_kind_defaults_to_task(relay_dir):
    _peers("parent", "child")
    msg = store.send_message(from_peer="parent", to_peer="child",
                             subject="s", body="b")
    assert store.get_message(msg.id).kind == "task"


def test_send_message_kind_threads_through(relay_dir):
    _peers("parent", "child")
    msg = store.send_message(from_peer="parent", to_peer="child",
                             subject="s", body="b", kind="backflow-ready")
    assert store.get_message(msg.id).kind == "backflow-ready"


def test_reply_kind_threads_and_sets_in_reply_to(relay_dir):
    _peers("parent", "child")
    orig = store.send_message(from_peer="parent", to_peer="child",
                              subject="task", body="do it")
    rep = store.reply_to(orig.id, body="done", from_peer="child",
                         kind="backflow-ready")
    fetched = store.get_message(rep.id)
    assert fetched.kind == "backflow-ready"
    assert fetched.in_reply_to == orig.id


def test_reply_archives_original_preserving_kind(relay_dir):
    # Archive round-trip (spec R-2): reply_to does to_dict()->from_dict() on the
    # original; a non-default kind must survive that round-trip.
    _peers("parent", "child")
    orig = store.send_message(from_peer="parent", to_peer="child",
                              subject="bf", body="findings",
                              kind="backflow-ready")
    store.reply_to(orig.id, body="ack", from_peer="child")
    archived = store.get_message(orig.id)
    assert archived.archived is True
    assert archived.kind == "backflow-ready"


def test_is_recipient_stale_fresh_last_seen_is_not_stale(relay_dir):
    _peers("c")
    assert store.is_recipient_stale("c") is False


def test_is_recipient_stale_old_last_seen_is_stale(relay_dir):
    from datetime import UTC, datetime, timedelta
    _peers("c")
    sessions = store._load_sessions()
    sessions["c"]["last_seen"] = (
        datetime.now(UTC) - timedelta(minutes=20)
    ).isoformat()
    store._save_sessions(sessions)
    assert store.is_recipient_stale("c") is True


def test_is_recipient_stale_missing_peer_is_not_stale(relay_dir):
    assert store.is_recipient_stale("ghost") is False


def test_is_recipient_stale_custom_threshold(relay_dir):
    from datetime import UTC, datetime, timedelta
    _peers("c")
    sessions = store._load_sessions()
    sessions["c"]["last_seen"] = (
        datetime.now(UTC) - timedelta(minutes=5)
    ).isoformat()
    store._save_sessions(sessions)
    assert store.is_recipient_stale("c", threshold_minutes=10) is False
    assert store.is_recipient_stale("c", threshold_minutes=3) is True


def test_poll_new_first_call_returns_all_new(relay_dir):
    _peers("p", "c")
    m1 = store.send_message(from_peer="p", to_peer="c", subject="s1", body="b1")
    m2 = store.send_message(from_peer="p", to_peer="c", subject="s2", body="b2")

    new_msgs, seen = store.poll_new("c", set())

    assert {m.id for m in new_msgs} == {m1.id, m2.id}
    assert seen == {m1.id, m2.id}


def test_poll_new_second_call_returns_empty(relay_dir):
    _peers("p", "c")
    store.send_message(from_peer="p", to_peer="c", subject="s", body="b")

    _, seen = store.poll_new("c", set())
    new_msgs, seen2 = store.poll_new("c", seen)

    assert new_msgs == []
    assert seen2 == seen  # seen unchanged (no new ids added)


def test_poll_new_only_returns_incremental(relay_dir):
    _peers("p", "c")
    m1 = store.send_message(from_peer="p", to_peer="c", subject="first", body="x")

    _, seen = store.poll_new("c", set())  # seed seen with m1

    m2 = store.send_message(from_peer="p", to_peer="c", subject="second", body="y")
    new_msgs, seen2 = store.poll_new("c", seen)

    assert [m.id for m in new_msgs] == [m2.id]
    assert m1.id not in {m.id for m in new_msgs}
    assert {m1.id, m2.id} <= seen2


def test_poll_new_excludes_non_new_states(relay_dir):
    _peers("p", "c")
    # delivered state: drain moves it from inbox/ to delivered/
    m_delivered = store.send_message(from_peer="p", to_peer="c",
                                     subject="delivered", body="x")
    store.deliver_messages(peer_name="c", session_id="s-c")
    assert store.get_message(m_delivered.id).state == MessageState.DELIVERED

    # archived state: ack after deliver
    m_acked = store.send_message(from_peer="p", to_peer="c",
                                 subject="acked", body="y")
    store.deliver_messages(peer_name="c", session_id="s-c")
    store.ack_messages([m_acked.id])
    assert store.get_message(m_acked.id).state == MessageState.ARCHIVED

    # One genuinely NEW message
    m_new = store.send_message(from_peer="p", to_peer="c",
                               subject="still new", body="z")

    new_msgs, _ = store.poll_new("c", set())

    ids = {m.id for m in new_msgs}
    assert m_new.id in ids
    assert m_delivered.id not in ids
    assert m_acked.id not in ids
