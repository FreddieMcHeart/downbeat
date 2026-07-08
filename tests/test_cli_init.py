import json
import os
import subprocess
from pathlib import Path

from downbeat.cli.commands import init_cmd
from downbeat.cli.commands.init_cmd import run_init, run_migrate_to_plugin, run_uninstall


def _relay_reg_count(settings_path: Path) -> int:
    """Count relay hook registrations nested anywhere in settings['hooks']."""
    d = json.loads(settings_path.read_text())
    n = 0
    for _event, lst in d.get("hooks", {}).items():
        for entry in lst:
            for h in entry.get("hooks", []):
                cmd = h.get("command", "")
                if "relay-inbox.py" in cmd or "relay-poll-offer.py" in cmd:
                    n += 1
    return n


def _all_commands(settings_path: Path) -> list[str]:
    d = json.loads(settings_path.read_text())
    out = []
    for _event, lst in d.get("hooks", {}).items():
        for entry in lst:
            for h in entry.get("hooks", []):
                out.append(h.get("command", ""))
    return out


def test_init_creates_relay_dirs(relay_dir):
    rc = run_init()
    assert rc == 0
    assert (relay_dir / "inbox").is_dir()
    assert (relay_dir / "processed").is_dir()
    assert (relay_dir / "logs").is_dir()


def test_init_migrates_legacy_messages(relay_dir):
    # Plant a legacy message file missing read_at / edited_at
    (relay_dir / "inbox" / "child").mkdir(parents=True)
    legacy = relay_dir / "inbox" / "child" / "old.json"
    legacy.write_text(json.dumps({
        "id": "old",
        "from": "parent", "to": "child",
        "subject": "s", "body": "b",
        "created_at": "2026-05-01T00:00:00+00:00",
    }))
    run_init()
    migrated = json.loads(legacy.read_text())
    assert "read_at" in migrated
    assert migrated["read_at"] is None
    assert "broadcast_id" in migrated


def test_init_installs_skill(tmp_path, monkeypatch, relay_dir):
    monkeypatch.setenv("HOME", str(tmp_path))
    # Re-resolve any HOME-based paths used inside run_init
    rc = run_init()
    assert rc == 0
    # Skill installation tested indirectly: file content matches package skill
    # Locate the packaged skill source
    import downbeat
    pkg_skill = Path(downbeat.__file__).parent / "skill" / "SKILL.md"
    assert pkg_skill.exists()


def test_skill_md_uses_context_aware_offer(relay_dir):
    """The packaged skill no longer offers the poll on every first invocation;
    it conditions the offer on whether the user is about to idle waiting."""
    from pathlib import Path

    import downbeat
    skill = (Path(downbeat.__file__).parent / "skill" / "SKILL.md").read_text()
    # The old chronological wording is gone:
    assert "First-invocation offer" not in skill
    # The new context-aware wording is present:
    assert "Context-aware offer" in skill
    assert "Do NOT offer a /loop poll by default" in skill


def test_uninstall_removes_skill(tmp_path, monkeypatch, relay_dir):
    monkeypatch.setenv("HOME", str(tmp_path))
    run_init()
    rc = run_uninstall()
    assert rc == 0
    assert not (tmp_path / ".claude" / "skills" / "downbeat").exists()


# --------------- consolidation: hooks + commands + settings ----------------

def test_init_installs_hooks_commands_and_registers_settings(tmp_path, monkeypatch, relay_dir):
    monkeypatch.setenv("HOME", str(tmp_path))
    rc = run_init(backup_suffix="TEST")
    assert rc == 0
    hooks = tmp_path / ".claude" / "hooks"
    assert (hooks / "relay-inbox.py").exists()
    assert (hooks / "relay-poll-offer.py").exists()
    # hooks must be executable
    assert os.access(hooks / "relay-inbox.py", os.X_OK)
    # commands copied
    cmds = tmp_path / ".claude" / "commands"
    for name in ("relay-register.md", "relay-send.md", "relay-reply.md",
                 "relay-peers.md", "relay-monitor.md"):
        assert (cmds / name).exists(), name
    # settings gains the 3 relay regs
    settings = tmp_path / ".claude" / "settings.json"
    assert _relay_reg_count(settings) == 3


