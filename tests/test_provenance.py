import json

import pytest

from downbeat.core import provenance


class _FakeDist:
    """Stands in for importlib.metadata.Distribution.

    direct_url: the parsed PEP 610 record, or None to simulate a plain
    release install (pip/uv write no direct_url.json for those).
    """

    def __init__(self, version="1.2.3", direct_url=None, raises=None):
        self.version = version
        self._direct_url = direct_url
        self._raises = raises

    def read_text(self, name):
        if self._raises is not None:
            raise self._raises
        if name != "direct_url.json":
            return None
        return json.dumps(self._direct_url) if self._direct_url else None


def _patch_dist(monkeypatch, dist):
    monkeypatch.setattr(provenance.Distribution, "from_name",
                        staticmethod(lambda _name: dist))


def test_release_install_reports_a_bare_trustworthy_version(monkeypatch):
    _patch_dist(monkeypatch, _FakeDist(version="0.9.2"))
    p = provenance.detect()
    assert p.version == "0.9.2"
    assert p.editable_path is None
    assert p.is_editable is False
    assert p.version_is_trustworthy is True
    assert p.describe() == "downbeat 0.9.2"


def test_editable_install_reports_the_working_tree_it_reads_from(monkeypatch):
    _patch_dist(monkeypatch, _FakeDist(
        version="0.7.1",
        direct_url={"url": "file:///Users/me/mama/downbeat",
                    "dir_info": {"editable": True}},
    ))
    p = provenance.detect()
    assert p.editable_path == "/Users/me/mama/downbeat"
    assert p.is_editable is True
    # The whole point: an editable version number describes nothing about the
    # code being run, so nothing may compare against it.
    assert p.version_is_trustworthy is False
    described = p.describe()
    assert "0.7.1" in described
    assert "/Users/me/mama/downbeat" in described
    assert "editable" in described


def test_non_editable_direct_url_is_not_treated_as_editable(monkeypatch):
    """A VCS/local install records direct_url too, but without the editable
    flag -- its version is stamped from real built metadata and IS accurate."""
    _patch_dist(monkeypatch, _FakeDist(
        version="0.9.2",
        direct_url={"url": "https://github.com/x/downbeat", "dir_info": {}},
    ))
    p = provenance.detect()
    assert p.is_editable is False
    assert p.version_is_trustworthy is True


def test_not_installed_as_a_package_says_so_rather_than_guessing(monkeypatch):
    from importlib.metadata import PackageNotFoundError

    def _boom(_name):
        raise PackageNotFoundError("downbeat")
    monkeypatch.setattr(provenance.Distribution, "from_name", staticmethod(_boom))
    p = provenance.detect()
    assert p.version is None
    assert p.version_is_trustworthy is False
    assert "not installed as a package" in p.describe()


@pytest.mark.parametrize("broken", [
    _FakeDist(raises=OSError("unreadable")),
    _FakeDist(direct_url=None),
])
def test_unreadable_or_absent_direct_url_degrades_to_not_editable(monkeypatch, broken):
    """--version and the staleness hook both call this; neither may explode
    because an install's metadata is odd."""
    _patch_dist(monkeypatch, broken)
    p = provenance.detect()
    assert p.is_editable is False
    assert p.version == "1.2.3"


def test_malformed_direct_url_json_does_not_raise(monkeypatch):
    class _Garbage(_FakeDist):
        def read_text(self, name):
            return "{not json"
    _patch_dist(monkeypatch, _Garbage())
    assert provenance.detect().is_editable is False


def test_editable_with_an_unusable_url_stays_editable(monkeypatch):
    """The path is best-effort; the editable FLAG is not. A url we can't turn
    into a path must never downgrade an editable install to a trustworthy one
    -- that would hand a fossil version back to the very check that exists to
    catch fossil versions."""
    _patch_dist(monkeypatch, _FakeDist(
        version="0.7.1",
        direct_url={"url": "", "dir_info": {"editable": True}},
    ))
    p = provenance.detect()
    assert p.is_editable is True
    assert p.version_is_trustworthy is False
    assert p.editable_path is None
    assert "editable" in p.describe()


@pytest.mark.parametrize("dir_info", [None, "yes", ["editable"], 1])
def test_non_dict_dir_info_does_not_raise(monkeypatch, dir_info):
    """detect() is called eagerly while building the argument parser, so a
    raise here would break every downbeat command, `tui` included -- not just
    --version."""
    _patch_dist(monkeypatch, _FakeDist(
        version="0.9.2", direct_url={"url": "file:///x", "dir_info": dir_info}))
    assert provenance.detect().is_editable is False


def test_non_dict_direct_url_document_does_not_raise(monkeypatch):
    _patch_dist(monkeypatch, _FakeDist(version="0.9.2", direct_url=["not", "a", "dict"]))
    assert provenance.detect().is_editable is False


def test_localhost_file_url_is_turned_into_a_real_path(monkeypatch):
    """file://localhost/x and file:///x are both legal; naive prefix stripping
    turns the first into 'localhost/x'."""
    _patch_dist(monkeypatch, _FakeDist(
        version="0.7.1",
        direct_url={"url": "file://localhost/Users/me/db", "dir_info": {"editable": True}},
    ))
    assert provenance.detect().editable_path == "/Users/me/db"
