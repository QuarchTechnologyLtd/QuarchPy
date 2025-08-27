from typing import Optional
from urllib.request import urlopen

from quarchpy.device import IDNInfo, FixtureIDNInfo, DeviceNetworkInfo

# A mapping of known codes to their corresponding dictionary keys.
# This handles all fields that are simple string values.
# Please refer to the below map for the device_info dict defined in this class.
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

class DiscoveredDevice:
    def __init__(self, idn: Optional[IDNInfo], fixture_idn: Optional[FixtureIDNInfo], device_net_info: Optional[DeviceNetworkInfo]):
        """

        Args:
            idn:
            fixture_idn:
            device_net_info:
        """
        self.device_info: {} = {}
        self.idn_info: Optional[IDNInfo] = idn
        self.fixture_idn_info: Optional[FixtureIDNInfo] = fixture_idn
        self.device_network_info: Optional[DeviceNetworkInfo] = device_net_info
        self.product_check_url = 'https://quarch.com/product-check/firmware-search/?field_part_number_value='

    def is_update_available(self):
        """

        Returns:

        """
        device_name: str = self.idn_info.serial_number.split('-')[0]
        prod_search_page = urlopen(f'{self.product_check_url}{device_name}')

        return False

    def populate_device_info(self):
        self.idn_info.set_idn_info_fields_from_device_info_dict(self.device_info)
        self.fixture_idn_info.set_fix_idn_info_fields_from_device_info_dict(self.device_info)
        self.device_network_info.set_network_info_fields_from_device_info_dict(self.device_info)