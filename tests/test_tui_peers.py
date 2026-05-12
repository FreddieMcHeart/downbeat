import pytest

from claude_relay.tui.app import RelayApp


@pytest.mark.asyncio
async def test_peer_list_shows_registered_peers(relay_dir):
    from claude_relay.core import store
    store.register_peer(name="parent", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="child", session_id="s2", cwd="/tmp", role="child")
    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        await pilot.pause()
        peer_widget = app.screen.query_one("PeerList")
        names = [item.peer_name for item in peer_widget.items]
        assert names == ["parent", "child"] or names == ["child", "parent"]


@pytest.mark.asyncio
async def test_peer_list_acting_as_default_first_parent(relay_dir):
    from claude_relay.core import store
    store.register_peer(name="parent", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="child", session_id="s2", cwd="/tmp", role="child")
    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        await pilot.pause()
        peer_widget = app.screen.query_one("PeerList")
        assert peer_widget.acting_as == "parent"


@pytest.mark.asyncio
async def test_peer_list_unread_count(relay_dir):
    from claude_relay.core import store
    store.register_peer(name="parent", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="child", session_id="s2", cwd="/tmp", role="child")
    store.send_message(from_peer="parent", to_peer="child", subject="x", body="y")
    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        await pilot.pause()
        peer_widget = app.screen.query_one("PeerList")
        peer_widget.refresh_from_store()
        await pilot.pause()
        child_row = next(i for i in peer_widget.items if i.peer_name == "child")
        assert child_row.unread == 1
