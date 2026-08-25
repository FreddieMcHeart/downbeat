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
import sys

from downbeat.cli.__main__ import main
from downbeat.core import store
from downbeat.core.models import Peer


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
    the listing is read at a glance and an empty field reads as a value."""
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
