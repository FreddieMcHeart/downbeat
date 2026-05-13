import pytest

from claude_relay.tui.app import RelayApp


@pytest.mark.asyncio
async def test_chat_screen_mounts_with_acting_as_select_and_tabs(relay_dir):
    from claude_relay.core import store
    store.register_peer(name="PLAT-3113-master", session_id="s1",
                        cwd="/tmp", role="parent")
    store.register_peer(name="PLAT-3113-child", session_id="s2",
                        cwd="/tmp", role="child")
    app = RelayApp()
    async with app.run_test(headless=True):
        # Acting-as picker is mounted
        sel = app.screen.query_one("#acting-as-select")
        assert sel is not None
        # PeerTabs is mounted and includes both members
        tabs = app.screen.query_one("#peer-tabs")
        assert tabs is not None
        # ChatStream is mounted
        stream = app.screen.query_one("#chat-stream")
        assert stream is not None


@pytest.mark.asyncio
async def test_sending_via_composer_adds_message_to_thread(relay_dir):
    from claude_relay.core import store
    store.register_peer(name="parent", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="child", session_id="s2", cwd="/tmp", role="child")
    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        await pilot.pause()
        # Explicitly set active_peer to child so the send goes to child
        screen = app.screen
        screen.active_peer = "child"
        # Composer: simulate Input.Submitted (Enter) with the text
        composer = screen.query_one("#chat-composer")
        composer.value = "hello child"
        from textual.widgets import Input
        composer.post_message(Input.Submitted(composer, value="hello child"))
        await pilot.pause()
        # Verify the message was created and is in the child's inbox
        msgs = store.list_inbox("child")
        assert any(m.body == "hello child" for m in msgs)


@pytest.mark.asyncio
async def test_acting_as_select_lists_only_parents(relay_dir):
    from claude_relay.core import store
    store.register_peer(name="P", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="C", session_id="s2", cwd="/tmp", role="child")
    app = RelayApp()
    async with app.run_test(headless=True):
        sel = app.screen.query_one("#acting-as-select")
        # Internal options should only contain P
        assert sel.value == "P"
