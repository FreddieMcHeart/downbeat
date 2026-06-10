import json

from claude_relay.core.models import Message, MessageState, Peer


def test_message_roundtrip_json():
    m = Message(
        id="a1f2",
        from_peer="parent",
        to_peer="child",
        subject="hi",
        body="do work",
        created_at="2026-05-12T14:02:11+00:00",
    )
    s = m.to_json()
    parsed = json.loads(s)
    assert parsed["from"] == "parent"
    assert parsed["to"] == "child"
    assert parsed["read_at"] is None
    again = Message.from_json(s)
    assert again == m


def test_message_state_new_when_unread():
    m = Message(id="a", from_peer="p", to_peer="c", subject="s", body="b",
                created_at="2026-05-12T14:00:00+00:00")
    assert m.state == MessageState.NEW


def test_message_state_read_when_read_at_set():
    m = Message(id="a", from_peer="p", to_peer="c", subject="s", body="b",
                created_at="2026-05-12T14:00:00+00:00",
                read_at="2026-05-12T14:05:00+00:00")
    assert m.state == MessageState.READ


def test_message_state_archived_when_archived_true():
    m = Message(id="a", from_peer="p", to_peer="c", subject="s", body="b",
                created_at="2026-05-12T14:00:00+00:00",
                archived=True)
    assert m.state == MessageState.ARCHIVED


def test_peer_roundtrip():
    p = Peer(name="parent", session_id="abc", cwd="/tmp",
             role="parent", registered_at="2026-05-12T14:00:00+00:00",
             last_seen="2026-05-12T14:00:00+00:00")
    d = p.to_dict()
    again = Peer.from_dict(d)
    assert again == p


def test_legacy_message_without_new_fields_parses_with_defaults():
    legacy = json.dumps({
        "id": "x",
        "from": "p", "to": "c",
        "subject": "s", "body": "b",
        "created_at": "2026-05-12T14:00:00+00:00",
    })
    m = Message.from_json(legacy)
    assert m.read_at is None
    assert m.edited_at is None
    assert m.broadcast_id is None
    assert m.archived is False


def test_legacy_message_with_ts_instead_of_created_at():
    legacy = json.dumps({
        "id": "old",
        "from": "p", "to": "c",
        "subject": "s", "body": "b",
        "ts": "2026-05-08T14:52:41+00:00",
    })
    m = Message.from_json(legacy)
    assert m.created_at == "2026-05-08T14:52:41+00:00"


def test_message_kind_roundtrip():
    m = Message(id="k1", from_peer="p", to_peer="c", subject="s", body="b",
                created_at="2026-06-04T10:00:00+00:00", kind="backflow-ready")
    d = m.to_dict()
    assert d["kind"] == "backflow-ready"
    again = Message.from_dict(d)
    assert again.kind == "backflow-ready"
    assert again == m


def test_message_kind_defaults_to_task():
    m = Message(id="k2", from_peer="p", to_peer="c", subject="s", body="b",
                created_at="2026-06-04T10:00:00+00:00")
    assert m.kind == "task"
    assert m.to_dict()["kind"] == "task"


def test_legacy_message_without_kind_reads_as_task():
    legacy = json.dumps({
        "id": "x", "from": "p", "to": "c",
        "subject": "s", "body": "b",
        "created_at": "2026-05-12T14:00:00+00:00",
    })
    m = Message.from_json(legacy)
    assert m.kind == "task"
