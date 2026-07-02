from downbeat.core import groups


def test_save_and_load_group(relay_dir):
    groups.save_group("fleet", ["a", "b", "c"])
    assert groups.list_groups() == {"fleet": ["a", "b", "c"]}
    assert groups.get_group("fleet") == ["a", "b", "c"]


def test_delete_group(relay_dir):
    groups.save_group("fleet", ["a"])
    groups.delete_group("fleet")
    assert groups.list_groups() == {}
