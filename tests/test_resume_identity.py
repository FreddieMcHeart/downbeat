"""Tests for the resume self-heal path (issue #71).

Resume assigns a NEW session id by design, so the pre-existing (claude_pid,
claude_pid_start)-based auto-rebind — which only covers `/clear` (same OS
process, new session id) — never fires for resume (new process AND new
session id). `_detect_peer_or_error` cannot fall back to a claim like "the
peer name is ours": the process has no trustworthy way to assert that. The
only provable signal available is `session_id_history`, which
`register_peer`/`rebind_session` already maintain: if the CURRENT session id
was, at some earlier point, itself the live `session_id` of exactly one peer
(e.g. resuming back into an older checkpoint whose id was later superseded),
that is provable lineage and self-heal may rebind. If it matches none, or
more than one peer's history, refusing is mandatory — silently guessing would
bind the session to the wrong identity, which is worse than an error.
"""
import pytest

from downbeat.core import session, store


def test_find_peer_by_session_history_matches_exactly_one(relay_dir):
    store.register_peer(name="p", session_id="resumed-sid", cwd="/tmp", role="parent")
    store.rebind_session("p", new_session_id="live-sid")
    matches = store.find_peer_by_session_history("resumed-sid")
    assert len(matches) == 1
    assert matches[0].name == "p"


def test_find_peer_by_session_history_no_match(relay_dir):
    store.register_peer(name="p", session_id="live-sid", cwd="/tmp", role="parent")
    assert store.find_peer_by_session_history("never-seen-sid") == []


def test_detect_peer_rebinds_on_provable_history_match(relay_dir, monkeypatch):
    # peer "p" resumed once already (manually reconciled): history=[resumed-sid],
    # live=live-sid. Now the session detects as resumed-sid again (e.g. resume
    # picked the older checkpoint back up) — provable lineage, self-heal must
    # rebind rather than error.
    store.register_peer(name="p", session_id="resumed-sid", cwd="/tmp", role="parent")
    store.rebind_session("p", new_session_id="live-sid")
    monkeypatch.setattr(session, "detect_session_id", lambda: "resumed-sid")
    # No claude_pid signal available — resume is a new OS process, so the
    # pre-existing /clear-only auto-rebind path must not be what saves this.
    monkeypatch.setattr(session, "detect_live_claude_pid", lambda: None)

    from downbeat.cli.commands.relay_cmds import _detect_peer_or_error
    name = _detect_peer_or_error(None)

    assert name == "p"
    assert store.get_peer("p").session_id == "resumed-sid"


def test_detect_peer_refuses_when_sid_in_no_peer_history(relay_dir, capsys, monkeypatch):
    store.register_peer(name="p", session_id="live-sid", cwd="/tmp", role="parent")
    monkeypatch.setattr(session, "detect_session_id", lambda: "totally-unseen-sid")
    monkeypatch.setattr(session, "detect_live_claude_pid", lambda: None)

    from downbeat.cli.commands.relay_cmds import _detect_peer_or_error
    with pytest.raises(SystemExit) as exc:
        _detect_peer_or_error(None)
    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "not registered" in err
    # Must not silently pick a winner when there is nothing to go on.
    assert "p" not in err.split("not registered")[0]


def test_detect_peer_refuses_when_sid_in_multiple_peer_histories(relay_dir, capsys, monkeypatch):
    # Two peers whose histories both happen to contain the current sid.
    # Ambiguous lineage — must refuse rather than guess.
    store.register_peer(name="A", session_id="shared-old-sid", cwd="/tmp", role="parent")
    store.rebind_session("A", new_session_id="a-live")
    store.register_peer(name="B", session_id="shared-old-sid", cwd="/tmp", role="parent")
    store.rebind_session("B", new_session_id="b-live")

    monkeypatch.setattr(session, "detect_session_id", lambda: "shared-old-sid")
    monkeypatch.setattr(session, "detect_live_claude_pid", lambda: None)

    from downbeat.cli.commands.relay_cmds import _detect_peer_or_error
    with pytest.raises(SystemExit) as exc:
        _detect_peer_or_error(None)
    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "ambiguous" in err.lower()
    assert "A" in err and "B" in err


def test_whoami_self_heals_after_resume(relay_dir, capsys, monkeypatch):
    # The issue's second reproduction: whoami itself couldn't identify the
    # peer after resume. Confirm the fix benefits whoami too, not only send.
    import sys
    store.register_peer(name="Skill-Builder", session_id="resumed-sid",
                        cwd="/tmp", role="parent")
    store.rebind_session("Skill-Builder", new_session_id="live-sid")
    monkeypatch.setattr(session, "detect_session_id", lambda: "resumed-sid")
    monkeypatch.setattr(session, "detect_live_claude_pid", lambda: None)
    monkeypatch.setattr(sys, "argv", ["downbeat", "whoami"])

    from downbeat.cli.__main__ import main
    rc = main()
    assert rc == 0
    out = capsys.readouterr().out
    assert "Skill-Builder" in out
