"""Clipboard copy from the TUI.

Regression coverage for "I cannot copy anything from the TUI": the base
Textual ``App.copy_to_clipboard`` emits only an OSC 52 escape sequence, which
silently drops on terminals that ignore OSC 52 clipboard writes (macOS
Terminal.app). ``RelayApp`` overrides it to ALSO write the local OS clipboard
(pbcopy/xclip/pyperclip), so the ``c``/``y`` keys and Textual's built-in
mouse-selection copy land in the system clipboard everywhere.

These are driven against the real objects — the real ``RelayApp`` method, the
real Textual event loop (``run_test``), and the real installed Textual bindings
— not mocks that would pass for the wrong reason.
"""
import pytest
from textual.binding import Binding
from textual.screen import Screen

from downbeat.tui import app as app_mod
from downbeat.tui.screens.message_detail import MessageDetailScreen


def _record_local(monkeypatch, sink, result=True):
    monkeypatch.setattr(
        app_mod._clipboard, "copy_to_clipboard",
        lambda text: sink.append(("local", text)) or result,
    )


def _record_osc52(monkeypatch, sink):
    # Patch the base App method so RelayApp's super() call is observable.
    monkeypatch.setattr(
        app_mod.App, "copy_to_clipboard",
        lambda self, text: sink.append(("osc52", text)),
    )


def test_copy_to_clipboard_hits_both_paths(monkeypatch):
    sink = []
    _record_osc52(monkeypatch, sink)
    _record_local(monkeypatch, sink, result=True)
    app = app_mod.RelayApp()
    result = app.copy_to_clipboard("payload")
    assert ("osc52", "payload") in sink, "OSC 52 (SSH-safe) path must fire"
    assert ("local", "payload") in sink, "local OS clipboard path must fire"
    assert result is True, "returns whether the local write succeeded"


def test_copy_to_clipboard_returns_local_failure(monkeypatch):
    sink = []
    _record_osc52(monkeypatch, sink)
    _record_local(monkeypatch, sink, result=False)
    app = app_mod.RelayApp()
    assert app.copy_to_clipboard("x") is False


def test_copy_to_clipboard_survives_osc52_error(monkeypatch):
    """If OSC 52 raises (no active driver), the local path still runs."""
    def boom(self, text):
        raise RuntimeError("no driver")
    monkeypatch.setattr(app_mod.App, "copy_to_clipboard", boom)
    sink = []
    _record_local(monkeypatch, sink, result=True)
    app = app_mod.RelayApp()
    assert app.copy_to_clipboard("y") is True
    assert ("local", "y") in sink


def test_mouse_selection_copy_binding_reaches_app_clipboard():
    """The mouse-selection copy path is Textual's own: Screen binds
    ctrl+c/super+c to ``screen.copy_text``, which calls ``app.copy_to_clipboard``.
    Our override intercepts that call — assert the wiring still exists in the
    installed Textual so a future upgrade can't silently break selection-copy.
    """
    actions = []
    for b in Screen.BINDINGS:
        if isinstance(b, Binding):
            actions.append((b.key, b.action))
        elif isinstance(b, tuple):
            actions.append((b[0], b[1]))
    assert any("ctrl+c" in k and "copy_text" in a for k, a in actions), \
        "Textual must bind ctrl+c -> screen.copy_text for mouse-selection copy"
    assert hasattr(Screen, "action_copy_text"), \
        "Screen.action_copy_text is the hop into app.copy_to_clipboard"


@pytest.mark.asyncio
async def test_copy_id_key_routes_through_dual_path(relay_dir, monkeypatch):
    """Pressing `c` on the detail screen copies the id through the dual-path
    clipboard — exercised end to end via the real Textual event loop."""
    from downbeat.core import store
    store.register_peer(name="p", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="c", session_id="s2", cwd="/tmp", role="child",
                        parent="p")
    msg = store.send_message(from_peer="c", to_peer="p", subject="hi",
                             body="the body")
    captured = []
    _record_local(monkeypatch, captured, result=True)
    app = app_mod.RelayApp()
    async with app.run_test(headless=True) as pilot:
        await pilot.pause()
        app.push_screen(MessageDetailScreen(msg.id))
        await pilot.pause()
        await pilot.press("c")
        await pilot.pause()
    assert ("local", msg.id) in captured, "`c` must copy the id via the local path"


@pytest.mark.asyncio
async def test_yank_body_key_routes_through_dual_path(relay_dir, monkeypatch):
    from downbeat.core import store
    store.register_peer(name="p", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="c", session_id="s2", cwd="/tmp", role="child",
                        parent="p")
    msg = store.send_message(from_peer="c", to_peer="p", subject="hi",
                             body="the body")
    captured = []
    _record_local(monkeypatch, captured, result=True)
    app = app_mod.RelayApp()
    async with app.run_test(headless=True) as pilot:
        await pilot.pause()
        app.push_screen(MessageDetailScreen(msg.id))
        await pilot.pause()
        await pilot.press("y")
        await pilot.pause()
    assert ("local", "the body") in captured, "`y` must copy the body via the local path"
