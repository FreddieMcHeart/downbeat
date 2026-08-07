import subprocess
import sys

import pytest

from downbeat.core import store
from downbeat.core.errors import (
    AmbiguousParent,
    InvalidParent,
    PeerNotFound,
    PeerReparentConflict,
)


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


def _parent_of(name):
    return next(p.parent for p in store.list_peers() if p.name == name)


def test_remove_interior_node_promotes_children_to_grandparent(relay_dir):
    """#19: removing a node must not leave its children's parent pointers
    dangling -- that made them vanish from every acting-as view while still
    living on disk and accepting messages. Promote them to the removed node's
    own parent (the natural tree semantic)."""
    store.register_peer(name="Root", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="Mid", session_id="s2", cwd="/tmp", role="parent")
    store.set_parent("Mid", "Root")
    store.register_peer(name="W1", session_id="s3", cwd="/tmp", role="child", parent="Mid")
    store.register_peer(name="W2", session_id="s4", cwd="/tmp", role="child", parent="Mid")

    store.remove_peer("Mid")

    assert "Mid" not in {p.name for p in store.list_peers()}
    # W1, W2 reattached to Root -- not left pointing at the gone 'Mid'
    assert _parent_of("W1") == "Root"
    assert _parent_of("W2") == "Root"
    # And they're reachable again: Root's children view includes them.
    assert {p.name for p in store.children_of("Root")} == {"Root", "W1", "W2"}


def test_remove_root_makes_its_children_roots(relay_dir):
    """Removing a root (no parent of its own) leaves its children as roots,
    not dangling."""
    store.register_peer(name="Root", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="C1", session_id="s2", cwd="/tmp", role="child", parent="Root")
    store.remove_peer("Root")
    assert _parent_of("C1") is None


def test_remove_leaf_touches_no_one(relay_dir):
    store.register_peer(name="Root", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="C1", session_id="s2", cwd="/tmp", role="child", parent="Root")
    store.register_peer(name="C2", session_id="s3", cwd="/tmp", role="child", parent="Root")
    store.remove_peer("C1")
    assert _parent_of("C2") == "Root"


def test_gc_sweep_removing_parent_and_child_together_keeps_a_forest(relay_dir):
    """GcStaleModal removes many peers in one loop. Whatever order a parent
    and its child come off in, no pointer may end up dangling."""
    store.register_peer(name="Root", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="Mid", session_id="s2", cwd="/tmp", role="parent")
    store.set_parent("Mid", "Root")
    store.register_peer(name="Leaf", session_id="s3", cwd="/tmp", role="child", parent="Mid")
    # Remove child then parent (one valid sweep order)
    store.remove_peer("Mid")
    assert _parent_of("Leaf") == "Root"
    store.remove_peer("Root")
    assert _parent_of("Leaf") is None
    # every surviving parent pointer resolves to a real peer (forest intact)
    names = {p.name for p in store.list_peers()}
    for p in store.list_peers():
        assert p.parent is None or p.parent in names


def test_touch_peer_updates_last_seen(relay_dir):
    store.register_peer(name="p", session_id="s-1", cwd="/tmp", role="parent")
    before = store.get_peer("p").last_seen
    store.touch_peer("p")
    after = store.get_peer("p").last_seen
    assert after >= before


def test_reply_to_touches_the_replying_peers_last_seen(relay_dir, monkeypatch):
    """#104: built from the incident, not the happy path. A test that SENDS
    passes against the pre-fix code and proves nothing about reply_to -- this
    one drives reply_to specifically and pins the new value with a
    monkeypatched clock so a no-op touch can't hide behind real-time
    coincidence."""
    store.register_peer(name="p", session_id="s-1", cwd="/tmp", role="parent")
    store.register_peer(name="other", session_id="s-2", cwd="/tmp", role="parent")
    msg = store.send_message("other", "p", "hi", "body")
    before = store.get_peer("p").last_seen

    monkeypatch.setattr(store, "now_iso", lambda: "2099-01-01T00:00:00+00:00")
    store.reply_to(msg.id, "reply body", from_peer="p")

    after = store.get_peer("p").last_seen
    assert after == "2099-01-01T00:00:00+00:00"
    assert after != before


def test_reply_to_from_unregistered_peer_does_not_raise(relay_dir):
    """The touch is best-effort (#104): reply_to's own docstring context
    already bypasses the peer check for from_peer (broadcast fan-out case),
    so an unregistered replier must not turn a successful reply into a
    PeerNotFound error."""
    store.register_peer(name="p", session_id="s-1", cwd="/tmp", role="parent")
    msg = store.send_message("p", "p", "hi", "body")
    reply = store.reply_to(msg.id, "reply body", from_peer="ghost-peer")
    assert reply.from_peer == "ghost-peer"


