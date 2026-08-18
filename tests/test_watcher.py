import time

from watchdog.events import (
    FileClosedEvent,
    FileClosedNoWriteEvent,
    FileCreatedEvent,
    FileDeletedEvent,
    FileModifiedEvent,
    FileMovedEvent,
    FileOpenedEvent,
)

from downbeat.core import store, watcher


def test_poll_watcher_detects_new_message(relay_dir):
    store.register_peer(name="p", session_id="s", cwd="/tmp", role="parent")
    store.register_peer(name="c", session_id="s2", cwd="/tmp", role="child")
    events: list[str] = []
    w = watcher.PollWatcher(interval=0.1, on_change=lambda: events.append("x"))
    w.start()
    try:
        store.send_message(from_peer="p", to_peer="c", subject="s", body="b")
        for _ in range(20):
            if events:
                break
            time.sleep(0.1)
    finally:
        w.stop()
    assert events, "PollWatcher did not fire on new message"


def test_make_watcher_returns_filesystem_watcher_by_default(relay_dir):
    def cb():
        pass
    w = watcher.make_watcher(on_change=cb, prefer="auto")
    assert w.__class__.__name__ in {"FsWatcher", "PollWatcher"}


# ---------------------------------------------------------------------------
# #118, round 2 -- FsWatcher's event predicate was matching read events too,
# which turned _on_change's own file reads into a self-sustaining loop
# (136,000 raw watchdog events / 29,700 on_change calls in one CI run,
# Linux/inotify only -- FSEvents on macOS never emits opened/closed_no_write
# at all, so this class of bug is invisible on that platform no matter how
# it is exercised). Tested at the handler level directly, against real
# watchdog event objects, rather than through the real filesystem: an
# integration test relying on real inotify/FSEvents behaviour would pass
# vacuously on macOS and prove nothing about the fix.
# ---------------------------------------------------------------------------


def test_read_events_never_trigger_on_change(relay_dir):
    calls: list[int] = []
    w = watcher.FsWatcher(on_change=lambda: calls.append(1))
    for event in (
        FileOpenedEvent(src_path="/tmp/x/m1.json"),
        FileClosedNoWriteEvent(src_path="/tmp/x/m1.json"),
        FileClosedEvent(src_path="/tmp/x/m1.json"),
    ):
        w._handler.on_any_event(event)
    assert calls == [], (
        f"read-only event types must never fire on_change, got {len(calls)} call(s)"
    )


def test_created_modified_deleted_json_events_still_match(relay_dir):
    """Positive control: the fix for read events must not also swallow the
    real change types it was never meant to touch."""
    calls: list[int] = []
    w = watcher.FsWatcher(on_change=lambda: calls.append(1))
    for event in (
        FileCreatedEvent(src_path="/tmp/x/m1.json"),
        FileModifiedEvent(src_path="/tmp/x/m1.json"),
        FileDeletedEvent(src_path="/tmp/x/m1.json"),
    ):
        w._handler.on_any_event(event)
    assert calls == [1, 1, 1]


def test_moved_event_matches_on_dest_path_not_src_path(relay_dir):
    """store._atomic_write_text writes via mkstemp(prefix=".tmp-") +
    os.replace(tmp, target): every real write surfaces as a MOVED event
    whose src_path is the temp name and whose dest_path is the real target.
    Checking src_path alone (the pre-fix predicate) silently matched no
    real write at all."""
    calls: list[int] = []
    w = watcher.FsWatcher(on_change=lambda: calls.append(1))
    event = FileMovedEvent(src_path="/tmp/x/.tmp-abc123", dest_path="/tmp/x/m1.json")
    w._handler.on_any_event(event)
    assert calls == [1], "a move landing on a .json dest_path must trigger on_change"


def test_moved_event_with_non_json_dest_does_not_match(relay_dir):
    calls: list[int] = []
    w = watcher.FsWatcher(on_change=lambda: calls.append(1))
    event = FileMovedEvent(src_path="/tmp/x/.tmp-abc123", dest_path="/tmp/x/notes.txt")
    w._handler.on_any_event(event)
    assert calls == []
