import logging

class MyListener:
    def __init__(self):
        self.found_devices = {}

    def update_service(self, zc, type_, name):
        return None

    def remove_service(self, zc, type_, name):
        info = zc.get_service_info(type_, name)
        if "Quarch:" in str(info):
            decoded_properties = {key.decode('utf-8'): value.decode('utf-8') for key, value in info.properties.items()}
            qtl_num = "QTL" + decoded_properties['86'] if '86' in decoded_properties else None
            for key, value in self.found_devices:
                if value == qtl_num:
                    del self.found_devices[key]

    def add_service(self, zc, type_, name):
        info = zc.get_service_info(type_, name)
        if "Quarch:" in str(info):
            # decode the incoming properties from mdns
            decoded_properties = {key.decode('utf-8'): value.decode('utf-8') for key, value in info.properties.items()}
            decoded_ip = ".".join(str(byte) for byte in info.addresses[0])
            self.add_device(decoded_properties, decoded_ip)

    def add_device(self, properties_dict, ip_address):
        qtl_num = "QTL" + properties_dict['86'] if '86' in properties_dict else None
        if '84' in properties_dict:
            if properties_dict['84'] == '80':
                # print("Rest connection exists for device: " + qtl_num)
                self.update_device_dict(device_dict={"REST:" + ip_address: qtl_num})
        if '85' in properties_dict:
            if properties_dict['85'] == "9760":
                # print("TCP connection exists for device: " + qtl_num)
                self.update_device_dict(device_dict={"TCP:" + ip_address: qtl_num})

    def update_device_dict(self, device_dict):
        self.found_devices.update(device_dict)

