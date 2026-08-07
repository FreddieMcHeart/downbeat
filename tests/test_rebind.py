"""Tests for /clear auto-rebind via (claude_pid, start_time) identity."""
import argparse

import pytest

from downbeat.core import session, store
from downbeat.core.errors import PeerSessionTakeover


def test_register_records_claude_pid_and_start(relay_dir, monkeypatch):
    monkeypatch.setattr(session, "detect_live_claude_pid", lambda: 12345)
    monkeypatch.setattr(session, "process_start_time", lambda pid: "2026-05-27T09:11:11")
    monkeypatch.setattr(session, "detect_session_id", lambda: "sid-A")
    monkeypatch.setattr(session, "write_marker_for_self", lambda sid: None)
    monkeypatch.setattr(session, "gc_stale_markers", lambda: {"tmp": 0, "relay": 0})
    from downbeat.cli.commands import relay_cmds
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
    from downbeat.cli.commands.relay_cmds import _detect_peer_or_error
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
    from downbeat.cli.commands.relay_cmds import _detect_peer_or_error
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
    from downbeat.cli.commands.relay_cmds import _detect_peer_or_error
    with pytest.raises(SystemExit) as exc:
        _detect_peer_or_error(None)
    assert exc.value.code == 2


# --- #100: rebind rewrites session-describing fields as a set -------------


def test_rebind_auto_detected_refreshes_pid_and_cwd(relay_dir, monkeypatch, tmp_path):
    """Built from the incident, not the happy path (#100). A rebind with
    new_session_id omitted means the CALLER is the session -- claude_pid,
    claude_pid_start and cwd must all refresh to describe the calling
    process, or #95's takeover guard evaluates a process that no longer
    owns the record. A test that only checks session_id passes against the
    pre-fix code (test_rebind_session_updates_id_and_appends_history above
    does exactly that) and proves nothing about this class."""
    store.register_peer(name="p", session_id="sid-A", cwd="/old/cwd", role="parent",
                        claude_pid=1111, claude_pid_start="2026-01-01T00:00:00")
    new_cwd = tmp_path / "new-cwd"
    new_cwd.mkdir()
    monkeypatch.chdir(new_cwd)
    monkeypatch.setattr(session, "detect_session_id", lambda: "sid-B")
    monkeypatch.setattr(session, "detect_live_claude_pid", lambda: 2222)
    monkeypatch.setattr(session, "process_start_time",
                        lambda pid: "2026-02-02T00:00:00")

    store.rebind_session("p")  # new_session_id omitted -> auto-detect

    peer = store.get_peer("p")
    assert peer.session_id == "sid-B"
    assert peer.claude_pid == 2222
    assert peer.claude_pid_start == "2026-02-02T00:00:00"
    assert peer.cwd == str(new_cwd)


def test_rebind_explicit_session_id_clears_pid_leaves_cwd(relay_dir):
    """new_session_id passed explicitly means the caller acts FOR another
    session -- it cannot know that session's pid, so claude_pid/
    claude_pid_start must be CLEARED to None rather than left describing
    the OLD process. cwd is left (display-only, tui/screens/peers.py)."""
    store.register_peer(name="p", session_id="sid-A", cwd="/kept/cwd", role="parent",
                        claude_pid=1111, claude_pid_start="2026-01-01T00:00:00")

    store.rebind_session("p", new_session_id="sid-B")

    peer = store.get_peer("p")
    assert peer.session_id == "sid-B"
    assert peer.claude_pid is None
    assert peer.claude_pid_start is None
    assert peer.cwd == "/kept/cwd"


def test_rebind_then_register_from_different_session_refused_while_alive(
        relay_dir, monkeypatch):
    """The #95 takeover guard must protect a REBOUND record, not only a
    freshly registered one. Before the fix, rebind left claude_pid
    describing the OLD process; _incumbent_liveness read that stale pid,
    found it dead, and let a different live session silently take the
    binding -- the guard ran and protected nothing."""
    store.register_peer(name="p", session_id="sid-A", cwd="/tmp", role="parent",
                        claude_pid=1111, claude_pid_start="2026-01-01T00:00:00")
    monkeypatch.setattr(session, "detect_session_id", lambda: "sid-B")
    monkeypatch.setattr(session, "detect_live_claude_pid", lambda: 2222)
    monkeypatch.setattr(session, "process_start_time",
                        lambda pid: "2026-02-02T00:00:00")
    store.rebind_session("p")  # -> session B, pid 2222

    # Session B's process is still alive.
    monkeypatch.setattr(session, "_process_is_claude", lambda pid: pid == 2222)

    with pytest.raises(PeerSessionTakeover):
        store.register_peer(name="p", session_id="sid-C", cwd="/tmp", role="parent",
                            claude_pid=3333, claude_pid_start="2026-03-03T00:00:00")
    assert store.get_peer("p").session_id == "sid-B"
