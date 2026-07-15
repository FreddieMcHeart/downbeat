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


def test_register_child_explicit_parent_can_be_a_child_peer(relay_dir):
    """A role=child peer is now a valid --parent target -- it becomes an
    interior node (structurally both a child and a parent)."""
    store.register_peer(name="parent", session_id="s-1", cwd="/tmp", role="parent")
    store.register_peer(name="other-child", session_id="s-2", cwd="/tmp", role="child",
                        parent="parent")
    grandchild = store.register_peer(name="child", session_id="s-3", cwd="/tmp",
                                     role="child", parent="other-child")
    assert grandchild.parent == "other-child"


def test_register_fresh_parent_role_peer_has_no_parent_value(relay_dir):
    """A *freshly* registered role=parent peer starts as a tree root. It can
    still be given a parent later (see the interior-node tests below) --
    role is not a structural gate."""
    p = store.register_peer(name="p", session_id="s-1", cwd="/tmp", role="parent")
    assert p.parent is None


def test_reregister_parent_role_interior_node_preserves_parent(relay_dir):
    """A role=parent peer that was given a parent via set_parent (an
    interior node) must keep it on a plain re-register with no --parent --
    parent-preservation must not be scoped to role=child only, now that
    role=parent peers can be interior nodes too."""
    store.register_peer(name="root", session_id="s-1", cwd="/tmp", role="parent")
    store.register_peer(name="mid", session_id="s-2", cwd="/tmp", role="parent")
    store.set_parent("mid", "root")
    again = store.register_peer(name="mid", session_id="s-2", cwd="/tmp", role="parent")
    assert again.parent == "root"


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


def test_set_parent_target_can_be_a_child_peer(relay_dir):
    """Repointing a peer's parent to another role=child peer is now valid --
    the target becomes an interior node."""
    store.register_peer(name="parent", session_id="s-1", cwd="/tmp", role="parent")
    store.register_peer(name="child", session_id="s-2", cwd="/tmp", role="child",
                        parent="parent")
    store.register_peer(name="other-child", session_id="s-3", cwd="/tmp", role="child",
                        parent="parent")
    updated = store.set_parent("child", "other-child")
    assert updated.parent == "other-child"


def test_set_parent_on_a_parent_peer_is_now_valid(relay_dir):
    """A role=parent peer can now also have its own parent -- role is no
    longer a structural gate."""
    store.register_peer(name="parent", session_id="s-1", cwd="/tmp", role="parent")
    store.register_peer(name="parent-2", session_id="s-2", cwd="/tmp", role="parent")
    updated = store.set_parent("parent", "parent-2")
    assert updated.parent == "parent-2"


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


def test_set_parent_direct_two_node_cycle_raises(relay_dir):
    from downbeat.core.errors import CycleDetected
    store.register_peer(name="A", session_id="s-1", cwd="/tmp", role="parent")
    store.register_peer(name="B", session_id="s-2", cwd="/tmp", role="child", parent="A")
    with pytest.raises(CycleDetected):
        store.set_parent("A", "B")


def test_register_explicit_parent_cycle_raises(relay_dir):
    """_check_no_cycle guards BOTH writers -- set_parent and register_peer's
    explicit --parent. Covering only set_parent would let a regression that
    drops the check from _resolve_parent through unnoticed."""
    from downbeat.core.errors import CycleDetected
    store.register_peer(name="A", session_id="s-1", cwd="/tmp", role="parent")
    store.register_peer(name="B", session_id="s-2", cwd="/tmp", role="child", parent="A")
    with pytest.raises(CycleDetected):
        store.register_peer(name="A", session_id="s-1", cwd="/tmp", role="parent",
                            parent="B")


def test_set_parent_self_parent_raises(relay_dir):
    from downbeat.core.errors import CycleDetected
    store.register_peer(name="A", session_id="s-1", cwd="/tmp", role="parent")
    with pytest.raises(CycleDetected):
        store.set_parent("A", "A")


