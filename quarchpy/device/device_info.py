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
UNSET_VALUES = ("", "not set", "qtl0000", "qtlffff")

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
}


def is_set(value) -> bool:
    """False for a field a module left empty, however it chose to say so."""
    return bool(value) and str(value).strip().lower() not in UNSET_VALUES


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

        #: Addresses and ports. Empty for a module found over USB.
        self.network: DeviceNetworkInfo = \
            network if network is not None else DeviceNetworkInfo()

        #: The decoded announce packet, when the module was found on the
        #: network. Empty for USB.
        self.device_info: dict = {}

        # Set by firmware_check, which is the only thing that uses them.
        self.is_update_required = False
        self.device_name = None

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
        """Deprecated. Use ``quarchpy.device.firmware_check``."""
        from quarchpy.device.firmware_check import is_update_available
        return is_update_available(self)

    def get_serial_from_device(self):
        """Deprecated. Use ``quarchpy.device.firmware_check``."""
        from quarchpy.device.firmware_check import get_serial_from_device
        return get_serial_from_device(self)
