from pathlib import Path

from claude_relay.core import paths


def test_default_relay_dir_under_home():
    assert paths.RELAY_DIR == Path.home() / ".claude" / "relay"


def test_subdirs_resolved_from_relay_dir():
    assert paths.INBOX_DIR == paths.RELAY_DIR / "inbox"
    assert paths.PROCESSED_DIR == paths.RELAY_DIR / "processed"
    assert paths.LOG_DIR == paths.RELAY_DIR / "logs"
    assert paths.SESSIONS_FILE == paths.RELAY_DIR / "sessions.json"
    assert paths.GROUPS_FILE == paths.RELAY_DIR / "groups.json"
    assert paths.CONFIG_FILE == paths.RELAY_DIR / "config.toml"


def test_override_via_env(monkeypatch, tmp_path):
    monkeypatch.setenv("CLAUDE_RELAY_DIR", str(tmp_path))
    import importlib
    importlib.reload(paths)
    assert paths.RELAY_DIR == tmp_path
    assert paths.INBOX_DIR == tmp_path / "inbox"
