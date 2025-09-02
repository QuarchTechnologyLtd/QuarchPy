from typing import Optional
from urllib.request import urlopen

from quarchpy.device.device_idn_info import IDNInfo
from quarchpy.device.device_fixture_idn_info import FixtureIDNInfo
from quarchpy.device.device_network_info import DeviceNetworkInfo

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
        self.is_update_required = False
        self.device_name = None
        self.device_info: {} = {}
        self.idn_info: Optional[IDNInfo] = idn
        self.fixture_idn_info: Optional[FixtureIDNInfo] = fixture_idn
        self.device_network_info: Optional[DeviceNetworkInfo] = device_net_info
        self.product_check_url = 'https://quarch.com/product-check/firmware-search/?field_part_number_value='

    def is_update_available(self):
        """Checks for firmware and FPGA updates by scraping a product webpage.

        This method determines the device's model number from its serial number,
        fetches the corresponding product page from a URL, and scrapes the page
        to find the latest available firmware and FPGA versions. It then compares
        these against the versions currently on the device.

        An instance attribute `self.is_update_required` is set to True if
        either the firmware or FPGA version is found to be outdated.

        Returns:
            bool: True if an update is available, False otherwise.
        """
        # Extract the base device name (model number) from the full serial number.
        self.device_name = self.get_serial_from_device()
        part_no = self.get_serial_from_device().split('-', 1)[0]
        # Fetch the product webpage content using the constructed URL.
        prod_search_page = urlopen(f'{self.product_check_url}{part_no}')

        # Read the raw byte data from the webpage and decode it into a string.
        data: str = prod_search_page.read().decode()
        # If the version marker isn't on the page, exit early as we can't proceed.
        if 'Ver:' not in data:
            return False
        # Find the start and end of the HTML block containing version information.
        start_index = data.find('Ver:')
        end_index = data.find('</div>', start_index)

        # Slice the HTML string to get only the relevant version info block.
        scraped_device_info = data[start_index:end_index]
        # Split the block into a list of individual lines for easier parsing.
        scraped_device_info_list = scraped_device_info.split('\r\n')
        # Initialize variables to hold the scraped version numbers.
        scraped_fw_version = None
        scraped_fpga_version = None
        scraped_download_link_zip = None

        # Get the current FW and FPGA versions from the connected device's info.
        # Assumes a format like "Some Text,12345".
        current_fw_version = self.idn_info.firmware.split(',')[1]
        current_fpga_version = self.idn_info.fpga_1.split(',')[1]

        # Loop through each line of the scraped text to find version details.
        for entry in scraped_device_info_list:
            # Check for the line containing the firmware version.
            if 'FW' in entry:
                # Extract the version number part of the string.
                scraped_fw_version = entry.split(',')[1]
                # Immediately compare versions and set the update flag if needed.
                if float(scraped_fw_version) > float(current_fw_version):
                    self.is_update_required = True
            # Check for the line containing the FPGA version.
            if 'FPGA' in entry:
                # Extract the version number part of the string.
                scraped_fpga_version = entry.split(',')[1]
                # Immediately compare versions and set the update flag if needed.
                if float(scraped_fpga_version) > float(current_fpga_version):
                    self.is_update_required = True
            # Extract the required link to download the zip file if required.
            if 'Link' in entry:
                scraped_download_link_zip = entry.split(':', 1)[1]

        # After checking all lines, if the update flag has been set...
        if self.is_update_required:
            # ...print a helpful message to the user and return True.
            print(f"\nThe module: {self.device_name} is not up-to-date. Current (FW: {current_fw_version}, FPGA: {current_fpga_version}) -> Latest (FW: {scraped_fw_version}, FPGA: {scraped_fpga_version})")
            print(f"Please download the update pack at the following link: {scraped_download_link_zip}")
            return True

        # If the flag was never set, no update is needed.
        return False

    def populate_device_info(self):
        self.idn_info.set_idn_info_fields_from_device_info_dict(self.device_info)
        self.fixture_idn_info.set_fix_idn_info_fields_from_device_info_dict(self.device_info)
        self.device_network_info.set_network_info_fields_from_device_info_dict(self.device_info)

    def get_serial_from_device(self):
        """

        Returns:

        """
        serialNo = self.idn_info.serial_number
        # Special case for IEC PAM
        if ('2582' in serialNo) or ('2751' in serialNo) or ('2789' in serialNo) or ('2843' in serialNo):
            response = serialNo
            device_string = response.rsplit(':', 1)[1].strip() if ':' in response else response
            return device_string
        # Special case for PPM+
        if '1944' in serialNo:
            response = self.idn_info.enclosure_serial_number
            device_string = response.split(':', 1)[1].strip() if ':' in response else response
            return device_string

        response = self.idn_info.enclosure_serial_number
        if response is None:
            response = serialNo
        device_string = response.rsplit(':', 1)[1].strip() if ':' in response else response
        return device_string
