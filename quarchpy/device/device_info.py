"""What a scan found out about one module.

A single record. Identity, versions and fixture details are fields on this
class rather than on separate sub-objects, because they describe one thing and
were only ever reached through it.

Network addressing stays in its own record, because those seven fields are
always empty for a module found over USB, and grouping them says so at a
glance.

Replaces ``IDNInfo``, ``FixtureIDNInfo`` and the old ``DiscoveredDevice``
wrapper. ``idn_info`` and ``fixture_idn_info`` remain as properties that
return the object itself, so existing code reading
``device.idn_info.firmware`` keeps working.
"""

import re
from typing import List, Optional

from quarchpy.device.device_network_info import DeviceNetworkInfo

# Codes used by the locate (announce) packet, mapped to the key each one
# produces in ``device_info``. decode_locate_packet() builds that dictionary;
# populate_from_packet() reads it, and the names must agree.
CODE_MAP = {
    0x80: 'firmware',
    0x81: 'bootloader',
    0x82: 'fpga',
    0x83: 'serial_number',
    0x84: 'rest_port',
    0x85: 'tcp_port',
    0x86: 'enclosure_serial_number',
    0x87: 'enclosure_position',
    0x88: 'enclosure_alias',
    0x89: 'product_string',
    0x8a: 'telnet_port',
    0x8c: 'fixture_name',
    0x8d: 'fixture_fpga',
    0x02: 'mac_address',
    0x03: 'mac_type',
    0x04: 'host_name',
    0x05: 'ipv4_address'
    # There are also some legacy fields with no code:
    # legacy_name, legacy_mac_string
}

# Values a module sends when a field is not set, rather than sending nothing.
UNSET_VALUES = ("", "not set", "not found", "qtl0000", "qtlffff")

# Keys found in an *IDN? response, and the field each one fills.
_IDN_KEY_MAP = {
    "Family": "family",
    "Name": "name",
    "Part#": "part_number",
    "FW": "firmware",
    "Bootloader": "bootloader",
    "FPGA 1": "fpga_1",
    "FPGA 2": "fpga_2",
    "FPGA 3": "fpga_3",
    "FPGA 4": "fpga_4",
    "Serial#": "serial_number",
    "Enclosure#": "enclosure_serial_number",
    "Position#": "enclosure_position",
    "Alias": "alias",
    # Present over USB only. The announce packet carries the same thing as
    # TLV 0x8c, and an empty bay reports "Not Found", which UNSET_VALUES
    # above already covers.
    "Fixture": "fixture_name",
}


def is_set(value) -> bool:
    """False for a field a module left empty, however it chose to say so."""
    return bool(value) and str(value).strip().lower() not in UNSET_VALUES


def split_version(reported):
    """Splits a reported version into its part number and its version.

    A module reports each component as "part number,version", for example
    "QTL2102-01,5.124". The part number is a label: it is not what the
    published file is named after, and often differs from both the product
    and the file. Matching is done on product, hardware version and boot
    type, not on this.

    Args:
        reported: the field as the module gave it, or None.

    Returns:
        (part_number, version), either of which may be None.
    """
    if not is_set(reported):
        return (None, None)

    part_number, _, version = str(reported).strip().partition(",")
    return (part_number.strip() or None, version.strip() or None)


def split_serial(serial_number):
    """Splits a serial into the product and hardware version it names.

    "QTL1999-06-243" is product QTL1999, hardware version 06. A fixture's
    part number, "QTL2347-02", gives the same two. Both are needed to find
    what is published: hardware versions of one product can be given
    different firmware, and nothing inside a .qfw file would refuse the
    wrong one.

    Args:
        serial_number: a user-level serial or a part number, or None.

    Returns:
        (product_number, hardware_version), or (None, None) if it does not
        read as either. Never a product with no hardware version: that would
        match every hardware version of that product.
    """
    if not is_set(serial_number):
        return (None, None)

    match = re.match(r"\s*(QTL\d+)-(\d+)", str(serial_number).strip(),
                     re.IGNORECASE)
    if not match:
        return (None, None)
    return (match.group(1).upper(), match.group(2))


