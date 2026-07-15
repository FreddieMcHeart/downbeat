import pytest

from downbeat.tui.app import RelayApp


@pytest.mark.asyncio
async def test_group_members_uses_explicit_parent_not_name_shape(relay_dir):
    """Tabs must reflect Peer.parent, not a name-prefix guess — a child whose
    name shares nothing with its parent's name is still grouped correctly,
    and a differently-paired child of another parent never leaks in."""
    from downbeat.core import store
    store.register_peer(name="parent", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="alpha", session_id="s2", cwd="/tmp", role="child",
                        parent="parent")
    store.register_peer(name="beta", session_id="s3", cwd="/tmp", role="child",
                        parent="parent")
    store.register_peer(name="PLAT-3113-master", session_id="s4", cwd="/tmp", role="parent")
    store.register_peer(name="PLAT-3113-child", session_id="s5", cwd="/tmp", role="child",
                        parent="PLAT-3113-master")
    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        await pilot.pause()
        screen = app.screen
        # If acting_as defaults to a different parent, force it
        screen.acting_as = "parent"
        members = screen._group_members()
        # Only "parent"'s own paired children, excluding "parent" itself
        assert set(members) == {"alpha", "beta"}
        assert "PLAT-3113-master" not in members
        assert "PLAT-3113-child" not in members
