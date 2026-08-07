"""Sort cycling and unread badges in SwitchActingAsModal (#107)."""
import importlib
import json
from datetime import UTC, datetime, timedelta

import pytest

from downbeat.core import paths, store
from downbeat.core.models import Message
from downbeat.tui.app import RelayApp
from downbeat.tui.widgets.switch_acting_as import SwitchActingAsModal


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
