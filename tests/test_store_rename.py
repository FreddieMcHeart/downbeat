"""Tests for store.rename_peer + the `downbeat peers rename` CLI (issue #40,
Option B — atomic, resumable peer rename)."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta

import pytest

from downbeat.cli.__main__ import main
from downbeat.core.errors import InvalidPeerName, PeerNameCollision, PeerNotFound


def _peers(store, *names, role="parent"):
    for n in names:
        store.register_peer(name=n, session_id=f"s-{n}", cwd="/tmp", role=role)


def _quarantine_for(relay_dir, store, peer, from_peer):
    msg = store.send_message(from_peer=from_peer, to_peer=peer,
                             subject="q", body="body")
    store.deliver_messages(peer_name=peer, session_id=f"sess-{peer}")
    delivered_file = relay_dir / "delivered" / peer / f"{msg.id}.json"
    d = json.loads(delivered_file.read_text())
    d["delivered_at"] = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    d["redelivery_count"] = 3
    delivered_file.write_text(json.dumps(d))
    store.reconcile(window_minutes=30, max_redelivery=3)
    return msg


def test_rename_preserves_thread_history(relay_dir):
    # The direct regression for the list_thread bug in #40: a rename must not
    # drop any message from the reconstructed thread.
    from downbeat.core import store
    _peers(store, "A", "B")
    for i in range(3):
        store.send_message(from_peer="B", to_peer="A", subject=f"b{i}", body="x")
        store.send_message(from_peer="A", to_peer="B", subject=f"a{i}", body="x")
    before = {m.id for m in store.list_thread("A", "B")}
    assert len(before) == 6

    store.rename_peer("A", "A2")

    after = {m.id for m in store.list_thread("A2", "B")}
    assert after == before                       # no message dropped
    assert store.list_thread("A", "B") == []     # old name resolves to nothing


def test_rename_moves_all_four_state_directories(relay_dir):
    from downbeat.core import store
    _peers(store, "A", "B")
    # Spread messages to A across all four state directories:
    delivered_msg = store.send_message(from_peer="B", to_peer="A", subject="d", body="x")
    processed_msg = store.send_message(from_peer="B", to_peer="A", subject="p", body="x")
    store.deliver_messages(peer_name="A", session_id="s-A")  # both → delivered/A/
    store.ack_messages([processed_msg.id])                   # one → processed/A/
    quarantined_msg = _quarantine_for(relay_dir, store, "A", "B")  # → quarantine/A/
    # sent after deliver, so it stays in inbox/A/
    inbox_msg = store.send_message(from_peer="B", to_peer="A", subject="i", body="x")

    all_ids_before = {inbox_msg.id, delivered_msg.id, processed_msg.id, quarantined_msg.id}

    store.rename_peer("A", "A2")

    # Nothing left under any A-named dir; everything present under A2.
    for base in ("inbox", "delivered", "processed", "quarantine"):
        old_dir = relay_dir / base / "A"
        assert not old_dir.exists() or not any(old_dir.iterdir()), f"{base}/A not emptied"
    found = set()
    for base in ("inbox", "delivered", "processed", "quarantine"):
        new_dir = relay_dir / base / "A2"
        if new_dir.exists():
            found |= {p.stem for p in new_dir.glob("*.json")}
    assert all_ids_before <= found


def test_rename_rewrites_from_and_to_fields(relay_dir):
    from downbeat.core import store
    _peers(store, "A", "B")
    to_a = store.send_message(from_peer="B", to_peer="A", subject="s", body="x")   # to==A
    from_a = store.send_message(from_peer="A", to_peer="B", subject="s", body="x")  # from==A

    store.rename_peer("A", "A2")

    assert store.get_message(to_a.id).to_peer == "A2"
    assert store.get_message(from_a.id).from_peer == "A2"


def test_rename_repoints_parent_pointers(relay_dir):
    from downbeat.core import store
    _peers(store, "A")
    store.register_peer(name="C", session_id="s-C", cwd="/tmp", role="child", parent="A")
    assert store.get_peer("C").parent == "A"

    store.rename_peer("A", "A2")

    assert store.get_peer("C").parent == "A2"
    assert store.get_peer("A2").name == "A2"


def test_rename_updates_group_membership(relay_dir):
    from downbeat.core import groups, store
    _peers(store, "A", "B")
    groups.save_group("team", ["A", "B"])

    store.rename_peer("A", "A2")

    assert groups.get_group("team") == ["A2", "B"]


def test_rename_collision_rejected_without_touching_files(relay_dir):
    from downbeat.core import store
    _peers(store, "A", "B")
    msg = store.send_message(from_peer="B", to_peer="A", subject="s", body="x")

    with pytest.raises(PeerNameCollision):
        store.rename_peer("A", "B")

    # Untouched: A still registered, message still addressed to A, dir intact.
    assert store.get_peer("A").name == "A"
    assert store.get_message(msg.id).to_peer == "A"
    assert (relay_dir / "inbox" / "A" / f"{msg.id}.json").exists()


def test_rename_missing_peer_raises(relay_dir):
    from downbeat.core import store
    with pytest.raises(PeerNotFound):
        store.rename_peer("ghost", "ghost2")


def test_rename_empty_new_name_raises(relay_dir):
    from downbeat.core import store
    _peers(store, "A")
    with pytest.raises(InvalidPeerName):
        store.rename_peer("A", "   ")


def test_rename_is_resumable_after_partial_failure(relay_dir, monkeypatch):
    # We chose resumable-not-transactional: a crash mid-rewrite must be
    # recoverable by re-running the same rename, converging to the full result.
    from downbeat.core import store
    _peers(store, "A", "B")
    for i in range(4):
        store.send_message(from_peer="B", to_peer="A", subject=f"b{i}", body="x")
        store.send_message(from_peer="A", to_peer="B", subject=f"a{i}", body="x")
    full = {m.id for m in store.list_thread("A", "B")}
    assert len(full) == 8

    real_write = store._atomic_write_text
    calls = {"n": 0}

    def flaky(target, text):
        calls["n"] += 1
        if calls["n"] == 3:
            raise OSError("simulated crash mid-rename")
        return real_write(target, text)

    monkeypatch.setattr(store, "_atomic_write_text", flaky)
    with pytest.raises(OSError):
        store.rename_peer("A", "A2")

    # Resume with the real writer — same args — and expect full convergence.
    monkeypatch.setattr(store, "_atomic_write_text", real_write)
    store.rename_peer("A", "A2")

    assert {m.id for m in store.list_thread("A2", "B")} == full
    with pytest.raises(PeerNotFound):
        store.get_peer("A")


# ── CLI wiring ───────────────────────────────────────────────────────────────

def test_cli_peers_rename_dispatches(relay_dir, capsys, monkeypatch):
    from downbeat.core import store
    _peers(store, "A", "B")
    store.send_message(from_peer="B", to_peer="A", subject="s", body="x")
    monkeypatch.setattr(sys, "argv", ["downbeat", "peers", "rename", "A", "A2"])
    rc = main()
    assert rc == 0
    out = capsys.readouterr().out
    assert "A2" in out
    assert store.get_peer("A2").name == "A2"


def test_cli_peers_rename_collision_returns_1(relay_dir, capsys, monkeypatch):
    from downbeat.core import store
    _peers(store, "A", "B")
    monkeypatch.setattr(sys, "argv", ["downbeat", "peers", "rename", "A", "B"])
    rc = main()
    assert rc == 1
    err = capsys.readouterr().err
    assert "B" in err


# ── review hardening (findings #1–#4) ────────────────────────────────────────

def test_rename_missing_old_to_existing_new_raises(relay_dir):
    # #1: a typo in old_name must NOT silently "succeed" by returning the
    # unrelated existing peer named new_name.
    from downbeat.core import store
    _peers(store, "RealPeer")
    with pytest.raises(PeerNotFound):
        store.rename_peer("typo-name", "RealPeer")


def test_rename_into_stale_removed_peer_dir_rejected(relay_dir):
    # #2: renaming to the name of a REMOVED peer whose message dirs still sit on
    # disk must not merge the two peers' mail.
    from downbeat.core import store
    _peers(store, "A", "X")
    store.send_message(from_peer="A", to_peer="X", subject="s", body="x")  # inbox/X/
    store.remove_peer("X")  # pops sessions but leaves inbox/X/ on disk
    assert (relay_dir / "inbox" / "X").exists()

    with pytest.raises(PeerNameCollision):
        store.rename_peer("A", "X")
    # A untouched by the rejected rename.
    assert store.get_peer("A").name == "A"


def test_rename_rejects_path_separator_and_dotdot(relay_dir):
    # #3: new_name becomes a directory + sessions key; reject path traversal.
    from downbeat.core import store
    _peers(store, "A")
    for bad in ("a/b", "..", ".", "x\\y", "  "):
        with pytest.raises(InvalidPeerName):
            store.rename_peer("A", bad)
    # And nothing escaped the relay tree.
    assert not (relay_dir.parent / "b").exists()


def test_register_rejects_path_separator_name(relay_dir):
    # #3 at the shared root: register_peer validates too.
    from downbeat.core import store
    with pytest.raises(InvalidPeerName):
        store.register_peer(name="../evil", session_id="s", cwd="/tmp", role="child")


def test_rename_skips_corrupt_unrelated_message(relay_dir):
    # #4: a corrupt file in an unrelated peer's dir must not abort the rename.
    from downbeat.core import store
    _peers(store, "A", "B", "C")
    m1 = store.send_message(from_peer="B", to_peer="A", subject="s", body="x")
    m2 = store.send_message(from_peer="A", to_peer="B", subject="s", body="x")
    store.send_message(from_peer="B", to_peer="C", subject="s", body="x")  # inbox/C/ exists
    corrupt = relay_dir / "inbox" / "C" / "deadbeefdeadbeef.json"
    corrupt.write_text("{ this is not valid json")

    store.rename_peer("A", "A2")  # must not raise

    assert {m.id for m in store.list_thread("A2", "B")} == {m1.id, m2.id}
    assert corrupt.exists()  # untouched, not deleted


def test_rename_clears_marker_on_success(relay_dir):
    from downbeat.core import store
    _peers(store, "A", "B")
    store.send_message(from_peer="B", to_peer="A", subject="s", body="x")
    store.rename_peer("A", "A2")
    assert not (relay_dir / ".rename-in-progress.json").exists()
