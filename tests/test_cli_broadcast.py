"""Tests for `downbeat broadcast` (#97): a CLI verb for the store's
broadcast(), so an announcement to N peers is reachable from a
non-interactive session and can express a non-task kind."""
import sys

from downbeat.cli.__main__ import main


def _peers(*names):
    from downbeat.core import store
    for n in names:
        store.register_peer(name=n, session_id=f"s-{n}", cwd="/tmp", role="parent")


def test_broadcast_cli_to_flag_sends_to_explicit_targets(relay_dir, capsys, monkeypatch):
    from downbeat.core import store
    _peers("parent", "a", "b", "c")
    monkeypatch.setattr(sys, "argv",
        ["downbeat", "broadcast", "--to", "a", "--to", "b",
         "--from", "parent", "subject", "body"])
    rc = main()
    assert rc == 0
    assert any(m.body == "body" for m in store.list_inbox("a"))
    assert any(m.body == "body" for m in store.list_inbox("b"))
    # "c" was never named, and was not the target of --all-children either
    assert not any(m.body == "body" for m in store.list_inbox("c"))


def test_broadcast_cli_all_children_flag_sends_to_children_only(relay_dir, capsys, monkeypatch):
    from downbeat.core import store
    store.register_peer(name="parent", session_id="s0", cwd="/tmp", role="parent")
    store.register_peer(name="child-a", session_id="s1", cwd="/tmp", role="child",
                        parent="parent")
    store.register_peer(name="child-b", session_id="s2", cwd="/tmp", role="child",
                        parent="parent")
    store.register_peer(name="stranger", session_id="s3", cwd="/tmp", role="parent")
    monkeypatch.setattr(sys, "argv",
        ["downbeat", "broadcast", "--all-children", "--from", "parent",
         "subject", "body"])
    rc = main()
    assert rc == 0
    assert any(m.body == "body" for m in store.list_inbox("child-a"))
    assert any(m.body == "body" for m in store.list_inbox("child-b"))
    # The sender itself never receives its own broadcast
    assert not any(m.body == "body" for m in store.list_inbox("parent"))
    # A peer that isn't a child of the sender is not swept in
    assert not any(m.body == "body" for m in store.list_inbox("stranger"))


def test_broadcast_cli_bad_target_mid_list_sends_nothing(relay_dir, capsys, monkeypatch):
    """Review finding: a typo'd --to used to partially send (earlier
    targets already delivered before the bad name is hit, since
    send_message resolves each recipient one at a time) and the error
    path threw away the broadcast_id, so the messages that DID land
    couldn't be traced back to anything. --to is free text (unlike the
    TUI's list-picker), so this is newly reachable. Pre-flight every
    target before sending any: rc=2 must mean nothing was sent."""
    from downbeat.core import store
    _peers("parent", "kid-a", "kid-b")
    monkeypatch.setattr(sys, "argv",
        ["downbeat", "broadcast", "--to", "kid-a", "--to", "ghost",
         "--to", "kid-b", "--from", "parent", "announce", "body"])
    rc = main()
    assert rc == 2
    err = capsys.readouterr().err
    assert "ghost" in err
    assert store.list_inbox("kid-a") == []
    assert store.list_inbox("kid-b") == []


def test_broadcast_cli_to_self_is_allowed_deliberately(relay_dir, capsys, monkeypatch):
    """PIN, not a driver: passes before and after, and must keep passing.

    --to <self> sends a peer a message from itself, and that is intended,
    not an oversight -- it looks asymmetric with --all-children (which
    excludes the sender) but the two are different kinds of set:
    --all-children is DERIVED (children_of returns the subtree INCLUDING
    the sender, an artifact of that helper that filtering here corrects);
    --to is STATED (the caller typed the name, and Decision 2's whole
    point is that the caller must say who -- they said). Untested-and-
    intended reads as untested-and-accidental to the next reader, who
    will "fix" it for symmetry; this test is what stops that."""
    from downbeat.core import store
    _peers("parent")
    monkeypatch.setattr(sys, "argv",
        ["downbeat", "broadcast", "--to", "parent", "--from", "parent",
         "subject", "body"])
    rc = main()
    assert rc == 0
    assert any(m.body == "body" for m in store.list_inbox("parent"))


