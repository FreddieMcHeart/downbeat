import pytest

from claude_relay.tui.app import RelayApp


@pytest.mark.skip(reason="three-pane view replaced by chat view")
@pytest.mark.asyncio
async def test_peer_list_shows_registered_peers(relay_dir):
    from claude_relay.core import store
    store.register_peer(name="parent", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="child", session_id="s2", cwd="/tmp", role="child")
    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        await pilot.pause()
        peer_widget = app.screen.query_one("PeerList")
        # List shows all peers (parent + children).
        # "parent" has no "-" so prefix is empty → fallback: all peers shown.
        names = [item.peer_name for item in peer_widget.items]
        assert "child" in names
        assert "parent" in names


@pytest.mark.skip(reason="three-pane view replaced by chat view")
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


@pytest.mark.skip(reason="three-pane view replaced by chat view")
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


@pytest.mark.skip(reason="three-pane view replaced by chat view")
@pytest.mark.asyncio
async def test_dropdown_lists_only_parents(relay_dir):
    from claude_relay.core import store
    store.register_peer(name="P1", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="P2", session_id="s2", cwd="/tmp", role="parent")
    store.register_peer(name="C1", session_id="s3", cwd="/tmp", role="child")
    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        peer_widget = app.screen.query_one("PeerList")
        peer_widget.refresh_from_store()
        # acting_as must be one of the parents, not the child
        assert peer_widget.acting_as in {"P1", "P2"}


@pytest.mark.skip(reason="three-pane view replaced by chat view")
@pytest.mark.asyncio
async def test_list_shows_all_related_peers_including_parent(relay_dir):
    from claude_relay.core import store
    store.register_peer(name="PLAT-3113-master", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="PLAT-3113-child", session_id="s2", cwd="/tmp", role="child")
    store.register_peer(name="PLAT-3113-slave", session_id="s3", cwd="/tmp", role="child")
    store.register_peer(name="other-child", session_id="s4", cwd="/tmp", role="child")
    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        peer_widget = app.screen.query_one("PeerList")
        peer_widget.refresh_from_store()
        names = [item.peer_name for item in peer_widget.items]
        assert set(names) == {"PLAT-3113-master", "PLAT-3113-child", "PLAT-3113-slave"}
        assert "other-child" not in names


@pytest.mark.asyncio
async def test_list_falls_back_to_ungrouped_peers_when_prefix_empty(relay_dir):
    """When acting-as parent has no '-', tabs should show only other
    ungrouped peers (no '-' in name)."""
    from claude_relay.core import store
    store.register_peer(name="parent", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="alpha",  session_id="s2", cwd="/tmp", role="child")
    store.register_peer(name="beta",   session_id="s3", cwd="/tmp", role="child")
    store.register_peer(name="PLAT-3113-master", session_id="s4", cwd="/tmp", role="parent")
    store.register_peer(name="PLAT-3113-child",  session_id="s5", cwd="/tmp", role="child")
    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        await pilot.pause()
        screen = app.screen
        # If acting_as defaults to a different parent, force it
        screen.acting_as = "parent"
        members = screen._group_members()
        # Only ungrouped peers, excluding "parent" itself
        assert set(members) == {"alpha", "beta"}
        assert "PLAT-3113-master" not in members
        assert "PLAT-3113-child" not in members
