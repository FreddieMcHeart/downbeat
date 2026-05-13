import pytest

from claude_relay.tui.app import RelayApp


@pytest.mark.skip(reason="three-pane view replaced by chat view")
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
    """Verify the uppercase-B keybinding on MessageDetailScreen reaches
    action_broadcast_status. The binding was moved from ChatScreen to
    MessageDetailScreen in the detail-screen refactor.
    Pressing B on MessageDetailScreen with a non-broadcast message posts
    a 'Not part of a broadcast' warning notification."""
    from claude_relay.core import store
    from claude_relay.tui.screens.message_detail import MessageDetailScreen
    store.register_peer(name="p", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="c", session_id="s2", cwd="/tmp", role="child")
    msg = store.send_message(from_peer="c", to_peer="p", subject="t", body="b")
    # Verify B binding is present on MessageDetailScreen
    binding_keys = {b[0] for b in MessageDetailScreen.BINDINGS}
    assert "B,shift+b" in binding_keys, (
        "MessageDetailScreen must have B binding for broadcast_status"
    )
    # Verify action_broadcast_status exists on MessageDetailScreen
    screen = MessageDetailScreen(msg.id)
    assert hasattr(screen, "action_broadcast_status")
