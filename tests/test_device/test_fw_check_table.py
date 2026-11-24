"""Tests for how the firmware check reads in a table.

Formatting only: the comparison itself is tested elsewhere.
"""

import sys

import pytest

from quarchpy.device.firmware_check import (UNKNOWN, UPDATE_AVAILABLE,
                                            UP_TO_DATE, ComponentStatus,
                                            status_symbol)
from quarchpy.device.scanDevices import _componentCell

# Not "from quarchpy.device import scanDevices": the package __init__
# imports a function of that name, which shadows the submodule. This is
# the module, which is what monkeypatch needs to reach.
scanDevices = sys.modules["quarchpy.device.scanDevices"]


def _cell(current, latest, status):
    return _componentCell(ComponentStatus("firmware", "QTL1", current,
                                          latest, status))


def test_an_update_shows_both_versions():
    """So the user can see what they would be moving to."""
    assert (_cell("1.1", "1.6", UPDATE_AVAILABLE)
            == "1.1 {0} 1.6".format(status_symbol(UPDATE_AVAILABLE)))


def test_up_to_date_does_not_repeat_the_version():
    """"5.000 OK(5)" invites the question of why the two differ."""
    assert (_cell("5.000", "5", UP_TO_DATE)
            == "5.000 {0}".format(status_symbol(UP_TO_DATE)))


def test_ahead_of_the_published_version_shows_it_in_brackets():
    """A smaller number than the one they are running, which is what
    explains the "?" without needing a fourth symbol."""
    assert _cell("6.021", "6.016", UNKNOWN) == "6.021 ?(6.016)"
    assert status_symbol(UNKNOWN) == "?", "the only symbol that is ASCII"


def test_nothing_published_shows_no_brackets():
    assert _cell("5.119", None, UNKNOWN) == "5.119 ?"


def test_the_table_scans_when_it_is_not_given_devices(monkeypatch):
    """So a caller wanting the whole bench writes one call, not two."""
    scanned = []
    monkeypatch.setattr(scanDevices, "scanDevicesWithDetails",
                        lambda *a, **kw: scanned.append(True) or [])

    scanDevices.displayDeviceFWTable()

    assert scanned == [True]


def test_an_empty_list_is_not_treated_as_no_list(monkeypatch):
    """A scan that found nothing must not provoke a second scan.

    None means "not scanned yet" and an empty list means "scanned, nothing
    there"; collapsing the two is how the USB bus gets walked twice.
    """
    monkeypatch.setattr(scanDevices, "scanDevicesWithDetails",
                        lambda *a, **kw: pytest.fail("scanned again"))

    assert scanDevices.displayDeviceFWTable([]) is None
