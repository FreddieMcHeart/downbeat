"""Regression guard on the App -> active screen StoreChanged hop (#118).

There was a poster (app.py's watcher callback) and a handler
(ChatScreen.on_store_changed) with nothing connecting them: `App.post_message`
queues onto the App's own message pump, and Textual only bubbles messages
UP toward a parent, never down to a child screen -- so the handler existed
but never fired, in any shipped version. Positive controls are included
deliberately: an assertion that only checks the target fires cannot tell a
working hop from a broken probe.
"""
from __future__ import annotations

import threading
import time

import pytest

from downbeat.core import store
from downbeat.tui.app import RelayApp
from downbeat.tui.messages import StoreChanged
from downbeat.tui.screens.chat import ChatScreen
from downbeat.tui.widgets.switch_acting_as import SwitchActingAsModal


@pytest.mark.asyncio
async def test_app_level_post_reaches_the_active_screens_handler(relay_dir):
    store.register_peer(name="alpha", session_id="s1", cwd="/tmp", role="parent")

    fired: dict[str, bool] = {"chat": False}
    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        assert isinstance(app.screen, ChatScreen)

        original = ChatScreen.on_store_changed

        async def spy(self, event):
            fired["chat"] = True
            await original(self, event)

        ChatScreen.on_store_changed = spy
        try:
            # Positive control: posting directly to the screen's own queue
            # must fire the handler -- if this fails, the handler itself (or
            # the test's spy) is broken, not the App -> screen hop.
            app.screen.post_message(StoreChanged())
            await pilot.pause()
            assert fired["chat"], (
                "control failed: direct post to the screen didn't fire its handler"
            )
            fired["chat"] = False

            # The actual regression: exercise the real production entry
            # point, `RelayApp._on_change` (what the filesystem watcher
            # calls via `call_from_thread`) -- not a hand-rolled
            # `app.post_message(...)`, which would only prove Textual's own
            # base method works, not that our code posts to the right target.
            app._on_change()
            await pilot.pause()
            await pilot.pause()
            assert fired["chat"], "RelayApp._on_change() never reached ChatScreen.on_store_changed"
        finally:
            ChatScreen.on_store_changed = original


@pytest.mark.asyncio
async def test_app_level_post_reaches_a_pushed_modals_handler(relay_dir):
    store.register_peer(name="alpha", session_id="s1", cwd="/tmp", role="parent")

    fired: dict[str, bool] = {"modal": False}
    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        app.push_screen(SwitchActingAsModal(current=None))
        await pilot.pause()
        modal = app.screen
        assert isinstance(modal, SwitchActingAsModal)

        # Class-level patch, not instance-level: Textual's dispatch walks
        # `self.__class__.__mro__` and reads handlers off the CLASS dict, so
        # an instance attribute of the same name is silently never seen.
        # Deliberately does NOT chain to the original handler -- this test
        # only cares whether dispatch reaches the class at all, not whether
        # the real (sync or async) implementation behind it behaves.
        original = getattr(SwitchActingAsModal, "on_store_changed", None)

        def spy(self, event):
            fired["modal"] = True

        SwitchActingAsModal.on_store_changed = spy
        try:
            # Positive control, same reasoning as above.
            modal.post_message(StoreChanged())
            await pilot.pause()
            assert fired["modal"], (
                "control failed: direct post to the modal didn't fire its handler"
            )
            fired["modal"] = False

            app._on_change()
            await pilot.pause()
            await pilot.pause()
            assert fired["modal"], "RelayApp._on_change() never reached the pushed modal's handler"
        finally:
            if original is not None:
                SwitchActingAsModal.on_store_changed = original
            else:
                del SwitchActingAsModal.on_store_changed


@pytest.mark.asyncio
async def test_watcher_callback_never_blocks_the_calling_thread(relay_dir):
    """The real watchdog observer thread calls whatever is registered as
    RelayApp's on_change callback (app.py's watcher setup) DIRECTLY -- this
    invokes the actual registered callable (app._watcher._on_change), not a
    reimplementation, so a regression in app.py's wiring is caught here even
    though watchdog/inotify itself is not exercised.

    The mechanism under test is OS-independent by construction: a loop whose
    thread is occupied by a slow synchronous callback (exactly what a real
    action_refresh() reading many message files synchronously does) stands
    in for what real inotify delivery (fast, frequent) can trigger and real
    FSEvents delivery (coalesced, delayed) usually doesn't -- so this is
    deterministic on any OS, unlike depending on the real watcher's platform
    timing. If the callback goes back to blocking (e.g. call_from_thread),
    the calling thread parks for close to the full busy window; the fixed,
    non-blocking version returns almost immediately regardless of it."""
    store.register_peer(name="alpha", session_id="s1", cwd="/tmp", role="parent")

    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        await pilot.pause()

        busy_seconds = 0.5
        busy_started = threading.Event()

        def occupy_the_loop() -> None:
            # Runs ON the loop's own thread (scheduled via call_soon), so
            # while this sleeps the loop cannot service anything else --
            # including a run_coroutine_threadsafe future, which is exactly
            # what a blocking watcher callback would be waiting on.
            busy_started.set()
            time.sleep(busy_seconds)

        elapsed: dict[str, float] = {}

        def invoke_from_watcher_thread() -> None:
            busy_started.wait(timeout=2)
            start = time.monotonic()
            app._watcher._on_change()
            elapsed["seconds"] = time.monotonic() - start

        t = threading.Thread(target=invoke_from_watcher_thread)
        t.start()

        app._loop.call_soon(occupy_the_loop)
        await pilot.pause()  # lets occupy_the_loop run; blocks ~busy_seconds
        t.join(timeout=5)

        assert not t.is_alive(), "watcher-thread call never returned"
        assert elapsed["seconds"] < busy_seconds / 2, (
            f"watcher callback took {elapsed['seconds']:.3f}s while the "
            f"loop's thread was occupied for {busy_seconds}s -- it must "
            f"return almost immediately, not wait for the loop to be free"
        )

        for _ in range(4):
            await pilot.pause()
