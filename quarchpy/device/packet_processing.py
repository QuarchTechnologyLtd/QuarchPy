import socket
from quarchpy.device.discovered_device import CODE_MAP

def decode_locate_packet(packet_fields: list[bytes]) -> dict:
    """
    Parses a device location packet and returns a dictionary of its properties.

    This function is designed to work with a packet that has already been
    split into a list of fields (byte strings). It interprets each field
    based on a leading code byte.

    Args:
        packet_fields: A list of bytes objects, where each object is a
                       field from the packet, typically prefixed with a code.

    Returns:
        A dictionary containing the parsed device information.
    """
    device_info = {}

    for field in packet_fields:
        if not field:
            continue

        code = field[0]
        data = field[1:]

        # Handle special cases with unique formatting
        if code == 0x02:  # MAC Address (binary)
            device_info['mac_address'] = _format_mac_address(data)
        elif code == 0x03:  # MAC Type
            device_info['mac_type'] = data.decode('ascii', errors='ignore').strip()
        elif code == 0x04:  # Host Name
            device_info['host_name'] = data.decode('ascii', errors='ignore').strip()
        elif code == 0x05:  # IPv4 Address
            try:
                # Use standard library to format the 4-byte IP address
                device_info['ipv4_address'] = socket.inet_ntoa(data)
            except (OSError, ValueError):
                # Fallback if data is not 4 bytes
                device_info['ipv4_address'] = "Invalid IP format"
        # Handle all standard string-based fields using the map
        elif code in CODE_MAP:
            key = CODE_MAP[code]
            device_info[key] = data.decode('ascii', errors='ignore').strip()

    # The first two fields in your example are a legacy header without codes.
    # We can add them based on their position if they exist.
    if len(packet_fields) > 1:
        device_info['legacy_name'] = packet_fields[0].decode('ascii', errors='ignore').strip()
        # The MAC address string from the legacy header is redundant if code 0x02 exists,
        # but we can include it for completeness.
        device_info['legacy_mac_string'] = packet_fields[1].decode('ascii', errors='ignore').strip()

    return device_info


def _format_mac_address(data: bytes) -> str:
    """
    Converts a 6-byte sequence into a standard MAC address string.

    This is a verbose implementation for maximum clarity.
    """

    # 1. Create an empty list to hold each hexadecimal part of the address.
    hex_parts = []

    # 2. Loop through each byte in the raw byte sequence.
    #    A 'byte' in this context is just a number from 0 to 255.
    for byte in data:
        # 3. For each number, format it as a two-digit, lowercase hexadecimal string.
        #    - The 'x' converts the number to hex.
        #    - The '02' ensures it's always two digits, adding a leading
        #      zero if needed (e.g., the number 10 becomes '0a').
        hex_part = f'{byte:02x}'

        # 4. Add the newly formatted two-character string to our list.
        hex_parts.append(hex_part)

    # After the loop, the `hex_parts` list will look like this:
    # ['9c', '95', '6e', '59', 'f0', 'e5']

    # 5. Join all the individual parts in the list together, using a colon
    #    as the separator.
    mac_address = ':'.join(hex_parts)

    return mac_address
