import platform  # For getting the operating system name
import subprocess  # For executing a shell command

from zeroconf import Zeroconf


def ping(host):
    """
    Returns True if host (str) responds to a ping request.
    """
    # Option for the number of packets as a function of
    param = '-n' if platform.system().lower() == 'windows' else '-c'

    # Building the command. Ex: "ping -c 1 google.com"
    command = ['ping', param, '1', host]

    # Execute the ping command and capture the output and return code
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    # Check the return code and output to determine the result
    if result.returncode == 0 and ("destination host unreachable" not in str(result.stdout).lower()):
        return True  # Ping successful
    else:
        return False  # Ping failed


class MyListener:
    """
    MyListener class to handle service updates, removals, and additions in Zeroconf
    """

    _instance = None

    @classmethod
    def get_instance(cls):
        """
        Get an instance of MyListener class. If none exists, create one.
        """
        if cls._instance is None:
            cls._instance = MyListener()
        return cls._instance

    def __init__(self):
        """
        Initialize MyListener instance.
        """
        self.found_devices = {}
        self.mdns_service_running = False
        self.zeroconf = None
        self.target_conn = None

    def update_service(self, zc, type_, name):
        """
        Handle service update event.
        """
        info = zc.get_service_info(type_, name)
        if "Quarch:" in str(info):
            # decode the incoming properties from mdns
            decoded_properties = {key.decode('utf-8'): value.decode('utf-8') for key, value in info.properties.items()}
            decoded_ip = ".".join(str(byte) for byte in info.addresses[0])
            self.get_instance().add_device(decoded_properties, decoded_ip)

    def remove_service(self, zc, type_, name):
        """
        Handle service removal event.
        """
        return None

    def add_service(self, zc, type_, name):
        """
        Handle service addition event.
        """
        info = zc.get_service_info(type_, name)
        if "Quarch:" in str(info):
            # decode the incoming properties from mdns
            decoded_properties = {key.decode('utf-8'): value.decode('utf-8') for key, value in info.properties.items()}
            decoded_ip = ".".join(str(byte) for byte in info.addresses[0])
            self.get_instance().add_device(decoded_properties, decoded_ip)

    def add_device(self, properties_dict, ip_address):
        """
        Add a device to the found devices dictionary.
        """
        qtl_num = "QTL" + properties_dict['86'] if '86' in properties_dict else None
        # Check if module contains REST connection
        if '84' in properties_dict:
            # Check the user specified connection type
            if self.get_instance().target_conn == "all" or self.get_instance().target_conn == "rest":
                if properties_dict['84'] == '80':
                    # print("Rest connection exists for device: " + qtl_num)
                    # Updates the found devices dict
                    self.get_instance().update_device_dict(device_dict={"REST:" + ip_address: qtl_num})
        # Check if module contains TCP connection
        if '85' in properties_dict:
            # Check the user specified connection type
            if self.get_instance().target_conn == "all" or self.get_instance().target_conn == "tcp":
                if properties_dict['85'] == "9760":
                    # print("TCP connection exists for device: " + qtl_num)
                    # Updates the found devices dict
                    self.get_instance().update_device_dict(device_dict={"TCP:" + ip_address: qtl_num})

    def update_device_dict(self, device_dict):
        """
        Update the found devices dictionary.
        """
        self.get_instance().found_devices.update(device_dict)

    def get_found_devices(self):
        """
        Get the found devices and perform ping check.
        """
        temp_dict = self.get_instance().found_devices
        for key, value in list(temp_dict.items()):
            result = ping(key[key.index(":") + 1:])
            if not result or self.get_instance().target_conn not in key.lower():
                del self.get_instance().found_devices[key]
        print(str(self.get_instance().found_devices))
        return self.get_instance().found_devices

    def get_zeroconf(self):
        """
        Get the Zeroconf instance. If none exists, create one.
        """
        if self.get_instance().zeroconf is None:
            self.get_instance().zeroconf = Zeroconf()
        return self.get_instance().zeroconf
