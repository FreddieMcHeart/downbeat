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
