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

    def sendCommand(self, Command, expectedResponse = True):
        Command = "/" + Command.replace(" ", "%20")
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
                print ("FAIL - Please power cycle the module!")
                self.Connection.close()
                return "FAIL: ", R1.status, R1.reason
        else:
            return None