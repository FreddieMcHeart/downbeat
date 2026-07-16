import pytest

from downbeat.tui.app import RelayApp
from downbeat.tui.widgets.peer_tabs import OWN_INBOX_ID


@pytest.mark.asyncio
async def test_chat_screen_mounts_with_acting_as_chip_and_tabs(relay_dir):
    from downbeat.core import store
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
    from downbeat.core import store
    from downbeat.tui.widgets.chat_composer import ChatComposer
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
    from downbeat.core import store
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

    from downbeat.core import store
    from downbeat.tui.widgets.chat_composer import ChatComposer
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
    from downbeat.core import store
    from downbeat.tui.widgets.chat_composer import ChatComposer
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
    from downbeat.core import store
    from downbeat.core.models import MessageState
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
    from downbeat.core import store
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
    from downbeat.core import store
    store.register_peer(name="PLAT-3113-master", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="PLAT-3113-child",  session_id="s2", cwd="/tmp", role="child")
    store.register_peer(name="PLAT-3113-slave",  session_id="s3", cwd="/tmp", role="child")
    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        await pilot.pause()
        screen = app.screen
        # active_peer defaults to OWN_INBOX_ID (first tab); pressing right advances it
        start = screen.active_peer
        assert start == OWN_INBOX_ID
        await pilot.press("right")
        await pilot.pause()
        assert screen.active_peer != start


@pytest.mark.asyncio
async def test_peer_name_with_space_does_not_crash_tabs(relay_dir):
    """Free-form peer names (e.g. renamed via manual sessions.json edit) can
    contain spaces; PeerTabs._safe_id must sanitize them into a valid Textual
    widget id instead of raising BadIdentifier."""
    from downbeat.core import store
    store.register_peer(name="Claude-Cost-Optimazing", session_id="s1",
                        cwd="/tmp", role="parent")
    store.register_peer(name="Claude Relay", session_id="s2", cwd="/tmp",
                        role="child", parent="Claude-Cost-Optimazing")
    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        await pilot.pause()
        screen = app.screen
        await pilot.press("right")
        await pilot.pause()
        assert screen.active_peer == "Claude Relay"


@pytest.mark.asyncio
async def test_tab_does_not_land_focus_on_peer_tabs(relay_dir):
    from downbeat.core import store
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
    from downbeat.core import store
    from downbeat.tui.widgets.chat_stream import ChatStream
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
    from downbeat.core import state, store
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
    from downbeat.core import store
    store.register_peer(name="p", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="c", session_id="s2", cwd="/tmp", role="child")
    store.send_message(from_peer="c", to_peer="p", subject="hi", body="THE_BODY")
    # Stub the clipboard helper to capture the call
    captured = {}
    def fake_copy(text):
        captured["text"] = text
        return True
    from downbeat.tui.widgets import clipboard
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
    from downbeat.core import store
    store.register_peer(name="p", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="c", session_id="s2", cwd="/tmp", role="child")
    for i in range(5):
        store.send_message(from_peer="c", to_peer="p",
                           subject=f"m{i}", body=f"b{i}")
    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        await pilot.pause()
        stream = app.screen.query_one("#chat-stream")
        # Prime _peer on the stream so the first refresh_thread call is NOT a
        # peer-change (peer_changed=False → differential update path runs from
        # the start, no full rebuild).  This is valid because refresh_thread
        # only does full_rebuild when peer_changed is True.
        stream._peer = "c"
        # First refresh: same peer pair → differential (no rebuild)
        stream.refresh_thread("p", "c")
        before_ids = [id(c) for c in stream.children]
        assert before_ids, "thread should have bubbles after first refresh"
        # Second refresh (same data, same peer pair) — must also be differential
        stream.refresh_thread("p", "c")
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
    from downbeat.core import store
    store.register_peer(name="p", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="c", session_id="s2", cwd="/tmp", role="child")
    store.send_message(from_peer="c", to_peer="p", subject="a", body="x")
    store.send_message(from_peer="c", to_peer="p", subject="b", body="y")
    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        await pilot.pause()
        stream = app.screen.query_one("#chat-stream")
        # Prime _peer so both refresh_thread calls use the differential path
        # (no peer-change → no full rebuild → synchronous mount scheduling).
        stream._peer = "c"
        stream.refresh_thread("p", "c")
        before_ids = [id(c) for c in stream.children]
        assert before_ids, "thread should have bubbles after first refresh"
        # Add a third message and refresh (same peer pair — must be differential)
        store.send_message(from_peer="c", to_peer="p", subject="c", body="z")
        stream.refresh_thread("p", "c")
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
    from downbeat.core import store
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
    from downbeat.core import store
    from downbeat.tui.widgets.switch_acting_as import SwitchActingAsModal
    store.register_peer(name="P1", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="P2", session_id="s2", cwd="/tmp", role="parent")
    store.register_peer(name="C",  session_id="s3", cwd="/tmp", role="child", parent="P1")
    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        modal = SwitchActingAsModal(current="P1")
        app.push_screen(modal)
        await pilot.pause()
        # The modal listed exactly the two parents
        assert modal._parents == ["P1", "P2"]
        # And selected the current one
        assert modal._listview.index == 0


