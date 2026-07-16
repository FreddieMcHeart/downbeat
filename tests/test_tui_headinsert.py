import pytest

from downbeat.tui.app import RelayApp


@pytest.mark.asyncio
async def test_two_consecutive_head_inserts_stay_ordered(relay_dir, monkeypatch):
    """Regression: a second head-insert (a message older than everything
    rendered, arriving in a later refresh) anchored on the first entry of the
    _bubbles dict -- but a prior head-insert had appended its id there, so the
    anchor was no longer the visual head. Rendered A/Z/B instead of Z/A/B."""
    from downbeat.core import store
    from downbeat.core.models import Message
    store.register_peer(name="CCO", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="P", session_id="s2", cwd="/tmp", role="child",
                        parent="CCO")

    def mk(mid, ts):
        # read_at set so _mark_focused_read (which only marks NEW mail) stays
        # a no-op -- these are monkeypatched into list_thread, not real store
        # messages, so a mark_read would MessageNotFound.
        return Message(id=mid, from_peer="P", to_peer="CCO", subject=mid,
                       body="b", created_at=ts, read_at=ts)

    sets = [
        [mk("B", "2026-01-03")],
        [mk("A", "2026-01-02"), mk("B", "2026-01-03")],
        [mk("Z", "2026-01-01"), mk("A", "2026-01-02"), mk("B", "2026-01-03")],
    ]
    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        await pilot.pause()
        screen = app.screen
        stream = screen.query_one("#chat-stream")
        screen.acting_as = "CCO"
        screen.active_peer = "P"
        for msgs in sets:
            monkeypatch.setattr(store, "list_thread", lambda a, b, ms=msgs: list(ms))
            stream.refresh_thread("CCO", "P")
            for _ in range(3):
                await pilot.pause()
        order = [c._msg.id for c in stream.children if getattr(c, "_msg", None)]
        assert order == ["Z", "A", "B"], f"misordered: {order}"