#: The fields that name something which can be updated, in the order they
#: should be shown. The bootloader is left out: nothing publishes one, so
#: including it would put a permanent "unknown" against every module.
COMPONENT_FIELDS = ("firmware", "fpga_1", "fpga_2", "fpga_3", "fpga_4",
                    "fixture_fpga")


class DeviceInfo:
    """A module found by a scan, and what it reported about itself.

    This is a record. It holds information and does not act on it: comparing
    against published firmware versions lives in ``firmware_check``, so that
    this class can be constructed, passed around and read without making
    network requests.
    """

    def __init__(self, network: Optional[DeviceNetworkInfo] = None):
        #: Connection target this module was found on, such as
        #: "USB:QTL2266-02-037" or "TCP:192.168.1.50". Pass it to
        #: getQuarchDevice() to open a connection to this module.
        self.connection_target: Optional[str] = None

        # Identity
        self.family: Optional[str] = None
        self.name: Optional[str] = None
        self.part_number: Optional[str] = None
        self.serial_number: Optional[str] = None
        self.alias: Optional[str] = None
        self.enclosure_serial_number: Optional[str] = None
        self.enclosure_position: Optional[str] = None

        # The serial number printed on the box, which is the only one the
        # customer ever sees. For a module inside an enclosure that is the
        # enclosure's number (QTL1999), not the component's (QTL1944), and for
        # a unit holding several modules it is the enclosure number plus the
        # port (QTL1995-01-002-003). Often it is simply the serial number
        # again, but it is always set: every scan path fills it in from the
        # very same value the scan uses as its own identifier, so the two
        # always agree. See get_user_level_serial_number() in scanDevices.py.
        self.user_level_serial_number: Optional[str] = None

        # Versions. Each is reported as "part number,version", for example
        # "QTL2267-01,5.000".
        self.firmware: Optional[str] = None
        self.fpga_1: Optional[str] = None
        self.fpga_2: Optional[str] = None
        self.fpga_3: Optional[str] = None
        self.fpga_4: Optional[str] = None
        self.bootloader: Optional[str] = None
        self.bootloader_mode: Optional[bool] = None

        # Attached fixture, if there is one.
        self.fixture_name: Optional[str] = None
        self.fixture_fpga: Optional[str] = None

        # The fixture's own part number, for example "QTL2347-02". A fixture
        # is a product in its own right and its FPGA is published under its
        # own number, so without this there is no way to look one up. Only a
        # "fix idn?" reply carries it, so it is None for a module found over
        # the network, where the announce packet gives only name and FPGA.
        self.fixture_part_number: Optional[str] = None

        #: Addresses and ports. Empty for a module found over USB.
        self.network: DeviceNetworkInfo = \
            network if network is not None else DeviceNetworkInfo()

        #: The decoded announce packet, when the module was found on the
        #: network. Empty for USB.
        self.device_info: dict = {}

    # -- reading -----------------------------------------------------------

    @property
    def fpgas(self) -> List[str]:
        """Every FPGA this module reported, in order.

        A module may carry up to four. Reading ``fpga_1`` alone is how an
        array controller's second FPGA goes unnoticed.
        """
        return [value for value in
                (self.fpga_1, self.fpga_2, self.fpga_3, self.fpga_4)
                if is_set(value)]

    @property
    def components(self) -> List[tuple]:
        """Everything this module reported that could be updated.

        Each entry is (field, part_number, version), where field is the name
        it was reported under: "firmware", "fpga_1" and so on. Keeping the
        field rather than a general "fpga" means a module with two of them
        can still be told apart.

        A component the module did not report is left out rather than
        returned with an empty version. For a module found over USB with no
        fixture fitted, and for every module found over the network, that is
        how "not reported" and "nothing there" both read.
        """
        found = []
        for field in COMPONENT_FIELDS:
            part_number, version = split_version(getattr(self, field, None))
            if version is None:
                continue
            found.append((field, part_number, version))
        return found

    @property
    def has_fixture(self) -> bool:
        return is_set(self.fixture_name) or is_set(self.fixture_fpga)

    def __repr__(self) -> str:
        return "DeviceInfo({0!r}, {1!r})".format(
            self.serial_number or self.part_number, self.connection_target)

    # -- populating --------------------------------------------------------

    def parse_idn_response(self, idn_response: str) -> bool:
        """Fill this record from the text of an ``*IDN?`` reply.

        Args:
            idn_response: the reply, one ``Key: value`` per line.

        Returns:
            True if at least one line was understood.
        """
        if not idn_response:
            return False

        was_successful = False

        for line in idn_response.strip().split('\n'):
            line = line.strip()

            # A module sitting in its bootloader says so on a line of its own.
            if line == "[Bootloader]":
                self.bootloader_mode = True
                was_successful = True
                continue

            if ':' not in line:
                continue

            # Split on the first colon only; a value may contain others.
            key, value = line.split(':', 1)
            key = key.strip()
            value = value.strip()

            # "Processor" is how some products report their firmware.
            if key == "Processor":
                self.firmware = value
                was_successful = True
                continue

            attribute = _IDN_KEY_MAP.get(key)
            if attribute:
                setattr(self, attribute, value)
                was_successful = True

        return was_successful

    def parse_fixture_idn_response(self, idn_response: str) -> bool:
        """Fill the fixture fields from the text of a ``fix idn?`` reply.

        Deliberately not parse_idn_response(). That reply describes the
        fixture, so its Name, Part# and Serial# lines would overwrite the
        module's own. Only the two fields the announce packet also carries
        are taken, so a module reads the same whichever way it was found.

        Args:
            idn_response: the reply, one ``Key: value`` per line. A module
                with no fixture answers ``FAIL: 0x66 ...``, which sets
                nothing and returns False.

        Returns:
            True if a fixture field was filled.
        """
        if not idn_response:
            return False

        was_successful = False

        for line in idn_response.strip().split('\n'):
            if ':' not in line:
                continue

            key, value = line.split(':', 1)
            key = key.strip()
            value = value.strip()

            if key == "Name":
                self.fixture_name = value
                was_successful = True
            elif key == "Part#":
                self.fixture_part_number = value
                was_successful = True
            elif key == "FPGA 1":
                self.fixture_fpga = value
                was_successful = True

        return was_successful

    def populate_from_packet(self, device_info: Optional[dict] = None) -> None:
        """Fill this record from a decoded locate (announce) packet.

        The keys read here must match CODE_MAP, which is what
        decode_locate_packet() produces. 'firmware' and 'fpga' were previously
        read as 'firmware_version' and 'fpga_1' - neither of which the packet
        ever contains - so every network-discovered module reported no
        firmware and no FPGA.
        """
        if device_info is not None:
            self.device_info = device_info
        source = self.device_info or {}

        self.name = source.get('legacy_name')
        self.firmware = source.get('firmware')
        self.fpga_1 = source.get('fpga')
        self.bootloader = source.get('bootloader')
        self.serial_number = source.get('serial_number')
        self.alias = source.get('enclosure_alias')
        self.enclosure_serial_number = source.get('enclosure_serial_number')
        self.enclosure_position = source.get('enclosure_position')

        self.fixture_name = source.get('fixture_name')
        self.fixture_fpga = source.get('fixture_fpga')

        self.network.set_network_info_fields_from_device_info_dict(source)

    # -- compatibility -----------------------------------------------------
    #
    # These let code written against the previous three-object layout keep
    # working: device.idn_info.firmware still resolves, because idn_info is
    # this same object.

    @property
    def idn_info(self) -> "DeviceInfo":
        """Deprecated. The fields are on this object; read them directly."""
        return self

    @property
    def fixture_idn_info(self) -> "DeviceInfo":
        """Deprecated. The fields are on this object; read them directly."""
        return self

    @property
    def device_network_info(self) -> DeviceNetworkInfo:
        """Deprecated. Use ``network``."""
        return self.network

    def populate_device_info(self) -> None:
        """Deprecated. Use ``populate_from_packet``."""
        self.populate_from_packet()

    def set_idn_info_fields_from_device_info_dict(self, device_info: dict) -> None:
        """Deprecated. Use ``populate_from_packet``."""
        self.populate_from_packet(device_info)

    def is_update_available(self):
        """Whether a newer version is published for this module.

        Kept so existing callers keep working. The check itself lives in
        ``quarchpy.device.firmware_check``.
        """
        from quarchpy.device.firmware_check import is_update_available
        return is_update_available(self)