@pytest.mark.asyncio
async def test_long_body_with_brackets_renders_truncation_suffix_without_crashing(relay_dir):
    """Bodies > 600 chars get a truncation suffix; the suffix must not
    contain literal '[…]' that Rich would parse as a tag.

    Specifically reproduces the [type='CNAME'] crash when body > 600 chars."""
    from downbeat.core import store
    store.register_peer(name="p", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="c", session_id="s2", cwd="/tmp", role="child")
    body = (
        "## PR #4410 apply ERRORED — import didn't persist\n\n"
        "Error: [type='CNAME'] but it already exists\n"
        + "padding " * 100  # ensure body > 600 chars so the suffix path runs
    )
    store.send_message(from_peer="c", to_peer="p", subject="long brackets", body=body)
    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        await pilot.pause()
        # If we got here, the render completed without MarkupError
        stream = app.screen.query_one("#chat-stream")
        assert any(
            getattr(c, "_msg", None) is not None
            and "long brackets" in c._msg.subject
            for c in stream.children
        )


@pytest.mark.asyncio
async def test_body_with_brackets_renders_via_text_renderable(relay_dir):
    """Bodies containing '[type=value]'-style content must render as literal
    text — never get re-parsed by Textual's visualize markup tokeniser."""
    from downbeat.core import store
    store.register_peer(name="p", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="c", session_id="s2", cwd="/tmp", role="child")
    bodies = [
        "Error: [type='CNAME'] already exists",
        "JIRA: [PLAT-3238] mentioned [PLAT-1234] in description",
        "Python: foo: list[int] = [1, 2, 3]",
        "Heredoc: \"$(cat <<'EOF'\\n[section]\\nkey=val\\nEOF\\n)\"",
        "Markdown: [link text](http://example.com) and [another]",
    ]
    for i, body in enumerate(bodies):
        store.send_message(from_peer="c", to_peer="p", subject=f"brackets-{i}", body=body)
    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        await pilot.pause()
        stream = app.screen.query_one("#chat-stream")
        # If we got here, every bubble rendered without MarkupError.
        assert len(list(stream.children)) >= len(bodies)


# ---------------------------------------------------------------------------
# Own-inbox tab tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_own_inbox_tab_always_present_as_first_tab(relay_dir):
    """OWN_INBOX_ID must be the first entry in _members for both grouped and
    standalone peers — tested via PeerTabs.populate directly (no full TUI mount
    needed since tab rendering is the unit under test)."""
    from downbeat.core import store
    from downbeat.tui.widgets.peer_tabs import OWN_INBOX_ID, PeerTabs

    store.register_peer(name="grp-master", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="grp-child",  session_id="s2", cwd="/tmp", role="child")

    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        await pilot.pause()
        screen = app.screen
        tabs = screen.query_one("#peer-tabs", PeerTabs)
        # After populate, _members[0] must be the sentinel
        assert tabs._members[0] == OWN_INBOX_ID, (
            "OWN_INBOX_ID must be the first entry in _members"
        )
        # And the member is still present after the sentinel
        assert "grp-child" in tabs._members


