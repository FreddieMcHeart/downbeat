"""RelayApp — root Textual application."""
from __future__ import annotations

import json
import logging

from textual.app import App

from ..core import logging as relay_logging
from ..core import notify, state, store, watcher
from .messages import StoreChanged
from .screens.chat import ChatScreen
from .widgets import clipboard as _clipboard

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

    def copy_to_clipboard(  # pyright: ignore[reportIncompatibleMethodOverride]
        self, text: str
    ) -> bool:
        """Copy ``text`` via BOTH OSC 52 and the local OS clipboard.

        The bool return intentionally widens the base's ``-> None`` so the
        ``c``/``y`` key handlers can report whether the local write landed;
        Textual's own callers (``Screen.action_copy_text``) ignore the return.

        Textual's base implementation emits only an OSC 52 escape sequence.
        That is SSH-safe but silently drops on terminals that don't honour
        OSC 52 clipboard writes (macOS Terminal.app being the common one), so
        a mouse-selection copy or the ``c``/``y`` keys appear to do nothing.
        Emitting OSC 52 *and* writing the local clipboard (pbcopy/xclip/
        pyperclip) makes copy land in the system clipboard everywhere: local
        terminals via the OS tool, remote sessions via OSC 52.

        This single override also upgrades Textual's built-in
        mouse-selection copy — Screen binds ``ctrl+c``/``super+c`` to
        ``screen.copy_text``, which routes the selection through
        ``app.copy_to_clipboard`` — so drag-select + Ctrl+C now works too.

        Returns whether the local clipboard write succeeded.
        """
        try:
            super().copy_to_clipboard(text)  # OSC 52 escape sequence
        except Exception:
            # No active driver (headless/tests) — the local path still applies.
            pass
        return _clipboard.copy_to_clipboard(text)

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
