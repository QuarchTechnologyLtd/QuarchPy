"""Tests for the scan-with-details helpers.

Pure functions only: nothing here needs a Quarch module attached.
"""

from quarchpy.device.device_info import DeviceInfo
from quarchpy.device.scanDevices import (_deviceName, _fixtureName,
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


# Captured from a QTL2312 PAM over USB. The fixture lines are the only
# difference between the two replies.

_IDN_WITH_FIXTURE = """Family:     Power Analysis Modules
Name:       Power Analysis Module
Part#:      QTL2312-01
Processor:  QTL2102-01,5.124
Bootloader: QTL2102-01,5.123
FPGA 1:     QTL2103,1.12
Serial#:    QTL2098-02-269
Enclosure#: QTL2312-01-263
Fixture:    QTL2347-02 Gen4 PCIe x16 PAM Fixture"""

_IDN_NO_FIXTURE = _IDN_WITH_FIXTURE.replace(
    "QTL2347-02 Gen4 PCIe x16 PAM Fixture", "Not Found")

_FIX_IDN = """Name:        Gen4 PCIe x16 PAM Fixture
Part#:       QTL2347-02
Serial#:     QTL2347-02-054
FPGA 1:      QTL2129,1.5
Internal#:   QTL2347-02-054"""


def test_a_fitted_fixture_is_seen_over_usb():
    """*IDN? names the fixture, so fix idn? is worth sending."""
    device = DeviceInfo()
    device.parse_idn_response(_IDN_WITH_FIXTURE)

    assert device.has_fixture is True


def test_an_empty_bay_is_not_a_fixture():
    """A module with no fixture says so in words, not by staying quiet."""
    device = DeviceInfo()
    device.parse_idn_response(_IDN_NO_FIXTURE)

    assert device.has_fixture is False
    assert _fixtureName(device) == "-"


def test_the_fixture_reads_the_same_over_usb_as_on_the_network():
    """fix idn? Name matches the announce packet, where the *IDN? line
    prefixes the part number and would not."""
    device = DeviceInfo()
    device.parse_idn_response(_IDN_WITH_FIXTURE)
    device.parse_fixture_idn_response(_FIX_IDN)

    assert device.fixture_name == "Gen4 PCIe x16 PAM Fixture"
    assert device.fixture_fpga == "QTL2129,1.5"


def test_the_fixture_reply_does_not_overwrite_the_module():
    """fix idn? carries its own Name, Part# and Serial#. Parsing it as a
    module reply would quietly replace the module's own identity."""
    device = DeviceInfo()
    device.parse_idn_response(_IDN_WITH_FIXTURE)
    device.parse_fixture_idn_response(_FIX_IDN)

    assert device.part_number == "QTL2312-01"
    assert device.serial_number == "QTL2098-02-269"
    assert device.name == "Power Analysis Module"
    assert device.fpga_1 == "QTL2103,1.12"


def test_a_fixture_that_will_not_answer_sets_nothing():
    """An empty bay answers with a fault, not a reply."""
    device = DeviceInfo()

    assert device.parse_fixture_idn_response(
        "FAIL: 0x66 -Fixture is not present or not responding") is False
    assert device.fixture_name is None
    assert device.fixture_fpga is None
