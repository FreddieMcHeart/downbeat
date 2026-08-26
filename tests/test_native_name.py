"""`Peer.native_name` — the join key between downbeat's registry and the
harness's own cross-session namespace (`ListAgents` / `SendMessage`).

The two namespaces share no key, so the field is SELF-REPORTED by the session
at registration rather than inferred -- which removes the matching heuristic
instead of tuning one that cannot be tuned into correctness.

The fleet measurement that establishes "no key" lives in ONE place, beside the
field itself in `core/models.py`. It is deliberately not restated here: a dated
measurement copied into two files drifts the first time either copy is
corrected, and the reader fixing one has no reason to look for the other.
"""
import json
import sys

from downbeat.cli.__main__ import main
from downbeat.core import paths, store
from downbeat.core.models import Peer

# A key no build models. Standing in for "the next field somebody adds",
# because the invariant these tests pin is not about native_name -- peer_id
# has exactly the same property and had exactly the same absence of a test.
_UNMODELLED = "__field_no_build_models_yet__"


def _peer(name):
    return next(p for p in store.list_peers() if p.name == name)


def test_register_stores_native_name(relay_dir):
    store.register_peer(name="p", session_id="s-1", cwd="/tmp", role="parent",
                        native_name="Claude Code cost optimizing")
    assert _peer("p").native_name == "Claude Code cost optimizing"


def test_native_name_defaults_to_empty_when_not_supplied(relay_dir):
    """Absent is empty, never None -- callers format it into output and a
    None would print as the string 'None' beside real names."""
    store.register_peer(name="p", session_id="s-1", cwd="/tmp", role="parent")
    assert _peer("p").native_name == ""


def test_reregister_without_native_name_preserves_the_stored_one(relay_dir):
    """The load-bearing case, and the one that would rot silently.

    `register_peer` is the ONLY one of the six read-modify-write sites on
    sessions.json that rebuilds the whole entry from the dataclass
    (`sessions[name] = peer.to_dict()`); every other site mutates the raw
    dict and carries unmodelled keys through untouched. Re-registration
    happens at every session start, so without this the field is wiped
    within one restart -- and a wiped field is indistinguishable from one
    that was never set.
    """
    store.register_peer(name="p", session_id="s-1", cwd="/tmp", role="parent",
                        native_name="Claude Relay")
    store.register_peer(name="p", session_id="s-2", cwd="/tmp", role="parent")
    p = _peer("p")
    assert p.session_id == "s-2", "the re-registration must still take effect"
    assert p.native_name == "Claude Relay", (
        "re-registering without --native-name must not wipe the stored one"
    )


def test_reregister_with_a_new_native_name_overwrites(relay_dir):
    """The other half of the rule above: silence preserves, an explicit
    value replaces. Without this test the preserve-branch could be written
    as 'never change it', which is a different and worse bug."""
    store.register_peer(name="p", session_id="s-1", cwd="/tmp", role="parent",
                        native_name="Old Name")
    store.register_peer(name="p", session_id="s-2", cwd="/tmp", role="parent",
                        native_name="New Name")
    assert _peer("p").native_name == "New Name"


def test_from_dict_tolerates_a_legacy_entry_with_no_native_name(relay_dir):
    """Every registry entry written before this change lacks the key.
    `from_dict` is a whitelist constructor using .get(), so this holds --
    asserted rather than assumed, because it is what makes the change
    safe without a registry schema-version ladder (there is none)."""
    legacy = {
        "name": "old", "session_id": "s-0", "cwd": "/tmp", "role": "child",
        "registered_at": "2026-01-01T00:00:00Z",
        "last_seen": "2026-01-01T00:00:00Z",
    }
    p = Peer.from_dict(legacy)
    assert p.native_name == ""


def test_native_name_survives_a_rename(relay_dir):
    """`rename_peer` re-keys the raw dict rather than rebuilding it, so this
    should already hold -- pinned so a future refactor of rename into a
    dataclass round-trip cannot silently drop the field."""
    store.register_peer(name="old", session_id="s-1", cwd="/tmp", role="parent",
                        native_name="Claude Relay")
    store.rename_peer("old", "new")
    assert _peer("new").native_name == "Claude Relay"


def test_cli_register_accepts_native_name_flag(relay_dir, capsys, monkeypatch):
    monkeypatch.setattr(sys, "argv", [
        "downbeat", "register", "p", "--role", "parent",
        "--native-name", "Claude Code cost optimizing",
    ])
    assert main() == 0
    assert _peer("p").native_name == "Claude Code cost optimizing"


