from telnetlib import Telnet
import time
#from telnetlib3 import Telnet


class TelnetConn:
    def __init__(self, ConnTarget):
        self.ConnTarget = ConnTarget
        self.Connection = Telnet(self.ConnTarget)
        time.sleep(1)
        self.Connection.read_very_eager()

    def close(self):
        self.Connection.close()
        # The closed device reports as in use if a connection is opened to it within 0.05s.
        # This happens during scanning as rest detects the device and shows it as "in use" Putting a sleep here
        #  allows time for the connection to be close,
        time.sleep(0.15)
        return True

    def sendCommand(self, Command, expectedResponse = True):
        self.Connection.write((Command + "\r\n").encode('latin-1'))
        self.Connection.read_until(b"\r\n",3)
        Result = self.Connection.read_until(b">",3)[:-1]
        Result = Result.decode()
        Result = Result.strip('> \t\n\r')
        return Result.strip()