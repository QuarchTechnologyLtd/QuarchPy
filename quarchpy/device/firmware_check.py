"""Checking a module's components against the versions Quarch publishes.

What was here scraped a product page on quarch.com and compared what it found
with ``float()``. It has been removed rather than patched: it read only
``fpga_1``, so a second FPGA or a fixture went unchecked; it compared both
version schemes as decimals, so an FPGA at 1.10 sorted below 1.9; it had no
timeout and caught nothing, so a slow network hung the caller; and it printed
its findings, which a GUI cannot catch and a script cannot suppress.

The replacement answers from the manifest published alongside the update files
themselves, a copy of which ships with quarchpy so that a machine with no
internet still gets an answer. Until it lands, the function below reports
nothing to do rather than guessing.
"""


def is_update_available(device_info):
    """Whether a newer firmware or FPGA version is published for this module.

    Args:
        device_info: the ``DeviceInfo`` to check.

    Returns:
        False, always, for now.

    TODO: milestone 3. Read the bundled manifest, match every component the
    module reported, and compare each by its own version scheme. Returning
    False until then tells a caller "nothing to do", which is the safe wrong
    answer: the alternative is offering an update worked out by the scraper
    this replaced, which was wrong for every FPGA.
    """
    return False
