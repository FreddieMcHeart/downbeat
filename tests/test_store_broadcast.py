from downbeat.core import store


def _peers(*names):
    for n in names:
        store.register_peer(name=n, session_id=f"s-{n}", cwd="/tmp", role="parent")


def test_broadcast_creates_one_message_per_target(relay_dir):
    _peers("a", "b", "c")
    bc = store.broadcast(from_peer="parent",
                         to_peers=["a", "b", "c"],
                         subject="run plan", body="atlantis plan")
    assert len(bc.message_ids) == 3
    targets = {store.get_message(mid).to_peer for mid in bc.message_ids}
    assert targets == {"a", "b", "c"}
    # All siblings share broadcast_id
    bids = {store.get_message(mid).broadcast_id for mid in bc.message_ids}
    assert bids == {bc.id}


def test_broadcast_status_aggregates_reply_state(relay_dir):
    _peers("a", "b")
    bc = store.broadcast(from_peer="parent", to_peers=["a", "b"],
                         subject="s", body="b")
    # 'a' reads and replies; 'b' does nothing
    a_msg_id = next(mid for mid in bc.message_ids
                    if store.get_message(mid).to_peer == "a")
    store.mark_read(a_msg_id)
    store.reply_to(a_msg_id, body="done", from_peer="a")
    status = store.broadcast_status(bc.id)
    by_target = {row["target"]: row for row in status}
    assert by_target["a"]["state"] == "replied"
    assert by_target["b"]["state"] == "pending"


def test_single_target_broadcast_is_just_one_message(relay_dir):
    _peers("only")
    bc = store.broadcast(from_peer="parent", to_peers=["only"],
                         subject="s", body="b")
    assert len(bc.message_ids) == 1


def test_broadcast_passes_kind_through_to_every_message(relay_dir):
    """#97 Decision 1: broadcast can express a non-task kind (e.g. status),
    which is the whole point -- an announcement to N peers should not
    create N obligations to reply."""
    _peers("a", "b")
    bc = store.broadcast(from_peer="parent", to_peers=["a", "b"],
                         subject="s", body="b", kind="status")
    kinds = {store.get_message(mid).kind for mid in bc.message_ids}
    assert kinds == {"status"}


def test_broadcast_default_kind_is_still_task(relay_dir):
    """#97 Decision 1: the default stays "task" -- send/reply both default
    to task and the TUI's existing broadcast call passes no kind, so
    flipping the default would silently change what it produces."""
    _peers("a")
    bc = store.broadcast(from_peer="parent", to_peers=["a"],
                         subject="s", body="b")
    assert store.get_message(bc.message_ids[0]).kind == "task"
