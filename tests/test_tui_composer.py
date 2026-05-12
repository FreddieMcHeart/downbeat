import pytest

from claude_relay.tui.app import RelayApp


@pytest.mark.asyncio
async def test_compose_new_message(relay_dir):
    from claude_relay.core import store
    store.register_peer(name="parent", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="child", session_id="s2", cwd="/tmp", role="child")
    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        await pilot.press("n")
        await pilot.pause()
        # After pressing 'n', Composer is the current screen (modal)
        from claude_relay.tui.widgets.composer import Composer
        assert isinstance(app.screen, Composer), f"Expected Composer, got {type(app.screen)}"
        comp = app.screen
        comp.to_field = "child"
        comp.subject_field = "s"
        comp.body_field = "b"
        comp.submit()
        await pilot.pause()
        msgs = store.list_inbox("child")
        assert any(m.subject == "s" for m in msgs)


@pytest.mark.asyncio
async def test_compose_broadcast(relay_dir):
    from claude_relay.core import store
    store.register_peer(name="parent", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="a", session_id="s2", cwd="/tmp", role="child")
    store.register_peer(name="b", session_id="s3", cwd="/tmp", role="child")
    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        await pilot.press("n")
        await pilot.pause()
        from claude_relay.tui.widgets.composer import Composer
        assert isinstance(app.screen, Composer), f"Expected Composer, got {type(app.screen)}"
        comp = app.screen
        comp.broadcast = True
        comp.to_field = "a, b"
        comp.subject_field = "x"
        comp.body_field = "y"
        comp.submit()
        await pilot.pause()
        assert store.list_inbox("a")
        assert store.list_inbox("b")
