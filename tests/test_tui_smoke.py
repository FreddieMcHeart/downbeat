import pytest

from claude_relay.tui.app import RelayApp


@pytest.mark.asyncio
async def test_app_starts_and_shows_three_panes(relay_dir):
    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        await pilot.pause()
        assert app.screen.query_one("#peers-pane") is not None
        assert app.screen.query_one("#inbox-pane") is not None
        assert app.screen.query_one("#message-pane") is not None


@pytest.mark.asyncio
async def test_app_quits_on_q(relay_dir):
    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        await pilot.press("q")
    # Reaching here means the app exited cleanly.


@pytest.mark.asyncio
async def test_toggle_logs_does_not_crash(relay_dir):
    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        await pilot.press("f6")
        await pilot.pause()
        await pilot.press("f6")


@pytest.mark.asyncio
async def test_help_opens_and_closes(relay_dir):
    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        await pilot.press("f1")
        await pilot.pause()
        await pilot.press("escape")


@pytest.mark.asyncio
async def test_uppercase_b_triggers_broadcast_status_action(relay_dir):
    """Verify the uppercase-B keybinding reaches action_broadcast_status.
    We don't expect a broadcast status screen to open (no message selected),
    but the action must be invoked — which posts a warning notification."""
    from claude_relay.core import store
    store.register_peer(name="p", session_id="s", cwd="/tmp", role="parent")
    app = RelayApp()
    notifications_captured = []
    original_notify = app.notify

    async with app.run_test(headless=True) as pilot:
        # Monkeypatch notify to capture calls before pressing B
        def capturing_notify(message, *args, **kwargs):
            notifications_captured.append(message)
            return original_notify(message, *args, **kwargs)
        app.notify = capturing_notify

        await pilot.press("B")
        await pilot.pause()

    # If the binding didn't fire, no notification would be posted.
    assert any(
        "Select a message first" in m or "not part of a broadcast" in m
        for m in notifications_captured
    ), (
        f"Expected a broadcast-status notification, got: {notifications_captured}"
    )
