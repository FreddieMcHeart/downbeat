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


def test_load_legacy_sessions_without_name_field(relay_dir):
    """Legacy sessions.json (from the old standalone relay.py) used the peer
    name as the dict KEY only — no `name` field in the value. Our loader
    must backfill it so Peer.from_dict() succeeds."""
    import json
    legacy = {
        "PLAT-3113-slave": {
            "session_id": "abc",
            "cwd": "/tmp",
            "role": "child",
            "registered_at": "2026-05-08T14:11:11+00:00",
            "last_seen": "2026-05-08T14:11:11+00:00",
        }
    }
    from claude_relay.core import paths
    (paths.SESSIONS_FILE.parent).mkdir(parents=True, exist_ok=True)
    paths.SESSIONS_FILE.write_text(json.dumps(legacy))
    peers = store.list_peers()
    assert len(peers) == 1
    assert peers[0].name == "PLAT-3113-slave"
    # get_peer must also work
    fetched = store.get_peer("PLAT-3113-slave")
    assert fetched.session_id == "abc"
