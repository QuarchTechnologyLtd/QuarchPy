class DeviceNetworkInfo:
    def __init__(self):
        self.mac_address = None
        self.mac_type = None
        self.host_name = None
        self.ip_address = None
        self.tcp_port = None
        self.rest_port = None
        self.telnet_port = None

    def set_network_info_fields_from_device_info_dict(self, device_info: {}):
        self.mac_address = device_info['mac_address']
        self.mac_type = device_info['mac_type']
        self.host_name = device_info['host_name']
        self.ip_address = device_info['ipv4_address']
        self.tcp_port = device_info['tcp_port']
        self.rest_port = device_info['rest_port']
        self.telnet_port = device_info['telnet_port']