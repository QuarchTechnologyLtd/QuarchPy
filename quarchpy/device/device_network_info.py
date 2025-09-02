class DeviceNetworkInfo:
    def __init__(self):
        self.mac_address = None
        self.mac_type = None
        self.host_name = None
        self.ip_address = None
        self.tcp_port = None
        self.rest_port = None
        self.telnet_port = None

    def set_network_info_fields_from_device_info_dict(self, device_info: dict):
        self.mac_address = device_info.get('mac_address')
        self.mac_type = device_info.get('mac_type')
        self.host_name = device_info.get('host_name')
        self.ip_address = device_info.get('ipv4_address')
        self.tcp_port = device_info.get('tcp_port')
        self.rest_port = device_info.get('rest_port')
        self.telnet_port = device_info.get('telnet_port')