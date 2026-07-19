"""Regression tests for #31 — the find-message modal never handed keyboard
focus from the search box to the results table, so a match couldn't be picked
with the keyboard. Driven against the real Textual modal (run_test), not a mock."""
import pytest
from textual.app import App

from downbeat.tui.widgets.find_message import FindMessageModal


def _seed_message(store):
    store.register_peer(name="a", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="b", session_id="s2", cwd="/tmp", role="child",
                        parent="a")
    return store.send_message(from_peer="a", to_peer="b", subject="hi", body="x")


class _Host(App):
    """Minimal host app that pushes the modal and records what it dismisses."""

    def __init__(self, sink: dict):
        super().__init__()
        self._sink = sink

    def on_mount(self) -> None:
        self.push_screen(FindMessageModal(),
                         lambda picked: self._sink.__setitem__("picked", picked))


@pytest.mark.asyncio
async def test_down_hands_focus_to_results_then_enter_opens(relay_dir):
    from downbeat.core import store
    msg = _seed_message(store)
    sink: dict = {}
    app = _Host(sink)
    async with app.run_test(headless=True) as pilot:
        await pilot.pause()
        modal = app.screen
        assert isinstance(modal, FindMessageModal)
        for ch in msg.id[:8]:
            await pilot.press(ch)
        await pilot.pause()
        assert modal._results, "id prefix should match the seeded message"
        assert app.focused is modal._input, "search box should start focused"
        # Down must hand focus into the results table (the #31 fix).
        await pilot.press("down")
        await pilot.pause()
        assert app.focused is modal._table, "Down should move focus to the table"
        # Enter on the focused row opens it.
        await pilot.press("enter")
        await pilot.pause()
    assert sink.get("picked") is not None, "a row should have been opened"
    assert sink["picked"].id == msg.id


@pytest.mark.asyncio
async def test_enter_in_search_box_opens_top_match(relay_dir):
    from downbeat.core import store
    msg = _seed_message(store)
    sink: dict = {}
    app = _Host(sink)
    async with app.run_test(headless=True) as pilot:
        await pilot.pause()
        modal = app.screen
        assert isinstance(modal, FindMessageModal)
        for ch in msg.id[:8]:
            await pilot.press(ch)
        await pilot.pause()
        assert modal._results
        # Enter while the search box is focused must open the top match, not
        # get swallowed by the Input's own submit.
        await pilot.press("enter")
        await pilot.pause()
    assert sink.get("picked") is not None, "Enter in the box should open the top match"
    assert sink["picked"].id == msg.id
