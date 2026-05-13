import pytest

from claude_relay.tui.app import RelayApp
from claude_relay.tui.widgets.add_peer_modal import AddPeerModal
from claude_relay.tui.widgets.peer_admin import (
    GcStaleModal,
    RemovePeerConfirm,
    perform_remove_peer,
)


@pytest.mark.asyncio
async def test_add_peer_programmatic(relay_dir):
    from claude_relay.core import store
    store.register_peer(name="existing", session_id="s0", cwd="/tmp", role="parent")
    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        # Press P to open AddPeerModal
        await pilot.press("P")
        await pilot.pause()
        assert isinstance(app.screen, AddPeerModal), f"Expected AddPeerModal, got {type(app.screen)}"
        modal = app.screen
        modal._name.value = "new-peer"
        modal._session_id.value = "abc"
        modal._cwd.value = "/tmp"
        modal.submit()
        await pilot.pause()
        assert any(p.name == "new-peer" for p in store.list_peers())


@pytest.mark.asyncio
async def test_remove_peer_helper(relay_dir):
    from claude_relay.core import store
    from claude_relay.core.errors import PeerNotFound
    store.register_peer(name="rm-me", session_id="s", cwd="/tmp", role="child")
    perform_remove_peer("rm-me")
    with pytest.raises(PeerNotFound):
        store.get_peer("rm-me")


@pytest.mark.asyncio
async def test_gc_stale_prunes_only_old_peers(relay_dir):
    import json
    from datetime import datetime, timedelta, timezone
    from claude_relay.core import store

    # Create two peers
    store.register_peer(name="old", session_id="s1", cwd="/tmp", role="child")
    store.register_peer(name="new", session_id="s2", cwd="/tmp", role="child")

    # Backdate "old" by 30 days by writing directly to sessions.json
    from claude_relay.core import paths
    sessions_file = paths.SESSIONS_FILE
    data = json.loads(sessions_file.read_text())
    data["old"]["last_seen"] = (
        datetime.now(timezone.utc) - timedelta(days=30)
    ).isoformat(timespec="seconds")
    sessions_file.write_text(json.dumps(data))

    # Reload store so it picks up the changed file
    import importlib
    importlib.reload(store)

    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        # Press G to open GcStaleModal
        await pilot.press("G")
        await pilot.pause()
        assert isinstance(app.screen, GcStaleModal), f"Expected GcStaleModal, got {type(app.screen)}"
        modal = app.screen
        modal._days.value = "14"
        modal._refresh_preview()
        pruned = modal._prune()
        assert "old" in pruned
        assert "new" not in pruned