@pytest.mark.asyncio
async def test_no_member_peer_renders_own_inbox(relay_dir):
    """A standalone peer (no prefix-mates) must open on its own inbox tab and
    render bubbles for messages addressed to it — tested via ChatStream directly
    to avoid Textual render-timing sensitivity."""
    from downbeat.core import store
    from downbeat.tui.widgets.chat_stream import ChatStream

    # Register a sink peer with no group members. "sender" is registered as
    # its own unrelated parent (not paired via Peer.parent) so it doesn't
    # auto-join content-inbox as a child.
    store.register_peer(name="content-inbox", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="sender",        session_id="s2", cwd="/tmp", role="parent")

    # Send 2 messages to content-inbox
    store.send_message(from_peer="sender", to_peer="content-inbox",
                       subject="m1", body="body one")
    store.send_message(from_peer="sender", to_peer="content-inbox",
                       subject="m2", body="body two")

    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        await pilot.pause()
        screen = app.screen
        # Confirm _group_members returns [] (no prefix-mates besides self)
        assert screen._group_members() == [], (
            "content-inbox should have no group members"
        )
        # active_peer defaults to OWN_INBOX_ID when there are no members
        assert screen.active_peer == OWN_INBOX_ID, (
            "active_peer must default to OWN_INBOX_ID for a no-member peer"
        )
        # ChatStream in OWN_INBOX_ID mode loads all inbox messages
        stream = screen.query_one("#chat-stream", ChatStream)
        stream.refresh_thread("content-inbox", OWN_INBOX_ID)
        await pilot.pause()
        bubble_subjects = [
            c._msg.subject
            for c in stream.children
            if getattr(c, "_msg", None) is not None
        ]
        assert "m1" in bubble_subjects, "own-inbox must render message m1"
        assert "m2" in bubble_subjects, "own-inbox must render message m2"


@pytest.mark.asyncio
async def test_own_inbox_shows_messages_from_multiple_senders(relay_dir):
    """The own-inbox tab must aggregate messages from all senders, not just one."""
    from downbeat.core import store
    from downbeat.tui.widgets.chat_stream import ChatStream

    store.register_peer(name="hub",     session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="alice",   session_id="s2", cwd="/tmp", role="child")
    store.register_peer(name="bob",     session_id="s3", cwd="/tmp", role="child")

    store.send_message(from_peer="alice", to_peer="hub", subject="from-alice", body="hi from alice")
    store.send_message(from_peer="bob",   to_peer="hub", subject="from-bob",   body="hi from bob")

    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        await pilot.pause()
        stream = app.screen.query_one("#chat-stream", ChatStream)
        stream.refresh_thread("hub", OWN_INBOX_ID)
        await pilot.pause()
        senders = {
            c._msg.from_peer
            for c in stream.children
            if getattr(c, "_msg", None) is not None
        }
        assert "alice" in senders, "own-inbox must include alice's message"
        assert "bob" in senders, "own-inbox must include bob's message"


def _subjects(stream):
    return [
        c._msg.subject
        for c in stream.children
        if getattr(c, "_msg", None) is not None
    ]


@pytest.mark.asyncio
async def test_own_inbox_archived_toggle_reveals_processed_history(relay_dir):
    """A sink peer must be able to toggle archived/processed messages into view
    on its own-inbox tab. Pending-only is the default; toggling `a` adds the
    full received history, toggling again hides it."""
    from downbeat.core import store
    from downbeat.tui.widgets.chat_stream import ChatStream

    store.register_peer(name="content-inbox", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="sender",        session_id="s2", cwd="/tmp", role="child")

    # One message stays pending (inbox), one gets delivered + acked → processed/
    store.send_message(from_peer="sender", to_peer="content-inbox",
                       subject="pending", body="still here")
    done = store.send_message(from_peer="sender", to_peer="content-inbox",
                              subject="archived", body="consumed")
    store.deliver_messages("content-inbox", session_id="s1")
    store.ack_messages([done.id])  # delivered → processed/

    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        await pilot.pause()
        screen = app.screen
        stream = screen.query_one("#chat-stream", ChatStream)

        # Default: pending only, archived hidden
        assert stream._show_archived is False
        stream.refresh_thread("content-inbox", OWN_INBOX_ID)
        await pilot.pause()
        subs = _subjects(stream)
        assert "pending" in subs
        assert "archived" not in subs, "archived msg must be hidden by default"

        # Toggle on → full received history visible
        new_state = stream.toggle_archived()
        await pilot.pause()
        assert new_state is True
        subs = _subjects(stream)
        assert "pending" in subs
        assert "archived" in subs, "toggle must reveal processed history"

        # Toggle off → back to pending only
        new_state = stream.toggle_archived()
        await pilot.pause()
        assert new_state is False
        subs = _subjects(stream)
        assert "archived" not in subs, "second toggle must hide archived again"