# --- Concurrent read-modify-write race (PR #74 review) --------------------
#
# touch_peer/register_peer/rebind_session all do
#   sessions = _load_sessions(); ...mutate...; _save_sessions(sessions)
# against the SAME sessions.json, with no lock. Wiring touch_peer into every
# send/drain (#72) made that unlocked snapshot-of-the-whole-registry hot: two
# real OS processes -- one repeatedly touching an existing peer (what a busy
# sender/drainer now does), one concurrently registering brand-new peers --
# can race, and whichever saves last silently reverts whatever the other one
# just wrote (the exact failure mode of #71: a reverted registration).
#
# This MUST use two real subprocesses, not two calls from one process /
# thread: the GIL would serialize the Python-level dict mutations and the
# test would pass for a reason that says nothing about the actual disk race.
# Each worker monkeypatches store._save_sessions to sleep briefly between its
# own load and save, deterministically widening the interleave window so the
# race reproduces every run instead of depending on incidental OS timing.

_TOUCH_WORKER = """
import sys, time
from downbeat.core import store
from downbeat.core.errors import PeerNotFound

_orig_save = store._save_sessions
def _slow_save(data):
    time.sleep(0.05)
    _orig_save(data)
store._save_sessions = _slow_save

n = int(sys.argv[1])
name = sys.argv[2]
for _ in range(n):
    try:
        store.touch_peer(name)
    except PeerNotFound:
        pass
"""

_REGISTER_WORKER = """
import sys, time
from downbeat.core import store

_orig_save = store._save_sessions
def _slow_save(data):
    time.sleep(0.05)
    _orig_save(data)
store._save_sessions = _slow_save

n = int(sys.argv[1])
prefix = sys.argv[2]
for i in range(n):
    store.register_peer(name=f"{prefix}{i}", session_id=f"s-{prefix}{i}",
                        cwd="/tmp", role="parent")
"""


def test_touch_peer_concurrent_with_register_peer_does_not_lose_writes(relay_dir):
    store.register_peer(name="p", session_id="s-p", cwd="/tmp", role="parent")

    n = 20
    touch_proc = subprocess.Popen([sys.executable, "-c", _TOUCH_WORKER, str(n), "p"])
    register_proc = subprocess.Popen(
        [sys.executable, "-c", _REGISTER_WORKER, str(n), "q"])
    assert touch_proc.wait(timeout=60) == 0
    assert register_proc.wait(timeout=60) == 0

    names = {peer.name for peer in store.list_peers()}
    expected = {f"q{i}" for i in range(n)}
    missing = expected - names
    assert not missing, (
        f"lost {len(missing)}/{n} concurrent registrations to an unlocked "
        f"touch_peer read-modify-write race: {sorted(missing)[:5]}"
    )
    # touch_peer's own target must survive too -- not just the registrations.
    assert "p" in names


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


def test_remove_heals_a_corrupt_cycle_instead_of_forwarding_it(relay_dir):
    """remove_peer is the one tree mutator with no _check_no_cycle gate, so a
    hand-corrupted sessions.json is the only way a cycle reaches it. Rather
    than forwarding the corruption (a 2-cycle A<->B would mint a self-parent
    B->B when A is removed), promotion to a vanished grandparent falls back to
    root. Removal heals."""
    import json

    from downbeat.core import paths
    paths.SESSIONS_FILE.write_text(json.dumps({
        "A": {"name": "A", "session_id": "s1", "cwd": "/tmp", "role": "parent",
              "registered_at": "t", "last_seen": "t", "parent": "B"},
        "B": {"name": "B", "session_id": "s2", "cwd": "/tmp", "role": "parent",
              "registered_at": "t", "last_seen": "t", "parent": "A"},
    }))
    store.remove_peer("A")
    # B must NOT end up its own parent; it becomes a root.
    assert _parent_of("B") is None


def test_remove_heals_a_dangling_grandparent(relay_dir):
    """If the removed node's own parent already points at a gone name, the
    orphans fall back to root rather than inheriting a fresh dangling pointer."""
    import json

    from downbeat.core import paths
    paths.SESSIONS_FILE.write_text(json.dumps({
        "Mid": {"name": "Mid", "session_id": "s1", "cwd": "/tmp", "role": "parent",
                "registered_at": "t", "last_seen": "t", "parent": "GHOST"},
        "W": {"name": "W", "session_id": "s2", "cwd": "/tmp", "role": "child",
              "registered_at": "t", "last_seen": "t", "parent": "Mid"},
    }))
    store.remove_peer("Mid")
    assert _parent_of("W") is None


