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
    assert session.detect_session_id() == "abc-123"


def test_marker_for_register(relay_dir):
    session.write_marker_for_self("xyz")
    import os
    assert (relay_dir / f".sid-{os.getpid()}").read_text() == "xyz"