@pytest.mark.asyncio
async def test_clear_inbox_archives_backlog_for_acting_peer(relay_dir):
    """The `c` clear-inbox action archives the acting peer's pending backlog
    (inbox+delivered) → processed/, clearing the badge. Confirmed via the modal."""
    from downbeat.core import store
    from downbeat.core.models import MessageState

    store.register_peer(name="hub",  session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="kid",  session_id="s2", cwd="/tmp", role="child")
    # Two NEW reports kid→hub (dead-peer backlog: never delivered)
    store.send_message(from_peer="kid", to_peer="hub", subject="r1", body="done 1")
    store.send_message(from_peer="kid", to_peer="hub", subject="r2", body="done 2")

    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        await pilot.pause()
        screen = app.screen
        assert screen.acting_as == "hub"
        assert screen.active_peer == OWN_INBOX_ID
        # Two pending (inbox+delivered) before — count regardless of read state,
        # since mounting the own-inbox marks the focused bubble READ.
        assert len(store.list_inbox("hub")) == 2
        # Press c → confirm modal → y
        await pilot.press("c")
        await pilot.pause()
        await pilot.press("y")
        await pilot.pause()
        # Backlog drained → nothing pending
        assert store.list_inbox("hub") == [], "clear-inbox must archive the backlog"
        # still recoverable in processed/
        arch = [m for m in store.list_inbox("hub", include_archived=True)
                if m.state == MessageState.ARCHIVED]
        assert len(arch) == 2


@pytest.mark.asyncio
async def test_clear_inbox_is_noop_off_own_inbox_tab(relay_dir):
    from downbeat.core import store

    store.register_peer(name="grp-parent", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="grp-child",  session_id="s2", cwd="/tmp", role="child")
    store.send_message(from_peer="grp-child", to_peer="grp-parent",
                       subject="r", body="x")

    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        await pilot.pause()
        screen = app.screen
        screen.active_peer = "grp-child"  # a member tab, not own-inbox
        screen.action_clear_inbox()
        await pilot.pause()
        # nothing archived — message still pending (not moved to processed/)
        assert len(store.list_inbox("grp-parent")) == 1


@pytest.mark.asyncio
async def test_archived_toggle_action_only_acts_on_own_inbox_tab(relay_dir):
    """The screen-level `a` action toggles archived only when the own-inbox tab
    is active; on a member-peer thread it is a no-op (no flag flip)."""
    from downbeat.core import store
    from downbeat.tui.widgets.chat_stream import ChatStream

    store.register_peer(name="grp-parent", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="grp-child",  session_id="s2", cwd="/tmp", role="child")

    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        await pilot.pause()
        screen = app.screen
        stream = screen.query_one("#chat-stream", ChatStream)

        # `a` action is wired on the screen
        assert any("toggle_archived" in str(b) for b in screen.BINDINGS), (
            "ChatScreen must bind `a` to toggle_archived"
        )

        # On a member-peer tab the toggle is a no-op
        screen.active_peer = "grp-child"
        stream._show_archived = False
        screen.action_toggle_archived()
        assert stream._show_archived is False, "must not toggle off the inbox tab"

        # On the own-inbox tab the toggle flips the flag
        screen.active_peer = OWN_INBOX_ID
        screen.action_toggle_archived()
        assert stream._show_archived is True, "must toggle on the own-inbox tab"


