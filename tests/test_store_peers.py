from claude_relay.core import store
from claude_relay.core.errors import PeerNotFound


def test_register_creates_peer(relay_dir):
    store.register_peer(name="parent", session_id="s-1", cwd="/tmp", role="parent")
    peers = store.list_peers()
    assert len(peers) == 1
    assert peers[0].name == "parent"
    assert peers[0].role == "parent"


def test_register_updates_existing_peer_in_place(relay_dir):
    store.register_peer(name="p", session_id="s-1", cwd="/tmp", role="parent")
    store.register_peer(name="p", session_id="s-2", cwd="/tmp", role="parent")
    peers = store.list_peers()
    assert len(peers) == 1
    assert peers[0].session_id == "s-2"


def test_get_peer_raises_when_missing(relay_dir):
    import pytest
    with pytest.raises(PeerNotFound):
        store.get_peer("nope")


def test_remove_peer(relay_dir):
    store.register_peer(name="p", session_id="s-1", cwd="/tmp", role="parent")
    store.remove_peer("p")
    assert store.list_peers() == []


def test_touch_peer_updates_last_seen(relay_dir):
    store.register_peer(name="p", session_id="s-1", cwd="/tmp", role="parent")
    before = store.get_peer("p").last_seen
    store.touch_peer("p")
    after = store.get_peer("p").last_seen
    assert after >= before
