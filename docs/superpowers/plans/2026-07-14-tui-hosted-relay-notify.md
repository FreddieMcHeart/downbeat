# TUI-hosted relay staleness notify Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the standalone `downbeat watch` CLI command with an automatic native-OS-notification nudge when mail arrives for an idle (>10min) peer — fired from the TUI's already-resident filesystem watcher when the TUI is open, or from the existing `relay-poll-offer.py` hook on `send`/`reply` when it isn't.

**Architecture:** Two independent, non-shared-code triggers (see Global Constraints) both call a native-OS-notify primitive on the same 10-minute staleness/cooldown contract, backed by a small extension to the existing `tui_state.json` ephemeral-state file (`core/state.py`). `downbeat watch` (the CLI subcommand and its `cmd_watch`/`_watch_emit` implementation) is deleted entirely; the underlying `FsWatcher`/`PollWatcher` primitive in `core/watcher.py` is untouched and stays as the TUI's live-update mechanism.

**Tech Stack:** Python 3.11+, stdlib `subprocess`/`shlex`/`json`/`pathlib`/`datetime` only (no new dependencies), Textual (existing TUI framework), pytest + pytest-asyncio (existing test stack).

**Spec:** `docs/superpowers/specs/2026-07-14-tui-hosted-relay-notify-design.md` — read it first if anything below is ambiguous; this plan implements it task-by-task.

## Global Constraints

