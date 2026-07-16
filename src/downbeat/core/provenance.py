"""Where is the downbeat you are actually running?

`importlib.metadata.version()` reports the version recorded when the
distribution was installed. For a normal release install that is the truth.
For an **editable** install it is a fossil: the metadata is stamped once, at
install time, while the code that actually executes is read live from the
working tree — which may be on any branch, any commit, arbitrarily newer or
older than the number claims.

That gap is not academic. It cost a real debugging session: a bug was filed
against "downbeat 0.7.1" (what `--version` said) while the code being run was
several releases ahead (what the working tree held), and the mismatch sent the
investigation the wrong way twice.

So: never report a bare version without also reporting where the code came
from. This module is the single place that answers that, so `--version` and
the plugin's staleness check cannot drift apart.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from importlib.metadata import Distribution
from urllib.parse import urlparse
from urllib.request import url2pathname

_DIST_NAME = "downbeat"


@dataclass(frozen=True)
class Provenance:
    """How the running downbeat got here.

    version:       what the install metadata claims. None if downbeat isn't
                   installed as a distribution at all (e.g. run straight from
                   a source checkout via `python -m downbeat.cli`).
    editable:      whether this is an editable install. Carried separately
                   from the path on purpose: the path is best-effort, and a
                   record we can't turn into a path must never downgrade an
                   editable install to a trustworthy-looking one.
    editable_path: the working tree the code is really read from, when we can
                   determine it.
    """

    version: str | None
    editable: bool = False
    editable_path: str | None = None

    @property
    def is_editable(self) -> bool:
        return self.editable

    @property
    def version_is_trustworthy(self) -> bool:
        """True only when `version` actually describes the running code.

        An editable install's version is stamped at install time and never
        moves again, so it says nothing about what the working tree currently
        holds -- do not compare it against anything.
        """
        return self.version is not None and not self.editable

    def describe(self) -> str:
        """One line, honest, for humans."""
        if self.version is None:
            return "downbeat (not installed as a package — running from source)"
        if not self.editable:
            return f"downbeat {self.version}"
        where = f" → {self.editable_path}" if self.editable_path else ""
        return (
            f"downbeat {self.version} (editable{where}; this number is from "
            f"install time, the code is whatever is checked out there now)"
        )


def detect() -> Provenance:
    """Inspect this interpreter's installed downbeat distribution.

    Never raises. Both `--version` (called eagerly while building the argument
    parser, so a raise here would break *every* downbeat command including
    `tui`) and the plugin's SessionStart hook call this; an odd install must
    answer "I don't know" rather than take them down.
    """
    try:
        dist = Distribution.from_name(_DIST_NAME)
    except Exception:
        # PackageNotFoundError is the expected one; anything else from a
        # damaged metadata dir gets the same honest shrug.
        return Provenance(version=None)

    try:
        version = dist.version
    except Exception:
        version = None

    editable, path = _editable_info(dist)
    return Provenance(version=version, editable=editable, editable_path=path)


def _editable_info(dist: Distribution) -> tuple[bool, str | None]:
    """(is_editable, working_tree_path) from PEP 610's direct_url.json.

    pip/uv record how a distribution was installed there; `dir_info.editable`
    is the editable flag. The file is absent for plain PyPI installs, which is
    itself the answer. Every failure degrades to "not editable" rather than
    raising -- see detect().
    """
    try:
        raw = dist.read_text("direct_url.json")
        if not raw:
            return False, None
        data = json.loads(raw)
        if not isinstance(data, dict):
            return False, None
        dir_info = data.get("dir_info")
        if not isinstance(dir_info, dict) or not dir_info.get("editable"):
            return False, None
        # Editable is now established. The path is best-effort from here: a
        # url we can't parse must NOT flip this back to non-editable, or a
        # fossil version would start looking trustworthy again.
        url = data.get("url")
        return True, _url_to_path(url) if isinstance(url, str) else None
    except Exception:
        return False, None


def _url_to_path(url: str) -> str | None:
    """file:///path -> /path. Also handles file://localhost/path and the
    Windows file:///C:/x form, which naive prefix-stripping mangles."""
    if not url:
        return None
    try:
        parsed = urlparse(url)
        if parsed.scheme == "file":
            return url2pathname(parsed.path) or None
    except Exception:
        pass
    return url
