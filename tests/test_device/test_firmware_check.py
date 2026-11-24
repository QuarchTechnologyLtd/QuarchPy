"""Tests for reading the published update manifest.

Nothing here needs a Quarch module attached or a network connection: the
manifest that ships with quarchpy is the thing under test.
"""

import json
from datetime import timedelta

import pytest

from quarchpy.device.firmware_check import (BUNDLED_MANIFEST, Catalogue,
                                            parse_generated)


def test_the_bundled_manifest_loads():
    """It ships inside the package, so this is also a packaging test."""
    catalogue = Catalogue.load()

    assert catalogue.path == BUNDLED_MANIFEST
    assert catalogue.product_numbers


def test_versions_keep_the_text_they_were_published_as():
    """The guard against json.load turning "5.000" into 5.0.

    FirmwareVersion is a JSON number. Read without parse_float=str, firmware
    loses its trailing zeros and an FPGA at 1.10 becomes 1.1, which sorts
    below 1.9. Both are silent and both are wrong.
    """
    catalogue = Catalogue.load()

    versions = [f.version for f in catalogue.files_for("QTL3351", "01")]

    assert "5.000" in versions


def test_every_published_version_is_text():
    """parse_float=str does not see a bare integer: QTL2266 firmware is
    published as 5, which arrives as int 5 unless it is coerced. One mixed
    type is enough to break a comparison."""
    catalogue = Catalogue.load()

    checked = 0
    for product_number in catalogue.product_numbers:
        for hardware_version in catalogue.hardware_versions(product_number):
            for published in catalogue.files_for(product_number,
                                                 hardware_version):
                assert isinstance(published.version, str), published
                checked += 1

    assert checked, "the manifest published nothing to check"


def test_a_version_with_no_minor_is_still_text():
    catalogue = Catalogue.load()

    firmware = [f for f in catalogue.files_for("QTL2266", "02")
                if f.boot_type == "Firmware"][0]

    assert firmware.version == "5"


def test_a_product_is_found_by_its_hardware_version():
    """hardware_versions is written out in full, so "06" is a lookup."""
    catalogue = Catalogue.load()

    found = catalogue.files_for("QTL1999", "06")

    assert found
    assert {f.boot_type for f in found} == {"Firmware", "FPGA"}


def test_a_hardware_version_outside_the_list_finds_nothing():
    catalogue = Catalogue.load()

    assert catalogue.files_for("QTL1999", "99") == []


def test_an_unpublished_product_finds_nothing_rather_than_raising():
    """"Not published here" has to be answerable, because most products
    are not in the manifest yet."""
    catalogue = Catalogue.load()

    assert catalogue.files_for("QTL9999", "01") == []
    assert catalogue.files_for("QTL9999") == []


def test_a_file_without_part_numbers_still_loads():
    """The published manifest carries no firmware_part_number or
    FirmwareTarget. Matching is on product, hardware version and boot type,
    so these are optional labels and must not be required to read a file."""
    catalogue = Catalogue.load()

    fpga = [f for f in catalogue.files_for("QTL2347", "02")
            if f.boot_type == "FPGA"][0]

    assert fpga.version == "1.5"
    assert fpga.sha256
    assert fpga.part_number is None
    assert fpga.targets == ()


def test_a_manifest_layout_we_do_not_read_is_refused(tmp_path):
    """Reading a newer layout hopefully would mean comparing versions we may
    have misunderstood. Refusing says so out loud."""
    manifest = tmp_path / "update_manifest.json"
    manifest.write_text(json.dumps({"manifest_format": 99, "products": {}}))

    with pytest.raises(ValueError) as refused:
        Catalogue.load(path=str(manifest))

    assert "99" in str(refused.value)





def test_the_build_time_is_read_without_fromisoformat():
    """datetime.fromisoformat() only accepts the trailing Z from Python 3.11.
    quarchpy supports 3.7, so this is parsed with strptime."""
    stamp = parse_generated("2026-11-23T15:01:09Z")

    assert stamp is not None
    assert (stamp.year, stamp.month, stamp.day) == (2026, 11, 23)
    assert (stamp.hour, stamp.minute, stamp.second) == (15, 1, 9)
    assert stamp.utcoffset() == timedelta(0), "must be aware, and UTC"


def test_a_build_time_we_cannot_read_is_treated_as_absent():
    """Better to tell the user the age is unknown than to show a wrong date,
    or to raise in the middle of a version check."""
    for value in (None, "", "   ", "not a date", "2026-11-23 15:01:09",
                  "2026-11-23T15:01:09+00:00", 20261123):
        assert parse_generated(value) is None, value


def test_a_manifest_without_a_build_time_still_loads(tmp_path):
    """The field was added after the first manifests were published."""
    manifest = tmp_path / "update_manifest.json"
    manifest.write_text(json.dumps({"manifest_format": 1, "products": {}}))

    catalogue = Catalogue.load(path=str(manifest))

    assert catalogue.generated is None
    assert catalogue.generated_utc is None


def test_a_manifest_build_time_is_kept_and_parsed(tmp_path):
    manifest = tmp_path / "update_manifest.json"
    manifest.write_text(json.dumps({"manifest_format": 1,
                                    "generated": "2026-11-23T15:01:09Z",
                                    "products": {}}))

    catalogue = Catalogue.load(path=str(manifest))

    assert catalogue.generated == "2026-11-23T15:01:09Z"
    assert catalogue.generated_utc.year == 2026