def test_broadcast_cli_to_and_all_children_union_is_ordered_and_deduped(
        relay_dir, monkeypatch):
    """PIN, not a driver: passes before and after (the union logic already
    existed; this only asserts the specific order it produces). --to and
    --all-children combine rather than conflict when both are given:
    --to names first, in the order given, then derived children not
    already named, deduplicated."""
    from downbeat.core import store
    store.register_peer(name="parent", session_id="s0", cwd="/tmp", role="parent")
    store.register_peer(name="child-a", session_id="s1", cwd="/tmp", role="child",
                        parent="parent")
    store.register_peer(name="child-b", session_id="s2", cwd="/tmp", role="child",
                        parent="parent")
    store.register_peer(name="explicit", session_id="s3", cwd="/tmp", role="parent")

    captured = {}
    orig_broadcast = store.broadcast

    def _capture(**kwargs):
        captured["to_peers"] = list(kwargs["to_peers"])
        return orig_broadcast(**kwargs)

    monkeypatch.setattr(store, "broadcast", _capture)
    monkeypatch.setattr(sys, "argv",
        ["downbeat", "broadcast", "--to", "explicit", "--to", "child-a",
         "--all-children", "--from", "parent", "subject", "body"])
    rc = main()
    assert rc == 0
    assert captured["to_peers"] == ["explicit", "child-a", "child-b"]


def test_broadcast_cli_no_targets_is_an_error(relay_dir, capsys, monkeypatch):
    """#97 Decision 2's whole point: no default target set. Neither --to
    nor --all-children given must refuse, not silently send nothing and
    not silently send everywhere."""
    _peers("parent")
    monkeypatch.setattr(sys, "argv",
        ["downbeat", "broadcast", "--from", "parent", "subject", "body"])
    rc = main()
    assert rc == 2
    err = capsys.readouterr().err
    assert "target" in err.lower()


def test_broadcast_cli_echoes_broadcast_id(relay_dir, capsys, monkeypatch):
    from downbeat.core import store
    _peers("parent", "a")
    monkeypatch.setattr(sys, "argv",
        ["downbeat", "broadcast", "--to", "a", "--from", "parent",
         "subject", "body"])
    rc = main()
    assert rc == 0
    out = capsys.readouterr().out
    assert "broadcast:" in out
    bc_id = out.strip().split("broadcast:", 1)[1].strip()
    status = store.broadcast_status(bc_id)
    assert len(status) == 1
    assert status[0]["target"] == "a"


def test_broadcast_cli_kind_flag_is_passed_through(relay_dir, capsys, monkeypatch):
    from downbeat.core import store
    _peers("parent", "a")
    monkeypatch.setattr(sys, "argv",
        ["downbeat", "broadcast", "--to", "a", "--from", "parent",
         "--kind", "status", "subject", "body"])
    rc = main()
    assert rc == 0
    msgs = store.list_inbox("a")
    assert len(msgs) == 1
    assert msgs[0].kind == "status"


def test_broadcast_cli_default_kind_is_task(relay_dir, capsys, monkeypatch):
    from downbeat.core import store
    _peers("parent", "a")
    monkeypatch.setattr(sys, "argv",
        ["downbeat", "broadcast", "--to", "a", "--from", "parent",
         "subject", "body"])
    rc = main()
    assert rc == 0
    msgs = store.list_inbox("a")
    assert len(msgs) == 1
    assert msgs[0].kind == "task"


def test_broadcast_cli_from_auto_detected_when_omitted(relay_dir, capsys, monkeypatch):
    """Mirrors send/reply's --from auto-detection (#97: model the flags on
    send for consistency)."""
    from downbeat.core import session, store
    _peers("parent", "a")
    monkeypatch.setattr(session, "detect_session_id", lambda: "s-parent")
    monkeypatch.setattr(sys, "argv",
        ["downbeat", "broadcast", "--to", "a", "subject", "body"])
    rc = main()
    assert rc == 0
    msgs = store.list_inbox("a")
    assert len(msgs) == 1
    assert msgs[0].from_peer == "parent"
