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
