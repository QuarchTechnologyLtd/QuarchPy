"""Tests for the scan-with-details helpers.

Pure functions only: nothing here needs a Quarch module attached.
"""

from quarchpy.device.device_info import DeviceInfo
from quarchpy.device.scanDevices import (_deviceName,
                                         _reconcileDiscoveredDevices)
from quarchpy.user_interface.user_interface import userRangeIntSelection


def _record(connection_target, serial_number, user_level_serial_number=None):
    device = DeviceInfo()
    device.connection_target = connection_target
    device.serial_number = serial_number
    device.user_level_serial_number = (user_level_serial_number
                                       or serial_number)
    return device


def _targets(devices):
    return [device.connection_target for device in devices]


def test_a_module_seen_twice_is_listed_once():
    """A module answering on USB and TCP must not appear twice."""
    devices = [_record("USB:QTL1999-05-005", "QTL1999-05-005"),
               _record("TCP:192.168.1.5", "QTL1999-05-005")]

    _reconcileDiscoveredDevices(devices, {"USB:QTL1999-05-005": "QTL1999-05-005"})

    assert _targets(devices) == ["USB:QTL1999-05-005"]


def test_every_connection_is_listed_when_favourites_are_off():
    """The network scan builds one record per module, not per protocol.

    A module answering on both TCP and REST is returned twice by the scan with
    favouriteOnly off, so it must be described twice. Without this the second
    connection was silently dropped, which is the opposite of what turning
    favouriteOnly off asks for.
    """
    devices = [_record("USB:QTL1999-06-243", "QTL1944-05-461", "QTL1999-06-243"),
               _record("TCP:10.0.9.154", "QTL1944-05-461", "QTL1999-06-243")]

    _reconcileDiscoveredDevices(devices, {"USB:QTL1999-06-243": "QTL1999-06-243",
                                          "REST:10.0.9.154": "QTL1999-06-243",
                                          "TCP:10.0.9.154": "QTL1999-06-243"})

    assert _targets(devices) == ["USB:QTL1999-06-243",
                                 "REST:10.0.9.154",
                                 "TCP:10.0.9.154"]


def test_a_copied_record_is_independent():
    """Editing one connection's record must not alter another's."""
    devices = [_record("TCP:10.0.9.154", "QTL1944-05-461", "QTL1999-06-243")]

    _reconcileDiscoveredDevices(devices, {"REST:10.0.9.154": "QTL1999-06-243",
                                          "TCP:10.0.9.154": "QTL1999-06-243"})

    assert len(devices) == 2
    assert devices[0] is not devices[1]
    assert devices[0].network is not devices[1].network


def test_a_copy_is_taken_from_the_same_address():
    """A TCP row should say what the module said over the network.

    Both the USB record and the network record describe the same module, but
    only one of them was read over the connection being described.
    """
    usb = _record("USB:QTL1999-06-243", "QTL1944-05-461", "QTL1999-06-243")
    usb.name = "HD Plus Programmable Power Module"
    network = _record("TCP:10.0.9.154", "QTL1944-05-461", "QTL1999-06-243")
    network.name = "1999-06-243"
    devices = [usb, network]

    _reconcileDiscoveredDevices(devices, {"USB:QTL1999-06-243": "QTL1999-06-243",
                                          "REST:10.0.9.154": "QTL1999-06-243",
                                          "TCP:10.0.9.154": "QTL1999-06-243"})

    byTarget = {device.connection_target: device for device in devices}
    assert byTarget["USB:QTL1999-06-243"].name == "HD Plus Programmable Power Module"
    assert byTarget["REST:10.0.9.154"].name == "1999-06-243"
    assert byTarget["TCP:10.0.9.154"].name == "1999-06-243"


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


def test_a_module_in_an_enclosure_is_matched_on_the_number_on_the_box():
    """The scan is keyed on the enclosure number, not the component's.

    An HD Plus reports serial QTL1944-05-461 from inside enclosure
    QTL1999-06-243, and it is the enclosure number the scan uses. Matching on
    the component serial found nothing at all for these modules.
    """
    devices = [_record("USB:QTL1999-06-243", "QTL1944-05-461",
                       "QTL1999-06-243")]

    _reconcileDiscoveredDevices(devices, {"USB:QTL1999-06-243": "QTL1999-06-243"})

    assert _targets(devices) == ["USB:QTL1999-06-243"]
    assert devices[0].serial_number == "QTL1944-05-461"


def test_an_enclosure_is_listed_under_the_number_on_the_box():
    """The customer has never seen the component's number."""
    device = _record("USB:QTL1999-06-243", "QTL1944-05-461", "QTL1999-06-243")

    assert _deviceName(device) == "QTL1999-06-243"


def test_a_multi_module_unit_is_listed_per_port():
    """A QTL1995 carries the port, so each one is told apart."""
    device = _record("TCP:10.0.9.20", "QTL1995-01-002", "QTL1995-01-002-003")

    assert _deviceName(device) == "QTL1995-01-002-003"


def test_selection_accepts_indexes_lists_and_ranges():
    assert userRangeIntSelection("3", intLength=None) == ["3"]
    assert userRangeIntSelection("1,2,3", intLength=None) == ["1", "2", "3"]
    assert userRangeIntSelection("1-3", intLength=None) == ["1", "2", "3"]
    assert userRangeIntSelection("1-3,5", intLength=None) == ["1", "2", "3", "5"]


def test_a_mistyped_selection_is_rejected_not_raised():
    """A typed answer is user input; it must never produce a traceback."""
    for answer in ["1-", "-2", "x-2", "-", "1-2-3", ""]:
        assert userRangeIntSelection(answer, intLength=None) == [], answer
