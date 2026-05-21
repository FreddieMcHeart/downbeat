from claude_relay.core import session


def test_detect_returns_none_when_no_markers(monkeypatch, tmp_path):
    monkeypatch.setenv("CLAUDE_RELAY_DIR", str(tmp_path))
    import importlib

    from claude_relay.core import paths
    importlib.reload(paths)
    importlib.reload(session)
    # Stop ancestor walking so no PID is checked against real markers
    monkeypatch.setattr(session, "_walk_ancestors", lambda: iter([]))
    assert session.detect_session_id() is None


def test_detect_via_marker_file(relay_dir, monkeypatch):
    # Write a marker for our own pid
    import os
    marker = relay_dir / f".sid-{os.getpid()}"
    marker.write_text("abc-123")
    # Force the walker to yield our own pid
    monkeypatch.setattr(session, "_walk_ancestors", lambda: iter([os.getpid()]))
    # Pretend this process is 'claude' so the marker is trusted
    monkeypatch.setattr(session, "_process_is_claude", lambda pid: True)
    assert session.detect_session_id() == "abc-123"


def test_marker_for_register(relay_dir):
    session.write_marker_for_self("xyz")
    import os
    assert (relay_dir / f".sid-{os.getpid()}").read_text() == "xyz"


def test_detect_skips_marker_when_pid_is_not_claude(relay_dir, monkeypatch):
    """If an ancestor PID has a marker but the PID is not a claude process
    (dead or recycled), detect_session_id must skip it and look at the next
    ancestor."""
    import os
    pid = os.getpid()
    monkeypatch.setattr(session, "_walk_ancestors", lambda: iter([pid]))
    # Write a marker for our own PID (this Python test process is NOT claude)
    marker = relay_dir / f".sid-{pid}"
    marker.write_text("stale-session-id")
    # Detect should skip our marker because we're not a claude process
    assert session.detect_session_id() is None


def test_gc_stale_markers_removes_dead_pid_markers(relay_dir):
    """gc_stale_markers prunes markers whose PIDs are not live claude procs."""
    # Plant a marker with an impossible PID (negative or unlikely value)
    (relay_dir / ".sid-99999999").write_text("ghost-session")
    counts = session.gc_stale_markers()
    assert counts["relay"] >= 1
    assert not (relay_dir / ".sid-99999999").exists()
