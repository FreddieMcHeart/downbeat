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
async def test_add_peer_modal_default_parent_prefills_and_registers(relay_dir):
    """Regression test: the modal's parent-name Input must be a distinct
    attribute from Widget's own internal `_parent` (DOM-parent tracking) —
    reusing that name once broke mount/attachment with a confusing
    MountError. Also exercises explicit --parent disambiguation when >1
    parent peer exists."""
    from downbeat.core import store
    store.register_peer(name="parent-a", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="parent-b", session_id="s2", cwd="/tmp", role="parent")
    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        app.push_screen(AddPeerModal(default_parent="parent-b"))
        await pilot.pause()
        modal = app.screen
        assert isinstance(modal, AddPeerModal)
        assert modal._parent_input.value == "parent-b"
        modal._name.value = "new-child"
        modal._session_id.value = "abc"
        modal._cwd.value = "/tmp"
        modal.submit()
        await pilot.pause()
        registered = store.get_peer("new-child")
        assert registered.role == "child"
        assert registered.parent == "parent-b"


@pytest.mark.asyncio
async def test_remove_peer_helper(relay_dir):
    from downbeat.core import store
    from downbeat.core.errors import PeerNotFound
    store.register_peer(name="rm-me", session_id="s", cwd="/tmp", role="parent")
    perform_remove_peer("rm-me")
    with pytest.raises(PeerNotFound):
        store.get_peer("rm-me")


@pytest.mark.asyncio
async def test_gc_stale_prunes_only_old_peers(relay_dir):
    import json
    from datetime import datetime, timedelta

    from downbeat.core import store

    # Create two peers
    store.register_peer(name="old", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="new", session_id="s2", cwd="/tmp", role="parent")

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
    store.register_peer(name="to-remove", session_id="s", cwd="/tmp", role="parent")
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
async def test_peers_screen_groups_by_explicit_parent(relay_dir):
    """Peers paired via Peer.parent appear adjacent, parents before children —
    grouping is data-driven, not inferred from any shared name shape."""
    from downbeat.core import store
    from downbeat.tui.screens.peers import PeersScreen
    # Register intentionally out-of-order, with deliberately unrelated names
    # to prove grouping doesn't depend on any shared prefix.
    store.register_peer(name="PLAT-2972-master", session_id="s2", cwd="/tmp", role="parent")
    store.register_peer(name="PLAT-3113-master", session_id="s3", cwd="/tmp", role="parent")
    store.register_peer(name="worker-one", session_id="s1", cwd="/tmp", role="child",
                        parent="PLAT-3113-master")
    store.register_peer(name="worker-two", session_id="s4", cwd="/tmp", role="child",
                        parent="PLAT-2972-master")
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
        # the parent first inside each group — grouped by Peer.parent, not name.
        expected = ["PLAT-2972-master", "worker-two",
                    "PLAT-3113-master", "worker-one"]
        assert names == expected
