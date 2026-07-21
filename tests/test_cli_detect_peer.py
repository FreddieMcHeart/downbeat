"""Regression tests for the relay CLI's feedback to sessions that cannot
auto-identify (the background-session traps).

Two distinct root causes, both surfaced from a real background session:
1. When peer auto-detection fails, the shared `_detect_peer_or_error` error
   text must name the override flag the CALLING subcommand actually exposes —
   `--peer` for inbox/whoami/quarantine, `--from` for send/reply. A hardcoded
   `--from` told an inbox caller to pass a flag inbox rejects.
2. `ack` only acts on delivered/; a message still in inbox/ (never drained,
   the common background-session case) can't be acked. ack must explain that
   rather than printing a bare "· <id>".
"""
import sys

import pytest

from downbeat.cli.__main__ import main


def _argv(monkeypatch, *args):
    monkeypatch.setattr(sys, "argv", ["downbeat", *args])


def test_inbox_detection_error_names_peer_not_from_flag(relay_dir, capsys, monkeypatch):
    from downbeat.core import session
    monkeypatch.setattr(session, "detect_session_id", lambda: None)
    _argv(monkeypatch, "inbox")
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "--peer" in err        # the flag inbox actually accepts
    assert "--from" not in err    # the flag it does NOT (the old bug)


def test_whoami_detection_error_names_peer_not_from_flag(relay_dir, capsys, monkeypatch):
    from downbeat.core import session
    monkeypatch.setattr(session, "detect_session_id", lambda: None)
    _argv(monkeypatch, "whoami")
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "--peer" in err
    assert "--from" not in err


def test_send_detection_error_still_names_from_flag(relay_dir, capsys, monkeypatch):
    from downbeat.core import session
    monkeypatch.setattr(session, "detect_session_id", lambda: None)
    _argv(monkeypatch, "send", "someone", "subj", "body")
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "--from" in err        # send's real override flag, unchanged


def test_whoami_peer_flag_bypasses_failed_detection(relay_dir, capsys, monkeypatch):
    # A background session that can't auto-identify can still ask explicitly.
    from downbeat.core import session, store
    store.register_peer(name="Uncapped-Main", session_id="sid-x",
                        cwd="/tmp", role="parent")
    monkeypatch.setattr(session, "detect_session_id", lambda: None)
    _argv(monkeypatch, "whoami", "--peer", "Uncapped-Main")
    rc = main()
    assert rc == 0
    out = capsys.readouterr().out
    assert "Uncapped-Main" in out
    assert "parent" in out


def test_ack_undelivered_inbox_message_explains_why(relay_dir, capsys, monkeypatch):
    # The exact screenshot case: mail still in inbox/ (never delivered) cannot
    # be acked; ack must say so, not just "· <id>" with a bare rc 2.
    from downbeat.core import store
    store.register_peer(name="parent", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="child", session_id="s2", cwd="/tmp", role="child")
    msg = store.send_message(from_peer="parent", to_peer="child",
                             subject="hi", body="b")
    _argv(monkeypatch, "ack", msg.id)
    rc = main()
    assert rc == 2
    out = capsys.readouterr().out
    assert "acked 0/1" in out
    assert "still in inbox" in out


def test_ack_unknown_id_says_not_found(relay_dir, capsys, monkeypatch):
    _argv(monkeypatch, "ack", "deadbeefdeadbeef")
    rc = main()
    assert rc == 2
    out = capsys.readouterr().out
    assert "not found" in out
