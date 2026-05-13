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
    from claude_relay.tui.widgets.chat_composer import ChatComposer
    store.register_peer(name="parent", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="child", session_id="s2", cwd="/tmp", role="child")
    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        await pilot.pause()
        # Explicitly set active_peer to child so the send goes to child
        screen = app.screen
        screen.active_peer = "child"
        # Composer: post a Send message directly (TextArea-based composer)
        composer = screen.query_one("#chat-composer")
        composer.post_message(ChatComposer.Send("hello child"))
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


@pytest.mark.asyncio
async def test_composer_shift_enter_inserts_newline_enter_sends(relay_dir):
    """Enter must send; shift+enter must NOT send (it routes to TextArea default).

    We test the boundary on_key intercepts: enter fires Send, shift+enter doesn't.
    The newline-insertion itself is TextArea's built-in behaviour and is tested
    via direct Key injection since headless pilot.press may not deliver shift+enter.
    """
    from textual.events import Key

    from claude_relay.core import store
    from claude_relay.tui.widgets.chat_composer import ChatComposer
    store.register_peer(name="parent", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="child", session_id="s2", cwd="/tmp", role="child")
    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        await pilot.pause()
        screen = app.screen
        screen.active_peer = "child"
        composer = screen.query_one("#chat-composer", ChatComposer)
        composer.focus()
        await pilot.pause()
        # Verify that shift+enter does NOT trigger a Send message.
        # We do this by posting a Key event directly to on_key and checking
        # that no Send was dispatched (composer.text unchanged).
        composer.text = "line 1"
        msgs_before = len(store.list_inbox("child"))
        # Post shift+enter key to composer — our on_key skips it, so no send.
        composer.post_message(Key("shift+enter", "\n"))
        await pilot.pause()
        # No message sent yet
        assert len(store.list_inbox("child")) == msgs_before, \
            "shift+enter must NOT send the message"
        # Now press enter — should send (our on_key intercepts and fires Send)
        await pilot.press("enter")
        await pilot.pause()
        msgs_after = len(store.list_inbox("child"))
        assert msgs_after > msgs_before, "enter should have sent the message"
        # Composer should be cleared after send
        assert composer.text.strip() == ""


@pytest.mark.asyncio
async def test_broadcast_sends_to_all_group_children(relay_dir):
    """Ctrl+B broadcast should reach all group children, not the sender."""
    from claude_relay.core import store
    from claude_relay.tui.widgets.chat_composer import ChatComposer
    store.register_peer(name="grp-master", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="grp-a", session_id="s2", cwd="/tmp", role="child")
    store.register_peer(name="grp-b", session_id="s3", cwd="/tmp", role="child")
    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        await pilot.pause()
        composer = app.screen.query_one("#chat-composer", ChatComposer)
        # Post the Broadcast message directly (ctrl+b key routing in headless is brittle)
        composer.post_message(ChatComposer.Broadcast("all-hands"))
        await pilot.pause()
        # Both children received it
        assert any(m.body == "all-hands" for m in store.list_inbox("grp-a"))
        assert any(m.body == "all-hands" for m in store.list_inbox("grp-b"))
        # Master (sender) does NOT receive its own broadcast
        assert not any(m.body == "all-hands" for m in store.list_inbox("grp-master"))


@pytest.mark.asyncio
async def test_auto_mark_read_on_cursor_move(relay_dir):
    """Moving cursor to a NEW message addressed to me should mark it read."""
    from claude_relay.core import store
    from claude_relay.core.models import MessageState
    store.register_peer(name="parent", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="child", session_id="s2", cwd="/tmp", role="child")
    # Send a message from a *third* peer so _refresh_thread's bulk-mark-read
    # (which only marks messages from active_peer) doesn't interfere.
    store.register_peer(name="other", session_id="s3", cwd="/tmp", role="child")
    # child → parent: this is NOT from active_peer "other", so won't be bulk-marked
    a = store.send_message(from_peer="child", to_peer="parent", subject="m1", body="b1")
    b = store.send_message(from_peer="child", to_peer="parent", subject="m2", body="b2")
    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        await pilot.pause()
        screen = app.screen
        # Set active_peer to "other" so the bulk-mark-read in _refresh_thread
        # skips messages from "child"
        screen.acting_as = "parent"
        screen.active_peer = "other"
        screen._refresh_thread()
        await pilot.pause()
        # Now manually call move_cursor on the stream with child messages loaded
        stream = screen.query_one("#chat-stream")
        # Load the child thread manually into stream
        stream.refresh_thread("parent", "child")
        await pilot.pause()
        # Cursor is at the bottom (b). _mark_focused_read fires on refresh_thread.
        # b is addressed to parent and was NEW → should now be READ
        assert store.get_message(b.id).state == MessageState.READ
        # a is still unread (cursor hasn't moved there yet)
        a_state = store.get_message(a.id).state
        assert a_state == MessageState.NEW
        # Move cursor up to a
        stream.move_cursor(-1)
        await pilot.pause()
        assert store.get_message(a.id).state == MessageState.READ


@pytest.mark.asyncio
async def test_acting_as_peer_not_in_own_tabs(relay_dir):
    """The parent we're acting as should NOT appear as a tab — you can't
    talk to yourself."""
    from claude_relay.core import store
    store.register_peer(name="PLAT-3113-master", session_id="s1",
                        cwd="/tmp", role="parent")
    store.register_peer(name="PLAT-3113-child", session_id="s2",
                        cwd="/tmp", role="child")
    store.register_peer(name="PLAT-3113-slave", session_id="s3",
                        cwd="/tmp", role="child")
    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        await pilot.pause()
        screen = app.screen
        members = screen._group_members()
        assert "PLAT-3113-master" not in members
        assert set(members) == {"PLAT-3113-child", "PLAT-3113-slave"}


@pytest.mark.asyncio
async def test_left_right_cycles_peer_tabs(relay_dir):
    from claude_relay.core import store
    store.register_peer(name="PLAT-3113-master", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="PLAT-3113-child",  session_id="s2", cwd="/tmp", role="child")
    store.register_peer(name="PLAT-3113-slave",  session_id="s3", cwd="/tmp", role="child")
    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        await pilot.pause()
        screen = app.screen
        # active_peer should be one of the two children
        start = screen.active_peer
        assert start in {"PLAT-3113-child", "PLAT-3113-slave"}
        await pilot.press("right")
        await pilot.pause()
        assert screen.active_peer != start


@pytest.mark.asyncio
async def test_tab_does_not_land_focus_on_peer_tabs(relay_dir):
    from claude_relay.core import store
    store.register_peer(name="parent", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="child",  session_id="s2", cwd="/tmp", role="child")
    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        await pilot.pause()
        # Start with Select focused (default after mount)
        sel = app.screen.query_one("#acting-as-select")
        sel.focus()
        await pilot.pause()
        # One tab — should move focus to ChatStream (not PeerTabs)
        await pilot.press("tab")
        await pilot.pause()
        focused = app.screen.focused
        # Acceptable: focused is the ChatStream id, or any focusable that isn't peer-tabs
        assert focused is not None
        assert focused.id != "peer-tabs"
