"""Sort cycling and unread badges in SwitchActingAsModal (#107, #118)."""
import importlib
import json
from datetime import UTC, datetime, timedelta

import pytest

from downbeat.core import paths, store
from downbeat.core.models import Message
from downbeat.tui.app import RelayApp
from downbeat.tui.messages import StoreChanged
from downbeat.tui.widgets.switch_acting_as import SwitchActingAsModal

_DEBOUNCE_SECONDS = 0.15  # keep in step with switch_acting_as._REFRESH_DEBOUNCE_SECONDS


def _backdate_registered_at(name: str, when: datetime) -> None:
    sessions_file = paths.SESSIONS_FILE
    data = json.loads(sessions_file.read_text())
    data[name]["registered_at"] = when.isoformat(timespec="seconds")
    sessions_file.write_text(json.dumps(data))
    importlib.reload(store)


def _write_inbox_message(to_peer: str, created_at: str, msg_id: str) -> None:
    msg = Message(
        id=msg_id,
        from_peer="someone",
        to_peer=to_peer,
        subject="s",
        body="b",
        created_at=created_at,
    )
    store._write_message(msg)


def _row_labels(modal: SwitchActingAsModal) -> list[str]:
    labels = []
    for item in modal._listview.children:
        static = next(iter(item.children))
        labels.append(str(static.render()))
    return labels


@pytest.mark.asyncio
async def test_recent_sort_is_default_newest_message_first_no_message_last(relay_dir):
    store.register_peer(name="alpha", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="beta", session_id="s2", cwd="/tmp", role="parent")
    store.register_peer(name="gamma", session_id="s3", cwd="/tmp", role="parent")
    # alpha: older message. beta: newest message. gamma: no messages at all.
    _write_inbox_message("alpha", "2026-01-01T00:00:00+00:00", "m1")
    _write_inbox_message("beta", "2026-06-01T00:00:00+00:00", "m2")

    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        app.push_screen(SwitchActingAsModal(current=None))
        await pilot.pause()
        modal = app.screen
        assert isinstance(modal, SwitchActingAsModal)
        assert modal._sort_index == 0  # recent is the default
        names = [r.name for r in modal._sorted]
        assert names == ["beta", "alpha", "gamma"], names


@pytest.mark.asyncio
async def test_name_sort_is_alphabetical(relay_dir):
    store.register_peer(name="zeta", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="alpha", session_id="s2", cwd="/tmp", role="parent")
    store.register_peer(name="mid", session_id="s3", cwd="/tmp", role="parent")

    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        app.push_screen(SwitchActingAsModal(current=None))
        await pilot.pause()
        modal = app.screen
        assert isinstance(modal, SwitchActingAsModal)
        await pilot.press("s")  # recent -> name
        await pilot.pause()
        assert modal._sort_index == 1
        names = [r.name for r in modal._sorted]
        assert names == ["alpha", "mid", "zeta"], names
        assert "sort (name)" in str(modal._hint.render())


@pytest.mark.asyncio
async def test_added_sort_is_registered_at_newest_first(relay_dir):
    store.register_peer(name="first", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="second", session_id="s2", cwd="/tmp", role="parent")
    store.register_peer(name="third", session_id="s3", cwd="/tmp", role="parent")
    now = datetime.now(UTC)
    _backdate_registered_at("first", now - timedelta(days=3))
    _backdate_registered_at("second", now - timedelta(days=1))
    _backdate_registered_at("third", now - timedelta(days=2))

    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        app.push_screen(SwitchActingAsModal(current=None))
        await pilot.pause()
        modal = app.screen
        assert isinstance(modal, SwitchActingAsModal)
        await pilot.press("s")  # recent -> name
        await pilot.press("s")  # name -> added
        await pilot.pause()
        assert modal._sort_index == 2
        names = [r.name for r in modal._sorted]
        assert names == ["second", "third", "first"], names
        # cycling wraps back to recent
        await pilot.press("s")
        await pilot.pause()
        assert modal._sort_index == 0


