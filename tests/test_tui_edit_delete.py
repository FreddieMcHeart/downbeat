import pytest


@pytest.mark.asyncio
async def test_edit_read_message_blocked(relay_dir):
    from downbeat.core import store
    from downbeat.core.errors import MessageLocked
    store.register_peer(name="p", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="c", session_id="s2", cwd="/tmp", role="child")
    msg = store.send_message(from_peer="p", to_peer="c", subject="s", body="b")
    store.mark_read(msg.id)
    import pytest

    from downbeat.tui.widgets.edit_modal import perform_edit
    with pytest.raises(MessageLocked):
        perform_edit(msg.id, new_body="b2")


@pytest.mark.asyncio
async def test_delete_message(relay_dir):
    from downbeat.core import store
    from downbeat.core.errors import MessageNotFound
    store.register_peer(name="p", session_id="s1", cwd="/tmp", role="parent")
    store.register_peer(name="c", session_id="s2", cwd="/tmp", role="child")
    msg = store.send_message(from_peer="p", to_peer="c", subject="s", body="b")
    from downbeat.tui.widgets.confirm import perform_delete
    perform_delete(msg.id)
    import pytest
    with pytest.raises(MessageNotFound):
        store.get_message(msg.id)
