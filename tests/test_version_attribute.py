from importlib.metadata import version

import downbeat


def test_version_attribute_matches_metadata():
    assert downbeat.__version__ == version("downbeat")
