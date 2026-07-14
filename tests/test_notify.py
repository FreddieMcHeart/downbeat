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