@pytest.mark.asyncio
async def test_badge_present_above_zero_absent_at_zero(relay_dir):
    store.register_peer(name="quiet", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="loud", session_id="s2", cwd="/tmp", role="parent")
    _write_inbox_message("loud", "2026-01-01T00:00:00+00:00", "m1")
    _write_inbox_message("loud", "2026-01-02T00:00:00+00:00", "m2")

    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        app.push_screen(SwitchActingAsModal(current=None))
        await pilot.pause()
        modal = app.screen
        assert isinstance(modal, SwitchActingAsModal)
        labels = _row_labels(modal)
        loud_label = next(label for label in labels if "loud" in label)
        quiet_label = next(label for label in labels if "quiet" in label)
        assert "●2" in loud_label, loud_label
        assert "●" not in quiet_label, quiet_label


@pytest.mark.asyncio
async def test_preselection_recomputed_by_name_after_resort(relay_dir):
    store.register_peer(name="zeta", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="alpha", session_id="s2", cwd="/tmp", role="parent")
    store.register_peer(name="mid", session_id="s3", cwd="/tmp", role="parent")

    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        app.push_screen(SwitchActingAsModal(current="mid"))
        await pilot.pause()
        modal = app.screen
        assert isinstance(modal, SwitchActingAsModal)
        # Whatever the initial (recent) order put "mid" at, the ListView index
        # must point at it.
        assert modal._sorted[modal._listview.index].name == "mid"
        await pilot.press("s")  # -> name: alpha, mid, zeta -- "mid" is now index 1
        await pilot.pause()
        assert modal._sorted[modal._listview.index].name == "mid"
        assert modal._listview.index == 1


# ---------------------------------------------------------------------------
# #118 -- live refresh on StoreChanged
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_store_changed_refreshes_badges_without_reordering(relay_dir):
    store.register_peer(name="alpha", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="beta", session_id="s2", cwd="/tmp", role="parent")
    _write_inbox_message("alpha", "2026-01-01T00:00:00+00:00", "m1")
    _write_inbox_message("beta", "2026-06-01T00:00:00+00:00", "m2")

    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        app.push_screen(SwitchActingAsModal(current=None))
        await pilot.pause()
        modal = app.screen
        assert isinstance(modal, SwitchActingAsModal)
        # Default "recent" sort: beta (newer) first, alpha second.
        assert [r.name for r in modal._sorted] == ["beta", "alpha"]
        # Baseline read AFTER the modal (and the ChatScreen mounted under
        # it, which may itself mark its default peer's top message read) has
        # settled -- the delta below is what proves the refresh, independent
        # of whatever that baseline happens to be.
        before = next(r for r in modal._sorted if r.name == "alpha").unread

        # alpha gets a message far newer than beta's -- if the modal were to
        # re-sort, alpha would now come first.
        _write_inbox_message("alpha", "2026-09-01T00:00:00+00:00", "m3")
        modal.post_message(StoreChanged())
        await pilot.pause(_DEBOUNCE_SECONDS * 2)

        assert [r.name for r in modal._sorted] == ["beta", "alpha"], (
            "order must stay frozen across a live refresh"
        )
        alpha_row = next(r for r in modal._sorted if r.name == "alpha")
        assert alpha_row.unread == before + 1, "badge must reflect the new message"


@pytest.mark.asyncio
async def test_store_changed_appends_new_peer_at_end(relay_dir):
    store.register_peer(name="alpha", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="beta", session_id="s2", cwd="/tmp", role="parent")

    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        app.push_screen(SwitchActingAsModal(current=None))
        await pilot.pause()
        modal = app.screen
        assert isinstance(modal, SwitchActingAsModal)
        before = [r.name for r in modal._sorted]
        assert len(before) == 2

        store.register_peer(name="gamma", session_id="s3", cwd="/tmp", role="parent")
        modal.post_message(StoreChanged())
        await pilot.pause(_DEBOUNCE_SECONDS * 2)

        names = [r.name for r in modal._sorted]
        assert names == before + ["gamma"], names


@pytest.mark.asyncio
async def test_store_changed_leaves_vanished_peer_with_last_known_count(relay_dir):
    store.register_peer(name="alpha", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="beta", session_id="s2", cwd="/tmp", role="parent")
    _write_inbox_message("beta", "2026-01-01T00:00:00+00:00", "m1")
    _write_inbox_message("beta", "2026-01-02T00:00:00+00:00", "m2")

    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        app.push_screen(SwitchActingAsModal(current=None))
        await pilot.pause()
        modal = app.screen
        assert isinstance(modal, SwitchActingAsModal)
        before = next(r for r in modal._sorted if r.name == "beta")
        assert before.unread == 2

        store.remove_peer("beta")
        # A live peer changes too, so a no-op handler (or one that simply
        # never touches beta) can't pass this test by doing nothing at all.
        _write_inbox_message("alpha", "2026-01-01T00:00:00+00:00", "m3")
        modal.post_message(StoreChanged())
        await pilot.pause(_DEBOUNCE_SECONDS * 2)

        alpha_row = next(r for r in modal._sorted if r.name == "alpha")
        assert alpha_row.unread == 1, "a live peer must actually refresh -- proves the handler ran"

        names = [r.name for r in modal._sorted]
        assert "beta" in names, "vanished peer's row must stay, not disappear"
        after = next(r for r in modal._sorted if r.name == "beta")
        assert after.unread == 2, "last known count must be preserved, not re-fetched or zeroed"


