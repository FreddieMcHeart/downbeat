import pytest

from claude_relay.tui.app import RelayApp


@pytest.mark.asyncio
async def test_opening_message_marks_it_read(relay_dir):
    from claude_relay.core import store
    from claude_relay.core.models import MessageState
    store.register_peer(name="p", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="c", session_id="s2", cwd="/tmp", role="child")
    msg = store.send_message(from_peer="p", to_peer="c", subject="s", body="hello")
    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        await pilot.pause()
        peers = app.screen.query_one("PeerList")
        peers.acting_as = "c"
        peers.refresh_from_store()
        await pilot.pause()
        inbox = app.screen.query_one("InboxList")
        inbox.refresh_for_peer("c")
        await pilot.pause()
        view = app.screen.query_one("MessageView")
        view.show(msg.id)
        await pilot.pause()
        assert store.get_message(msg.id).state == MessageState.READ
        assert "hello" in view.body_text