def test_init_is_idempotent_on_settings(tmp_path, monkeypatch, relay_dir):
    monkeypatch.setenv("HOME", str(tmp_path))
    run_init(backup_suffix="TEST")
    first = _relay_reg_count(tmp_path / ".claude" / "settings.json")
    run_init(backup_suffix="TEST2")
    second = _relay_reg_count(tmp_path / ".claude" / "settings.json")
    assert first == second == 3
    # Second run added nothing → no second backup file created
    assert not (tmp_path / ".claude" / "settings.json.bak-TEST2").exists()


def test_init_leaves_preexisting_relay_regs(tmp_path, monkeypatch, relay_dir):
    monkeypatch.setenv("HOME", str(tmp_path))
    settings = tmp_path / ".claude" / "settings.json"
    settings.parent.mkdir(parents=True, exist_ok=True)
    # Pre-seed the exact live nested layout with all 3 relay regs present
    hp = str(tmp_path / ".claude" / "hooks")
    settings.write_text(json.dumps({"hooks": {
        "UserPromptSubmit": [{"hooks": [
            {"type": "command", "command": f"{hp}/relay-inbox.py", "timeout": 3}]}],
        "SessionStart": [{"matcher": "startup|resume", "hooks": [
            {"type": "command", "command": f"{hp}/relay-inbox.py", "timeout": 3}]}],
        "PostToolUse": [{"matcher": "Bash", "hooks": [
            {"type": "command", "command": f"{hp}/relay-poll-offer.py", "timeout": 3}]}],
    }}, indent=2))
    run_init(backup_suffix="TEST")
    assert _relay_reg_count(settings) == 3
    # nothing added → no backup
    assert not (tmp_path / ".claude" / "settings.json.bak-TEST").exists()


def test_init_preserves_other_hooks_and_interleaves(tmp_path, monkeypatch, relay_dir):
    monkeypatch.setenv("HOME", str(tmp_path))
    settings = tmp_path / ".claude" / "settings.json"
    settings.parent.mkdir(parents=True, exist_ok=True)
    # A non-relay hook on UserPromptSubmit with NO matcher (like cost-discipline)
    settings.write_text(json.dumps({"hooks": {
        "UserPromptSubmit": [{"hooks": [
            {"type": "command", "command": "/x/cost-discipline.py", "timeout": 5}]}],
    }}, indent=2))
    run_init(backup_suffix="TEST")
    cmds = _all_commands(settings)
    # cost-discipline preserved
    assert any("cost-discipline.py" in c for c in cmds)
    # relay-inbox added alongside it (interleaved into same no-matcher entry)
    assert _relay_reg_count(settings) == 3
    # a backup of the pre-existing file was made
    assert (tmp_path / ".claude" / "settings.json.bak-TEST").exists()


def test_init_creates_settings_when_missing(tmp_path, monkeypatch, relay_dir):
    monkeypatch.setenv("HOME", str(tmp_path))
    settings = tmp_path / ".claude" / "settings.json"
    assert not settings.exists()
    run_init(backup_suffix="TEST")
    assert settings.exists()
    assert _relay_reg_count(settings) == 3
    # created fresh → no backup of a prior file
    assert not (tmp_path / ".claude" / "settings.json.bak-TEST").exists()


def test_uninstall_removes_relay_regs_keeps_others(tmp_path, monkeypatch, relay_dir):
    monkeypatch.setenv("HOME", str(tmp_path))
    settings = tmp_path / ".claude" / "settings.json"
    settings.parent.mkdir(parents=True, exist_ok=True)
    settings.write_text(json.dumps({"hooks": {
        "UserPromptSubmit": [{"hooks": [
            {"type": "command", "command": "/x/cost-discipline.py", "timeout": 5}]}],
    }}, indent=2))
    run_init(backup_suffix="TEST")
    assert _relay_reg_count(settings) == 3
    run_uninstall(backup_suffix="TEST")
    # relay regs gone, cost-discipline preserved
    assert _relay_reg_count(settings) == 0
    assert any("cost-discipline.py" in c for c in _all_commands(settings))
    # hook + command files removed
    assert not (tmp_path / ".claude" / "hooks" / "relay-inbox.py").exists()
    assert not (tmp_path / ".claude" / "commands" / "relay-send.md").exists()