@pytest.mark.asyncio
async def test_selection_follows_highlighted_peer_across_refresh(relay_dir):
    store.register_peer(name="alpha", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="beta", session_id="s2", cwd="/tmp", role="parent")
    store.register_peer(name="gamma", session_id="s3", cwd="/tmp", role="parent")

    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        app.push_screen(SwitchActingAsModal(current="alpha"))
        await pilot.pause()
        modal = app.screen
        assert isinstance(modal, SwitchActingAsModal)
        assert modal._sorted[modal._listview.index].name == "alpha"

        # Navigate away from the acting-as peer -- this is the case Decision
        # 2 exists for: a refresh must not snap the cursor back to `current`.
        await pilot.press("down")
        await pilot.pause()
        highlighted_before = modal._sorted[modal._listview.index].name
        assert highlighted_before != "alpha", "test setup: must have actually moved"

        _write_inbox_message("gamma", "2026-01-01T00:00:00+00:00", "m1")
        modal.post_message(StoreChanged())
        await pilot.pause(_DEBOUNCE_SECONDS * 2)

        # Prove a refresh actually happened -- otherwise "cursor didn't move"
        # would trivially pass with no handler at all.
        gamma_row = next(r for r in modal._sorted if r.name == "gamma")
        assert gamma_row.unread == 1, "a refresh must actually have run"

        assert modal._sorted[modal._listview.index].name == highlighted_before, (
            "a live refresh must not move the cursor off the peer the user was on"
        )


@pytest.mark.asyncio
async def test_debounce_coalesces_a_burst_into_one_refresh(relay_dir, monkeypatch):
    store.register_peer(name="alpha", session_id="s1", cwd="/tmp", role="parent")

    calls = []
    original = store.inbox_summary

    def counting(name):
        calls.append(name)
        return original(name)

    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        app.push_screen(SwitchActingAsModal(current=None))
        await pilot.pause()
        modal = app.screen
        assert isinstance(modal, SwitchActingAsModal)

        monkeypatch.setattr(store, "inbox_summary", counting)
        # A fan-out writes N files; the watcher fires once per file. Five
        # events in fast succession must still coalesce into one re-read.
        for _ in range(5):
            modal.post_message(StoreChanged())
        await pilot.pause(_DEBOUNCE_SECONDS * 2)

        assert calls == ["alpha"], f"expected exactly one refresh pass, got {calls}"


@pytest.mark.asyncio
async def test_debounce_event_mid_window_extends_rather_than_drops(relay_dir, monkeypatch):
    store.register_peer(name="alpha", session_id="s1", cwd="/tmp", role="parent")

    calls = []
    original = store.inbox_summary

    def counting(name):
        calls.append(name)
        return original(name)

    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        app.push_screen(SwitchActingAsModal(current=None))
        await pilot.pause()
        modal = app.screen
        assert isinstance(modal, SwitchActingAsModal)

        monkeypatch.setattr(store, "inbox_summary", counting)
        modal.post_message(StoreChanged())
        await pilot.pause(_DEBOUNCE_SECONDS * 0.6)
        # A second event arrives DURING the window. If it were dropped, the
        # window would still expire at ~1.0x the first event and the refresh
        # would already have run by the next check below. Extending it means
        # nothing has run yet at 1.2x the first event / 0.6x the second.
        modal.post_message(StoreChanged())
        await pilot.pause(_DEBOUNCE_SECONDS * 0.6)
        assert calls == [], (
            "a mid-window event must extend the window, not be dropped -- "
            "the refresh fired before the second event's own window elapsed"
        )

        await pilot.pause(_DEBOUNCE_SECONDS * 0.8)
        assert calls == ["alpha"], "the extended window must still eventually fire, exactly once"
