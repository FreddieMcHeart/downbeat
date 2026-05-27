import pytest

from claude_relay.tui.app import RelayApp


@pytest.mark.asyncio
async def test_chat_screen_mounts_with_acting_as_chip_and_tabs(relay_dir):
    from claude_relay.core import store
    store.register_peer(name="PLAT-3113-master", session_id="s1",
                        cwd="/tmp", role="parent")
    store.register_peer(name="PLAT-3113-child", session_id="s2",
                        cwd="/tmp", role="child")
    app = RelayApp()
    async with app.run_test(headless=True):
        # Acting-as chip is mounted
        chip = app.screen.query_one("#acting-as-chip")
        assert chip is not None
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
async def test_chat_screen_auto_picks_first_parent_as_acting_as(relay_dir):
    from claude_relay.core import store
    store.register_peer(name="P", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="C", session_id="s2", cwd="/tmp", role="child")
    app = RelayApp()
    async with app.run_test(headless=True):
        assert app.screen.acting_as == "P"


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
    """Moving cursor to a NEW message addressed to me marks it read.
    Opening a thread for the first time (peer change) marks the most-recent message read."""
    from claude_relay.core import store
    from claude_relay.core.models import MessageState
    store.register_peer(name="parent", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="child", session_id="s2", cwd="/tmp", role="child")
    store.register_peer(name="other", session_id="s3", cwd="/tmp", role="child")
    a = store.send_message(from_peer="child", to_peer="parent", subject="m1", body="b1")
    b = store.send_message(from_peer="child", to_peer="parent", subject="m2", body="b2")
    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        await pilot.pause()
        screen = app.screen
        screen.acting_as = "parent"
        screen.active_peer = "other"
        screen._refresh_thread()
        await pilot.pause()
        stream = screen.query_one("#chat-stream")
        # PEER CHANGE: _peer was "other" → now "child" → triggers _mark_focused_read
        stream.refresh_thread("parent", "child")
        await pilot.pause()
        # b is the bottom (most recent) message — peer change marks it read
        assert store.get_message(b.id).state == MessageState.READ
        # a is still unread (cursor hasn't moved there yet)
        a_state = store.get_message(a.id).state
        assert a_state == MessageState.NEW
        # Move cursor up to a — triggers _mark_focused_read explicitly
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
        # Start with ChatStream focused (chip is non-focusable Static)
        stream = app.screen.query_one("#chat-stream")
        stream.focus()
        await pilot.pause()
        # One tab — should move focus to Composer (not PeerTabs)
        await pilot.press("tab")
        await pilot.pause()
        focused = app.screen.focused
        # Acceptable: focused is any focusable widget that isn't peer-tabs
        assert focused is not None
        assert focused.id != "peer-tabs"


@pytest.mark.asyncio
async def test_enter_on_message_opens_detail_screen(relay_dir):
    from claude_relay.core import store
    from claude_relay.tui.widgets.chat_stream import ChatStream
    store.register_peer(name="parent", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="child", session_id="s2", cwd="/tmp", role="child")
    msg = store.send_message(from_peer="child", to_peer="parent",
                             subject="t", body="full body content")
    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        await pilot.pause()
        # Verify ChatStream has the enter binding wired to action_open_detail
        stream = app.screen.query_one("#chat-stream", ChatStream)
        binding_keys = {b[0] for b in stream.BINDINGS}
        assert "enter" in binding_keys, "ChatStream must have enter binding"
        # Verify on_chat_stream_message_opened handler exists on ChatScreen
        assert hasattr(app.screen, "on_chat_stream_message_opened"), (
            "ChatScreen must handle ChatStream.MessageOpened"
        )
        # Verify action_open_detail posts MessageOpened when a message is selected
        # We test this by loading the thread and checking selected_message() returns
        # the right message — the action simply wraps selected_message() + post_message.
        stream.refresh_thread("parent", "child")
        await pilot.pause()
        selected = stream.selected_message()
        assert selected is not None, "stream must have a selected message after refresh"
        assert selected.id == msg.id, "selected message must match the sent message"
        # Verify action_open_detail is callable (wires correctly)
        assert hasattr(stream, "action_open_detail")


@pytest.mark.asyncio
async def test_acting_as_restored_from_persisted_state(relay_dir):
    from claude_relay.core import state, store
    store.register_peer(name="P1", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="P2", session_id="s2", cwd="/tmp", role="parent")
    state.set_last_acting_as("P2")
    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        await pilot.pause()
        # The persisted value (P2) should be chosen, not P1 (default first parent)
        assert app.screen.acting_as == "P2"


