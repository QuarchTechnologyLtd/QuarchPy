"""Tests for the scan-with-details helpers.

Pure functions only: nothing here needs a Quarch module attached.
"""

from quarchpy.device.device_info import DeviceInfo
from quarchpy.device.scanDevices import _reconcileDiscoveredDevices
from quarchpy.user_interface.user_interface import userRangeIntSelection


def _record(connection_target, serial_number):
    device = DeviceInfo()
    device.connection_target = connection_target
    device.serial_number = serial_number
    return device


def _targets(devices):
    return [device.connection_target for device in devices]


def test_a_module_seen_twice_is_listed_once():
    """A module answering on USB and TCP must not appear twice."""
    devices = [_record("USB:QTL1999-05-005", "QTL1999-05-005"),
               _record("TCP:192.168.1.5", "QTL1999-05-005")]

    _reconcileDiscoveredDevices(devices, {"USB:QTL1999-05-005": "QTL1999-05-005"})

    assert _targets(devices) == ["USB:QTL1999-05-005"]


def test_the_surviving_connection_is_written_back():
    """The record must carry a target the caller can actually open.

    The broadcast scan picks TCP, but favouriteOnly prefers USB. Without the
    write-back the caller would be handed a target that the scan had already
    discarded.
    """
    devices = [_record("TCP:192.168.1.5", "QTL1999-05-005")]

    _reconcileDiscoveredDevices(devices, {"USB:QTL1999-05-005": "QTL1999-05-005"})

    assert _targets(devices) == ["USB:QTL1999-05-005"]


def test_filtered_out_modules_are_dropped():
    """Filters apply to the returned dictionary; the details must follow."""
    devices = [_record("USB:QTL1999-05-005", "QTL1999-05-005"),
               _record("USB:QTL2312-01-001", "QTL2312-01-001")]

    _reconcileDiscoveredDevices(devices, {"USB:QTL2312-01-001": "QTL2312-01-001"})

    assert _targets(devices) == ["USB:QTL2312-01-001"]


def test_a_locked_module_adds_nothing():
    """A module held by another program answers nothing, so has no record."""
    devices = [_record("USB:QTL1999-05-005", "QTL1999-05-005")]

    _reconcileDiscoveredDevices(devices, {"USB:QTL1999-05-005": "QTL1999-05-005",
                                          "USB:???": "LOCKED MODULE"})

    assert _targets(devices) == ["USB:QTL1999-05-005"]


def test_nothing_found_means_nothing_listed():
    devices = [_record("USB:QTL1999-05-005", "QTL1999-05-005")]

    _reconcileDiscoveredDevices(devices, {})

    assert devices == []


def test_selection_accepts_indexes_lists_and_ranges():
    assert userRangeIntSelection("3", intLength=None) == ["3"]
    assert userRangeIntSelection("1,2,3", intLength=None) == ["1", "2", "3"]
    assert userRangeIntSelection("1-3", intLength=None) == ["1", "2", "3"]
    assert userRangeIntSelection("1-3,5", intLength=None) == ["1", "2", "3", "5"]


def test_a_mistyped_selection_is_rejected_not_raised():
    """A typed answer is user input; it must never produce a traceback."""
    for answer in ["1-", "-2", "x-2", "-", "1-2-3", ""]:
        assert userRangeIntSelection(answer, intLength=None) == [], answer
