"""Tests for how the firmware check reads in a table.

Formatting only: the comparison itself is tested elsewhere.
"""

from quarchpy.device.firmware_check import (UNKNOWN, UPDATE_AVAILABLE,
                                            UP_TO_DATE, ComponentStatus,
                                            status_symbol)
from quarchpy.device.scanDevices import _componentCell


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
