import importlib
import pytest


@pytest.fixture
def relay_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_RELAY_DIR", str(tmp_path))
    # Reload paths so CLAUDE_RELAY_DIR is picked up
    from claude_relay.core import paths
    importlib.reload(paths)
    # Reload store so it binds to the reloaded paths
    from claude_relay.core import store
    importlib.reload(store)
    paths.ensure_dirs()
    yield tmp_path
    # Restore default paths so unrelated tests (e.g. test_paths) see the real env
    monkeypatch.delenv("CLAUDE_RELAY_DIR", raising=False)
    importlib.reload(paths)
    importlib.reload(store)