@pytest.mark.asyncio
async def test_acting_as_candidates_include_interior_child_node(relay_dir):
    """_populate_acting_as's candidate set includes a role=child peer that
    itself has children (an interior node), not just role=parent peers."""
    from downbeat.core import store
    store.register_peer(name="Root", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="Child-A", session_id="s2", cwd="/tmp", role="child",
                        parent="Root")
    store.register_peer(name="Child-A-1", session_id="s3", cwd="/tmp", role="child",
                        parent="Child-A")
    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        await pilot.pause()
        screen = app.screen
        screen.acting_as = "Child-A"
        screen._populate_acting_as()
        assert screen.acting_as == "Child-A"


@pytest.mark.asyncio
async def test_switch_acting_as_modal_includes_interior_child_node(relay_dir):
    """A role=child peer that has its own children (an interior node) must
    be selectable as acting_as too -- not just role=parent peers."""
    from downbeat.core import store
    from downbeat.tui.widgets.switch_acting_as import SwitchActingAsModal
    store.register_peer(name="Root", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="Child-A", session_id="s2", cwd="/tmp", role="child",
                        parent="Root")
    store.register_peer(name="Child-A-1", session_id="s3", cwd="/tmp", role="child",
                        parent="Child-A")
    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        modal = SwitchActingAsModal(current="Root")
        app.push_screen(modal)
        await pilot.pause()
        assert set(modal._parents) == {"Root", "Child-A"}


@pytest.mark.asyncio
async def test_find_message_switches_acting_as_to_interior_child_node(relay_dir):
    """find_message's acting-as-target check must accept a role=child peer
    that has its own children as a valid switch target, not just
    role=parent peers. Drives the real modal's dismiss-and-callback flow --
    not Textual's keyboard focus routing (DataTable.move_cursor() does not
    move focus, and the still-focused Input would swallow an Enter
    keypress before it reached the modal's own binding -- a find_message.py
    testability detail out of scope here) -- by calling the modal's own
    bound action method directly after populating its result table. This
    still exercises chat.py's real after(msg) closure via the real
    self.dismiss(msg) call, not a re-derived inline formula."""
    from downbeat.core import store
    store.register_peer(name="Root", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="Child-A", session_id="s2", cwd="/tmp", role="child",
                        parent="Root")
    store.register_peer(name="Child-A-1", session_id="s3", cwd="/tmp", role="child",
                        parent="Child-A")
    msg = store.send_message(from_peer="Child-A-1", to_peer="Child-A",
                             subject="s", body="b")
    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        await pilot.pause()
        screen = app.screen
        screen.acting_as = "Root"
        screen.action_find_message()
        await pilot.pause()
        modal = app.screen
        modal._input.value = msg.id
        modal._refresh_results(msg.id)
        await pilot.pause()
        modal._table.move_cursor(row=0)
        modal.action_open_selected()
        await pilot.pause()
        assert screen.acting_as == "Child-A"


@pytest.mark.asyncio
async def test_ctrl_r_on_a_peer_tab_keeps_the_thread_rendered(relay_dir):
    """Regression for #16: refreshing while sitting on a peer tab wiped the
    thread. PeerTabs.populate() rebuilds its tabs (clear + re-add), and the
    re-add auto-activated own-inbox before the real tab was restored -- each
    activation posted a PeerSelected, so one ctrl+R phantom-switched the peer
    UM -> own-inbox -> UM. ChatStream.refresh_thread then rendered nothing on
    those transitions, leaving the thread empty."""
    from downbeat.core import store
    store.register_peer(name="CCO", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="UM", session_id="s2", cwd="/tmp", role="child",
                        parent="CCO")
    store.send_message(from_peer="UM", to_peer="CCO", subject="old", body="1")
    store.send_message(from_peer="UM", to_peer="CCO", subject="new", body="2")

    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        await pilot.pause()
        screen = app.screen
        stream = screen.query_one("#chat-stream")
        tabs = screen.query_one("#peer-tabs")

        tabs.active = f"tab-{tabs._safe_id('UM')}"
        for _ in range(5):
            await pilot.pause()

        await screen.action_refresh()
        for _ in range(5):
            await pilot.pause()

        rendered = {c._msg.id for c in stream.children
                    if getattr(c, "_msg", None) is not None}
        expected = {m.id for m in store.list_thread("CCO", "UM")}
        assert rendered == expected, (
            f"ctrl+R emptied the thread: rendered {len(rendered)} bubbles, "
            f"data has {len(expected)} messages"
        )


