"""Shared test setup.

Keeps the suite off the developer's own machine state. A test that reads
whatever happens to be cached locally passes or fails for reasons that have
nothing to do with the code, and does so differently on every machine.
"""

import pytest

from quarchpy.device import firmware_check


@pytest.fixture(autouse=True)
def isolated_manifest_cache(tmp_path, monkeypatch):
    """Points the manifest cache at an empty temp directory.

    Without this, anything calling Catalogue.load() reads the per-user
    cache that refresh_manifest() writes, if one exists, so the tests that
    assert on the bundled manifest's contents fail as soon as a developer has run
    a scan that refreshed it. The failure looks like a code fault and is not
    reproducible on a clean machine.

    Autouse and repository-wide on purpose: a test has to opt out rather
    than remember to opt in.
    """
    cache = tmp_path / "manifest-cache"
    monkeypatch.setattr(firmware_check, "manifest_cache_dir",
                        lambda: str(cache))
    firmware_check.forget_catalogue()
    yield cache
    firmware_check.forget_catalogue()
