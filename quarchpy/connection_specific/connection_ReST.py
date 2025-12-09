import socket
import logging
logger = logging.getLogger(__name__)
from time import time
try:
    import httplib as httplib
except ImportError:
    import http.client as httplib

class ReSTConn:
    def __init__(self, ConnTarget):
        self.ConnTarget = ConnTarget

        self.Connection = httplib.HTTPConnection(self.ConnTarget, 80, timeout=10)
        self.Connection.close()
        
    def close(self):
        return True

    def sendCommand(self, Command, expectedResponse = True, max_retries=2):
        Command = "/" + Command.replace(" ", "%20")
        for attempt in range(0, max_retries ):
            try:
                self.Connection.request("GET", Command)
                if expectedResponse == True:
                    R2 = self.Connection.getresponse()
                    if R2.status == 200:
                        Result = R2.read()
                        Result = Result.decode()
                        Result = Result.strip('> \t\n\r')
                        self.Connection.close()
                        return Result
                    else:
                        logger.error("FAIL - Please power cycle the module!")
                        self.Connection.close()
                        return "FAIL: ", R1.status, R1.reason
                else:
                    return None
            except socket.timeout as e:
                if attempt < max_retries:
                    logger.warning("Socket timed out, retrying command...")
                    time.sleep(0.1)
                else:
                    logger.error("Maximum number of retries reached on module at: "+self.ConnTarget+". Exiting.")
                    raise e