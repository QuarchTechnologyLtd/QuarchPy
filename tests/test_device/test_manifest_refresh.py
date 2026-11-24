"""Tests for downloading a newer manifest.

A real HTTP server on localhost, so the ETag handling and the failure paths
are exercised rather than mocked. Nothing here reaches the internet, and the
cache is redirected into a temp directory so a test run cannot touch the
developer's own copy.
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from quarchpy.device import firmware_check
from quarchpy.device.firmware_check import (ALREADY_CURRENT, FAILED, UPDATED,
                                            BUNDLED_MANIFEST, Catalogue,
                                            refresh_manifest)

GOOD_MANIFEST = {
    "manifest_format": 1,
    "generated": "2026-11-23T16:22:01Z",
    "products": {
        "QTL9001": {
            "hardware": {
                "QTL9001-01": {
                    "hardware_versions": ["01"],
                    "files": [{"path": "p.qfw", "boot_type": "Firmware",
                               "firmware_version": "9.001", "sha256": "ab"}],
                }
            }
        }
    },
}

ETAG = '"test-etag-1"'


class _Handler(BaseHTTPRequestHandler):
    body = json.dumps(GOOD_MANIFEST).encode()
    status = 200
    send_etag = True

    def do_GET(self):
        if (self.status == 200 and self.send_etag
                and self.headers.get("If-None-Match") == ETAG):
            self.send_response(304)
            self.end_headers()
            return
        self.send_response(self.status)
        self.send_header("Content-Type", "application/json")
        if self.send_etag:
            self.send_header("ETag", ETAG)
        self.send_header("Content-Length", str(len(self.body)))
        self.end_headers()
        self.wfile.write(self.body)

    def log_message(self, *args):
        pass


@pytest.fixture
def server():
    httpd = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield "http://127.0.0.1:{0}/manifest.json".format(httpd.server_port)
    httpd.shutdown()
    httpd.server_close()


@pytest.fixture
def cache(isolated_manifest_cache):
    """The shared cache redirection from conftest, plus a clean server.

    Named rather than autouse so the tests read as using it deliberately;
    the redirection itself is repository-wide.
    """
    _Handler.status = 200
    _Handler.send_etag = True
    _Handler.body = json.dumps(GOOD_MANIFEST).encode()
    isolated_manifest_cache.mkdir(parents=True, exist_ok=True)
    return isolated_manifest_cache


def test_a_newer_manifest_is_downloaded_and_cached(server, cache):
    result = refresh_manifest(url=server)

    assert result.status == UPDATED
    assert (cache / "update_manifest.json").exists()
    assert (cache / "update_manifest.etag").read_text().strip() == ETAG


def test_a_second_check_transfers_nothing(server, cache):
    """The point of storing the ETag: an unchanged manifest costs one
    request and no body at all."""
    assert refresh_manifest(url=server).status == UPDATED

    result = refresh_manifest(url=server)

    assert result.status == ALREADY_CURRENT


def test_the_cached_copy_is_preferred_over_the_bundled_one(server, cache):
    refresh_manifest(url=server)

    catalogue = Catalogue.load()

    assert catalogue.path == str(cache / "update_manifest.json")
    assert catalogue.product_numbers == ["QTL9001"]


def test_no_network_falls_back_to_what_we_have(cache):
    """Expected, not exceptional: an offline machine still gets an answer."""
    result = refresh_manifest(url="http://127.0.0.1:9/manifest.json",
                              timeout=2)

    assert result.status == FAILED
    assert Catalogue.load().path == BUNDLED_MANIFEST


def test_a_404_does_not_guess_why(server, cache):
    """A private repo answers 404, exactly as a mistyped path does. Saying
    which it was would be a guess."""
    _Handler.status = 404

    result = refresh_manifest(url=server)

    assert result.status == FAILED
    assert "404" in result.message


def test_rubbish_never_replaces_a_good_cache(server, cache):
    """A captive portal or an error page returns 200 with a body that is not
    a manifest. Writing it would destroy the copy that worked."""
    assert refresh_manifest(url=server).status == UPDATED
    _Handler.body = b"<html>Sign in to continue</html>"
    _Handler.send_etag = False

    result = refresh_manifest(url=server)

    assert result.status == FAILED
    assert Catalogue.load().product_numbers == ["QTL9001"]


def test_a_manifest_layout_we_cannot_read_is_not_cached(server, cache):
    _Handler.body = json.dumps({"manifest_format": 99, "products": {}}).encode()
    _Handler.send_etag = False

    result = refresh_manifest(url=server)

    assert result.status == FAILED
    assert not (cache / "update_manifest.json").exists()


def test_a_damaged_cache_falls_back_to_the_bundled_copy(server, cache):
    refresh_manifest(url=server)
    (cache / "update_manifest.json").write_text("{ truncated")

    assert Catalogue.load().path == BUNDLED_MANIFEST


def test_an_unwritable_cache_is_reported_not_raised(server, cache,
                                                    monkeypatch):
    """Program Files is read-only for most users; the equivalent must not
    take the version check down with it."""
    def refuse(*args, **kwargs):
        raise OSError("read-only")
    monkeypatch.setattr(firmware_check.os, "makedirs", refuse)

    result = refresh_manifest(url=server)

    assert result.status == FAILED
    assert "could not save" in result.message


def test_an_unverified_catalogue_says_so(cache):
    """"Up to date" is only honest if we know the list is current."""
    catalogue, result = Catalogue.load_latest(allow_download=False)

    assert catalogue.verified is False
    assert result.status == FAILED
    assert catalogue.product_numbers, "still usable, just not confirmed"


def test_a_damaged_cache_recovers_on_the_next_check(server, cache):
    """The trap: offer the ETag because the file exists, and the server
    answers 304 for ever. Nothing is downloaded, and the broken copy is
    never replaced."""
    assert refresh_manifest(url=server).status == UPDATED
    (cache / "update_manifest.json").write_text("{ truncated")

    result = refresh_manifest(url=server)

    assert result.status == UPDATED, "must fetch, not be told 304"
    assert Catalogue.load().product_numbers == ["QTL9001"]


def test_verified_needs_the_catalogue_to_be_the_confirmed_copy(server, cache,
                                                               monkeypatch):
    """ALREADY_CURRENT says the cached copy matches what is published. It
    says nothing about a catalogue that loaded the bundled one instead.

    With the ETag now sent only for a readable cache, that mismatch should
    not arise, so this forces it: the guard is what keeps a future change to
    load() from quietly reinstating "checked and current" on a copy nothing
    confirmed.
    """
    monkeypatch.setattr(firmware_check, "MANIFEST_URL", server)
    assert refresh_manifest(url=server).status == UPDATED

    bundled = Catalogue.load(path=BUNDLED_MANIFEST)
    monkeypatch.setattr(Catalogue, "load",
                        classmethod(lambda cls, path=None: bundled))

    catalogue, result = Catalogue.load_latest()

    assert result.status == ALREADY_CURRENT
    assert catalogue.path == BUNDLED_MANIFEST
    assert catalogue.verified is False


def test_a_refreshed_cache_is_verified(server, cache, monkeypatch):
    """The other side of it: when the catalogue really is the confirmed
    copy, it must say so, or every answer reads as doubtful."""
    monkeypatch.setattr(firmware_check, "MANIFEST_URL", server)

    catalogue, result = Catalogue.load_latest()

    assert result.status == UPDATED
    assert catalogue.path == str(cache / "update_manifest.json")
    assert catalogue.verified is True


def _plantCache(cache, manifest):
    cache.mkdir(parents=True, exist_ok=True)
    (cache / "update_manifest.json").write_text(json.dumps(manifest))


def _bundled():
    return json.loads(open(BUNDLED_MANIFEST, encoding="utf-8").read())


def test_a_cache_older_than_the_bundled_copy_is_not_used(cache):
    """Install a newer quarchpy and a cache from before it must not keep
    answering with the older published versions, which is what happens
    every time a refresh cannot be made."""
    stale = _bundled()
    stale["generated"] = "2020-01-01T00:00:00Z"
    _plantCache(cache, stale)

    catalogue = Catalogue.load()

    assert catalogue.path == BUNDLED_MANIFEST
    assert catalogue.generated == _bundled()["generated"]


def test_a_cache_newer_than_the_bundled_copy_is_used(cache):
    """The normal case: a refresh has to take effect."""
    fresh = _bundled()
    fresh["generated"] = "2027-01-01T00:00:00Z"
    _plantCache(cache, fresh)

    catalogue = Catalogue.load()

    assert catalogue.path == str(cache / "update_manifest.json")
    assert catalogue.generated == "2027-01-01T00:00:00Z"


def test_an_undated_cache_loses_to_a_dated_bundled_copy(cache):
    undated = _bundled()
    undated.pop("generated", None)
    _plantCache(cache, undated)

    assert Catalogue.load().path == BUNDLED_MANIFEST
