import sys

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
