import sys

from downbeat.cli.__main__ import main


def test_register_child_auto_defaults_to_sole_parent(relay_dir, capsys, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["downbeat", "register", "parent", "--role", "parent"])
    assert main() == 0
    monkeypatch.setattr(sys, "argv", ["downbeat", "register", "any-free-name", "--role", "child"])
    assert main() == 0
    out = capsys.readouterr().out
    assert "parent=parent" in out


def test_register_child_no_parent_prints_clean_error_not_traceback(relay_dir, capsys, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["downbeat", "register", "orphan", "--role", "child"])
    rc = main()
    assert rc == 1
    err = capsys.readouterr().err
    assert "Traceback" not in err
    assert "no role=parent peer" in err


def test_register_child_ambiguous_parent_prints_clean_error(relay_dir, capsys, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["downbeat", "register", "parent-a", "--role", "parent"])
    main()
    monkeypatch.setattr(sys, "argv", ["downbeat", "register", "parent-b", "--role", "parent"])
    main()
    monkeypatch.setattr(sys, "argv", ["downbeat", "register", "child", "--role", "child"])
    rc = main()
    assert rc == 1
    err = capsys.readouterr().err
    assert "multiple parent peers exist" in err


def test_register_child_explicit_parent_flag_disambiguates(relay_dir, capsys, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["downbeat", "register", "parent-a", "--role", "parent"])
    main()
    monkeypatch.setattr(sys, "argv", ["downbeat", "register", "parent-b", "--role", "parent"])
    main()
    monkeypatch.setattr(
        sys, "argv",
        ["downbeat", "register", "child", "--role", "child", "--parent", "parent-b"],
    )
    rc = main()
    assert rc == 0
    out = capsys.readouterr().out
    assert "parent=parent-b" in out


def test_peers_set_parent_backfills_and_lists(relay_dir, capsys, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["downbeat", "register", "parent-a", "--role", "parent"])
    main()
    monkeypatch.setattr(sys, "argv", ["downbeat", "register", "parent-b", "--role", "parent"])
    main()
    monkeypatch.setattr(
        sys, "argv",
        ["downbeat", "register", "child", "--role", "child", "--parent", "parent-a"],
    )
    main()
    capsys.readouterr()

    monkeypatch.setattr(
        sys, "argv", ["downbeat", "peers", "set-parent", "child", "parent-b"],
    )
    rc = main()
    assert rc == 0
    out = capsys.readouterr().out
    assert "parent set to parent-b" in out

    monkeypatch.setattr(sys, "argv", ["downbeat", "peers"])
    main()
    out = capsys.readouterr().out
    assert "parent=parent-b" in out


def test_peers_set_parent_unknown_child_prints_clean_error(relay_dir, capsys, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["downbeat", "register", "parent", "--role", "parent"])
    main()
    capsys.readouterr()
    monkeypatch.setattr(sys, "argv", ["downbeat", "peers", "set-parent", "nope", "parent"])
    rc = main()
    assert rc == 1
    err = capsys.readouterr().err
    assert "Traceback" not in err
