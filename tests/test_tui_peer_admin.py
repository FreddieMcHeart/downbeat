from datetime import UTC

import pytest

from downbeat.tui.app import RelayApp
from downbeat.tui.widgets.add_peer_modal import AddPeerModal
from downbeat.tui.widgets.peer_admin import (
    GcStaleModal,
    RemovePeerConfirm,
    perform_remove_peer,
)


@pytest.mark.asyncio
async def test_add_peer_programmatic(relay_dir):
    from downbeat.core import store
    from downbeat.tui.screens.peers import PeersScreen
    store.register_peer(name="existing", session_id="s0", cwd="/tmp", role="parent")
    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        # Open PeersScreen then press n to open AddPeerModal
        app.push_screen(PeersScreen())
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        assert isinstance(app.screen, AddPeerModal), (
            f"Expected AddPeerModal, got {type(app.screen)}"
        )
        modal = app.screen
        modal._name.value = "new-peer"
        modal._session_id.value = "abc"
        modal._cwd.value = "/tmp"
        modal.submit()
        await pilot.pause()
        assert any(p.name == "new-peer" for p in store.list_peers())


@pytest.mark.asyncio
async def test_remove_peer_helper(relay_dir):
    from downbeat.core import store
    from downbeat.core.errors import PeerNotFound
    store.register_peer(name="rm-me", session_id="s", cwd="/tmp", role="child")
    perform_remove_peer("rm-me")
    with pytest.raises(PeerNotFound):
        store.get_peer("rm-me")


@pytest.mark.asyncio
async def test_gc_stale_prunes_only_old_peers(relay_dir):
    import json
    from datetime import datetime, timedelta

    from downbeat.core import store

    # Create two peers
    store.register_peer(name="old", session_id="s1", cwd="/tmp", role="child")
    store.register_peer(name="new", session_id="s2", cwd="/tmp", role="child")

    # Backdate "old" by 30 days by writing directly to sessions.json
    from downbeat.core import paths
    sessions_file = paths.SESSIONS_FILE
    data = json.loads(sessions_file.read_text())
    data["old"]["last_seen"] = (
        datetime.now(UTC) - timedelta(days=30)
    ).isoformat(timespec="seconds")
    sessions_file.write_text(json.dumps(data))

    # Reload store so it picks up the changed file
    import importlib
    importlib.reload(store)

    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        # Open PeersScreen then press g to open GcStaleModal
        from downbeat.tui.screens.peers import PeersScreen
        app.push_screen(PeersScreen())
        await pilot.pause()
        await pilot.press("g")
        await pilot.pause()
        assert isinstance(app.screen, GcStaleModal), (
            f"Expected GcStaleModal, got {type(app.screen)}"
        )
        modal = app.screen
        modal._days.value = "14"
        modal._refresh_preview()
        pruned = modal._prune()
        assert "old" in pruned
        assert "new" not in pruned


@pytest.mark.asyncio
async def test_remove_peer_y_keybinding_triggers_removal(relay_dir):
    """Pressing 'y' in the RemovePeerConfirm modal must actually remove the peer."""
    from downbeat.core import store
    from downbeat.core.errors import PeerNotFound
    store.register_peer(name="to-remove", session_id="s", cwd="/tmp", role="child")
    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        app.push_screen(RemovePeerConfirm("to-remove"))
        await pilot.pause()
        await pilot.press("y")
        await pilot.pause()
        # Peer should be gone
        with pytest.raises(PeerNotFound):
            store.get_peer("to-remove")


@pytest.mark.asyncio
async def test_peers_screen_lists_peers(relay_dir):
    from downbeat.core import store
    from downbeat.tui.screens.peers import PeersScreen
    store.register_peer(name="p1", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="p2", session_id="s2", cwd="/tmp", role="child")
    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        app.push_screen(PeersScreen())
        await pilot.pause()
        table = app.screen.query_one("#peers-table")
        # 2 peers
        assert table.row_count == 2


@pytest.mark.asyncio
async def test_peers_screen_groups_by_prefix(relay_dir):
    """Peers with shared prefix appear adjacent, parents before children."""
    from downbeat.core import store
    from downbeat.tui.screens.peers import PeersScreen
    # Register intentionally out-of-order
    store.register_peer(name="PLAT-3113-child", session_id="s1", cwd="/tmp", role="child")
    store.register_peer(name="PLAT-2972-master", session_id="s2", cwd="/tmp", role="parent")
    store.register_peer(name="PLAT-3113-master", session_id="s3", cwd="/tmp", role="parent")
    store.register_peer(name="PLAT-2972-child", session_id="s4", cwd="/tmp", role="child")
    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        app.push_screen(PeersScreen())
        await pilot.pause()
        table = app.screen.query_one("#peers-table")
        # Read the name column from each non-blank row in order
        names: list[str] = []
        for row_idx in range(table.row_count):
            row = table.get_row_at(row_idx)
            name = row[0].strip() if row[0] else ""
            if name:
                names.append(name)
        # Both PLAT-2972 rows together, both PLAT-3113 rows together, with
        # the parent first inside each group.
        expected = ["PLAT-2972-master", "PLAT-2972-child",
                    "PLAT-3113-master", "PLAT-3113-child"]
        assert names == expected
