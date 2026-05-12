from claude_relay.core import store
from claude_relay.core.models import MessageState


def _peers(*names):
    for n in names:
        store.register_peer(name=n, session_id=f"s-{n}", cwd="/tmp", role="child")


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
