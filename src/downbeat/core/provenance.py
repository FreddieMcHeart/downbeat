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
from importlib.metadata import Distribution, PackageNotFoundError

_DIST_NAME = "downbeat"


@dataclass(frozen=True)
class Provenance:
    """How the running downbeat got here.

    version:       what the install metadata claims. None if downbeat isn't
                   installed as a distribution at all (e.g. run straight from
                   a source checkout via `python -m downbeat.cli`).
    editable_path: the working tree the code is really read from, if this is
                   an editable install. None for a normal release install.
    """

    version: str | None
    editable_path: str | None

    @property
    def is_editable(self) -> bool:
        return self.editable_path is not None

    @property
    def version_is_trustworthy(self) -> bool:
        """True only when `version` actually describes the running code.

        An editable install's version is stamped at install time and never
        moves again, so it says nothing about what the working tree currently
        holds -- do not compare it against anything.
        """
        return self.version is not None and not self.is_editable

    def describe(self) -> str:
        """One line, honest, for humans."""
        if self.version is None:
            return "downbeat (not installed as a package — running from source)"
        if self.is_editable:
            return (
                f"downbeat {self.version} (editable → {self.editable_path}; "
                f"this number is from install time, the code is whatever is "
                f"checked out there now)"
            )
        return f"downbeat {self.version}"


def detect() -> Provenance:
    """Inspect this interpreter's installed downbeat distribution.

    Never raises: a missing/odd install answers with the honest 'I don't know'
    rather than exploding a --version call or a hook.
    """
    try:
        dist = Distribution.from_name(_DIST_NAME)
    except PackageNotFoundError:
        return Provenance(version=None, editable_path=None)

    try:
        version = dist.version
    except Exception:
        version = None

    return Provenance(version=version, editable_path=_editable_path(dist))


def _editable_path(dist: Distribution) -> str | None:
    """The working tree an editable install points at, or None.

    PEP 610 records how a distribution was installed in direct_url.json;
    `dir_info.editable` is the flag pip/uv set for editable installs. The file
    is absent for plain PyPI installs, which is itself the answer.
    """
    try:
        raw = dist.read_text("direct_url.json")
    except Exception:
        return None
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except ValueError:
        return None
    if not data.get("dir_info", {}).get("editable"):
        return None
    url = data.get("url", "")
    prefix = "file://"
    return url[len(prefix):] if url.startswith(prefix) else url or None
