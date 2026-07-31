"""Tests for issue #89 — the two halves of register's collision guard.

1. The refusal's printed remedy ("omit --parent") is correct only from the
   session that owns the record, and destructive from any other, because
   `register <name>` takes its subject from the CALLING session and omitting
   --parent skips the only check that fired.

2. The guard refuses on a PARENT mismatch and merely happens to prevent a
   session takeover as a side effect. Incidental protection is not protection:
   nothing checks whether proceeding would repoint session_id onto a different
   LIVE session, and nothing records that the parent check was doing it.
"""
import pytest

from downbeat.core import session, store
from downbeat.core.errors import PeerReparentConflict, PeerSessionTakeover


def _register(name, sid, *, parent=None, role="parent", pid=None, start=None):
    return store.register_peer(name=name, session_id=sid, cwd="/tmp", role=role,
                               claude_pid=pid, claude_pid_start=start,
                               parent=parent)


# --- half 1: the printed remedy carries its precondition ------------------


def test_remedy_offers_reattach_when_caller_owns_the_record(relay_dir):
    """From the record's own session, "omit --parent" is safe and correct."""
    _register("Parent-A", "sid-a")
    _register("Parent-B", "sid-b")
    _register("Dev One", "sid-owner", parent="Parent-A", role="child")

    with pytest.raises(PeerReparentConflict) as exc:
        store.register_peer(name="Dev One", session_id="sid-owner", cwd="/tmp",
                            role="child", parent="Parent-B")

    msg = str(exc.value)
    assert "omit --parent" in msg
    assert "set-parent" in msg


def test_remedy_withheld_when_caller_is_not_the_records_session(relay_dir):
    """From any other session it would take the binding, so it is not offered.

    This is the defect: the way out printed by the error, followed literally
    from the terminal where that error most often appears, re-creates the
    collision the guard just prevented.
    """
    _register("Parent-A", "sid-a")
    _register("Parent-B", "sid-b")
    _register("Dev One", "sid-owner", parent="Parent-A", role="child")

    with pytest.raises(PeerReparentConflict) as exc:
        store.register_peer(name="Dev One", session_id="sid-STRANGER", cwd="/tmp",
                            role="child", parent="Parent-B")

    msg = str(exc.value)
    assert "omit --parent" not in msg
    # It must still say what IS safe, rather than merely refusing.
    assert "set-parent" in msg
    assert "sid-owner"[:8] in msg or "different session" in msg


# --- half 2: the session takeover is checked, not incidentally prevented ---


def test_refuses_to_take_a_binding_from_a_demonstrably_live_incumbent(
        relay_dir, monkeypatch):
    """A different session cannot silently become an existing live peer."""
    _register("Dev One", "sid-owner", pid=4242, start="2026-07-31T10:00:00")
    monkeypatch.setattr(session, "_process_is_claude", lambda pid: pid == 4242)
    monkeypatch.setattr(session, "process_start_time",
                        lambda pid: "2026-07-31T10:00:00")

    with pytest.raises(PeerSessionTakeover) as exc:
        _register("Dev One", "sid-STRANGER", pid=9999, start="2026-07-31T12:00:00")

    msg = str(exc.value)
    assert "Dev One" in msg
    assert "downbeat rebind" in msg
    assert store.get_peer("Dev One").session_id == "sid-owner"


def test_allows_reattach_when_the_incumbent_process_is_gone(relay_dir, monkeypatch):
    """The normal resume path: same agent, new session id, old process dead."""
    _register("Dev One", "sid-old", pid=4242, start="2026-07-31T10:00:00")
    monkeypatch.setattr(session, "_process_is_claude", lambda pid: False)

    _register("Dev One", "sid-new", pid=8888, start="2026-07-31T12:00:00")
    assert store.get_peer("Dev One").session_id == "sid-new"


def test_allows_reattach_when_the_incumbent_pid_was_recycled(relay_dir, monkeypatch):
    """Alive is not enough -- a recycled pid is a different process.

    Start time is what distinguishes them, and a mismatch means the claude
    that held this record is gone even though something answers to its pid.
    """
    _register("Dev One", "sid-old", pid=4242, start="2026-07-31T10:00:00")
    monkeypatch.setattr(session, "_process_is_claude", lambda pid: True)
    monkeypatch.setattr(session, "process_start_time",
                        lambda pid: "2026-07-31T11:59:00")

    _register("Dev One", "sid-new", pid=4242, start="2026-07-31T11:59:00")
    assert store.get_peer("Dev One").session_id == "sid-new"


def test_proceeds_when_incumbent_liveness_is_unknown(relay_dir, monkeypatch):
    """Unknown must not silently become either answer.

    A record with no recorded pid cannot be proven live, and refusing would
    block legitimate reattach for every peer registered before pids were
    stored. It proceeds -- but the store logs that the check could not run,
    so the absence of a refusal is not mistaken for a passed check.
    """
    _register("Dev One", "sid-old", pid=None, start=None)
    calls = []
    monkeypatch.setattr(store._log, "warning",
                        lambda msg, *a, **k: calls.append(msg % a if a else msg))

    _register("Dev One", "sid-new", pid=8888, start="2026-07-31T12:00:00")

    assert store.get_peer("Dev One").session_id == "sid-new"
    assert any("liveness" in c or "unknown" in c for c in calls), calls


def test_same_session_reregistering_is_never_a_takeover(relay_dir, monkeypatch):
    """Re-registering yourself is not taking anything, live process or not."""
    _register("Dev One", "sid-owner", pid=4242, start="2026-07-31T10:00:00")
    monkeypatch.setattr(session, "_process_is_claude", lambda pid: True)
    monkeypatch.setattr(session, "process_start_time",
                        lambda pid: "2026-07-31T10:00:00")

    _register("Dev One", "sid-owner", pid=4242, start="2026-07-31T10:00:00")
    assert store.get_peer("Dev One").session_id == "sid-owner"


def test_a_brand_new_name_is_unaffected(relay_dir, monkeypatch):
    monkeypatch.setattr(session, "_process_is_claude", lambda pid: True)
    _register("Fresh", "sid-fresh", pid=4242, start="2026-07-31T10:00:00")
    assert store.get_peer("Fresh").session_id == "sid-fresh"