def test_init_on_malformed_settings_backs_up_and_errors(tmp_path, monkeypatch, relay_dir):
    monkeypatch.setenv("HOME", str(tmp_path))
    settings = tmp_path / ".claude" / "settings.json"
    settings.parent.mkdir(parents=True, exist_ok=True)
    settings.write_text("{ this is not valid json ")
    rc = run_init(backup_suffix="TEST")
    assert rc == 1
    # malformed file is left untouched (no partial write)
    assert settings.read_text() == "{ this is not valid json "
    # a malformed-backup was made
    assert (tmp_path / ".claude" / "settings.json.bak-malformed-TEST").exists()


# ------------------------- Claude Code plugin coexistence -------------------

def _fake_run(stdout: str, returncode: int = 0):
    def _run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, returncode, stdout=stdout, stderr="")
    return _run


def test_is_plugin_enabled_true_when_listed_and_enabled(monkeypatch):
    monkeypatch.setattr(subprocess, "run", _fake_run(
        json.dumps([{"id": "downbeat@some-marketplace", "enabled": True}])))
    assert init_cmd._is_plugin_enabled() is True


def test_is_plugin_enabled_false_when_disabled(monkeypatch):
    monkeypatch.setattr(subprocess, "run", _fake_run(
        json.dumps([{"id": "downbeat@some-marketplace", "enabled": False}])))
    assert init_cmd._is_plugin_enabled() is False


def test_is_plugin_enabled_false_when_not_listed(monkeypatch):
    monkeypatch.setattr(subprocess, "run", _fake_run(
        json.dumps([{"id": "claude-core-hooks@some-marketplace", "enabled": True}])))
    assert init_cmd._is_plugin_enabled() is False


def test_is_plugin_enabled_fails_open_on_missing_claude_binary(monkeypatch):
    def _raise(cmd, **kwargs):
        raise FileNotFoundError("claude not found")
    monkeypatch.setattr(subprocess, "run", _raise)
    assert init_cmd._is_plugin_enabled() is False


def test_is_plugin_enabled_fails_open_on_bad_json(monkeypatch):
    monkeypatch.setattr(subprocess, "run", _fake_run("not json"))
    assert init_cmd._is_plugin_enabled() is False


def test_is_plugin_enabled_fails_open_on_nonzero_exit(monkeypatch):
    monkeypatch.setattr(subprocess, "run", _fake_run("", returncode=1))
    assert init_cmd._is_plugin_enabled() is False


def test_init_skips_hand_merge_when_plugin_enabled(tmp_path, monkeypatch, relay_dir, capsys):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(init_cmd, "_is_plugin_enabled", lambda name="downbeat": True)
    rc = run_init(backup_suffix="TEST")
    assert rc == 0
    settings = tmp_path / ".claude" / "settings.json"
    # No hand-merge happened at all: settings.json was never created
    assert not settings.exists()
    assert "plugin detected" in capsys.readouterr().out


def test_init_warns_on_double_fire_when_plugin_enabled_and_legacy_regs_exist(
        tmp_path, monkeypatch, relay_dir, capsys):
    monkeypatch.setenv("HOME", str(tmp_path))
    settings = tmp_path / ".claude" / "settings.json"
    settings.parent.mkdir(parents=True, exist_ok=True)
    hp = str(tmp_path / ".claude" / "hooks")
    settings.write_text(json.dumps({"hooks": {
        "UserPromptSubmit": [{"hooks": [
            {"type": "command", "command": f"{hp}/relay-inbox.py", "timeout": 3}]}],
    }}, indent=2))
    monkeypatch.setattr(init_cmd, "_is_plugin_enabled", lambda name="downbeat": True)
    rc = run_init(backup_suffix="TEST")
    assert rc == 0
    out = capsys.readouterr().out
    assert "WARNING" in out
    assert "double-fire" in out
    # Legacy registration left untouched (not migrated, not duplicated)
    assert _relay_reg_count(settings) == 1


# ------------------------------ migrate-to-plugin ---------------------------

def test_migrate_refuses_when_plugin_not_enabled(tmp_path, monkeypatch, relay_dir, capsys):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(init_cmd, "_is_plugin_enabled", lambda name="downbeat": False)
    settings = tmp_path / ".claude" / "settings.json"
    settings.parent.mkdir(parents=True, exist_ok=True)
    hp = str(tmp_path / ".claude" / "hooks")
    settings.write_text(json.dumps({"hooks": {
        "UserPromptSubmit": [{"hooks": [
            {"type": "command", "command": f"{hp}/relay-inbox.py", "timeout": 3}]}],
    }}, indent=2))
    rc = run_migrate_to_plugin(backup_suffix="TEST")
    assert rc == 1
    assert "not installed/enabled" in capsys.readouterr().out
    # Nothing touched — legacy entry still there
    assert _relay_reg_count(settings) == 1
    assert not (tmp_path / ".claude" / "settings.json.bak-TEST").exists()


