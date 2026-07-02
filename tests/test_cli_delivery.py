import sys

from downbeat.cli.__main__ import main


def test_drain_cmd(relay_dir, monkeypatch):
    from downbeat.core import store
    store.register_peer(name="p", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="c", session_id="s2", cwd="/tmp", role="child")
    store.send_message(from_peer="p", to_peer="c", subject="x", body="y")
    monkeypatch.setattr(sys, "argv",
        ["downbeat", "drain", "--peer", "c", "--session-id", "abc"])
    rc = main()
    assert rc == 0
    msgs = store.list_inbox("c")
    assert msgs[0].state.value == "delivered"


def test_ack_cmd(relay_dir, monkeypatch):
    from downbeat.core import store
    store.register_peer(name="p", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="c", session_id="s2", cwd="/tmp", role="child")
    msg = store.send_message(from_peer="p", to_peer="c", subject="x", body="y")
    store.deliver_messages(peer_name="c", session_id="abc")
    monkeypatch.setattr(sys, "argv", ["downbeat", "ack", msg.id])
    rc = main()
    assert rc == 0
    assert store.get_message(msg.id).archived is True
