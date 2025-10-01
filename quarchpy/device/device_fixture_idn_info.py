class FixtureIDNInfo:
    def __init__(self):
        self.fixture_name = None
        self.fixture_fpga = None

    def set_fix_idn_info_fields_from_device_info_dict(self, device_info: {}):
        self.fixture_name = device_info.get('fixture_name')
        self.fixture_fpga = device_info.get('fixture_fpga')
