from quarchpy import quarchDevice


class DeviceAPI:
    def __init__(self, quarch_device: quarchDevice):
        self.quarch_device = quarch_device

    def get_identity(self):
        command = '*IDN?'
        response = self.quarch_device.send_command(command)
        return response




