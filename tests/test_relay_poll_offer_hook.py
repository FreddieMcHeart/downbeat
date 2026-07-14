"""Tests for the staleness-notify addition to relay-poll-offer.py.

The hook is a standalone, stdlib-only script (no downbeat package import —
see docs/superpowers/specs/2026-07-14-tui-hosted-relay-notify-design.md,
"Implementation constraint"), so it's loaded per-test via
importlib.util.spec_from_file_location rather than a normal import."""
from __future__ import annotations

import importlib.util
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import downbeat


def _load_hook_module():
    path = (Path(downbeat.__file__).parent / "assets" / "hooks"
            / "relay-poll-offer.py")
    spec = importlib.util.spec_from_file_location("relay_poll_offer", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_sessions(relay_dir, peers: dict) -> None:
    (relay_dir / "sessions.json").write_text(json.dumps(peers))


def _iso_minutes_ago(minutes: int) -> str:
    return (datetime.now(UTC) - timedelta(minutes=minutes)).isoformat()


def test_resolve_recipient_from_send_command(relay_dir):
    hook = _load_hook_module()
    cmd = 'downbeat send Claude-Relay "subject" "body"'
    assert hook._resolve_recipient(cmd) == "Claude-Relay"


def test_resolve_recipient_from_reply_looks_up_original_sender(relay_dir):
    hook = _load_hook_module()
    inbox = relay_dir / "inbox" / "someone"
    inbox.mkdir(parents=True)
    (inbox / "abc123.json").write_text(json.dumps({"from_peer": "Claude-Relay"}))
    cmd = 'downbeat reply abc123 "done"'
    assert hook._resolve_recipient(cmd) == "Claude-Relay"


def test_resolve_recipient_reply_missing_message_returns_none(relay_dir):
    hook = _load_hook_module()
    cmd = 'downbeat reply ghost123 "done"'
    assert hook._resolve_recipient(cmd) is None


def test_resolve_recipient_unrelated_command_returns_none(relay_dir):
    hook = _load_hook_module()
    assert hook._resolve_recipient('downbeat inbox --peer child') is None


def test_is_recipient_stale_true_for_old_last_seen(relay_dir):
    hook = _load_hook_module()
    _write_sessions(relay_dir, {"child": {"last_seen": _iso_minutes_ago(20)}})
    assert hook._is_recipient_stale("child") is True


def test_is_recipient_stale_false_for_fresh_last_seen(relay_dir):
    hook = _load_hook_module()
    _write_sessions(relay_dir, {"child": {"last_seen": _iso_minutes_ago(1)}})
    assert hook._is_recipient_stale("child") is False


def test_is_recipient_stale_false_for_missing_peer(relay_dir):
    hook = _load_hook_module()
    _write_sessions(relay_dir, {})
    assert hook._is_recipient_stale("ghost") is False


def test_is_recipient_stale_false_for_missing_last_seen(relay_dir):
    hook = _load_hook_module()
    _write_sessions(relay_dir, {"child": {}})
    assert hook._is_recipient_stale("child") is False


def test_is_recipient_stale_false_for_malformed_last_seen(relay_dir):
    hook = _load_hook_module()
    _write_sessions(relay_dir, {"child": {"last_seen": "not-a-timestamp"}})
    assert hook._is_recipient_stale("child") is False


def test_maybe_notify_fires_when_stale_and_no_tui(relay_dir):
    hook = _load_hook_module()
    _write_sessions(relay_dir, {"child": {"last_seen": _iso_minutes_ago(20)}})
    with patch.object(hook, "_notify") as mock_notify:
        hook._maybe_notify_stale_recipient('downbeat send child "s" "b"')
    mock_notify.assert_called_once()
    assert "child" in mock_notify.call_args[0][1]


def test_maybe_notify_skips_when_tui_heartbeat_fresh(relay_dir):
    hook = _load_hook_module()
    _write_sessions(relay_dir, {"child": {"last_seen": _iso_minutes_ago(20)}})
    (relay_dir / "tui_state.json").write_text(
        json.dumps({"watcher_heartbeat_at": _iso_minutes_ago(0)}))
    with patch.object(hook, "_notify") as mock_notify:
        hook._maybe_notify_stale_recipient('downbeat send child "s" "b"')
    mock_notify.assert_not_called()


def test_maybe_notify_fires_when_tui_heartbeat_stale_but_within_10min(relay_dir):
    """Regression for the blind-window bug: a heartbeat aged past the
    liveness threshold (90s) but still within the unrelated 10-minute
    recipient-staleness window must NOT be treated as "TUI still live" —
    the hook should notify. Before the fix, this case incorrectly matched
    test_maybe_notify_skips_when_tui_heartbeat_fresh's semantics because
    both checks shared the same 10-minute constant."""
    hook = _load_hook_module()
    _write_sessions(relay_dir, {"child": {"last_seen": _iso_minutes_ago(20)}})
    (relay_dir / "tui_state.json").write_text(
        json.dumps({"watcher_heartbeat_at": _iso_minutes_ago(3)}))
    with patch.object(hook, "_notify") as mock_notify:
        hook._maybe_notify_stale_recipient('downbeat send child "s" "b"')
    mock_notify.assert_called_once()


def test_stale_and_liveness_thresholds_are_independent_constants(relay_dir):
    hook = _load_hook_module()
    assert hook._TUI_LIVENESS_THRESHOLD_SECONDS != hook._STALE_THRESHOLD_MINUTES * 60


def test_hook_and_store_staleness_constants_match():
    """The 10-minute recipient-staleness window is duplicated (hooks can't
    import the downbeat package — see the module docstring), so nothing
    stops the two from silently drifting apart if one is tuned without the
    other. This test is the guard."""
    from downbeat.core import store
    hook = _load_hook_module()
    assert hook._STALE_THRESHOLD_MINUTES == store.STALE_THRESHOLD_MINUTES


def test_maybe_notify_skips_when_recipient_not_stale(relay_dir):
    hook = _load_hook_module()
    _write_sessions(relay_dir, {"child": {"last_seen": _iso_minutes_ago(1)}})
    with patch.object(hook, "_notify") as mock_notify:
        hook._maybe_notify_stale_recipient('downbeat send child "s" "b"')
    mock_notify.assert_not_called()


def test_maybe_notify_respects_cooldown(relay_dir):
    hook = _load_hook_module()
    _write_sessions(relay_dir, {"child": {"last_seen": _iso_minutes_ago(20)}})
    (relay_dir / "tui_state.json").write_text(
        json.dumps({"notify_last_sent": {"child": _iso_minutes_ago(1)}}))
    with patch.object(hook, "_notify") as mock_notify:
        hook._maybe_notify_stale_recipient('downbeat send child "s" "b"')
    mock_notify.assert_not_called()


def test_maybe_notify_updates_cooldown_after_firing(relay_dir):
    hook = _load_hook_module()
    _write_sessions(relay_dir, {"child": {"last_seen": _iso_minutes_ago(20)}})
    with patch.object(hook, "_notify"):
        hook._maybe_notify_stale_recipient('downbeat send child "s" "b"')
    written = json.loads((relay_dir / "tui_state.json").read_text())
    assert "child" in written["notify_last_sent"]


def test_maybe_notify_preserves_other_tui_state_keys(relay_dir):
    hook = _load_hook_module()
    _write_sessions(relay_dir, {"child": {"last_seen": _iso_minutes_ago(20)}})
    (relay_dir / "tui_state.json").write_text(
        json.dumps({"last_acting_as": "alice"}))
    with patch.object(hook, "_notify"):
        hook._maybe_notify_stale_recipient('downbeat send child "s" "b"')
    written = json.loads((relay_dir / "tui_state.json").read_text())
    assert written["last_acting_as"] == "alice"
    assert "child" in written["notify_last_sent"]


def test_maybe_notify_never_raises_on_garbage_sessions_file(relay_dir):
    hook = _load_hook_module()
    (relay_dir / "sessions.json").write_text("not json")
    with patch.object(hook, "_notify") as mock_notify:
        hook._maybe_notify_stale_recipient('downbeat send child "s" "b"')
    mock_notify.assert_not_called()


def test_write_tui_state_roundtrips_via_atomic_write(relay_dir):
    hook = _load_hook_module()
    data = {"last_acting_as": "alice", "notify_last_sent": {"child": _iso_minutes_ago(1)}}
    hook._write_tui_state(data)
    tui_state_file = relay_dir / "tui_state.json"
    assert tui_state_file.exists()
    written = json.loads(tui_state_file.read_text())
    assert written == data
