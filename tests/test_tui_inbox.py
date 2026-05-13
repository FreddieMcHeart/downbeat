import pytest

from claude_relay.tui.app import RelayApp


@pytest.mark.asyncio
async def test_inbox_shows_messages_for_acting_as(relay_dir):
    from claude_relay.core import store
    store.register_peer(name="parent", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="child", session_id="s2", cwd="/tmp", role="child")
    store.send_message(from_peer="parent", to_peer="child", subject="A", body="x")
    store.send_message(from_peer="parent", to_peer="child", subject="B", body="y")
    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        await pilot.pause()
        # Switch acting-as to child
        peers = app.screen.query_one("PeerList")
        peers.acting_as = "child"
        peers.refresh_from_store()
        await pilot.pause()
        inbox = app.screen.query_one("InboxList")
        inbox.refresh_for_peer("child")
        await pilot.pause()
        subjects = inbox.subjects()
        assert {"A", "B"} <= set(subjects)


@pytest.mark.asyncio
async def test_inbox_empty_when_no_messages(relay_dir):
    from claude_relay.core import store
    store.register_peer(name="p", session_id="s", cwd="/tmp", role="parent")
    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        await pilot.pause()
        inbox = app.screen.query_one("InboxList")
        inbox.refresh_for_peer("p")
        assert inbox.subjects() == []


@pytest.mark.asyncio
async def test_inbox_does_not_include_archived_by_default(relay_dir):
    from claude_relay.core import store
    store.register_peer(name="p", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="c", session_id="s2", cwd="/tmp", role="child")
    msg = store.send_message(from_peer="p", to_peer="c", subject="A", body="x")
    store.mark_read(msg.id)
    store.reply_to(msg.id, body="reply", from_peer="c")
    # After reply_to, the original is archived in processed/
    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        inbox = app.screen.query_one("InboxList")
        inbox.refresh_for_peer("c")
        # archived 'A' should NOT show; only any new messages in inbox/ should
        assert "A" not in inbox.subjects()


@pytest.mark.asyncio
async def test_inbox_preserves_selection_across_refresh(relay_dir):
    """Refreshing the inbox (e.g. after a read mutation) must not reset
    the cursor to row 0 — selection should follow the same message id."""
    from claude_relay.core import store
    store.register_peer(name="p", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="c", session_id="s2", cwd="/tmp", role="child")
    msgs = [
        store.send_message(from_peer="p", to_peer="c",
                           subject=f"m{i}", body="x")
        for i in range(3)
    ]
    # Newest message comes first after sort; so msgs[2] is at row 0
    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        inbox = app.screen.query_one("InboxList")
        inbox.refresh_for_peer("c")
        await pilot.pause()
        # Move cursor to row 1 (second-newest message: msgs[1])
        inbox.move_cursor(row=1)
        target_id = inbox.selected_message().id
        # Mutate a different message to trigger a refresh-like situation
        store.mark_read(msgs[2].id)
        inbox.refresh_for_peer("c")
        await pilot.pause()
        # Cursor must still be on `target_id`, not back at row 0
        assert inbox.selected_message().id == target_id


@pytest.mark.asyncio
async def test_inbox_shows_id_column(relay_dir):
    from claude_relay.core import store
    store.register_peer(name="p", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="c", session_id="s2", cwd="/tmp", role="child")
    msg = store.send_message(from_peer="p", to_peer="c", subject="hi", body="b")
    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        inbox = app.screen.query_one("InboxList")
        inbox.refresh_for_peer("c")
        col_labels = [str(c.label) for c in inbox.columns.values()]
        assert "id" in col_labels