- **Hooks cannot import the `downbeat` package.** `assets/hooks/relay-poll-offer.py` runs under a bare `#!/usr/bin/env python3` shebang via plain system Python (`python3 -c "import downbeat"` fails with `ModuleNotFoundError` — verified directly). All staleness/notify/state logic needed by the hook must be self-contained stdlib code duplicated inside that file — never `from ...core import ...`.
- **Single staleness/cooldown constant: 10 minutes**, used both for "is the recipient idle" and "is a just-sent notification still in cooldown." One named constant per implementation (`core/store.py`'s module-level constant for the in-package path; a private module-level constant inside the hook for the self-contained path) — never a second independent magic number.
- **Notify must fail open everywhere.** Any notify call (`core/notify.py`'s `notify()`, and the hook's private `_notify()`) wraps its `subprocess.run` in `try/except Exception` and never raises into its caller — missing binary, timeout, and unsupported platform are all silent no-ops (with a log line where a logger is available).
- **No `PushNotification` tool involvement.** Both paths shell out to `osascript` (macOS) / `notify-send` (Linux) directly via `subprocess`.
- **Versioning:** the commit that deletes `downbeat watch` (Task 6) is `feat!:` with a `BREAKING CHANGE:` footer — `python-semantic-release` picks this up automatically from conventional commits; never hand-edit `pyproject.toml`'s version or `CHANGELOG.md`.
- **`docs/decisions.md` and `CHANGELOG.md` are not touched by this plan** — the former is historical record (the `FsWatcher.stop()` entry is about the class, not the CLI wrapper being removed), the latter is generated.
- Branch: `feat/tui-hosted-relay-notify` (already created from `origin/main` — confirm you're on it before Task 1; `git status --short` should be clean, `git log --oneline -3` should show the two spec-doc commits as the tip).

---

### Task 1: `core/notify.py` — native OS notification helper

**Files:**
- Create: `src/downbeat/core/notify.py`
- Test: `tests/test_notify.py`

**Interfaces:**
- Produces: `notify(title: str, message: str) -> None` — fails open, never raises. Consumed by Task 4 (`tui/app.py`).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_notify.py`:

```python
import subprocess
from unittest.mock import patch

from downbeat.core import notify


def test_notify_macos_calls_osascript():
    with patch("downbeat.core.notify.sys") as mock_sys, \
         patch("downbeat.core.notify.subprocess.run") as mock_run:
        mock_sys.platform = "darwin"
        notify.notify("downbeat", "New message for Claude-Relay")

    args = mock_run.call_args[0][0]
    assert args[0] == "osascript"
    assert "New message for Claude-Relay" in args[2]


def test_notify_linux_calls_notify_send():
    with patch("downbeat.core.notify.sys") as mock_sys, \
         patch("downbeat.core.notify.subprocess.run") as mock_run:
        mock_sys.platform = "linux"
        notify.notify("downbeat", "hello")

    args = mock_run.call_args[0][0]
    assert args == ["notify-send", "downbeat", "hello"]


def test_notify_unsupported_platform_is_noop():
    with patch("downbeat.core.notify.sys") as mock_sys, \
         patch("downbeat.core.notify.subprocess.run") as mock_run:
        mock_sys.platform = "win32"
        notify.notify("downbeat", "hello")

    mock_run.assert_not_called()


def test_notify_fails_open_on_missing_binary():
    with patch("downbeat.core.notify.sys") as mock_sys, \
         patch("downbeat.core.notify.subprocess.run",
               side_effect=FileNotFoundError()):
        mock_sys.platform = "darwin"
        notify.notify("downbeat", "hello")  # must not raise


def test_notify_fails_open_on_timeout():
    with patch("downbeat.core.notify.sys") as mock_sys, \
         patch("downbeat.core.notify.subprocess.run",
               side_effect=subprocess.TimeoutExpired(cmd="osascript", timeout=3)):
        mock_sys.platform = "darwin"
        notify.notify("downbeat", "hello")  # must not raise


def test_notify_escapes_quotes_in_applescript():
    with patch("downbeat.core.notify.sys") as mock_sys, \
         patch("downbeat.core.notify.subprocess.run") as mock_run:
        mock_sys.platform = "darwin"
        notify.notify('title with "quotes"', 'message with "quotes"')

    script = mock_run.call_args[0][0][2]
    assert 'title with \\"quotes\\"' in script
    assert 'message with \\"quotes\\"' in script
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/mama/downbeat && pytest tests/test_notify.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'downbeat.core.notify'`

- [ ] **Step 3: Write the implementation**

Create `src/downbeat/core/notify.py`:

```python
"""Native OS notification helper — best-effort, fails open.

Used by the TUI's resident FsWatcher (tui/app.py) to alert the human when a
message arrives for a stale (idle) recipient while the TUI itself is
running. The headless case (no TUI open) is covered by a SEPARATE, private
implementation inside assets/hooks/relay-poll-offer.py — that hook cannot
import this module (see docs/superpowers/specs/
2026-07-14-tui-hosted-relay-notify-design.md, "Implementation constraint").
"""
from __future__ import annotations

import logging
import subprocess
import sys

_log = logging.getLogger("downbeat.notify")


def _escape_applescript(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def notify(title: str, message: str) -> None:
    """Fire a native OS notification. Never raises — logs and returns on
    any failure (missing binary, timeout, unsupported platform)."""
    try:
        if sys.platform == "darwin":
            script = (
                f'display notification "{_escape_applescript(message)}" '
                f'with title "{_escape_applescript(title)}"'
            )
            subprocess.run(["osascript", "-e", script], timeout=3,
                           capture_output=True, check=False)
        elif sys.platform.startswith("linux"):
            subprocess.run(["notify-send", title, message], timeout=3,
                           capture_output=True, check=False)
        else:
            _log.debug("notify: unsupported platform %s, skipping", sys.platform)
    except Exception:
        _log.exception("notify() failed")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_notify.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
cd ~/mama/downbeat
git add src/downbeat/core/notify.py tests/test_notify.py
git commit -m "feat: add core/notify.py native OS notification helper"
```

---

### Task 2: `core/store.py` — `is_recipient_stale()`

**Files:**
- Modify: `src/downbeat/core/store.py`
- Test: `tests/test_store_messages.py`

**Interfaces:**
- Consumes: `get_peer(name: str) -> Peer` (existing, `store.py:152`), `Peer.last_seen: str` (existing field).
- Produces: `is_recipient_stale(peer_name: str, threshold_minutes: int = 10) -> bool`, module constant `STALE_THRESHOLD_MINUTES = 10`, private helper `_is_timestamp_stale(iso_ts: str | None, threshold_minutes: int) -> bool`. Consumed by Task 4 (`tui/app.py`, both for `is_recipient_stale` and for cooldown checks via `_is_timestamp_stale`).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_store_messages.py` (file already imports `pytest`, `store`, `MessageLocked`/`MessageNotFound`/`PeerNotFound`, `MessageState`, and has a `_peers(*names)` helper — reuse them, don't redefine):

```python
def test_is_recipient_stale_fresh_last_seen_is_not_stale(relay_dir):
    _peers("c")
    assert store.is_recipient_stale("c") is False


def test_is_recipient_stale_old_last_seen_is_stale(relay_dir):
    from datetime import UTC, datetime, timedelta
    _peers("c")
    sessions = store._load_sessions()
    sessions["c"]["last_seen"] = (
        datetime.now(UTC) - timedelta(minutes=20)
    ).isoformat()
    store._save_sessions(sessions)
    assert store.is_recipient_stale("c") is True


def test_is_recipient_stale_missing_peer_is_not_stale(relay_dir):
    assert store.is_recipient_stale("ghost") is False


def test_is_recipient_stale_custom_threshold(relay_dir):
    from datetime import UTC, datetime, timedelta
    _peers("c")
    sessions = store._load_sessions()
    sessions["c"]["last_seen"] = (
        datetime.now(UTC) - timedelta(minutes=5)
    ).isoformat()
    store._save_sessions(sessions)
    assert store.is_recipient_stale("c", threshold_minutes=10) is False
    assert store.is_recipient_stale("c", threshold_minutes=3) is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_store_messages.py -k is_recipient_stale -v`
Expected: FAIL — `AttributeError: module 'downbeat.core.store' has no attribute 'is_recipient_stale'`

- [ ] **Step 3: Write the implementation**

In `src/downbeat/core/store.py`, find this exact block:

```python
def touch_peer(name: str) -> None:
    sessions = _load_sessions()
    if name not in sessions:
        raise PeerNotFound(name)
    sessions[name]["last_seen"] = now_iso()
    _save_sessions(sessions)


def _message_path(msg: Message) -> Path:
```

Replace it with:

```python
def touch_peer(name: str) -> None:
    sessions = _load_sessions()
    if name not in sessions:
        raise PeerNotFound(name)
    sessions[name]["last_seen"] = now_iso()
    _save_sessions(sessions)


STALE_THRESHOLD_MINUTES = 10


def _is_timestamp_stale(iso_ts: str | None, threshold_minutes: int) -> bool:
    """True if iso_ts is older than threshold_minutes, or missing/malformed.
    Package-private, reused by callers that need the same staleness check
    against a timestamp that isn't a peer's last_seen (e.g. a notify
    cooldown timestamp) — same reuse pattern as core/state.py importing
    _atomic_write_text from this module."""
    if not iso_ts:
        return False
    from datetime import datetime, timedelta
    try:
        ts = datetime.fromisoformat(iso_ts)
    except ValueError:
        return False
    return ts < datetime.now(UTC) - timedelta(minutes=threshold_minutes)


def is_recipient_stale(peer_name: str,
                       threshold_minutes: int = STALE_THRESHOLD_MINUTES) -> bool:
    """True if peer_name's last_seen is older than threshold_minutes, or the
    peer doesn't exist. Never raises — used for a best-effort notify nudge,
    not a hard dependency."""
    try:
        peer = get_peer(peer_name)
    except PeerNotFound:
        return False
    return _is_timestamp_stale(peer.last_seen, threshold_minutes)


def _message_path(msg: Message) -> Path:
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_store_messages.py -k is_recipient_stale -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Run the full store test suite to check for regressions**

Run: `pytest tests/test_store_messages.py tests/test_store_peers.py -v`
Expected: PASS (all tests, including the 4 new ones)

- [ ] **Step 6: Commit**

```bash
git add src/downbeat/core/store.py tests/test_store_messages.py
git commit -m "feat: add store.is_recipient_stale() for the idle-recipient notify check"
```

---

### Task 3: `core/state.py` — heartbeat and per-recipient notify cooldown

**Files:**
- Modify: `src/downbeat/core/state.py`
- Test: `tests/test_state.py`

**Interfaces:**
- Produces: `get_watcher_heartbeat_at() -> str | None`, `set_watcher_heartbeat_at(when: str | None) -> None`, `get_notify_last_sent(peer_name: str) -> str | None`, `set_notify_last_sent(peer_name: str, when: str) -> None`. Consumed by Task 4 (`tui/app.py`).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_state.py` (already imports `from downbeat.core import state`):

```python
def test_watcher_heartbeat_starts_unset(relay_dir):
    assert state.get_watcher_heartbeat_at() is None


def test_set_and_get_watcher_heartbeat_at(relay_dir):
    state.set_watcher_heartbeat_at("2026-07-14T10:00:00+00:00")
    assert state.get_watcher_heartbeat_at() == "2026-07-14T10:00:00+00:00"


def test_notify_last_sent_starts_unset(relay_dir):
    assert state.get_notify_last_sent("child") is None


def test_set_and_get_notify_last_sent(relay_dir):
    state.set_notify_last_sent("child", "2026-07-14T10:00:00+00:00")
    assert state.get_notify_last_sent("child") == "2026-07-14T10:00:00+00:00"


def test_notify_last_sent_independent_per_peer(relay_dir):
    state.set_notify_last_sent("child", "2026-07-14T10:00:00+00:00")
    state.set_notify_last_sent("other", "2026-07-14T11:00:00+00:00")
    assert state.get_notify_last_sent("child") == "2026-07-14T10:00:00+00:00"
    assert state.get_notify_last_sent("other") == "2026-07-14T11:00:00+00:00"


def test_notify_last_sent_coexists_with_acting_as(relay_dir):
    state.set_last_acting_as("alice")
    state.set_notify_last_sent("child", "2026-07-14T10:00:00+00:00")
    assert state.get_last_acting_as() == "alice"
    assert state.get_notify_last_sent("child") == "2026-07-14T10:00:00+00:00"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_state.py -v`
Expected: FAIL — `AttributeError: module 'downbeat.core.state' has no attribute 'get_watcher_heartbeat_at'`

- [ ] **Step 3: Write the implementation**

In `src/downbeat/core/state.py`, find this exact block:

```python
def get_last_seen_rebind_at() -> str | None:
    return _load().get("last_seen_rebind_at")


def set_last_seen_rebind_at(when: str | None) -> None:
    data = _load()
    if when is None:
        data.pop("last_seen_rebind_at", None)
    else:
        data["last_seen_rebind_at"] = when
    _save(data)


def now_iso() -> str:
```

Replace it with:

```python
def get_last_seen_rebind_at() -> str | None:
    return _load().get("last_seen_rebind_at")


def set_last_seen_rebind_at(when: str | None) -> None:
    data = _load()
    if when is None:
        data.pop("last_seen_rebind_at", None)
    else:
        data["last_seen_rebind_at"] = when
    _save(data)


def get_watcher_heartbeat_at() -> str | None:
    """Global fact: is a TUI resident FsWatcher alive right now. Written by
    tui/app.py on mount and refreshed periodically; read by the headless
    relay-poll-offer.py hook (via its own self-contained duplicate of this
    file, not this function — see docs/superpowers/specs/
    2026-07-14-tui-hosted-relay-notify-design.md) to avoid double-firing a
    notification when a TUI is already watching."""
    return _load().get("watcher_heartbeat_at")


def set_watcher_heartbeat_at(when: str | None) -> None:
    data = _load()
    if when is None:
        data.pop("watcher_heartbeat_at", None)
    else:
        data["watcher_heartbeat_at"] = when
    _save(data)


def get_notify_last_sent(peer_name: str) -> str | None:
    """Per-recipient cooldown timestamp for the idle-recipient notify,
    shared by the TUI path (this function) and the headless hook's own
    duplicate implementation, so cooldown is coherent regardless of which
    path fired last."""
    return _load().get("notify_last_sent", {}).get(peer_name)


def set_notify_last_sent(peer_name: str, when: str) -> None:
    data = _load()
    sent = data.setdefault("notify_last_sent", {})
    sent[peer_name] = when
    _save(data)


def now_iso() -> str:
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_state.py -v`
Expected: PASS (all tests, including the 6 new ones)

- [ ] **Step 5: Commit**

```bash
git add src/downbeat/core/state.py tests/test_state.py
git commit -m "feat: add TUI heartbeat and per-recipient notify cooldown to tui_state.json"
```

---

### Task 4: `tui/app.py` — wire staleness notify into the resident FsWatcher

**Files:**
- Modify: `src/downbeat/tui/app.py`
- Test: `tests/test_tui_notify.py`

**Interfaces:**
- Consumes: `store.list_peers() -> list[Peer]` (existing), `store.poll_new(peer_name: str, seen: set[str]) -> tuple[list[Message], set[str]]` (existing, `store.py:697`), `store.is_recipient_stale(peer_name, threshold_minutes=10) -> bool` (Task 2), `store._is_timestamp_stale(iso_ts, threshold_minutes) -> bool` (Task 2), `state.get_notify_last_sent/set_notify_last_sent` (Task 3), `state.set_watcher_heartbeat_at/now_iso` (Task 3), `notify.notify(title, message) -> None` (Task 1).
- Produces: `RelayApp._check_stale_notify() -> None`, `RelayApp._seed_notify_seen() -> dict[str, set[str]]`, `RelayApp._heartbeat_tick() -> None` — internal, no external consumers.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_tui_notify.py`:

```python
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

from downbeat.core import state, store
from downbeat.tui.app import RelayApp


def _iso_minutes_ago(minutes: int) -> str:
    return (datetime.now(UTC) - timedelta(minutes=minutes)).isoformat()


def _make_stale(peer_name: str) -> None:
    sessions = store._load_sessions()
    sessions[peer_name]["last_seen"] = _iso_minutes_ago(20)
    store._save_sessions(sessions)


@pytest.mark.asyncio
async def test_heartbeat_written_on_mount(relay_dir):
    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        await pilot.pause()
        assert state.get_watcher_heartbeat_at() is not None


@pytest.mark.asyncio
async def test_stale_notify_fires_for_message_arriving_after_mount(relay_dir):
    store.register_peer(name="parent", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="child", session_id="s2", cwd="/tmp", role="child")
    _make_stale("child")

    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        await pilot.pause()  # baseline seeded here (empty inbox)
        store.send_message(from_peer="parent", to_peer="child",
                           subject="s", body="b")
        with patch("downbeat.tui.app.notify.notify") as mock_notify:
            app._check_stale_notify()
        mock_notify.assert_called_once()
        assert "child" in mock_notify.call_args[0][1]


@pytest.mark.asyncio
async def test_stale_notify_skips_fresh_recipient(relay_dir):
    store.register_peer(name="parent", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="child", session_id="s2", cwd="/tmp", role="child")

    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        await pilot.pause()
        store.send_message(from_peer="parent", to_peer="child",
                           subject="s", body="b")
        with patch("downbeat.tui.app.notify.notify") as mock_notify:
            app._check_stale_notify()
        mock_notify.assert_not_called()


@pytest.mark.asyncio
async def test_stale_notify_respects_cooldown(relay_dir):
    store.register_peer(name="parent", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="child", session_id="s2", cwd="/tmp", role="child")
    _make_stale("child")
    state.set_notify_last_sent("child", state.now_iso())  # just notified

    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        await pilot.pause()
        store.send_message(from_peer="parent", to_peer="child",
                           subject="s", body="b")
        with patch("downbeat.tui.app.notify.notify") as mock_notify:
            app._check_stale_notify()
        mock_notify.assert_not_called()


@pytest.mark.asyncio
async def test_stale_notify_does_not_fire_for_pre_existing_backlog(relay_dir):
    """Messages already sitting in the inbox before the TUI mounted must
    not be announced — only genuinely-new arrivals while the TUI is open."""
    store.register_peer(name="parent", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="child", session_id="s2", cwd="/tmp", role="child")
    _make_stale("child")
    store.send_message(from_peer="parent", to_peer="child",
                       subject="pre-existing", body="b")

    app = RelayApp()
    async with app.run_test(headless=True) as pilot:
        await pilot.pause()  # baseline seeding happens in on_mount
        with patch("downbeat.tui.app.notify.notify") as mock_notify:
            app._check_stale_notify()
        mock_notify.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_tui_notify.py -v`
Expected: FAIL — `AttributeError: 'RelayApp' object has no attribute '_check_stale_notify'`

- [ ] **Step 3: Write the implementation**

In `src/downbeat/tui/app.py`, find this exact block (the full current file):

```python
"""RelayApp — root Textual application."""
from __future__ import annotations

import json
import logging

from textual.app import App

from ..core import logging as relay_logging
from ..core import store, watcher
from .messages import StoreChanged
from .screens.chat import ChatScreen


class RelayApp(App):
    CSS_PATH = "theme.tcss"
    TITLE = "downbeat"
    SUB_TITLE = "local relay TUI"
    ENABLE_COMMAND_PALETTE = False
    # Mouse / trackpad scroll is enabled by default; affirming here for clarity:
    # Textual's terminal layer emits mouse wheel as MouseScrollUp/MouseScrollDown.
    # Scroll-container widgets (VerticalScroll, RichLog, DataTable) handle them
    # natively when their content exceeds viewport.

    def __init__(self):
        super().__init__()
        self._watcher = None

    def on_mount(self) -> None:
        relay_logging.setup(level="INFO")
        try:
            counts = store.reconcile()
            if counts["quarantined"] > 0:
                logging.getLogger("downbeat.tui").warning(
                    "reconcile at startup: %s", counts
                )
        except Exception:
            logging.getLogger("downbeat.tui").exception("reconcile failed at startup")

        # Check for unseen rebind events and surface as toasts
        try:
            unseen = self._unseen_rebinds()
            if unseen:
                for event in unseen:
                    self.notify(
                        f"{event['peer']} rebound after /clear: "
                        f"session {event['old_session_id'][:8]}→"
                        f"{event['new_session_id'][:8]}",
                        timeout=5,
                    )
                self._mark_rebinds_seen()
        except Exception:
            logging.getLogger("downbeat.tui").exception("rebind notification failed")

        logging.getLogger("downbeat.tui").info("app mounted")
        self.push_screen(ChatScreen())
        self._watcher = watcher.make_watcher(
            on_change=lambda: self.call_from_thread(self._on_change)
        )
        self._watcher.start()

    def _unseen_rebinds(self) -> list[dict]:
        """Return rebind events newer than the last-seen timestamp in tui_state."""
        from ..core import paths, state
        if not paths.REBIND_LOG.exists():
            return []
        last_seen = state.get_last_seen_rebind_at()
        events: list[dict] = []
        with paths.REBIND_LOG.open() as f:
            for line in f:
                try:
                    event = json.loads(line)
                except Exception:
                    continue
                ts = event.get("at", "")
                if last_seen is None or ts > last_seen:
                    events.append(event)
        return events

    def _mark_rebinds_seen(self) -> None:
        from ..core import state
        state.set_last_seen_rebind_at(state.now_iso())

    def on_unmount(self) -> None:
        if self._watcher:
            self._watcher.stop()

    def _on_change(self) -> None:
        self.post_message(StoreChanged())
```

Replace it with:

```python
"""RelayApp — root Textual application."""
from __future__ import annotations

import json
import logging

from textual.app import App

from ..core import logging as relay_logging
from ..core import notify, state, store, watcher
from .messages import StoreChanged
from .screens.chat import ChatScreen

_HEARTBEAT_INTERVAL_SECONDS = 30


class RelayApp(App):
    CSS_PATH = "theme.tcss"
    TITLE = "downbeat"
    SUB_TITLE = "local relay TUI"
    ENABLE_COMMAND_PALETTE = False
    # Mouse / trackpad scroll is enabled by default; affirming here for clarity:
    # Textual's terminal layer emits mouse wheel as MouseScrollUp/MouseScrollDown.
    # Scroll-container widgets (VerticalScroll, RichLog, DataTable) handle them
    # natively when their content exceeds viewport.

    def __init__(self):
        super().__init__()
        self._watcher = None
        self._notify_seen: dict[str, set[str]] = {}

    def on_mount(self) -> None:
        relay_logging.setup(level="INFO")
        try:
            counts = store.reconcile()
            if counts["quarantined"] > 0:
                logging.getLogger("downbeat.tui").warning(
                    "reconcile at startup: %s", counts
                )
        except Exception:
            logging.getLogger("downbeat.tui").exception("reconcile failed at startup")

        # Check for unseen rebind events and surface as toasts
        try:
            unseen = self._unseen_rebinds()
            if unseen:
                for event in unseen:
                    self.notify(
                        f"{event['peer']} rebound after /clear: "
                        f"session {event['old_session_id'][:8]}→"
                        f"{event['new_session_id'][:8]}",
                        timeout=5,
                    )
                self._mark_rebinds_seen()
        except Exception:
            logging.getLogger("downbeat.tui").exception("rebind notification failed")

        logging.getLogger("downbeat.tui").info("app mounted")
        self.push_screen(ChatScreen())

        # Seed the notify-seen baseline BEFORE writing the heartbeat or
        # starting the watcher, synchronously — same race-avoidance
        # rationale the old cmd_watch used: a pre-populated inbox must not
        # be announced as "new" the moment the TUI starts.
        try:
            self._notify_seen = self._seed_notify_seen()
        except Exception:
            logging.getLogger("downbeat.tui").exception("notify-seen seeding failed")

        state.set_watcher_heartbeat_at(state.now_iso())
        self.set_interval(_HEARTBEAT_INTERVAL_SECONDS, self._heartbeat_tick)

        self._watcher = watcher.make_watcher(
            on_change=lambda: self.call_from_thread(self._on_change)
        )
        self._watcher.start()

    def _seed_notify_seen(self) -> dict[str, set[str]]:
        seen: dict[str, set[str]] = {}
        for peer in store.list_peers():
            _, seen[peer.name] = store.poll_new(peer.name, set())
        return seen

    def _heartbeat_tick(self) -> None:
        state.set_watcher_heartbeat_at(state.now_iso())

    def _unseen_rebinds(self) -> list[dict]:
        """Return rebind events newer than the last-seen timestamp in tui_state."""
        from ..core import paths, state
        if not paths.REBIND_LOG.exists():
            return []
        last_seen = state.get_last_seen_rebind_at()
        events: list[dict] = []
        with paths.REBIND_LOG.open() as f:
            for line in f:
                try:
                    event = json.loads(line)
                except Exception:
                    continue
                ts = event.get("at", "")
                if last_seen is None or ts > last_seen:
                    events.append(event)
        return events

    def _mark_rebinds_seen(self) -> None:
        from ..core import state
        state.set_last_seen_rebind_at(state.now_iso())

    def on_unmount(self) -> None:
        if self._watcher:
            self._watcher.stop()

    def _on_change(self) -> None:
        self.post_message(StoreChanged())
        try:
            self._check_stale_notify()
        except Exception:
            logging.getLogger("downbeat.tui").exception("stale-notify check failed")

    def _check_stale_notify(self) -> None:
        for peer in store.list_peers():
            seen = self._notify_seen.setdefault(peer.name, set())
            new_msgs, seen = store.poll_new(peer.name, seen)
            self._notify_seen[peer.name] = seen
            if not new_msgs:
                continue
            if not store.is_recipient_stale(peer.name):
                continue
            last_sent = state.get_notify_last_sent(peer.name)
            in_cooldown = last_sent is not None and not store._is_timestamp_stale(
                last_sent, store.STALE_THRESHOLD_MINUTES)
            if in_cooldown:
                continue
            notify.notify("downbeat", f"New message for {peer.name}")
            state.set_notify_last_sent(peer.name, state.now_iso())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_tui_notify.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Run the full TUI test suite to check for regressions**

Run: `pytest tests/test_tui_smoke.py tests/test_tui_chat.py tests/test_tui_notify.py -v`
Expected: PASS (all tests — the on_mount changes must not break existing rebind/quit/chat behavior)

- [ ] **Step 6: Commit**

```bash
git add src/downbeat/tui/app.py tests/test_tui_notify.py
git commit -m "feat: wire staleness notify into the TUI's resident FsWatcher"
```

---

### Task 5: `assets/hooks/relay-poll-offer.py` — self-contained staleness notify for headless sessions

**Files:**
- Modify: `src/downbeat/assets/hooks/relay-poll-offer.py`
- Test: `tests/test_relay_poll_offer_hook.py`

**Interfaces:**
- Produces (all private, self-contained — do **not** import `downbeat.core`, see Global Constraints): `_relay_dir() -> Path`, `_is_recipient_stale(peer_name, threshold_minutes=_STALE_THRESHOLD_MINUTES) -> bool`, `_notify(title, message) -> None`, `_escape_applescript(s) -> str`, `_read_tui_state() -> dict`, `_write_tui_state(data) -> None`, `_resolve_recipient(command) -> str | None`, `_lookup_original_sender(msg_id) -> str | None`, `_is_fresh(iso_ts, threshold_minutes) -> bool`, `_maybe_notify_stale_recipient(command) -> None`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_relay_poll_offer_hook.py`:

```python
"""Tests for the staleness-notify addition to relay-poll-offer.py.

The hook is a standalone, stdlib-only script (no downbeat package import —
see docs/superpowers/specs/2026-07-14-tui-hosted-relay-notify-design.md,
"Implementation constraint"), so it's loaded per-test via
importlib.util.spec_from_file_location rather than a normal import."""
from __future__ import annotations

import importlib.util
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import downbeat


def _load_hook_module():
    path = (Path(downbeat.__file__).parent / "assets" / "hooks"
            / "relay-poll-offer.py")
    spec = importlib.util.spec_from_file_location("relay_poll_offer", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_sessions(relay_dir, peers: dict) -> None:
    (relay_dir / "sessions.json").write_text(json.dumps(peers))


def _iso_minutes_ago(minutes: int) -> str:
    return (datetime.now(UTC) - timedelta(minutes=minutes)).isoformat()


def test_resolve_recipient_from_send_command(relay_dir):
    hook = _load_hook_module()
    cmd = 'downbeat send Claude-Relay "subject" "body"'
    assert hook._resolve_recipient(cmd) == "Claude-Relay"


def test_resolve_recipient_from_reply_looks_up_original_sender(relay_dir):
    hook = _load_hook_module()
    inbox = relay_dir / "inbox" / "someone"
    inbox.mkdir(parents=True)
    (inbox / "abc123.json").write_text(json.dumps({"from_peer": "Claude-Relay"}))
    cmd = 'downbeat reply abc123 "done"'
    assert hook._resolve_recipient(cmd) == "Claude-Relay"


def test_resolve_recipient_reply_missing_message_returns_none(relay_dir):
    hook = _load_hook_module()
    cmd = 'downbeat reply ghost123 "done"'
    assert hook._resolve_recipient(cmd) is None


def test_resolve_recipient_unrelated_command_returns_none(relay_dir):
    hook = _load_hook_module()
    assert hook._resolve_recipient('downbeat inbox --peer child') is None


def test_is_recipient_stale_true_for_old_last_seen(relay_dir):
    hook = _load_hook_module()
    _write_sessions(relay_dir, {"child": {"last_seen": _iso_minutes_ago(20)}})
    assert hook._is_recipient_stale("child") is True


def test_is_recipient_stale_false_for_fresh_last_seen(relay_dir):
    hook = _load_hook_module()
    _write_sessions(relay_dir, {"child": {"last_seen": _iso_minutes_ago(1)}})
    assert hook._is_recipient_stale("child") is False


def test_is_recipient_stale_false_for_missing_peer(relay_dir):
    hook = _load_hook_module()
    _write_sessions(relay_dir, {})
    assert hook._is_recipient_stale("ghost") is False


def test_maybe_notify_fires_when_stale_and_no_tui(relay_dir):
    hook = _load_hook_module()
    _write_sessions(relay_dir, {"child": {"last_seen": _iso_minutes_ago(20)}})
    with patch.object(hook, "_notify") as mock_notify:
        hook._maybe_notify_stale_recipient('downbeat send child "s" "b"')
    mock_notify.assert_called_once()
    assert "child" in mock_notify.call_args[0][1]


def test_maybe_notify_skips_when_tui_heartbeat_fresh(relay_dir):
    hook = _load_hook_module()
    _write_sessions(relay_dir, {"child": {"last_seen": _iso_minutes_ago(20)}})
    (relay_dir / "tui_state.json").write_text(
        json.dumps({"watcher_heartbeat_at": _iso_minutes_ago(0)}))
    with patch.object(hook, "_notify") as mock_notify:
        hook._maybe_notify_stale_recipient('downbeat send child "s" "b"')
    mock_notify.assert_not_called()


def test_maybe_notify_skips_when_recipient_not_stale(relay_dir):
    hook = _load_hook_module()
    _write_sessions(relay_dir, {"child": {"last_seen": _iso_minutes_ago(1)}})
    with patch.object(hook, "_notify") as mock_notify:
        hook._maybe_notify_stale_recipient('downbeat send child "s" "b"')
    mock_notify.assert_not_called()


def test_maybe_notify_respects_cooldown(relay_dir):
    hook = _load_hook_module()
    _write_sessions(relay_dir, {"child": {"last_seen": _iso_minutes_ago(20)}})
    (relay_dir / "tui_state.json").write_text(
        json.dumps({"notify_last_sent": {"child": _iso_minutes_ago(1)}}))
    with patch.object(hook, "_notify") as mock_notify:
        hook._maybe_notify_stale_recipient('downbeat send child "s" "b"')
    mock_notify.assert_not_called()


def test_maybe_notify_updates_cooldown_after_firing(relay_dir):
    hook = _load_hook_module()
    _write_sessions(relay_dir, {"child": {"last_seen": _iso_minutes_ago(20)}})
    with patch.object(hook, "_notify"):
        hook._maybe_notify_stale_recipient('downbeat send child "s" "b"')
    written = json.loads((relay_dir / "tui_state.json").read_text())
    assert "child" in written["notify_last_sent"]


def test_maybe_notify_preserves_other_tui_state_keys(relay_dir):
    hook = _load_hook_module()
    _write_sessions(relay_dir, {"child": {"last_seen": _iso_minutes_ago(20)}})
    (relay_dir / "tui_state.json").write_text(
        json.dumps({"last_acting_as": "alice"}))
    with patch.object(hook, "_notify"):
        hook._maybe_notify_stale_recipient('downbeat send child "s" "b"')
    written = json.loads((relay_dir / "tui_state.json").read_text())
    assert written["last_acting_as"] == "alice"
    assert "child" in written["notify_last_sent"]


def test_maybe_notify_never_raises_on_garbage_sessions_file(relay_dir):
    hook = _load_hook_module()
    (relay_dir / "sessions.json").write_text("not json")
    with patch.object(hook, "_notify") as mock_notify:
        hook._maybe_notify_stale_recipient('downbeat send child "s" "b"')
    mock_notify.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_relay_poll_offer_hook.py -v`
Expected: FAIL — `AttributeError: module 'relay_poll_offer' has no attribute '_resolve_recipient'`

- [ ] **Step 3: Write the implementation**

In `src/downbeat/assets/hooks/relay-poll-offer.py`, find this exact block (the imports + the `main()` function body up to and including the exit-code check):

```python
import json
import re
import sys
import traceback
from datetime import UTC, datetime
from pathlib import Path

STATE_FILE = Path.home() / ".claude" / "relay" / "loop_offer_state.json"
```

Replace it with:

```python
import json
import os
import re
import shlex
import subprocess
import sys
import traceback
from datetime import UTC, datetime, timedelta
from pathlib import Path

STATE_FILE = Path.home() / ".claude" / "relay" / "loop_offer_state.json"

# --- Idle-recipient staleness notify -----------------------------------
# Self-contained: this hook has NO downbeat package import available (see
# docs/superpowers/specs/2026-07-14-tui-hosted-relay-notify-design.md,
# "Implementation constraint") — every helper below duplicates, rather than
# imports, the equivalent logic in core/store.py, core/state.py, and
# core/notify.py.

_STALE_THRESHOLD_MINUTES = 10


def _relay_dir() -> Path:
    return Path(os.environ.get("CLAUDE_RELAY_DIR",
                               str(Path.home() / ".claude" / "relay")))


def _is_fresh(iso_ts: str | None, threshold_minutes: int) -> bool:
    if not iso_ts:
        return False
    try:
        ts = datetime.fromisoformat(iso_ts)
    except ValueError:
        return False
    return ts >= datetime.now(UTC) - timedelta(minutes=threshold_minutes)


def _is_recipient_stale(peer_name: str,
                        threshold_minutes: int = _STALE_THRESHOLD_MINUTES) -> bool:
    sessions_file = _relay_dir() / "sessions.json"
    if not sessions_file.exists():
        return False
    try:
        sessions = json.loads(sessions_file.read_text() or "{}")
    except Exception:
        return False
    peer = sessions.get(peer_name)
    if not peer:
        return False
    return not _is_fresh(peer.get("last_seen"), threshold_minutes)


def _escape_applescript(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _notify(title: str, message: str) -> None:
    try:
        if sys.platform == "darwin":
            script = (
                f'display notification "{_escape_applescript(message)}" '
                f'with title "{_escape_applescript(title)}"'
            )
            subprocess.run(["osascript", "-e", script], timeout=3,
                          capture_output=True, check=False)
        elif sys.platform.startswith("linux"):
            subprocess.run(["notify-send", title, message], timeout=3,
                          capture_output=True, check=False)
    except Exception:
        pass


def _read_tui_state() -> dict:
    tui_state_file = _relay_dir() / "tui_state.json"
    if not tui_state_file.exists():
        return {}
    try:
        return json.loads(tui_state_file.read_text() or "{}")
    except Exception:
        return {}


def _write_tui_state(data: dict) -> None:
    tui_state_file = _relay_dir() / "tui_state.json"
    tui_state_file.parent.mkdir(parents=True, exist_ok=True)
    tui_state_file.write_text(json.dumps(data, indent=2))


def _lookup_original_sender(msg_id: str) -> str | None:
    for sub in ("inbox", "delivered", "processed"):
        base = _relay_dir() / sub
        if not base.exists():
            continue
        for match in base.glob(f"*/{msg_id}.json"):
            try:
                data = json.loads(match.read_text())
            except Exception:
                continue
            return data.get("from_peer")
    return None


def _resolve_recipient(command: str) -> str | None:
    try:
        tokens = shlex.split(command)
    except ValueError:
        return None
    for i, tok in enumerate(tokens):
        if tok in ("send", "reply") and i + 1 < len(tokens):
            arg = tokens[i + 1]
            if tok == "send":
                return arg
            return _lookup_original_sender(arg)
    return None


def _maybe_notify_stale_recipient(command: str) -> None:
    """Best-effort native notification if the send/reply's recipient looks
    idle and no TUI is currently watching. Never raises."""
    try:
        to_peer = _resolve_recipient(command)
        if not to_peer:
            return
        if not _is_recipient_stale(to_peer):
            return
        tui_state = _read_tui_state()
        if _is_fresh(tui_state.get("watcher_heartbeat_at"),
                     _STALE_THRESHOLD_MINUTES):
            return  # a TUI is open and will notify itself — avoid double-fire
        last_sent = tui_state.get("notify_last_sent", {}).get(to_peer)
        if _is_fresh(last_sent, _STALE_THRESHOLD_MINUTES):
            return  # cooldown
        _notify("downbeat", f"New message for {to_peer}")
        tui_state.setdefault("notify_last_sent", {})[to_peer] = (
            datetime.now(UTC).isoformat(timespec="seconds")
        )
        _write_tui_state(tui_state)
    except Exception:
        traceback.print_exc(file=sys.stderr)
```

Then, in the same file, find this exact block inside `main()`:

```python
    # Tool result inspection: only fire if the command succeeded.
    tool_result = payload.get("tool_result") or payload.get("toolResult") or {}
    # Exit code field varies; treat absent as success (best-effort).
    exit_code = tool_result.get("exit_code")
    if exit_code is not None and exit_code != 0:
        return

    session_id = (
```

Replace it with:

```python
    # Tool result inspection: only fire if the command succeeded.
    tool_result = payload.get("tool_result") or payload.get("toolResult") or {}
    # Exit code field varies; treat absent as success (best-effort).
    exit_code = tool_result.get("exit_code")
    if exit_code is not None and exit_code != 0:
        return

    # Independent of the once-per-session /loop-offer gate below — fires
    # every send/reply that targets a currently-stale peer, subject to its
    # own per-recipient cooldown.
    _maybe_notify_stale_recipient(command)

    session_id = (
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_relay_poll_offer_hook.py -v`
Expected: PASS (14 tests)

- [ ] **Step 5: Run the hooks-manifest-parity test to confirm nothing about hook registration broke**

Run: `pytest tests/test_hooks_manifest_parity.py -v`
Expected: PASS (unchanged — this task doesn't touch `hooks_manifest.json` or `hooks/hooks.json`)

- [ ] **Step 6: Commit**

```bash
git add src/downbeat/assets/hooks/relay-poll-offer.py tests/test_relay_poll_offer_hook.py
git commit -m "feat: staleness notify in relay-poll-offer hook for headless sessions"
```

---

### Task 6: Remove the standalone `downbeat watch` CLI

**Files:**
- Modify: `src/downbeat/cli/commands/relay_cmds.py`
- Modify: `src/downbeat/cli/__main__.py`
- Modify: `tests/test_store_messages.py` (migrate in 4 pure tests)
- Delete: `tests/test_watch.py`

**Interfaces:**
- Removes: `cmd_watch`, `_watch_emit` (no longer produced by anything; nothing in this codebase consumes them after this task).

- [ ] **Step 1: Migrate the 4 pure `poll_new` tests out of `tests/test_watch.py` into `tests/test_store_messages.py`**

Append to `tests/test_store_messages.py` (verbatim from `tests/test_watch.py`, unchanged — these test `store.poll_new` directly, nothing watcher/CLI-related):

```python
def test_poll_new_first_call_returns_all_new(relay_dir):
    _peers("p", "c")
    m1 = store.send_message(from_peer="p", to_peer="c", subject="s1", body="b1")
    m2 = store.send_message(from_peer="p", to_peer="c", subject="s2", body="b2")

    new_msgs, seen = store.poll_new("c", set())

    assert {m.id for m in new_msgs} == {m1.id, m2.id}
    assert seen == {m1.id, m2.id}


def test_poll_new_second_call_returns_empty(relay_dir):
    _peers("p", "c")
    store.send_message(from_peer="p", to_peer="c", subject="s", body="b")

    _, seen = store.poll_new("c", set())
    new_msgs, seen2 = store.poll_new("c", seen)

    assert new_msgs == []
    assert seen2 == seen  # seen unchanged (no new ids added)


def test_poll_new_only_returns_incremental(relay_dir):
    _peers("p", "c")
    m1 = store.send_message(from_peer="p", to_peer="c", subject="first", body="x")

    _, seen = store.poll_new("c", set())  # seed seen with m1

    m2 = store.send_message(from_peer="p", to_peer="c", subject="second", body="y")
    new_msgs, seen2 = store.poll_new("c", seen)

    assert [m.id for m in new_msgs] == [m2.id]
    assert m1.id not in {m.id for m in new_msgs}
    assert {m1.id, m2.id} <= seen2


def test_poll_new_excludes_non_new_states(relay_dir):
    _peers("p", "c")
    # delivered state: drain moves it from inbox/ to delivered/
    m_delivered = store.send_message(from_peer="p", to_peer="c",
                                     subject="delivered", body="x")
    store.deliver_messages(peer_name="c", session_id="s-c")
    assert store.get_message(m_delivered.id).state == MessageState.DELIVERED

    # archived state: ack after deliver
    m_acked = store.send_message(from_peer="p", to_peer="c",
                                 subject="acked", body="y")
    store.deliver_messages(peer_name="c", session_id="s-c")
    store.ack_messages([m_acked.id])
    assert store.get_message(m_acked.id).state == MessageState.ARCHIVED

    # One genuinely NEW message
    m_new = store.send_message(from_peer="p", to_peer="c",
                               subject="still new", body="z")

    new_msgs, _ = store.poll_new("c", set())

    ids = {m.id for m in new_msgs}
    assert m_new.id in ids
    assert m_delivered.id not in ids
    assert m_acked.id not in ids
```

- [ ] **Step 2: Run the migrated tests to confirm they pass in their new home**

Run: `pytest tests/test_store_messages.py -k poll_new -v`
Expected: PASS (4 tests)

- [ ] **Step 3: Delete `tests/test_watch.py`**

```bash
cd ~/mama/downbeat
git rm tests/test_watch.py
```

- [ ] **Step 4: Remove `cmd_watch`/`_watch_emit` from `relay_cmds.py`**

In `src/downbeat/cli/commands/relay_cmds.py`, find this exact block:

```python
import argparse
import sys
import threading
from datetime import UTC, datetime, timedelta

from ...core import session, store
from ...core import watcher as watcher_mod
from ...core.errors import AmbiguousParent, InvalidParent, MessageNotFound, PeerNotFound
from ...core.models import MessageState
```

Replace it with:

```python
import argparse
import sys
from datetime import UTC, datetime, timedelta

from ...core import session, store
from ...core.errors import AmbiguousParent, InvalidParent, MessageNotFound, PeerNotFound
from ...core.models import MessageState
```

Then, in the same file, find this exact block:

```python
def cmd_tui(args: argparse.Namespace) -> int:
    from ...tui.app import RelayApp
    RelayApp().run()
    return 0


def _watch_emit(peer: str, seen: set[str]) -> set[str]:
    """Poll for new messages and print them. Returns updated seen set.

    Pure helper — no watcher dependency; directly testable.
    """
    new_msgs, seen = store.poll_new(peer, seen)
    if new_msgs:
        print("NEW RELAY MESSAGE(S):")
        for m in new_msgs:
            print(f"* {m.id}  {m.created_at}  {m.from_peer}  {m.subject}")
    return seen


def cmd_watch(args: argparse.Namespace) -> int:
    peer = _detect_peer_or_error(args.peer)

    if args.once:
        # --once: announce everything currently NEW (start with empty seen)
        seen: set[str] = set()
        new_msgs, _ = store.poll_new(peer, seen)
        if new_msgs:
            print("NEW RELAY MESSAGE(S):")
            for m in new_msgs:
                print(f"* {m.id}  {m.created_at}  {m.from_peer}  {m.subject}")
        return 0

    # Seed seen with current NEW ids BEFORE starting the watcher so a
    # pre-populated inbox is NOT re-announced on startup.
    seen = {m.id for m in store.list_inbox(peer) if m.state == MessageState.NEW}

    # Mutable holder so the callback closure can update seen across fires.
    state: dict[str, set[str]] = {"seen": seen}

    def _on_change() -> None:
        state["seen"] = _watch_emit(peer, state["seen"])

    prefer = "poll" if args.poll else "auto"
    w = watcher_mod.make_watcher(
        on_change=_on_change,
        prefer=prefer,
        poll_interval=args.interval,
    )

    backend = type(w).__name__
    if backend == "FsWatcher":
        print("[watch] event-driven (fswatch/FSEvents)")
    else:
        print(f"[watch] polling every {args.interval}s (event watcher unavailable)")

    w.start()
    try:
        threading.Event().wait()  # block until KeyboardInterrupt
    except KeyboardInterrupt:
        pass
    finally:
        w.stop()
    print("[watch] stopped")
    return 0


def cmd_init(args: argparse.Namespace) -> int:
```

Replace it with:

```python
def cmd_tui(args: argparse.Namespace) -> int:
    from ...tui.app import RelayApp
    RelayApp().run()
    return 0


def cmd_init(args: argparse.Namespace) -> int:
```

- [ ] **Step 5: Remove the `watch` subcommand registration from `__main__.py`**

In `src/downbeat/cli/__main__.py`, find this exact block:

```python
    sp_rec = sub.add_parser("reconcile", help="re-queue or quarantine stale delivered messages",
                            parents=[debug_parent])
    sp_rec.add_argument("--window-minutes", type=int, default=30)
    sp_rec.add_argument("--max-redelivery", type=int, default=3)
    sp_rec.set_defaults(func=relay_cmds.cmd_reconcile)

    sp_watch = sub.add_parser("watch", help="watch inbox for new messages",
                              parents=[debug_parent])
    sp_watch.add_argument("--peer", default=None,
                          help="peer name; auto-detected if omitted")
    sp_watch.add_argument("--interval", type=int, default=90,
                          help="poll interval in seconds (default: 90)")
    sp_watch.add_argument("--once", action="store_true",
                          help="poll once and exit (announces all current NEW)")
    sp_watch.add_argument("--quiet", action="store_true",
                          help="suppress idle output; print only on new messages")
    sp_watch.add_argument("--poll", action="store_true",
                          help="force poll fallback instead of event-driven")
    sp_watch.set_defaults(func=relay_cmds.cmd_watch)

    sp_init = sub.add_parser("init", help="bootstrap relay dir, skill, shim",
                             parents=[debug_parent])
```

Replace it with:

```python
    sp_rec = sub.add_parser("reconcile", help="re-queue or quarantine stale delivered messages",
                            parents=[debug_parent])
    sp_rec.add_argument("--window-minutes", type=int, default=30)
    sp_rec.add_argument("--max-redelivery", type=int, default=3)
    sp_rec.set_defaults(func=relay_cmds.cmd_reconcile)

    sp_init = sub.add_parser("init", help="bootstrap relay dir, skill, shim",
                             parents=[debug_parent])
```

- [ ] **Step 6: Run the full test suite to confirm the removal is clean**

Run: `pytest -v`
Expected: PASS — zero references to `cmd_watch`/`_watch_emit`/`watcher_mod` remain anywhere in `tests/` or `src/`; `tests/test_watch.py` no longer exists.

- [ ] **Step 7: Run ruff to catch any lint issue from the edits (e.g. unused imports)**

Run: `ruff check src/downbeat/cli/commands/relay_cmds.py src/downbeat/cli/__main__.py`
Expected: no errors (in particular, confirm `threading` and `watcher as watcher_mod` are actually gone from `relay_cmds.py` — ruff's `F401` unused-import check would catch it if the earlier edit missed a reference)

- [ ] **Step 8: Commit as the breaking-change commit**

```bash
git add -A
git commit -m "$(cat <<'EOF'
feat!: remove standalone downbeat-watch CLI, replace with automatic staleness notify

downbeat watch (the standalone CLI subcommand for observing a peer's inbox
from an external terminal) is removed. Its underlying FsWatcher/PollWatcher
primitive (core/watcher.py) is unchanged and continues to power the TUI's
live updates.

In its place: an automatic native OS notification fires when a message
arrives for a peer that's been idle for more than 10 minutes — from the
TUI's own resident watcher when downbeat tui is open, or from the
relay-poll-offer hook on the next send/reply when it isn't. No manual step
required.

BREAKING CHANGE: the `downbeat watch` subcommand no longer exists. Any
script or workflow invoking `downbeat watch [--peer X] [--once] [--poll]
[--interval N] [--quiet]` will now fail with an argparse error. Use
`downbeat tui` (for the TUI-hosted automatic notify) or rely on the
headless hook path — no replacement command for the standalone
external-observer use case.
EOF
)"
```

---

### Task 7: Update documentation to remove `downbeat watch` references

**Files:**
- Modify: `README.md`
- Modify: `src/downbeat/skill/SKILL.md`
- Modify: `examples/parent-child-handoff/README.md`
- Modify: `src/downbeat/assets/commands/relay-monitor.md`

**Interfaces:** none (documentation only).

- [ ] **Step 1: Update `README.md` — replace the "Always-on inbox watch" section**

Find this exact block:

```markdown
### Always-on inbox watch

Give a child session always-on inbox awareness after pairing:

```bash
downbeat watch                     # event-driven (fswatch/FSEvents); instant, ~0 idle cost
downbeat watch --peer child-1      # parent watching a child's inbox
downbeat watch --poll              # force poll fallback (every --interval seconds)
downbeat watch --interval 30       # poll fallback interval (default: 90s)
downbeat watch --once              # one-shot: print all current NEW, then exit
```

Run `downbeat watch` in the child terminal (or as a Monitor job) immediately
after `downbeat register`. The watcher notifies only — it never drains, acks,
or takes any action. The human (or the session's hook at the next prompt) drives action.
Stop with Ctrl+C.

`watch` is event-driven by default (uses watchdog FSEvents/inotify — fires instantly on
inbox changes, near-zero idle CPU). If watchdog is unavailable it falls back to polling
automatically and prints `[watch] polling every Ns` on startup so you always know which
backend is active. Use `--poll` to force the interval fallback regardless.

**watch-vs-monitor cost table:**

| Want | Use | Cost on idle channel |
|---|---|---|
| Cheap notify-to-wake, you act when woken | `downbeat watch` as a Monitor | ~0 (blocks on FS event; model turn only on real mail) |
| Session auto-acts role-aware on a cadence | `/relay-monitor` (/loop) | a model turn every interval |
```

Replace it with:

```markdown
### Automatic idle-recipient notify

No manual step needed. If the TUI (`downbeat tui`) is open, its resident
event-driven watcher (watchdog FSEvents/inotify) fires a native OS
notification the moment mail arrives for a peer that's been idle for more
than 10 minutes. If the TUI isn't open, a Claude Code session
sending/replying to an idle peer gets the same native notification from
its own hook, independent of the TUI. Either way: notify-only, never
drains/acks/acts.
```

- [ ] **Step 2: Update `README.md` — replace the "watch vs /relay-monitor" comparison table**

Find this exact block:

```markdown
**watch vs /relay-monitor — key distinction:**

| | `downbeat watch` | `/relay-monitor` |
|---|---|---|
| Runs as | external process (pane / Monitor job) | in-session `/loop` |
| Backend | event-driven (FSEvents/inotify), poll fallback | timer-based loop |
| Does | prints new mail to a pane (human reads) | session pulls mail into its own context + acts per role |
| Acts? | never | child: yes (autonomous); parent: no (surfaces) |
| Idle cost | ~0 (event-driven; model turn only on real mail) | a model turn every interval |
| Use when | operator watching from outside | a session should self-drive on its inbox |

Both tools are complementary and can be run simultaneously.
```

Replace it with:

```markdown
**Automatic notify vs /relay-monitor — key distinction:**

| | Automatic idle-notify | `/relay-monitor` |
|---|---|---|
| Runs as | TUI's resident watcher, or a Claude Code hook — no separate process to start | in-session `/loop` |
| Does | fires a native OS notification (human reads it, decides what to do) | session pulls mail into its own context + acts per role |
| Acts? | never | child: yes (autonomous); parent: no (surfaces) |
| Idle cost | ~0 (event-driven when TUI open; hook-adjacent cadence otherwise) | a model turn every interval |
| Use when | you want a nudge, not automation | a session should self-drive on its inbox |

Both are complementary and can run at the same time.
```

- [ ] **Step 3: Update `src/downbeat/skill/SKILL.md`**

Find this exact block:

```markdown
## Registration + always-on watch

After a child registers (`downbeat register <name>`), run `downbeat watch` in the
child terminal (or as a Monitor job) for always-on surfacing of new mail — notify-only; the
human still drives action at the next prompt.

`downbeat watch` is event-driven (fswatch/FSEvents) with automatic poll fallback — it
blocks on filesystem events and costs ~0 on an idle channel. For cheap notify-to-wake, run
it as a Monitor; `/relay-monitor` is for in-session role-aware auto-acting and costs a model
turn per tick.
```

Replace it with:

```markdown
## Registration + automatic idle-notify

After a child registers (`downbeat register <name>`), no manual step is needed for
always-on mail awareness: if `downbeat tui` is open, its resident watcher fires a
native OS notification the moment mail arrives for an idle (>10min) peer; if the TUI
isn't open, the same notification fires from a Claude Code session's own hook on its
next `send`/`reply`. Notify-only in both cases — the human still drives action.
`/relay-monitor` is the separate in-session role-aware auto-acting option, costing a
model turn per tick.
```

- [ ] **Step 4: Update `examples/parent-child-handoff/README.md`**

Find this exact block:

```markdown
## Next steps

- `downbeat tui` — full management UI over the same data instead of raw CLI calls.
- `downbeat watch --peer demo-child` — event-driven inbox notifications (run this in
  a second terminal, then re-run the `send` command above from a third).
- `/relay-monitor` (inside a registered Claude Code session) — the self-driving,
  role-aware version of the same loop; see the main [README](../../README.md).
```

Replace it with:

```markdown
## Next steps

- `downbeat tui` — full management UI over the same data instead of raw CLI calls;
  also fires an automatic native notification for idle-peer mail while it's open.
- `/relay-monitor` (inside a registered Claude Code session) — the self-driving,
  role-aware version of the same loop; see the main [README](../../README.md).
```

- [ ] **Step 5: Update `src/downbeat/assets/commands/relay-monitor.md`**

Find this exact line:

```markdown
- This is the **in-session self-driver**. For an **external pane observer** that only prints new mail (never acts), use `downbeat watch [--peer X]` instead.
```

Replace it with:

```markdown
- This is the **in-session self-driver**. For a passive nudge instead — a native OS notification when mail arrives for an idle peer — no separate command is needed: `downbeat tui` notifies automatically while open, and a Claude Code session's own hook covers the headless case.
```

- [ ] **Step 6: Grep to confirm no `downbeat watch` reference survives outside historical/out-of-scope files**

Run: `grep -rn "downbeat watch" --include="*.md" .`
Expected: zero matches (the only prior matches were in the 4 files just edited; `docs/decisions.md` and `docs/oss-readiness-research.md` do not contain the literal string `downbeat watch`, only unrelated mentions of the `watchdog` library — confirm this is still true).

- [ ] **Step 7: Commit**

```bash
git add README.md src/downbeat/skill/SKILL.md examples/parent-child-handoff/README.md src/downbeat/assets/commands/relay-monitor.md
git commit -m "docs: replace downbeat-watch docs with automatic staleness-notify docs"
```

---

### Task 8: Full verification and PR

**Files:** none (verification only).

- [ ] **Step 1: Run the complete test suite**

Run: `cd ~/mama/downbeat && pytest -v`
Expected: PASS, zero failures, zero errors. Note the total test count for the PR description.

- [ ] **Step 2: Run ruff across the whole repo**

Run: `ruff check .`
Expected: no errors.

- [ ] **Step 3: Confirm the branch's commit log tells a clean story**

Run: `git log --oneline origin/main..HEAD`
Expected: spec-doc commits, then one `feat:` commit per Task 1-5, then the `feat!:` removal commit (Task 6), then the `docs:` commit (Task 7) — 9 commits total, no `fixup`/`wip` noise.

- [ ] **Step 4: Push and open the PR**

```bash
git push -u origin feat/tui-hosted-relay-notify
gh pr create --title "feat!: automatic staleness notify, remove standalone downbeat watch" --body "$(cat <<'EOF'
## Summary
- Replaces the standalone `downbeat watch` CLI command with an automatic native OS notification when mail arrives for an idle (>10min) peer.
- TUI-hosted path: fires from the TUI's already-resident FsWatcher when `downbeat tui` is open — zero new process.
- Headless fallback: fires from the existing `relay-poll-offer.py` hook on `send`/`reply` when the TUI isn't open — also self-contained, since hooks can't import the `downbeat` package (see the design spec for why).
- Full design rationale and the feasibility thread this closes: `docs/superpowers/specs/2026-07-14-tui-hosted-relay-notify-design.md`.

## Breaking change
`downbeat watch` no longer exists as a subcommand. See the Task 6 commit message for the full BREAKING CHANGE note.

## Test plan
- [x] `pytest -v` — full suite green
- [x] `ruff check .` — clean
- [ ] Manual: open `downbeat tui`, send a message from another registered peer to a peer whose `last_seen` is >10min old, confirm a native macOS notification appears
- [ ] Manual: with the TUI closed, run `downbeat send <idle-peer> ...` from a Claude Code session, confirm the same notification fires from the hook and the TUI-open case does not double-fire
EOF
)"
```

- [ ] **Step 5: Report the PR URL back to the human** — this plan's execution ends here; merging is a separate, explicit human decision (matches this session's established pattern for PR #13/#15).

---

## Self-Review

**Spec coverage:** every numbered component in the spec (`core/notify.py`, `core/store.py` extension, `core/state.py` extension, `tui/app.py` wiring, `relay-poll-offer.py` self-contained extension, the full removal scope, the doc updates, the `feat!:` versioning) maps to Tasks 1–7 respectively, with Task 8 covering the spec's implicit "ship it" step. The spec's "Known limitations" section (headless + non-Claude sender gap, rename-staleness cosmetic gap, near-simultaneous-write race) are accepted trade-offs already reflected in the design, not additional implementation work — no task needed for them.

**Placeholder scan:** no TBD/TODO; every step has complete, runnable code or an exact command with an expected result.

**Type consistency:** `is_recipient_stale(peer_name: str, threshold_minutes: int = 10) -> bool` (Task 2) is called identically in Task 4 (`store.is_recipient_stale(peer.name)`) and independently re-implemented (not called) as `_is_recipient_stale` in Task 5 — the naming deliberately mirrors across the two independent implementations for readability, confirmed **not** to be an accidental single shared reference (Task 5's version has no `store.` prefix and lives in a different file with no import). `notify.notify(title: str, message: str) -> None` (Task 1) matches its one call site in Task 4 exactly; `_notify(title: str, message: str) -> None` (Task 5) is the hook's independent duplicate, same signature, no cross-reference. `state.get_notify_last_sent`/`set_notify_last_sent` (Task 3) match their Task 4 call sites; the hook's `_read_tui_state`/`_write_tui_state` (Task 5) operate on the same **file format** (top-level `notify_last_sent` dict, `watcher_heartbeat_at` string) without sharing code, confirmed consistent between Task 3's `state.py` implementation and Task 5's hook implementation (both write `notify_last_sent[peer_name] = <ISO string>` under that exact key).
