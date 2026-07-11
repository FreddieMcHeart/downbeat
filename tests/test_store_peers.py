import pytest

from downbeat.core import store
from downbeat.core.errors import AmbiguousParent, InvalidParent, PeerNotFound


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


def test_rebind_updates_session_id_only(relay_dir):
    store.register_peer(name="p", session_id="old-sid",
                        cwd="/orig", role="parent")
    peer = store.rebind_session("p", "new-sid")
    assert peer.session_id == "new-sid"
    # role, cwd, registered_at preserved
    assert peer.role == "parent"
    assert peer.cwd == "/orig"
    fresh = store.get_peer("p")
    assert fresh.session_id == "new-sid"
    assert fresh.registered_at == peer.registered_at


def test_rebind_unknown_peer_raises(relay_dir):
    with pytest.raises(PeerNotFound):
        store.rebind_session("nope", "sid")


def test_rebind_auto_detect_fails_when_no_marker(relay_dir, monkeypatch):
    from downbeat.core import session as session_mod
    from downbeat.core.errors import RelayError
    store.register_peer(name="p", session_id="old", cwd="/tmp", role="parent")
    monkeypatch.setattr(session_mod, "detect_session_id", lambda: None)
    with pytest.raises(RelayError):
        store.rebind_session("p", None)


def test_register_child_auto_defaults_to_sole_parent(relay_dir):
    store.register_peer(name="parent", session_id="s-1", cwd="/tmp", role="parent")
    child = store.register_peer(name="anything-goes", session_id="s-2", cwd="/tmp",
                                role="child")
    assert child.parent == "parent"


def test_register_child_no_parent_at_all_raises(relay_dir):
    with pytest.raises(InvalidParent):
        store.register_peer(name="orphan", session_id="s-1", cwd="/tmp", role="child")


def test_register_child_ambiguous_parent_raises(relay_dir):
    store.register_peer(name="parent-a", session_id="s-1", cwd="/tmp", role="parent")
    store.register_peer(name="parent-b", session_id="s-2", cwd="/tmp", role="parent")
    with pytest.raises(AmbiguousParent):
        store.register_peer(name="child", session_id="s-3", cwd="/tmp", role="child")


def test_register_child_explicit_parent_disambiguates(relay_dir):
    store.register_peer(name="parent-a", session_id="s-1", cwd="/tmp", role="parent")
    store.register_peer(name="parent-b", session_id="s-2", cwd="/tmp", role="parent")
    child = store.register_peer(name="child", session_id="s-3", cwd="/tmp", role="child",
                                parent="parent-b")
    assert child.parent == "parent-b"


def test_register_child_explicit_parent_not_found_raises(relay_dir):
    store.register_peer(name="parent", session_id="s-1", cwd="/tmp", role="parent")
    with pytest.raises(InvalidParent):
        store.register_peer(name="child", session_id="s-2", cwd="/tmp", role="child",
                            parent="nope")


def test_register_child_explicit_parent_wrong_role_raises(relay_dir):
    store.register_peer(name="parent", session_id="s-1", cwd="/tmp", role="parent")
    store.register_peer(name="other-child", session_id="s-2", cwd="/tmp", role="child",
                        parent="parent")
    with pytest.raises(InvalidParent):
        store.register_peer(name="child", session_id="s-3", cwd="/tmp", role="child",
                            parent="other-child")


def test_register_parent_never_gets_a_parent_value(relay_dir):
    p = store.register_peer(name="p", session_id="s-1", cwd="/tmp", role="parent")
    assert p.parent is None


def test_rebind_preserves_previously_set_parent(relay_dir):
    store.register_peer(name="parent", session_id="s-1", cwd="/tmp", role="parent")
    store.register_peer(name="child", session_id="s-2", cwd="/tmp", role="child",
                        parent="parent")
    store.register_peer(name="parent-b", session_id="s-3", cwd="/tmp", role="parent")
    # Re-registering the same child without --parent, even though there are
    # now 2 parents (which would otherwise be ambiguous), must keep its
    # existing pairing rather than erroring or re-guessing.
    again = store.register_peer(name="child", session_id="s-2", cwd="/tmp", role="child")
    assert again.parent == "parent"


def test_children_of_returns_parent_and_its_children_only(relay_dir):
    store.register_peer(name="parent-a", session_id="s-1", cwd="/tmp", role="parent")
    store.register_peer(name="parent-b", session_id="s-2", cwd="/tmp", role="parent")
    store.register_peer(name="alpha", session_id="s-3", cwd="/tmp", role="child",
                        parent="parent-a")
    store.register_peer(name="beta", session_id="s-4", cwd="/tmp", role="child",
                        parent="parent-b")
    related = {p.name for p in store.children_of("parent-a")}
    assert related == {"parent-a", "alpha"}


def test_children_of_does_not_use_name_prefix(relay_dir):
    """Free-form names must not need to share a prefix with their parent."""
    store.register_peer(name="Some-Parent-Name", session_id="s-1", cwd="/tmp",
                        role="parent")
    store.register_peer(name="Totally-Unrelated-Name", session_id="s-2", cwd="/tmp",
                        role="child", parent="Some-Parent-Name")
    related = {p.name for p in store.children_of("Some-Parent-Name")}
    assert related == {"Some-Parent-Name", "Totally-Unrelated-Name"}


def test_set_parent_backfills_existing_child(relay_dir):
    store.register_peer(name="parent-a", session_id="s-1", cwd="/tmp", role="parent")
    store.register_peer(name="parent-b", session_id="s-2", cwd="/tmp", role="parent")
    store.register_peer(name="child", session_id="s-3", cwd="/tmp", role="child",
                        parent="parent-a")
    updated = store.set_parent("child", "parent-b")
    assert updated.parent == "parent-b"
    assert store.get_peer("child").parent == "parent-b"


def test_set_parent_unknown_child_raises(relay_dir):
    store.register_peer(name="parent", session_id="s-1", cwd="/tmp", role="parent")
    with pytest.raises(PeerNotFound):
        store.set_parent("nope", "parent")


def test_set_parent_target_not_a_parent_raises(relay_dir):
    store.register_peer(name="parent", session_id="s-1", cwd="/tmp", role="parent")
    store.register_peer(name="child", session_id="s-2", cwd="/tmp", role="child",
                        parent="parent")
    store.register_peer(name="other-child", session_id="s-3", cwd="/tmp", role="child",
                        parent="parent")
    with pytest.raises(InvalidParent):
        store.set_parent("child", "other-child")


def test_set_parent_on_a_parent_peer_raises(relay_dir):
    store.register_peer(name="parent", session_id="s-1", cwd="/tmp", role="parent")
    store.register_peer(name="parent-2", session_id="s-2", cwd="/tmp", role="parent")
    with pytest.raises(InvalidParent):
        store.set_parent("parent", "parent-2")


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
    from downbeat.core import paths
    (paths.SESSIONS_FILE.parent).mkdir(parents=True, exist_ok=True)
    paths.SESSIONS_FILE.write_text(json.dumps(legacy))
    peers = store.list_peers()
    assert len(peers) == 1
    assert peers[0].name == "PLAT-3113-slave"
    # get_peer must also work
    fetched = store.get_peer("PLAT-3113-slave")
    assert fetched.session_id == "abc"