def test_set_parent_multi_hop_cycle_raises(relay_dir):
    from downbeat.core.errors import CycleDetected
    store.register_peer(name="A", session_id="s-1", cwd="/tmp", role="parent")
    store.register_peer(name="B", session_id="s-2", cwd="/tmp", role="child", parent="A")
    store.register_peer(name="C", session_id="s-3", cwd="/tmp", role="child", parent="B")
    with pytest.raises(CycleDetected):
        store.set_parent("A", "C")


def test_set_parent_cycle_error_message_lists_the_chain(relay_dir):
    from downbeat.core.errors import CycleDetected
    store.register_peer(name="A", session_id="s-1", cwd="/tmp", role="parent")
    store.register_peer(name="B", session_id="s-2", cwd="/tmp", role="child", parent="A")
    store.register_peer(name="C", session_id="s-3", cwd="/tmp", role="child", parent="B")
    with pytest.raises(CycleDetected) as exc_info:
        store.set_parent("A", "C")
    message = str(exc_info.value)
    assert "A" in message
    assert "B" in message
    assert "C" in message


def test_set_parent_valid_deep_chain_accepted(relay_dir):
    store.register_peer(name="L1", session_id="s-1", cwd="/tmp", role="parent")
    store.register_peer(name="L2", session_id="s-2", cwd="/tmp", role="child", parent="L1")
    store.register_peer(name="L3", session_id="s-3", cwd="/tmp", role="child", parent="L2")
    store.register_peer(name="L4", session_id="s-4", cwd="/tmp", role="child", parent="L3")
    store.register_peer(name="L5", session_id="s-5", cwd="/tmp", role="child", parent="L4")
    assert store.get_peer("L5").parent == "L4"
    assert store.get_peer("L1").parent is None


def test_autonomy_role_unchanged_when_gaining_children(relay_dir):
    store.register_peer(name="Root", session_id="s-1", cwd="/tmp", role="parent")
    store.register_peer(name="Child-A", session_id="s-2", cwd="/tmp", role="child",
                        parent="Root")
    store.register_peer(name="Child-A-1", session_id="s-3", cwd="/tmp", role="child",
                        parent="Child-A")
    # Child-A just gained its own child -- its own role/autonomy must not
    # have changed as a side effect.
    assert store.get_peer("Child-A").role == "child"


def test_acting_as_candidates_excludes_pure_leaf(relay_dir):
    store.register_peer(name="Root", session_id="s-1", cwd="/tmp", role="parent")
    store.register_peer(name="Leaf", session_id="s-2", cwd="/tmp", role="child",
                        parent="Root")
    names = {p.name for p in store.acting_as_candidates()}
    assert "Leaf" not in names


def test_acting_as_candidates_includes_childless_parent_role(relay_dir):
    store.register_peer(name="Root", session_id="s-1", cwd="/tmp", role="parent")
    names = {p.name for p in store.acting_as_candidates()}
    assert names == {"Root"}


def test_acting_as_candidates_includes_interior_child_role_node(relay_dir):
    store.register_peer(name="Root", session_id="s-1", cwd="/tmp", role="parent")
    store.register_peer(name="Child-A", session_id="s-2", cwd="/tmp", role="child",
                        parent="Root")
    store.register_peer(name="Child-A-1", session_id="s-3", cwd="/tmp", role="child",
                        parent="Child-A")
    names = {p.name for p in store.acting_as_candidates()}
    assert names == {"Root", "Child-A"}


def test_acting_as_candidates_no_duplicate_for_parent_role_with_children(relay_dir):
    store.register_peer(name="Root", session_id="s-1", cwd="/tmp", role="parent")
    store.register_peer(name="Child", session_id="s-2", cwd="/tmp", role="child",
                        parent="Root")
    candidates = store.acting_as_candidates()
    names = [p.name for p in candidates]
    assert names.count("Root") == 1
