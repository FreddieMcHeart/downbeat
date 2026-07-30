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


def test_detect_peer_reports_history_lead_without_taking_the_record(relay_dir, capsys, monkeypatch):
    """Was: asserts the auto-rebind. Now: asserts it refuses (#88).

    The scenario is unchanged -- a session whose id sits in exactly one peer's
    history -- but the correct outcome inverted. Taking the record on that
    evidence is the nondeterminism #88 describes.
    """
    store.register_peer(name="p", session_id="resumed-sid", cwd="/tmp", role="parent")
    store.rebind_session("p", new_session_id="live-sid")
    monkeypatch.setattr(session, "detect_session_id", lambda: "resumed-sid")
    monkeypatch.setattr(session, "detect_live_claude_pid", lambda: None)

    from downbeat.cli.commands.relay_cmds import _detect_peer_or_error
    with pytest.raises(SystemExit) as exc:
        _detect_peer_or_error(None)

    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "p" in err
    assert "downbeat rebind" in err
    assert "not proof" in err
    assert store.get_peer("p").session_id == "live-sid"


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


def test_whoami_reports_the_lead_instead_of_self_healing(relay_dir, capsys, monkeypatch):
    """Was: asserts whoami self-heals. Now: asserts it names the lead (#88).

    whoami is the read-out path, so it is where a human most often meets this.
    It must say which peer the session probably is and how to claim it --
    without claiming it on their behalf.
    """
    import sys
    store.register_peer(name="Skill-Builder", session_id="resumed-sid",
                        cwd="/tmp", role="parent")
    store.rebind_session("Skill-Builder", new_session_id="live-sid")
    monkeypatch.setattr(session, "detect_session_id", lambda: "resumed-sid")
    monkeypatch.setattr(session, "detect_live_claude_pid", lambda: None)
    monkeypatch.setattr(sys, "argv", ["downbeat", "whoami"])

    from downbeat.cli.__main__ import main
    with pytest.raises(SystemExit) as exc:
        main()

    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "Skill-Builder" in err
    assert "downbeat rebind" in err
    assert store.get_peer("Skill-Builder").session_id == "live-sid"


def test_history_match_reports_but_does_not_rebind(relay_dir, capsys, monkeypatch):
    """A history hit is a lead, not a licence to take the record (#88).

    session_id_history cannot distinguish "the same agent resumed" from "a
    different agent that once held this name" -- on disk they are the same
    shape. #71 established that a guess is worse than a refusal precisely
    because it can bind a session to the wrong identity, so the history hit
    must be reported for a human to act on, never acted on automatically.
    """
    store.register_peer(name="p", session_id="old-sid", cwd="/tmp", role="parent")
    store.rebind_session("p", new_session_id="live-sid")
    monkeypatch.setattr(session, "detect_session_id", lambda: "old-sid")
    monkeypatch.setattr(session, "detect_live_claude_pid", lambda: None)

    from downbeat.cli.commands.relay_cmds import _detect_peer_or_error
    with pytest.raises(SystemExit) as exc:
        _detect_peer_or_error(None)

    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "p" in err                       # names the lead
    assert "downbeat rebind" in err         # names the repair
    # The record must be untouched: no silent takeover.
    assert store.get_peer("p").session_id == "live-sid"


def test_two_live_ids_in_one_history_do_not_oscillate(relay_dir, monkeypatch):
    """Production reproduction of #88.

    rebind_log.jsonl recorded six events for one record, five of them
    alternating between two live session ids. Each self-heal was a theft in
    the other direction and each printed as a success. Alternating detection
    must leave the binding stable.
    """
    store.register_peer(name="Dev One", session_id="sid-a", cwd="/tmp", role="parent")
    store.rebind_session("Dev One", new_session_id="sid-b")
    store.rebind_session("Dev One", new_session_id="sid-a")
    # Both live ids are now entitled by history -- the state that produced
    # the ping-pong.
    bound = store.get_peer("Dev One").session_id

    from downbeat.cli.commands.relay_cmds import _detect_peer_or_error
    for sid in ("sid-b", "sid-a", "sid-b", "sid-a"):
        monkeypatch.setattr(session, "detect_session_id", lambda s=sid: s)
        monkeypatch.setattr(session, "detect_live_claude_pid", lambda: None)
        try:
            _detect_peer_or_error(None)
        except SystemExit:
            pass
        assert store.get_peer("Dev One").session_id == bound, (
            f"binding moved after a command from {sid}"
        )
