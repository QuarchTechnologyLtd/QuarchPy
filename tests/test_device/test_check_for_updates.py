"""Tests for answering "is this module up to date?".

Modules built from what real hardware reported, checked against the manifest
bundled with quarchpy. conftest redirects the per-user cache to a temp
directory, so this really is the bundled copy and not whatever the developer
last downloaded. Nothing here reaches the network.
"""

import pytest

from quarchpy.device import firmware_check
from quarchpy.device.device_info import DeviceInfo
from quarchpy.device.firmware_check import (UNKNOWN, UPDATE_AVAILABLE,
                                            UP_TO_DATE, Catalogue,
                                            check_for_updates,
                                            is_update_available)


@pytest.fixture
def catalogue():
    return Catalogue.load()


@pytest.fixture(autouse=True)
def no_downloads(monkeypatch):
    """is_update_available() would otherwise refresh over the network."""
    firmware_check.forget_catalogue()
    monkeypatch.setattr(firmware_check, "shared_catalogue", Catalogue.load)
    yield
    firmware_check.forget_catalogue()


def _qtl2266():
    """QTL2266-02-037 exactly as it was scanned over USB."""
    device = DeviceInfo()
    device.user_level_serial_number = "QTL2266-02-037"
    device.firmware = "QTL2267-01,5.000"
    device.fpga_1 = "QTL2220,1.1"
    return device


def _qtl2312_with_fixture():
    """A PAM with its Gen4 x16 fixture fitted, as scanned over USB."""
    device = DeviceInfo()
    device.user_level_serial_number = "QTL2312-01-263"
    device.firmware = "QTL2102-01,5.124"
    device.fpga_1 = "QTL2103,1.12"
    device.fixture_name = "Gen4 PCIe x16 PAM Fixture"
    device.fixture_part_number = "QTL2347-02"
    device.fixture_fpga = "QTL2129,1.5"
    return device


def _statuses(device, catalogue):
    return {c.role: c for c in check_for_updates(device, catalogue)}


def test_a_module_needing_an_fpga_update_says_so(catalogue):
    found = _statuses(_qtl2266(), catalogue)

    assert found["fpga_1"].currentV == "1.1"
    assert found["fpga_1"].latestV == "1.6"
    assert found["fpga_1"].status == UPDATE_AVAILABLE


def test_firmware_published_as_a_bare_integer_matches(catalogue):
    """The module reports 5.000, the manifest publishes 5."""
    found = _statuses(_qtl2266(), catalogue)

    assert found["firmware"].status == UP_TO_DATE


def test_a_fixture_is_checked_against_its_own_product(catalogue):
    """The fixture's FPGA is published under QTL2347, not under the QTL2312
    it is plugged into. Looking it up under the module would offer the
    module's own FPGA image as a fixture update."""
    found = _statuses(_qtl2312_with_fixture(), catalogue)

    assert found["fixture_fpga"].latestV == "1.5"
    assert found["fixture_fpga"].status == UP_TO_DATE
    assert found["fpga_1"].latestV == "1.12", "the module's own, unchanged"


def test_a_fixture_we_cannot_identify_is_not_guessed_at(catalogue):
    """A PPM reports fixture_name "5V Mode" and a fixture_fpga that simply
    repeats fpga_1, and a network scan gives no part number at all. With
    nothing to look up, the answer is unknown, never the module's file."""
    device = DeviceInfo()
    device.user_level_serial_number = "QTL1999-06-243"
    device.fpga_1 = "QTL2899,1.15"
    device.fixture_name = "5V Mode"
    device.fixture_fpga = "QTL2899,1.15"

    found = _statuses(device, catalogue)

    assert found["fixture_fpga"].latestV is None
    assert found["fixture_fpga"].status == UNKNOWN


def test_a_module_ahead_of_the_published_version_is_unknown(catalogue):
    """QTL1999-06-243 runs 6.021 where 6.016 is published."""
    device = DeviceInfo()
    device.user_level_serial_number = "QTL1999-06-243"
    device.firmware = "QTL2898-01,6.021"

    found = _statuses(device, catalogue)

    assert found["firmware"].latestV == "6.016"
    assert found["firmware"].status == UNKNOWN


def test_hardware_versions_of_one_product_are_not_mixed(catalogue):
    """QTL3236-01 is published 5.005 and QTL3236-02 is published 5.006.
    Nothing in a .qfw file would refuse the wrong one."""
    for hardware, expected in (("01", "5.005"), ("02", "5.006")):
        device = DeviceInfo()
        device.user_level_serial_number = "QTL3236-{0}-001".format(hardware)
        device.firmware = "QTL3139,5.005"

        found = _statuses(device, catalogue)

        assert found["firmware"].latestV == expected, hardware


def test_an_unpublished_product_is_unknown_not_up_to_date(catalogue):
    device = DeviceInfo()
    device.user_level_serial_number = "QTL9999-01-001"
    device.firmware = "QTL9999,1.000"

    found = _statuses(device, catalogue)

    assert found["firmware"].latestV is None
    assert found["firmware"].status == UNKNOWN


def test_a_serial_with_no_hardware_version_matches_nothing(catalogue):
    """Falling back to "any hardware version of this product" would be how
    a QTL3236-01 gets offered the QTL3236-02 firmware."""
    device = DeviceInfo()
    device.user_level_serial_number = "QTL3236"
    device.firmware = "QTL3139,5.005"

    found = _statuses(device, catalogue)

    assert found["firmware"].status == UNKNOWN


def test_a_module_reporting_nothing_has_nothing_checked(catalogue):
    device = DeviceInfo()
    device.user_level_serial_number = "QTL2266-02-037"

    assert check_for_updates(device, catalogue) == []


def test_is_update_available_is_true_only_for_a_real_update():
    assert is_update_available(_qtl2266()) is True
    assert is_update_available(_qtl2312_with_fixture()) is False


def test_unknown_does_not_count_as_an_update():
    """A product we know nothing about must not be reported as needing one."""
    device = DeviceInfo()
    device.user_level_serial_number = "QTL9999-01-001"
    device.firmware = "QTL9999,1.000"

    assert is_update_available(device) is False