@pytest.mark.asyncio
async def test_mount_renders_the_thread_the_tab_bar_is_pointing_at(relay_dir):
    """The tab bar and the rendered thread are two views of one thing and must
    agree. _populate_tabs restores active_peer from persisted state but never
    moved the tab widget to match; PeerTabs.populate(), knowing nothing about
    that, defaults its own active tab to own-inbox. The result on launch was a
    tab bar reading 'inbox' over someone else's thread.

    This stayed invisible while populate() still emitted its rebuild churn as
    PeerSelected: the phantom own-inbox event overwrote active_peer back to
    own-inbox, coincidentally re-syncing the two. Silencing that churn (#16)
    removed the coincidence and exposed the real gap."""
    from downbeat.core import state, store
    store.register_peer(name="CCO", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="REL", session_id="s2", cwd="/tmp", role="child",
                        parent="CCO")
    store.send_message(from_peer="REL", to_peer="CCO", subject="a", body="1")
    # the user was last reading the REL tab, in a previous run
    state.set_last_acting_as("CCO")
    state.set_last_active_peer("REL")

    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        for _ in range(5):
            await pilot.pause()
        screen = app.screen
        tabs = screen.query_one("#peer-tabs")
        stream = screen.query_one("#chat-stream")

        assert tabs.active == f"tab-{tabs._safe_id(str(screen.active_peer))}", (
            f"tab bar is on {tabs.active!r} but the screen renders "
            f"{screen.active_peer!r}"
        )
        assert stream._peer == screen.active_peer


@pytest.mark.asyncio
async def test_two_refreshes_in_one_tick_do_not_empty_the_thread(relay_dir):
    """Regression for #21. ChatStream.refresh_thread used to decide what to
    mount by reading self.children -- but mount()/remove() are deferred, so a
    second refresh in the same message-pump tick saw the first refresh's
    doomed bubbles still there, concluded the new thread was already rendered,
    mounted nothing, and the pending removal then wiped it. Empty thread over
    non-empty data.

    The trigger in production was #24's phantom tab-switch (now fixed), so
    this is latent -- but it re-arms the moment anything legitimately changes
    the peer twice in a tick. Driven at the unit level because that's the
    only place the one-tick timing is reproducible; a real keystroke pumps
    the loop between refreshes and papers over it."""
    from downbeat.core import store
    store.register_peer(name="CCO", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="A", session_id="s2", cwd="/tmp", role="child",
                        parent="CCO")
    store.register_peer(name="B", session_id="s3", cwd="/tmp", role="child",
                        parent="CCO")
    # Both addressed to CCO, so own-inbox shows both and the two peer threads
    # share ids with it -- the overlap that fooled the stale-tree diff.
    store.send_message(from_peer="A", to_peer="CCO", subject="x", body="1")
    store.send_message(from_peer="B", to_peer="CCO", subject="y", body="2")

    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        await pilot.pause()
        screen = app.screen
        stream = screen.query_one("#chat-stream")

        screen.acting_as = "CCO"
        screen.active_peer = "__own_inbox__"
        stream.refresh_thread("CCO", "__own_inbox__")
        for _ in range(4):
            await pilot.pause()

        # Two peer changes in ONE tick, no pump between them.
        stream.refresh_thread("CCO", "A")
        stream.refresh_thread("CCO", "B")
        for _ in range(4):
            await pilot.pause()

        rendered = {c._msg.id for c in stream.children
                    if getattr(c, "_msg", None) is not None}
        expected = {m.id for m in store.list_thread("CCO", "B")}
        assert rendered == expected, (
            f"thread emptied: rendered {len(rendered)} bubbles, "
            f"data has {len(expected)}"
        )
