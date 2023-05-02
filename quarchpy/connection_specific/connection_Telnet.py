import telnetlib
import time

class TelnetConn:
    def __init__(self, ConnTarget):
        self.ConnTarget = ConnTarget
        self.Connection = telnetlib.Telnet(self.ConnTarget)
        time.sleep(1)
        self.Connection.read_very_eager()

    def close(self):
        self.Connection.close()
        return True

    def sendCommand(self, Command, expectedResponse = True):
        self.Connection.write((Command + "\r\n").encode('latin-1'))
        self.Connection.read_until(b"\r\n",3)
        Result = self.Connection.read_until(b">",3)[:-1]
        Result = Result.decode()
        Result = Result.strip('> \t\n\r')
        return Result.strip()