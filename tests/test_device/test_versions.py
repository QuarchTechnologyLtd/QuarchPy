"""Tests for reading a module's components and comparing their versions.

Pure functions: nothing here needs a module attached. The reported strings
are copied from real modules.
"""

from quarchpy.device.device_info import DeviceInfo, split_version
from quarchpy.device.firmware_check import (UNKNOWN, UPDATE_AVAILABLE,
                                            UP_TO_DATE, compare_versions,
                                            status_for, status_symbol)


def test_a_reported_component_splits_into_part_and_version():
    assert split_version("QTL2102-01,5.124") == ("QTL2102-01", "5.124")
    assert split_version("QTL2103,1.12") == ("QTL2103", "1.12")


def test_a_component_a_module_did_not_report_splits_to_nothing():
    for value in (None, "", "   ", "Not Set", "QTL0000", "QTLFFFF"):
        assert split_version(value) == (None, None), value


def test_a_component_with_no_comma_has_no_version():
    """Better than guessing which half of the string a lone value is."""
    assert split_version("QTL2103") == ("QTL2103", None)


def test_every_reported_component_is_listed():
    """A QTL2312 PAM with its fixture fitted, as scanned over USB."""
    device = DeviceInfo()
    device.firmware = "QTL2102-01,5.124"
    device.fpga_1 = "QTL2103,1.12"
    device.fixture_name = "Gen4 PCIe x16 PAM Fixture"
    device.fixture_fpga = "QTL2129,1.5"

    assert device.components == [
        ("firmware", "QTL2102-01", "5.124"),
        ("fpga_1", "QTL2103", "1.12"),
        ("fixture_fpga", "QTL2129", "1.5"),
    ]


def test_a_module_with_several_fpgas_keeps_them_apart():
    """Reporting both as "fpga" would make them indistinguishable."""
    device = DeviceInfo()
    device.fpga_1 = "QTL1234,1.1"
    device.fpga_2 = "QTL5678,2.2"

    assert [field for field, _, _ in device.components] == ["fpga_1", "fpga_2"]


def test_an_empty_fixture_bay_adds_no_component():
    device = DeviceInfo()
    device.firmware = "QTL2102-01,5.124"
    device.fixture_name = "Not Found"

    assert [field for field, _, _ in device.components] == ["firmware"]


def test_the_bootloader_is_not_a_component():
    """Nothing publishes one, so listing it would put a permanent unknown
    against every module."""
    device = DeviceInfo()
    device.firmware = "QTL2102-01,5.124"
    device.bootloader = "QTL2102-01,5.123"

    assert [field for field, _, _ in device.components] == ["firmware"]


def test_an_fpga_at_1_10_is_newer_than_1_9():
    """The bug in the code this replaced: float("1.10") < float("1.9")."""
    assert compare_versions("1.10", "1.9") == 1
    assert compare_versions("1.9", "1.10") == -1


def test_firmware_minors_compare_as_whole_numbers():
    assert compare_versions("6.016", "6.020") == -1
    assert compare_versions("5.006", "5.005") == 1
    assert compare_versions("5.124", "5.124") == 0


def test_a_version_with_no_minor_reads_as_zero():
    """QTL2266 firmware is published as "5"."""
    assert compare_versions("5", "5.000") == 0
    assert compare_versions("5", "5.001") == -1


def test_a_version_we_cannot_read_compares_to_nothing():
    """None rather than a guess: this is reported to the user as fact."""
    for value in (None, "", "   ", "unknown", "1.2.3", "v1.2"):
        assert compare_versions(value, "1.0") is None, value
        assert compare_versions("1.0", value) is None, value


def test_an_older_version_offers_an_update():
    assert status_for("6.016", "6.020") == UPDATE_AVAILABLE


def test_a_matching_version_is_up_to_date():
    assert status_for("1.12", "1.12") == UP_TO_DATE


def test_a_version_ahead_of_the_published_one_is_not_a_tick():
    """A pre-release build. Showing a tick would claim we checked it."""
    assert status_for("6.021", "6.016") == UNKNOWN


def test_nothing_published_is_unknown_not_up_to_date():
    """Most products have no manifest entry yet. Reading that as "up to
    date" would be the one wrong answer that is never noticed."""
    assert status_for("5.124", None) == UNKNOWN


def test_a_symbol_the_console_cannot_print_falls_back(monkeypatch):
    """A Windows console is usually cp1252, which has no tick and no up
    arrow. Printing one raises part way through the table."""
    class Cp1252:
        encoding = "cp1252"

    assert status_symbol(UP_TO_DATE, stream=Cp1252()) == "OK"
    assert status_symbol(UPDATE_AVAILABLE, stream=Cp1252()) == "NEW"

    class Utf8:
        encoding = "utf-8"

    assert status_symbol(UP_TO_DATE, stream=Utf8()) == "\u2713"
    assert status_symbol(UPDATE_AVAILABLE, stream=Utf8()) == "\u2191"


def test_a_stream_that_will_not_say_its_encoding_still_works():
    class Silent:
        encoding = None

    assert status_symbol(UP_TO_DATE, stream=Silent()) == "OK"