# --- issue #70: register_peer must refuse to silently re-home a name that
# already belongs to a different parent, instead of overwriting it. Option
# (b) from the issue: names stay globally unique; the collision becomes an
# explicit, actionable refusal instead of a silent overwrite. ---

def test_register_explicit_parent_conflicting_with_stored_raises(relay_dir):
    store.register_peer(name="parent-a", session_id="s-1", cwd="/tmp", role="parent")
    store.register_peer(name="parent-b", session_id="s-2", cwd="/tmp", role="parent")
    store.register_peer(name="Dev One", session_id="s-3", cwd="/tmp", role="child",
                        parent="parent-a")
    with pytest.raises(PeerReparentConflict):
        store.register_peer(name="Dev One", session_id="s-4", cwd="/tmp", role="child",
                            parent="parent-b")
    # Refusal must not write -- the peer's parent must be unchanged.
    assert store.get_peer("Dev One").parent == "parent-a"


def test_register_conflict_message_is_actionable(relay_dir):
    """The refusal must state the existing peer's current parent, when it was
    registered, and how many messages it holds -- a bare 'name taken' is not
    enough, since the whole point is showing the human what they'd destroy."""
    store.register_peer(name="parent-a", session_id="s-1", cwd="/tmp", role="parent")
    store.register_peer(name="parent-b", session_id="s-2", cwd="/tmp", role="parent")
    store.register_peer(name="Dev One", session_id="s-3", cwd="/tmp", role="child",
                        parent="parent-a")
    store.send_message(from_peer="parent-a", to_peer="Dev One",
                       subject="s1", body="x")
    store.send_message(from_peer="parent-a", to_peer="Dev One",
                       subject="s2", body="x")
    with pytest.raises(PeerReparentConflict) as exc_info:
        store.register_peer(name="Dev One", session_id="s-4", cwd="/tmp", role="child",
                            parent="parent-b")
    message = str(exc_info.value)
    assert "parent-a" in message                # existing parent
    assert "Dev One" in message
    registered_at = store.get_peer("Dev One").registered_at
    assert registered_at in message              # when it was registered
    assert "2" in message                        # message count (inbox)
    assert "set-parent" in message               # the escape hatch


def test_register_explicit_parent_equal_to_stored_is_not_a_conflict(relay_dir):
    store.register_peer(name="parent-a", session_id="s-1", cwd="/tmp", role="parent")
    store.register_peer(name="Dev One", session_id="s-2", cwd="/tmp", role="child",
                        parent="parent-a")
    # Re-registering with the SAME explicit parent must succeed -- it isn't a
    # conflict, it's confirming the existing pairing.
    again = store.register_peer(name="Dev One", session_id="s-3", cwd="/tmp",
                                role="child", parent="parent-a")
    assert again.parent == "parent-a"


def test_register_no_parent_argument_reattaches_as_today(relay_dir):
    """The plain resume/reattach path (no --parent passed at all) must behave
    exactly as before this fix -- carry the existing parent over silently,
    no error, no --reparent needed."""
    store.register_peer(name="parent-a", session_id="s-1", cwd="/tmp", role="parent")
    store.register_peer(name="Dev One", session_id="s-2", cwd="/tmp", role="child",
                        parent="parent-a")
    again = store.register_peer(name="Dev One", session_id="s-3", cwd="/tmp", role="child")
    assert again.parent == "parent-a"
    assert again.session_id == "s-3"


def test_register_genuinely_new_name_unaffected(relay_dir):
    store.register_peer(name="parent-a", session_id="s-1", cwd="/tmp", role="parent")
    store.register_peer(name="parent-b", session_id="s-2", cwd="/tmp", role="parent")
    peer = store.register_peer(name="Brand New", session_id="s-3", cwd="/tmp",
                               role="child", parent="parent-b")
    assert peer.parent == "parent-b"


def test_register_peer_with_no_parent_reregistered_stays_rootless(relay_dir):
    """A role=parent peer with parent=None (a root), re-registered with no
    --parent, must stay parentless and must not raise -- this is the
    plain-resume path applied to a root peer specifically, since a naive
    conflict check keyed on truthiness of the stored parent could special-case
    None incorrectly."""
    store.register_peer(name="Root One", session_id="s-1", cwd="/tmp", role="parent")
    again = store.register_peer(name="Root One", session_id="s-2", cwd="/tmp",
                                role="parent")
    assert again.parent is None
