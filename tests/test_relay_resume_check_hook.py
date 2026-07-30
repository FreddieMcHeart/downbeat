"""Tests for relay-resume-check.py — the SessionStart hook that makes a
resumed session's stale relay identity LOUD at startup instead of silent
until the first `send`.

See issue #71 (and its correction comment): the session_id_history self-heal
(PR #77) only fires when the resumed session's id already appears in some
peer's history. For a genuinely fresh resumed id -- the reported case -- no
provable lineage exists, so the fix is not a better guess; it is telling the
user at resume that no peer can be determined automatically.

Predicate (deliberately narrow, to never cry wolf on an ordinary fresh
session that was never a peer at all):
  - only ever considers `source == "resume"` SessionStart events
  - only fires when this session's id is NOT already any peer's current
    session_id (nothing to warn about)
  - only fires when this session's id is NOT in any peer's
    session_id_history (that case self-heals silently at the next relay
    command -- warning about it too would be noise about something that
    already fixes itself)
  - only fires when the resumed cwd matches EXACTLY ONE registered peer's
    cwd (real evidence this machine's registry expected this session to be
    that peer) -- zero or ambiguous (>1) matches stay silent, because a
    guess among candidates is exactly what this issue rejects

The hook is a standalone, stdlib-only script (no downbeat package import --
matches the constraint documented atop relay-poll-offer.py), so it is loaded
per-test via importlib.util.spec_from_file_location rather than a normal
import, AND driven as a real subprocess for the end-to-end cases (per the
"verify against the real artifact" rule -- a test that only calls the pure
predicate function never proves the hook's stdin/stdout/exit-code contract
holds against the actual script Claude Code will invoke).
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import downbeat

HOOK = (Path(downbeat.__file__).parent / "assets" / "hooks"
        / "relay-resume-check.py")


def _load_hook_module():
    spec = importlib.util.spec_from_file_location("relay_resume_check", HOOK)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _peer(session_id, cwd, history=None):
    return {
        "session_id": session_id,
        "cwd": cwd,
        "session_id_history": history or [],
    }


# --- unit tests: the pure predicate --------------------------------------

def test_silent_when_cwd_was_never_a_registered_peer():
    hook = _load_hook_module()
    sessions = {"Other": _peer("aaa", "/some/other/project")}
    assert hook.find_stale_binding("new-sid", "/my/project", sessions) is None


def test_silent_when_session_id_is_already_correctly_bound():
    hook = _load_hook_module()
    sessions = {"Me": _peer("new-sid", "/my/project")}
    assert hook.find_stale_binding("new-sid", "/my/project", sessions) is None


def test_warns_when_session_id_is_in_exactly_one_peers_history():
    """A history hit is now the STRONGEST evidence, not a reason for silence.

    It used to return None because the CLI self-healed the case on the next
    command (PR #77). #88 removed that self-heal -- the history cannot tell a
    resumed session apart from a different one that once held the name -- so
    the session will be refused at its first relay command, and saying so at
    resume is the whole point of this hook.
    """
    hook = _load_hook_module()
    sessions = {"Me": _peer("old-sid", "/my/project", history=["new-sid"])}
    hit = hook.find_stale_binding("new-sid", "/my/project", sessions)
    assert hit is not None
    name, meta = hit
    assert name == "Me"
    assert meta["session_id"] == "old-sid"


def test_silent_when_session_id_is_in_several_peers_histories():
    """Ambiguous across peers -- never guess which one this session is."""
    hook = _load_hook_module()
    sessions = {
        "PeerA": _peer("live-a", "/a", history=["shared-old"]),
        "PeerB": _peer("live-b", "/b", history=["shared-old"]),
    }
    assert hook.find_stale_binding("shared-old", "/a", sessions) is None


def test_warns_when_cwd_matches_exactly_one_stale_peer():
    hook = _load_hook_module()
    sessions = {"Skill-Builder": _peer("da8ae321-old", "/my/project")}
    hit = hook.find_stale_binding("4dec4a90-new", "/my/project", sessions)
    assert hit is not None
    name, meta = hit
    assert name == "Skill-Builder"
    assert meta["session_id"] == "da8ae321-old"


def test_silent_when_cwd_matches_more_than_one_peer_ambiguous():
    hook = _load_hook_module()
    sessions = {
        "PeerA": _peer("old-a", "/shared/project"),
        "PeerB": _peer("old-b", "/shared/project"),
    }
    assert hook.find_stale_binding("new-sid", "/shared/project", sessions) is None


def test_silent_when_cwd_is_empty():
    hook = _load_hook_module()
    sessions = {"Me": _peer("old-sid", "")}
    assert hook.find_stale_binding("new-sid", "", sessions) is None


def test_silent_when_peer_cwd_field_missing():
    hook = _load_hook_module()
    sessions = {"Me": {"session_id": "old-sid"}}
    assert hook.find_stale_binding("new-sid", "/my/project", sessions) is None


# --- unit test: the message itself must be actionable --------------------

def test_message_names_peer_states_cannot_send_and_gives_exact_command():
    hook = _load_hook_module()
    msg = hook.render_message("Skill-Builder", "da8ae321-old-sid",
                              "4dec4a90-new-sid", "/my/project")
    assert "Skill-Builder" in msg
    assert "cannot send" in msg
    assert "downbeat rebind Skill-Builder --session-id 4dec4a90-new-sid" in msg


# --- end-to-end: the real script, real subprocess, real stdin/stdout -----

def _run(tmp_path, payload, sessions=None, home=None):
    relay_dir = tmp_path / "relay"
    relay_dir.mkdir(parents=True, exist_ok=True)
    if sessions is not None:
        (relay_dir / "sessions.json").write_text(json.dumps(sessions))
    proc = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=20,
        env={
            "PATH": "/usr/bin:/bin",
            "HOME": str(home or tmp_path),
            "CLAUDE_RELAY_DIR": str(relay_dir),
        },
    )
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.strip()


def test_end_to_end_warns_on_the_reported_scenario(tmp_path):
    sessions = {"Skill-Builder": _peer("da8ae321-789f", "/my/project")}
    out = _run(
        tmp_path,
        {"session_id": "4dec4a90-9eea", "cwd": "/my/project",
         "source": "resume", "hook_event_name": "SessionStart"},
        sessions=sessions,
    )
    assert out, "the exact reported failure must now be loud, not silent"
    msg = json.loads(out)["systemMessage"]
    assert "Skill-Builder" in msg
    assert "downbeat rebind Skill-Builder --session-id 4dec4a90-9eea" in msg


def test_end_to_end_silent_on_a_genuinely_fresh_session(tmp_path):
    """A session whose cwd never had a registered peer must not be nagged --
    this is the anti-cry-wolf case."""
    out = _run(
        tmp_path,
        {"session_id": "brand-new-sid", "cwd": "/never/registered",
         "source": "resume", "hook_event_name": "SessionStart"},
        sessions={"Someone": _peer("other-sid", "/some/other/project")},
    )
    assert out == ""


def test_end_to_end_silent_on_ordinary_startup_even_with_stale_cwd_match(tmp_path):
    """source == "startup" is a brand new session by definition, never a
    resume -- must stay silent even if by coincidence cwd matches a peer."""
    sessions = {"Skill-Builder": _peer("da8ae321-789f", "/my/project")}
    out = _run(
        tmp_path,
        {"session_id": "4dec4a90-9eea", "cwd": "/my/project",
         "source": "startup", "hook_event_name": "SessionStart"},
        sessions=sessions,
    )
    assert out == ""


def test_end_to_end_silent_when_no_sessions_file(tmp_path):
    out = _run(
        tmp_path,
        {"session_id": "sid", "cwd": "/my/project", "source": "resume",
         "hook_event_name": "SessionStart"},
        sessions=None,
    )
    assert out == ""


def test_end_to_end_silent_and_exits_zero_on_malformed_sessions_json(tmp_path):
    relay_dir = tmp_path / "relay"
    relay_dir.mkdir(parents=True, exist_ok=True)
    (relay_dir / "sessions.json").write_text("{not valid json")
    proc = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps({"session_id": "sid", "cwd": "/my/project",
                          "source": "resume", "hook_event_name": "SessionStart"}),
        capture_output=True, text=True, timeout=20,
        env={"PATH": "/usr/bin:/bin", "HOME": str(tmp_path),
             "CLAUDE_RELAY_DIR": str(relay_dir)},
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == ""


def test_end_to_end_silent_on_empty_stdin(tmp_path):
    """No payload at all must never raise -- defensive against a malformed
    hook invocation."""
    relay_dir = tmp_path / "relay"
    relay_dir.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [sys.executable, str(HOOK)], input="", capture_output=True, text=True,
        timeout=20,
        env={"PATH": "/usr/bin:/bin", "HOME": str(tmp_path),
             "CLAUDE_RELAY_DIR": str(relay_dir)},
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == ""


def test_end_to_end_warns_when_history_holds_this_session_id(tmp_path):
    """End-to-end counterpart of the unit test above (#88)."""
    sessions = {"Me": _peer("old-sid", "/my/project", history=["new-sid"])}
    out = _run(
        tmp_path,
        {"session_id": "new-sid", "cwd": "/my/project", "source": "resume",
         "hook_event_name": "SessionStart"},
        sessions=sessions,
    )
    assert out != ""
    assert "Me" in out
