import datetime
import serial
import time
import serial.tools.list_ports as serialList

def serial_read_until (Port, Char, Timeout):
    ReturnStr = b""
    Start = datetime.datetime.now()
    Done = False

    # Loop until done
    while (Done == False):
        # Loop through waiting chars
        while (Port.inWaiting() > 0):
            # Read 1 char
            NewChar = Port.read (1)
            # If this is the exit char
            if NewChar == Char:
                # Return the current string
                return ReturnStr
            # Else append to the current string
            else:
                ReturnStr += NewChar
                # Reset start time for latest char
                Start = datetime.datetime.now()

        # If no further chars to read and timeout has passed, exit with what we currently have
        Now = datetime.datetime.now()
        if (Now - Start).seconds > Timeout:
            return ReturnStr

    return ReturnStr

class SerialConn:
    def __init__(self, ConnTarget):
        self.ConnTarget = ConnTarget

        self.Connection = serial.Serial (port=self.ConnTarget,
                        baudrate=19200,
                        parity=serial.PARITY_NONE,
                        stopbits=serial.STOPBITS_ONE,
                        bytesize=serial.EIGHTBITS)

    def close(self):
        self.Connection.close()
        return True
    
    def sendCommand(self, Command, expectedResponse = True):
        Command = (Command + "\r\n").encode()
        self.Connection.write(Command)
        Result = serial_read_until(self.Connection,b"\n",3)
        Result = serial_read_until(self.Connection,b">",3).strip()
        Result = Result.decode()
        Result = Result.strip('> \t\n\r')
        return Result.strip()