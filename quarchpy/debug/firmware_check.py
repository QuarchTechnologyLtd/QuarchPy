import requests

class FirmwareChecker:
    QUERY_URL = 'https://quarch.com/product-check/firmware-search/?field_part_number_value=QTL2312'

    def __init__(self, device_serial_number: str, device_list_details: {}):
        self.device_serial_number = device_serial_number
        self.device_fpga = device_list_details['fpga']
        self.device_fw = device_list_details['fw']
        self.update_pack_link = None

    def main(self):
        return False

    def check_for_fw_fpga_update(self):
        return False

    def get_version_block(self):
        return False

    def download_update_pack(self):
        return False


