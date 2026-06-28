import json
import sys

import pytest

from claude_relay.cli.__main__ import main


def test_peers_lists_registered_peers(relay_dir, capsys, monkeypatch):
    from claude_relay.core import store
    store.register_peer(name="p", session_id="s", cwd="/tmp", role="parent")
    monkeypatch.setattr(sys, "argv", ["claude-relay", "peers"])
    rc = main()
    assert rc == 0
    out = capsys.readouterr().out
    assert "p" in out


def test_send_writes_message(relay_dir, capsys, monkeypatch):
    from claude_relay.core import store
    store.register_peer(name="parent", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="child", session_id="s2", cwd="/tmp", role="child")
    monkeypatch.setattr(sys, "argv",
        ["claude-relay", "send", "child", "hi", "do work",
         "--from", "parent"])
    rc = main()
    assert rc == 0
    msgs = store.list_inbox("child")
    assert len(msgs) == 1
    assert msgs[0].body == "do work"


def test_rebind_cli_updates_session_id(relay_dir, capsys, monkeypatch):
    from claude_relay.core import store
    store.register_peer(name="p", session_id="old", cwd="/tmp", role="parent")
    monkeypatch.setattr(sys, "argv",
        ["claude-relay", "rebind", "p", "--session-id", "new-sid"])
    rc = main()
    assert rc == 0
    assert store.get_peer("p").session_id == "new-sid"


def test_inbox_prints_messages(relay_dir, capsys, monkeypatch):
    from claude_relay.core import store
    store.register_peer(name="parent", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="child", session_id="s2", cwd="/tmp", role="child")
    store.send_message(from_peer="parent", to_peer="child",
                       subject="hello", body="world")
    monkeypatch.setattr(sys, "argv", ["claude-relay", "inbox", "--peer", "child"])
    rc = main()
    assert rc == 0
    assert "hello" in capsys.readouterr().out


def test_send_with_kind_flag(relay_dir, capsys, monkeypatch):
    from claude_relay.core import store
    store.register_peer(name="parent", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="child", session_id="s2", cwd="/tmp", role="child")
    monkeypatch.setattr(sys, "argv",
        ["claude-relay", "send", "child", "bf", "body",
         "--from", "parent", "--kind", "backflow-ready"])
    rc = main()
    assert rc == 0
    assert store.list_inbox("child")[0].kind == "backflow-ready"


def test_send_without_kind_defaults_to_task(relay_dir, capsys, monkeypatch):
    from claude_relay.core import store
    store.register_peer(name="parent", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="child", session_id="s2", cwd="/tmp", role="child")
    monkeypatch.setattr(sys, "argv",
        ["claude-relay", "send", "child", "hi", "b", "--from", "parent"])
    rc = main()
    assert rc == 0
    assert store.list_inbox("child")[0].kind == "task"


# --- whoami tests ---

def test_whoami_prints_name_and_role(relay_dir, capsys, monkeypatch):
    from claude_relay.core import store, session
    store.register_peer(name="my-child", session_id="sid-abc", cwd="/tmp", role="child")
    monkeypatch.setattr(session, "detect_session_id", lambda: "sid-abc")
    monkeypatch.setattr(sys, "argv", ["claude-relay", "whoami"])
    rc = main()
    assert rc == 0
    out = capsys.readouterr().out
    assert "my-child" in out
    assert "child" in out
    # Must be exactly two space-separated tokens on one line
    line = out.strip()
    parts = line.split()
    assert parts == ["my-child", "child"]


def test_whoami_json_flag(relay_dir, capsys, monkeypatch):
    from claude_relay.core import store, session
    store.register_peer(name="par", session_id="sid-xyz", cwd="/tmp", role="parent")
    monkeypatch.setattr(session, "detect_session_id", lambda: "sid-xyz")
    monkeypatch.setattr(sys, "argv", ["claude-relay", "whoami", "--json"])
    rc = main()
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["name"] == "par"
    assert data["role"] == "parent"


def test_whoami_unregistered_exits_2(relay_dir, capsys, monkeypatch):
    from claude_relay.core import session
    monkeypatch.setattr(session, "detect_session_id", lambda: "unknown-sid")
    monkeypatch.setattr(session, "detect_live_claude_pid", lambda: None)
    monkeypatch.setattr(sys, "argv", ["claude-relay", "whoami"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
