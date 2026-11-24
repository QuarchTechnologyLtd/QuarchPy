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


@pytest.fixture(autouse=True)
def cache(tmp_path, monkeypatch):
    """Point the cache at a temp directory for every test in this file."""
    monkeypatch.setattr(firmware_check, "manifest_cache_dir",
                        lambda: str(tmp_path))
    _Handler.status = 200
    _Handler.send_etag = True
    _Handler.body = json.dumps(GOOD_MANIFEST).encode()
    return tmp_path


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


def test_a_verified_catalogue_is_marked(server, cache, monkeypatch):
    monkeypatch.setattr(firmware_check, "MANIFEST_URL", server)

    catalogue, result = Catalogue.load_latest()

    assert result.status == UPDATED
    assert catalogue.verified is True
