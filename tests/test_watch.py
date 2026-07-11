"""Unit tests for poll_new (pure, no sleeping) and cmd_watch --once."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from downbeat.cli.__main__ import main
from downbeat.cli.commands.relay_cmds import _watch_emit
from downbeat.core import store
from downbeat.core.models import MessageState


def _peers(*names):
    for n in names:
        store.register_peer(name=n, session_id=f"s-{n}", cwd="/tmp", role="parent")


# ---------------------------------------------------------------------------
# 1. First poll with empty seen returns all NEW + populated seen
# ---------------------------------------------------------------------------
def test_poll_new_first_call_returns_all_new(relay_dir):
    _peers("p", "c")
    m1 = store.send_message(from_peer="p", to_peer="c", subject="s1", body="b1")
    m2 = store.send_message(from_peer="p", to_peer="c", subject="s2", body="b2")

    new_msgs, seen = store.poll_new("c", set())

    assert {m.id for m in new_msgs} == {m1.id, m2.id}
    assert seen == {m1.id, m2.id}


# ---------------------------------------------------------------------------
# 2. Second poll (same inbox, seen from #1) returns []
# ---------------------------------------------------------------------------
def test_poll_new_second_call_returns_empty(relay_dir):
    _peers("p", "c")
    store.send_message(from_peer="p", to_peer="c", subject="s", body="b")

    _, seen = store.poll_new("c", set())
    new_msgs, seen2 = store.poll_new("c", seen)

    assert new_msgs == []
    assert seen2 == seen  # seen unchanged (no new ids added)


# ---------------------------------------------------------------------------
# 3. Newly-added message appears on next poll; prior ones don't repeat
# ---------------------------------------------------------------------------
def test_poll_new_only_returns_incremental(relay_dir):
    _peers("p", "c")
    m1 = store.send_message(from_peer="p", to_peer="c", subject="first", body="x")

    _, seen = store.poll_new("c", set())  # seed seen with m1

    m2 = store.send_message(from_peer="p", to_peer="c", subject="second", body="y")
    new_msgs, seen2 = store.poll_new("c", seen)

    assert [m.id for m in new_msgs] == [m2.id]
    assert m1.id not in {m.id for m in new_msgs}
    assert {m1.id, m2.id} <= seen2


# ---------------------------------------------------------------------------
# 4. Archived / delivered messages are NOT returned (only NEW)
# ---------------------------------------------------------------------------
def test_poll_new_excludes_non_new_states(relay_dir):
    _peers("p", "c")
    # delivered state: drain moves it from inbox/ to delivered/
    m_delivered = store.send_message(from_peer="p", to_peer="c",
                                     subject="delivered", body="x")
    store.deliver_messages(peer_name="c", session_id="s-c")
    assert store.get_message(m_delivered.id).state == MessageState.DELIVERED

    # archived state: ack after deliver
    m_acked = store.send_message(from_peer="p", to_peer="c",
                                 subject="acked", body="y")
    store.deliver_messages(peer_name="c", session_id="s-c")
    store.ack_messages([m_acked.id])
    assert store.get_message(m_acked.id).state == MessageState.ARCHIVED

    # One genuinely NEW message
    m_new = store.send_message(from_peer="p", to_peer="c",
                               subject="still new", body="z")

    new_msgs, _ = store.poll_new("c", set())

    ids = {m.id for m in new_msgs}
    assert m_new.id in ids
    assert m_delivered.id not in ids
    assert m_acked.id not in ids


# ---------------------------------------------------------------------------
# 5. cmd_watch --once --peer X: exits 0; prints header when NEW exists
# ---------------------------------------------------------------------------
def test_cmd_watch_once_with_new_messages(relay_dir, capsys):
    _peers("p", "c")
    store.send_message(from_peer="p", to_peer="c", subject="hello", body="world")

    rc = main(["watch", "--peer", "c", "--once"])

    assert rc == 0
    out = capsys.readouterr().out
    assert "NEW RELAY MESSAGE(S):" in out
    assert "hello" in out


def test_cmd_watch_once_empty_inbox(relay_dir, capsys):
    _peers("p", "c")

    rc = main(["watch", "--peer", "c", "--once"])

    assert rc == 0
    out = capsys.readouterr().out
    # No new messages — output should be empty (no header)
    assert "NEW RELAY MESSAGE(S):" not in out


# ---------------------------------------------------------------------------
# _watch_emit tests — pure helper, no watcher involved
# ---------------------------------------------------------------------------

# 6. _watch_emit first call: empty seen prints all NEW + returns populated seen
def test_watch_emit_first_call_prints_all_new(relay_dir, capsys):
    _peers("p", "c")
    m1 = store.send_message(from_peer="p", to_peer="c", subject="msg1", body="b1")
    m2 = store.send_message(from_peer="p", to_peer="c", subject="msg2", body="b2")

    seen2 = _watch_emit("c", set())

    out = capsys.readouterr().out
    assert "NEW RELAY MESSAGE(S):" in out
    assert "msg1" in out
    assert "msg2" in out
    assert seen2 == {m1.id, m2.id}


# 7. _watch_emit second call (same seen): prints nothing, seen unchanged
def test_watch_emit_second_call_prints_nothing(relay_dir, capsys):
    _peers("p", "c")
    store.send_message(from_peer="p", to_peer="c", subject="msg1", body="b1")

    seen1 = _watch_emit("c", set())
    capsys.readouterr()  # flush

    seen2 = _watch_emit("c", seen1)

    out = capsys.readouterr().out
    assert "NEW RELAY MESSAGE(S):" not in out
    assert seen2 == seen1


# 8. _watch_emit with new message: prints only the new one
def test_watch_emit_prints_only_new_message(relay_dir, capsys):
    _peers("p", "c")
    m1 = store.send_message(from_peer="p", to_peer="c", subject="first", body="x")

    seen1 = _watch_emit("c", set())
    capsys.readouterr()  # flush

    m2 = store.send_message(from_peer="p", to_peer="c", subject="second", body="y")
    seen2 = _watch_emit("c", seen1)

    out = capsys.readouterr().out
    assert "second" in out
    assert "first" not in out
    assert m1.id in seen2
    assert m2.id in seen2


# 9. --poll flag causes make_watcher to receive prefer="poll"
def test_cmd_watch_poll_flag_selects_poll_watcher(relay_dir):
    _peers("p", "c")

    captured: dict = {}

    def fake_make_watcher(on_change, prefer="auto", poll_interval=2.0):
        captured["prefer"] = prefer
        captured["poll_interval"] = poll_interval
        return MagicMock()  # .start() and .stop() are no-ops

    mock_watcher_mod = MagicMock()
    mock_watcher_mod.make_watcher.side_effect = fake_make_watcher

    # Patch threading.Event so .wait() raises KeyboardInterrupt immediately,
    # unblocking cmd_watch without a real filesystem watcher or sleep.
    mock_event = MagicMock()
    mock_event.wait.side_effect = KeyboardInterrupt

    with patch("downbeat.cli.commands.relay_cmds.watcher_mod", mock_watcher_mod), \
         patch("downbeat.cli.commands.relay_cmds.threading") as mock_threading:
        mock_threading.Event.return_value = mock_event
        rc = main(["watch", "--peer", "c", "--poll"])

    assert captured.get("prefer") == "poll"
    assert rc == 0
