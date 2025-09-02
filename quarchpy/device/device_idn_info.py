from typing import Optional


class IDNInfo:
    def __init__(self):
        self.family: Optional[str] = None
        self.name: Optional[str] = None
        self.part_number: Optional[str] = None
        self.firmware: Optional[str] = None
        self.alias: Optional[str] = None
        self.enclosure_position: Optional[str] = None
        self.enclosure_serial_number: Optional[str] = None
        self.serial_number: Optional[str] = None
        self.fpga_1: Optional[str] = None
        self.fpga_2: Optional[str] = None
        self.fpga_3: Optional[str] = None
        self.fpga_4: Optional[str] = None
        self.bootloader: Optional[str] = None
        self.bootloader_mode: Optional[str] = None

    def parse_idn_response(self, idn_response: str) -> bool:
        """
        Parses the '*idn?' response from the module.

        Args:
            idn_response: The textual response containing the idn information of the module.

        Returns:
            True if at least one line of the response was parsed successfully, False otherwise.
        """
        if not idn_response:
            return False

        was_successful = False

        # A mapping of keys found in the IDN string to the class attribute names
        key_to_attr_map = {
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
            "Alias": "alias"
        }

        idn_string_list = idn_response.strip().split('\n')

        for line in idn_string_list:
            line = line.strip()

            # Handle special case for bootloader mode
            if line == "[Bootloader]":
                self.bootloader_mode = True
                was_successful = True
                continue

            # Skip lines without a colon separator
            if ':' not in line:
                continue

            # Split only on the first colon to handle values that might contain colons
            key, value = line.split(':', 1)
            key = key.strip()
            value = value.strip()

            # The "Processor" key in Java sets both product string and firmware.
            # Here we will just map it to firmware.
            if key == "Processor":
                self.firmware = value
                was_successful = True
                continue

            # Use the dictionary to find the correct attribute to set
            attr_name = key_to_attr_map.get(key)
            if attr_name:
                # Use setattr to dynamically set the class attribute
                setattr(self, attr_name, value)
                was_successful = True

        return was_successful

    def set_idn_info_fields_from_device_info_dict(self, device_info: dict):
        self.family = None  # Unknown
        self.name = device_info.get('legacy_name')
        self.part_number = None  # Unknown
        self.firmware = device_info.get('firmware_version')
        self.alias = device_info.get('enclosure_alias')
        self.enclosure_position = device_info.get('enclosure_position')
        self.enclosure_serial_number = device_info.get('enclosure_serial_number')
        self.serial_number = device_info.get('serial_number')
        self.fpga_1 = device_info.get('fpga_1')
        self.bootloader = device_info.get('bootloader')
        self.bootloader_mode = None  # Unknown
