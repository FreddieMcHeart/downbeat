from downbeat.core import state


def test_set_and_get_last_acting_as(relay_dir):
    assert state.get_last_acting_as() is None
    state.set_last_acting_as("alice")
    assert state.get_last_acting_as() == "alice"
    state.set_last_acting_as(None)
    assert state.get_last_acting_as() is None


def test_set_and_get_last_active_peer(relay_dir):
    state.set_last_active_peer("bob")
    assert state.get_last_active_peer() == "bob"


def test_acting_as_and_active_peer_independent(relay_dir):
    state.set_last_acting_as("alice")
    state.set_last_active_peer("bob")
    assert state.get_last_acting_as() == "alice"
    assert state.get_last_active_peer() == "bob"


def test_state_file_resilient_to_garbage(relay_dir):
    # Corrupt file
    (relay_dir / "tui_state.json").write_text("garbage")
    # Should not crash; reads as empty
    assert state.get_last_acting_as() is None
