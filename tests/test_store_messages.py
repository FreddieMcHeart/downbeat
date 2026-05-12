import pytest

from claude_relay.core import store
from claude_relay.core.errors import MessageLocked, MessageNotFound, PeerNotFound
from claude_relay.core.models import MessageState


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
