import pathlib
import tomllib

import downbeat


def test_version_attribute_tracks_the_release_bump():
    pyproject = tomllib.loads(
        (pathlib.Path(__file__).parent.parent / "pyproject.toml").read_text()
    )
    assert downbeat.__version__ == pyproject["project"]["version"]
