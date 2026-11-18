"""Checking a module's firmware against the versions published on quarch.com.

Moved here from the device record, which describes what a scan found and
should not be making web requests or printing. The behaviour is unchanged for
now; it is slated for rework, and the known problems are listed below so they
are not rediscovered.

Known problems, to be addressed when this is reworked:

* ``urlopen`` has no timeout, so a slow or unreachable network hangs the call.
* Nothing catches a failed request; the exception reaches the caller.
* Versions are compared with ``float()``, so 1.10 sorts below 1.9. Wrong for
  every FPGA, and right for firmware only by luck.
* ``.split(',')[1]`` assumes every field carries a comma and is not None.
  A module that does not report a firmware or FPGA version raises here.
* Only ``fpga_1`` is considered, so a module with more than one FPGA is only
  half checked.
* It prints its findings, which a GUI cannot catch and a script cannot
  suppress.
* The URL and the section delimiter differ from the ones the Torridon updater
  uses (``https`` with a trailing slash and ``</div>`` here, ``http`` without
  and ``</section>`` there). One of the two is wrong.
"""

from urllib.request import urlopen

PRODUCT_CHECK_URL = \
    'https://quarch.com/product-check/firmware-search/?field_part_number_value='


def get_serial_from_device(device_info):
    """Returns the serial number used to look a module up on the website.

    Some products report the number to search on in a different field, hence
    the special cases below.
    """
    serialNo = device_info.serial_number
    # Special case for IEC PAM
    if ('2582' in serialNo) or ('2751' in serialNo) or ('2789' in serialNo) or ('2843' in serialNo):
        response = serialNo
        device_string = response.rsplit(':', 1)[1].strip() if ':' in response else response
        return device_string
    # Special case for PPM+
    if '1944' in serialNo:
        response = device_info.enclosure_serial_number
        device_string = response.split(':', 1)[1].strip() if ':' in response else response
        return device_string

    response = device_info.enclosure_serial_number
    if response is None:
        response = serialNo
    device_string = response.rsplit(':', 1)[1].strip() if ':' in response else response
    return device_string


def is_update_available(device_info, product_check_url=PRODUCT_CHECK_URL):
    """Checks for firmware and FPGA updates by scraping a product webpage.

    This method determines the device's model number from its serial number,
    fetches the corresponding product page from a URL, and scrapes the page
    to find the latest available firmware and FPGA versions. It then compares
    these against the versions currently on the device.

    ``device_info.is_update_required`` is set to True if either the
    firmware or FPGA version is found to be outdated.

    Returns:
        bool: True if an update is available, False otherwise.
    """
    # Extract the base device name (model number) from the full serial number.
    device_info.device_name = get_serial_from_device(device_info)
    part_no = get_serial_from_device(device_info).split('-', 1)[0]
    # Fetch the product webpage content using the constructed URL.
    prod_search_page = urlopen(f'{product_check_url}{part_no}')

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
    current_fw_version = device_info.firmware.split(',')[1]
    current_fpga_version = device_info.fpga_1.split(',')[1]

    # Loop through each line of the scraped text to find version details.
    for entry in scraped_device_info_list:
        # Check for the line containing the firmware version.
        if 'FW' in entry:
            # Extract the version number part of the string.
            scraped_fw_version = entry.split(',')[1]
            # Immediately compare versions and set the update flag if needed.
            if float(scraped_fw_version) > float(current_fw_version):
                device_info.is_update_required = True
        # Check for the line containing the FPGA version.
        if 'FPGA' in entry:
            # Extract the version number part of the string.
            scraped_fpga_version = entry.split(',')[1]
            # Immediately compare versions and set the update flag if needed.
            if float(scraped_fpga_version) > float(current_fpga_version):
                device_info.is_update_required = True
        # Extract the required link to download the zip file if required.
        if 'Link' in entry:
            scraped_download_link_zip = entry.split(':', 1)[1]

    # After checking all lines, if the update flag has been set...
    if device_info.is_update_required:
        # ...print a helpful message to the user and return True.
        print(f"\nThe module: {device_info.device_name} is not up-to-date. Current (FW: {current_fw_version}, FPGA: {current_fpga_version}) -> Latest (FW: {scraped_fw_version}, FPGA: {scraped_fpga_version})")
        print(f"Please download the update pack at the following link: {scraped_download_link_zip}")
        return True

    # If the flag was never set, no update is needed.
    return False