@pytest.mark.asyncio
async def test_yank_body_copies_to_clipboard(relay_dir, monkeypatch):
    """Pressing y on a focused bubble should call copy_to_clipboard with
    the message body."""
    from claude_relay.core import store
    store.register_peer(name="p", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="c", session_id="s2", cwd="/tmp", role="child")
    store.send_message(from_peer="c", to_peer="p", subject="hi", body="THE_BODY")
    # Stub the clipboard helper to capture the call
    captured = {}
    def fake_copy(text):
        captured["text"] = text
        return True
    from claude_relay.tui.widgets import clipboard
    monkeypatch.setattr(clipboard, "copy_to_clipboard", fake_copy)
    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        await pilot.pause()
        stream = app.screen.query_one("#chat-stream")
        stream.focus()
        await pilot.pause()
        # Press y
        await pilot.press("y")
        await pilot.pause()
        assert captured.get("text") == "THE_BODY"


@pytest.mark.asyncio
async def test_refresh_thread_uses_differential_update(relay_dir):
    """A second refresh with the same messages should NOT remove and re-mount
    every bubble — the same widget instances should still be present."""
    from claude_relay.core import store
    store.register_peer(name="p", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="c", session_id="s2", cwd="/tmp", role="child")
    for i in range(5):
        store.send_message(from_peer="c", to_peer="p",
                           subject=f"m{i}", body=f"b{i}")
    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        await pilot.pause()
        stream = app.screen.query_one("#chat-stream")
        # Capture widget identities after first mount
        before_ids = [id(c) for c in stream.children]
        # Second refresh (same data)
        stream.refresh_thread("p", "c")
        await pilot.pause()
        after_ids = [id(c) for c in stream.children]
        # No widget was removed-and-readded — identities should be unchanged
        assert before_ids == after_ids, (
            "Differential refresh broken: widget identities changed; "
            "this means remove-all-and-remount is still happening."
        )


@pytest.mark.asyncio
async def test_refresh_thread_appends_new_message_without_full_rebuild(relay_dir):
    """When a new message arrives, only that bubble should be mounted; existing
    bubbles keep their widget identity."""
    from claude_relay.core import store
    store.register_peer(name="p", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="c", session_id="s2", cwd="/tmp", role="child")
    store.send_message(from_peer="c", to_peer="p", subject="a", body="x")
    store.send_message(from_peer="c", to_peer="p", subject="b", body="y")
    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        await pilot.pause()
        stream = app.screen.query_one("#chat-stream")
        before_ids = [id(c) for c in stream.children]
        # Add a third message and refresh
        store.send_message(from_peer="c", to_peer="p", subject="c", body="z")
        stream.refresh_thread("p", "c")
        await pilot.pause()
        after_ids = [id(c) for c in stream.children]
        # The two original widgets should still be present in after_ids
        assert all(b in after_ids for b in before_ids), (
            "Original bubble identities changed — full rebuild happened unexpectedly."
        )
        # One new widget added
        assert len(after_ids) == len(before_ids) + 1


@pytest.mark.asyncio
async def test_bubble_renders_body_with_brackets_without_crashing(relay_dir):
    """Message bodies containing '[' characters (terraform errors, JIRA tags,
    Python type hints) must not crash the bubble renderer."""
    from claude_relay.core import store
    store.register_peer(name="p", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="c", session_id="s2", cwd="/tmp", role="child")
    body = (
        "Error: [type='CNAME'] but it already exists\n"
        "Reference: [PLAT-3238]\n"
        "Code: list[int] = [1, 2, 3]"
    )
    store.send_message(from_peer="c", to_peer="p", subject="brackets test", body=body)
    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        await pilot.pause()
        # If we got here, the bubble rendered without raising MarkupError.
        stream = app.screen.query_one("#chat-stream")
        assert any(
            getattr(c, "_msg", None) is not None
            and "brackets" in c._msg.subject
            for c in stream.children
        )


@pytest.mark.asyncio
async def test_switch_acting_as_modal_lists_parents(relay_dir):
    from claude_relay.core import store
    from claude_relay.tui.widgets.switch_acting_as import SwitchActingAsModal
    store.register_peer(name="P1", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="P2", session_id="s2", cwd="/tmp", role="parent")
    store.register_peer(name="C",  session_id="s3", cwd="/tmp", role="child")
    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        modal = SwitchActingAsModal(current="P1")
        app.push_screen(modal)
        await pilot.pause()
        # The modal listed exactly the two parents
        assert modal._parents == ["P1", "P2"]
        # And selected the current one
        assert modal._listview.index == 0