def test_peers_output_shows_native_name_only_when_set(relay_dir, capsys, monkeypatch):
    """A peer with no native name must not grow an empty `native=` column --
    the listing is read at a glance and an empty field reads as a value.

    This test is DELIBERATELY coupled to the output format: the literal
    `native=` prefix and `repr()`'s quoting. If you are reading it because it
    went red after a cosmetic change -- switching the value to `json.dumps`,
    dropping the quotes, renaming the prefix -- that is a RENAME, not a
    regression, and the fix is to update this assertion. It goes red on a real
    regression too (the column appearing when unset), and only the diff you
    just made tells you which of the two you are looking at.
    """
    store.register_peer(name="withname", session_id="s-1", cwd="/tmp", role="parent",
                        native_name="Claude Relay")
    store.register_peer(name="plain", session_id="s-2", cwd="/tmp", role="parent")
    monkeypatch.setattr(sys, "argv", ["downbeat", "peers"])
    assert main() == 0
    lines = capsys.readouterr().out.splitlines()
    with_line = next(ln for ln in lines if ln.startswith("withname"))
    plain_line = next(ln for ln in lines if ln.startswith("plain"))
    assert "native='Claude Relay'" in with_line
    assert "native=" not in plain_line


# ---------------------------------------------------------------------------
# The whole-entry invariant.
#
# `register_peer` is the only write site that rebuilds an entry from the
# dataclass; the other five mutate the raw dict, so they preserve keys no
# build models. That was true when this branch was written and it was
# established by READING, which is a statement about now — a test is a
# statement about later. The refactor that breaks it (turning any of these
# into a Peer(...) round-trip) produces no failure at all, which is the
# family this repo keeps recording.
#
# So these assert the CLASS, not the field: an unmodelled key must survive
# too. A test named after native_name protects native_name; this protects
# whatever gets added next, and retroactively protects peer_id, which had
# the same property and the same absence of a test.
# ---------------------------------------------------------------------------


def _raw(name: str) -> dict:
    return json.loads(paths.SESSIONS_FILE.read_text())[name]


def _inject_unmodelled(name: str) -> None:
    """Write a key no dataclass models — the shape a NEWER build leaves behind."""
    sessions = json.loads(paths.SESSIONS_FILE.read_text())
    sessions[name][_UNMODELLED] = {"written_by": "a newer build"}
    paths.SESSIONS_FILE.write_text(json.dumps(sessions))


def _assert_entry_intact(before: dict, after: dict, changed: set) -> None:
    dropped = sorted(set(before) - set(after))
    assert not dropped, f"the operation DROPPED keys: {dropped}"
    drifted = sorted(k for k in before
                     if k not in changed and before[k] != after[k])
    assert not drifted, f"the operation silently CHANGED keys: {drifted}"


def _seed(name: str = "p", role: str = "parent", parent: str | None = None) -> dict:
    store.register_peer(name=name, session_id=f"s-{name}", cwd="/tmp", role=role,
                        parent=parent, native_name="Claude Relay")
    _inject_unmodelled(name)
    return _raw(name)


def test_touch_peer_preserves_the_whole_entry(relay_dir):
    before = _seed()
    store.touch_peer("p")
    after = _raw("p")
    assert after["last_seen"] != before["last_seen"], "touch must actually touch"
    _assert_entry_intact(before, after, changed={"last_seen"})


def test_set_parent_preserves_the_whole_entry(relay_dir):
    store.register_peer(name="parent-a", session_id="s-a", cwd="/tmp", role="parent")
    store.register_peer(name="parent-b", session_id="s-b", cwd="/tmp", role="parent")
    before = _seed("kid", role="child", parent="parent-a")
    store.set_parent("kid", "parent-b")
    after = _raw("kid")
    assert after["parent"] == "parent-b", "set_parent must actually reparent"
    _assert_entry_intact(before, after, changed={"parent"})


def test_rebind_session_preserves_the_whole_entry(relay_dir):
    before = _seed()
    store.rebind_session("p", new_session_id="s-rebound")
    after = _raw("p")
    assert after["session_id"] == "s-rebound", "rebind must actually rebind"
    _assert_entry_intact(before, after, changed={
        "session_id", "session_id_history", "last_rebind_at", "last_seen",
        "claude_pid", "claude_pid_start", "cwd",
    })


def test_remove_peer_leaves_other_entries_whole(relay_dir):
    """remove_peer rewrites the WHOLE registry to drop one key. Every peer it
    is not removing has to come back byte-identical."""
    store.register_peer(name="doomed", session_id="s-d", cwd="/tmp", role="parent")
    before = _seed("survivor")
    store.remove_peer("doomed")
    assert "doomed" not in json.loads(paths.SESSIONS_FILE.read_text()), \
        "remove_peer must actually remove"
    _assert_entry_intact(before, _raw("survivor"), changed=set())
