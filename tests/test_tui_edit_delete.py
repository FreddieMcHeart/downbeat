import pytest

from claude_relay.tui.app import RelayApp


@pytest.mark.asyncio
async def test_edit_unread_message(relay_dir):
    from claude_relay.core import store
    store.register_peer(name="p", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="c", session_id="s2", cwd="/tmp", role="child")
    msg = store.send_message(from_peer="p", to_peer="c", subject="s", body="old")
    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        peers = app.screen.query_one("PeerList")
        peers.acting_as = "c"
        peers.refresh_from_store()
        inbox = app.screen.query_one("InboxList")
        inbox.refresh_for_peer("c")
        await pilot.pause()
        # Programmatic edit (skip modal UI for testability):
        from claude_relay.tui.widgets.edit_modal import perform_edit
        perform_edit(msg.id, new_body="new")
        assert store.get_message(msg.id).body == "new"


@pytest.mark.asyncio
async def test_edit_read_message_blocked(relay_dir):
    from claude_relay.core import store
    from claude_relay.core.errors import MessageLocked
    store.register_peer(name="p", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="c", session_id="s2", cwd="/tmp", role="child")
    msg = store.send_message(from_peer="p", to_peer="c", subject="s", body="b")
    store.mark_read(msg.id)
    import pytest

    from claude_relay.tui.widgets.edit_modal import perform_edit
    with pytest.raises(MessageLocked):
        perform_edit(msg.id, new_body="b2")


@pytest.mark.asyncio
async def test_delete_message(relay_dir):
    from claude_relay.core import store
    from claude_relay.core.errors import MessageNotFound
    store.register_peer(name="p", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="c", session_id="s2", cwd="/tmp", role="child")
    msg = store.send_message(from_peer="p", to_peer="c", subject="s", body="b")
    from claude_relay.tui.widgets.confirm import perform_delete
    perform_delete(msg.id)
    import pytest
    with pytest.raises(MessageNotFound):
        store.get_message(msg.id)
