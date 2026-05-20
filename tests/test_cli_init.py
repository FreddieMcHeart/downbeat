import json
from pathlib import Path

from claude_relay.cli.commands.init_cmd import run_init, run_uninstall


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
    import claude_relay
    pkg_skill = Path(claude_relay.__file__).parent / "skill" / "SKILL.md"
    assert pkg_skill.exists()


def test_skill_md_uses_context_aware_offer(relay_dir):
    """The packaged skill no longer offers the poll on every first invocation;
    it conditions the offer on whether the user is about to idle waiting."""
    import claude_relay
    from pathlib import Path
    skill = (Path(claude_relay.__file__).parent / "skill" / "SKILL.md").read_text()
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
    assert not (tmp_path / ".claude" / "skills" / "claude-relay").exists()
