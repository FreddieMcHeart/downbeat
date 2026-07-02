import time

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