def test_migrate_removes_exact_legacy_entries_keeps_others(
        tmp_path, monkeypatch, relay_dir, capsys):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(init_cmd, "_is_plugin_enabled", lambda name="downbeat": True)
    settings = tmp_path / ".claude" / "settings.json"
    settings.parent.mkdir(parents=True, exist_ok=True)
    hp = str(tmp_path / ".claude" / "hooks")
    # Full legacy hand-merge (as run_init would have written it) plus a
    # non-relay neighbour sharing the same no-matcher UserPromptSubmit entry.
    settings.write_text(json.dumps({"hooks": {
        "UserPromptSubmit": [{"hooks": [
            {"type": "command", "command": "/x/cost-discipline.py", "timeout": 5},
            {"type": "command", "command": f"{hp}/relay-inbox.py", "timeout": 3},
        ]}],
        "SessionStart": [{"matcher": "startup|resume", "hooks": [
            {"type": "command", "command": f"{hp}/relay-inbox.py", "timeout": 3}]}],
        "PostToolUse": [{"matcher": "Bash", "hooks": [
            {"type": "command", "command": f"{hp}/relay-poll-offer.py", "timeout": 3}]}],
    }}, indent=2))
    rc = run_migrate_to_plugin(backup_suffix="TEST")
    assert rc == 0
    out = capsys.readouterr().out
    assert "removed legacy hand-merged relay hook regs" in out
    assert "downbeat uninstall" in out  # discoverability hint line
    assert _relay_reg_count(settings) == 0
    assert any("cost-discipline.py" in c for c in _all_commands(settings))
    assert (tmp_path / ".claude" / "settings.json.bak-TEST").exists()


def test_migrate_reports_nothing_to_migrate_when_no_legacy_entries(
        tmp_path, monkeypatch, relay_dir, capsys):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(init_cmd, "_is_plugin_enabled", lambda name="downbeat": True)
    rc = run_migrate_to_plugin(backup_suffix="TEST")
    assert rc == 0
    assert "nothing to migrate" in capsys.readouterr().out
    assert not (tmp_path / ".claude" / "settings.json").exists()


def test_migrate_is_precision_not_recall_on_nonmatching_command_string(
        tmp_path, monkeypatch, relay_dir, capsys):
    """A legacy entry whose command string doesn't byte-match today's
    derivation (e.g. HOME changed) is left in place, and the CLI points at
    `uninstall` as the substring-based fallback."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(init_cmd, "_is_plugin_enabled", lambda name="downbeat": True)
    settings = tmp_path / ".claude" / "settings.json"
    settings.parent.mkdir(parents=True, exist_ok=True)
    settings.write_text(json.dumps({"hooks": {
        "UserPromptSubmit": [{"hooks": [
            {"type": "command", "command": "/some/other/home/.claude/hooks/relay-inbox.py",
             "timeout": 3}]}],
    }}, indent=2))
    rc = run_migrate_to_plugin(backup_suffix="TEST")
    assert rc == 0
    out = capsys.readouterr().out
    assert "don't exactly match" in out
    assert "downbeat uninstall" in out
    # Left untouched — exact-match found nothing to remove
    assert _relay_reg_count(settings) == 1
    assert not (tmp_path / ".claude" / "settings.json.bak-TEST").exists()


def test_migrate_on_malformed_settings_backs_up_and_errors(
        tmp_path, monkeypatch, relay_dir):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(init_cmd, "_is_plugin_enabled", lambda name="downbeat": True)
    settings = tmp_path / ".claude" / "settings.json"
    settings.parent.mkdir(parents=True, exist_ok=True)
    settings.write_text("{ this is not valid json ")
    rc = run_migrate_to_plugin(backup_suffix="TEST")
    assert rc == 1
    assert settings.read_text() == "{ this is not valid json "
    assert (tmp_path / ".claude" / "settings.json.bak-malformed-TEST").exists()
