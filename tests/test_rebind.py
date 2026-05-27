"""Tests for /clear auto-rebind via (claude_pid, start_time) identity."""
import argparse

import pytest

from claude_relay.core import session, store


def test_register_records_claude_pid_and_start(relay_dir, monkeypatch):
    monkeypatch.setattr(session, "detect_live_claude_pid", lambda: 12345)
    monkeypatch.setattr(session, "process_start_time", lambda pid: "2026-05-27T09:11:11")
    monkeypatch.setattr(session, "detect_session_id", lambda: "sid-A")
    monkeypatch.setattr(session, "write_marker_for_self", lambda sid: None)
    monkeypatch.setattr(session, "gc_stale_markers", lambda: {"tmp": 0, "relay": 0})
    from claude_relay.cli.commands import relay_cmds
    args = argparse.Namespace(name="parent", role="parent")
    rc = relay_cmds.cmd_register(args)
    assert rc == 0
    peer = store.get_peer("parent")
    assert peer.claude_pid == 12345
    assert peer.claude_pid_start == "2026-05-27T09:11:11"


def test_rebind_session_updates_id_and_appends_history(relay_dir):
    store.register_peer(name="p", session_id="old-sid", cwd="/tmp", role="parent",
                        claude_pid=12345, claude_pid_start="2026-05-27T09:11:11")
    store.rebind_session("p", new_session_id="new-sid")
    peer = store.get_peer("p")
    assert peer.session_id == "new-sid"
    assert "old-sid" in peer.session_id_history
    assert peer.last_rebind_at is not None


def test_find_peer_by_claude_pid_strict_start(relay_dir):
    store.register_peer(name="p1", session_id="s1", cwd="/tmp", role="parent",
                        claude_pid=100, claude_pid_start="2026-01-01T00:00:00")
    store.register_peer(name="p2", session_id="s2", cwd="/tmp", role="parent",
                        claude_pid=100, claude_pid_start="2026-02-02T00:00:00")
    # Same PID, different start times — strict match returns only one
    matches = store.find_peer_by_claude_pid(100, "2026-01-01T00:00:00")
    assert len(matches) == 1
    assert matches[0].name == "p1"


def test_auto_rebind_on_session_mismatch(relay_dir, monkeypatch):
    # Setup: peer registered with claude_pid=12345
    store.register_peer(name="parent", session_id="old-sid",
                        cwd="/tmp", role="parent",
                        claude_pid=12345, claude_pid_start="2026-05-27T09:11:11")
    # Simulate /clear: new session_id, same PID
    monkeypatch.setattr(session, "detect_session_id", lambda: "new-sid")
    monkeypatch.setattr(session, "detect_live_claude_pid", lambda: 12345)
    monkeypatch.setattr(session, "process_start_time", lambda pid: "2026-05-27T09:11:11")
    from claude_relay.cli.commands.relay_cmds import _detect_peer_or_error
    name = _detect_peer_or_error(None)
    assert name == "parent"
    # And the peer's stored session_id was rebound
    assert store.get_peer("parent").session_id == "new-sid"
    assert "old-sid" in store.get_peer("parent").session_id_history


def test_auto_rebind_ambiguous_multiple_candidates(relay_dir, monkeypatch):
    # Two peers, same PID + start → ambiguous, must error out
    store.register_peer(name="A", session_id="sA", cwd="/tmp", role="parent",
                        claude_pid=12345, claude_pid_start="2026-05-27T09:11:11")
    store.register_peer(name="B", session_id="sB", cwd="/tmp", role="parent",
                        claude_pid=12345, claude_pid_start="2026-05-27T09:11:11")
    monkeypatch.setattr(session, "detect_session_id", lambda: "new-sid")
    monkeypatch.setattr(session, "detect_live_claude_pid", lambda: 12345)
    monkeypatch.setattr(session, "process_start_time", lambda pid: "2026-05-27T09:11:11")
    from claude_relay.cli.commands.relay_cmds import _detect_peer_or_error
    with pytest.raises(SystemExit) as exc:
        _detect_peer_or_error(None)
    assert exc.value.code == 2


def test_no_rebind_when_pid_mismatch(relay_dir, monkeypatch):
    # Peer registered with claude_pid=100, current pid=999 → no rebind, error
    store.register_peer(name="p", session_id="sX", cwd="/tmp", role="parent",
                        claude_pid=100, claude_pid_start="2026-05-27T09:11:11")
    monkeypatch.setattr(session, "detect_session_id", lambda: "completely-new-sid")
    monkeypatch.setattr(session, "detect_live_claude_pid", lambda: 999)
    monkeypatch.setattr(session, "process_start_time", lambda pid: "2026-05-27T09:11:11")
    from claude_relay.cli.commands.relay_cmds import _detect_peer_or_error
    with pytest.raises(SystemExit) as exc:
        _detect_peer_or_error(None)
    assert exc.value.code == 2
