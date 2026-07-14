from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

from downbeat.core import state, store
from downbeat.tui.app import RelayApp


def _iso_minutes_ago(minutes: int) -> str:
    return (datetime.now(UTC) - timedelta(minutes=minutes)).isoformat()


def _make_stale(peer_name: str) -> None:
    sessions = store._load_sessions()
    sessions[peer_name]["last_seen"] = _iso_minutes_ago(20)
    store._save_sessions(sessions)


@pytest.mark.asyncio
async def test_heartbeat_written_on_mount(relay_dir):
    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        await pilot.pause()
        assert state.get_watcher_heartbeat_at() is not None


@pytest.mark.asyncio
async def test_stale_notify_fires_for_message_arriving_after_mount(relay_dir):
    store.register_peer(name="parent", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="child", session_id="s2", cwd="/tmp", role="child")
    _make_stale("child")

    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        await pilot.pause()  # baseline seeded here (empty inbox)
        store.send_message(from_peer="parent", to_peer="child",
                           subject="s", body="b")
        with patch("downbeat.tui.app.notify.notify") as mock_notify:
            app._check_stale_notify()
        mock_notify.assert_called_once()
        assert "child" in mock_notify.call_args[0][1]


@pytest.mark.asyncio
async def test_stale_notify_skips_fresh_recipient(relay_dir):
    store.register_peer(name="parent", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="child", session_id="s2", cwd="/tmp", role="child")

    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        await pilot.pause()
        store.send_message(from_peer="parent", to_peer="child",
                           subject="s", body="b")
        with patch("downbeat.tui.app.notify.notify") as mock_notify:
            app._check_stale_notify()
        mock_notify.assert_not_called()


@pytest.mark.asyncio
async def test_stale_notify_respects_cooldown(relay_dir):
    store.register_peer(name="parent", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="child", session_id="s2", cwd="/tmp", role="child")
    _make_stale("child")
    state.set_notify_last_sent("child", state.now_iso())  # just notified

    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        await pilot.pause()
        store.send_message(from_peer="parent", to_peer="child",
                           subject="s", body="b")
        with patch("downbeat.tui.app.notify.notify") as mock_notify:
            app._check_stale_notify()
        mock_notify.assert_not_called()


@pytest.mark.asyncio
async def test_stale_notify_does_not_fire_for_pre_existing_backlog(relay_dir):
    """Messages already sitting in the inbox before the TUI mounted must
    not be announced — only genuinely-new arrivals while the TUI is open."""
    store.register_peer(name="parent", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="child", session_id="s2", cwd="/tmp", role="child")
    _make_stale("child")
    store.send_message(from_peer="parent", to_peer="child",
                       subject="pre-existing", body="b")

    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        await pilot.pause()  # baseline seeding happens in on_mount
        with patch("downbeat.tui.app.notify.notify") as mock_notify:
            app._check_stale_notify()
        mock_notify.assert_not_called()
