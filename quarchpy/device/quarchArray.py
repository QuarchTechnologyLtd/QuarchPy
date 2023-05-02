from .device import quarchDevice

'''
Returns true if the given part/serial number refers to an Array Controller
'''
def isThisAnArrayController (moduleString):
    if ("QTL1079" in moduleString or "QTL1461" in moduleString):
        return True
    else:
        return False

class quarchArray(quarchDevice):
    def __init__(self,baseDevice):

        self.ConType=baseDevice.ConType
        self.connectionObj=baseDevice.connectionObj
        pass

    def getSubDevice(self, port):
        return subDevice(self, port)

    def scanSubModules(self):
        moduleList = dict()

        # Query the attached devices
        responseText = self.sendCommand("conf:list:mod?")
        if responseText == "":
            return dict()
        responseList = responseText.split("\n")
        ConType = self.connectionObj.ConnTypeStr
        arrayConnTarget = self.connectionObj.ConnTarget
        # Check for immediate command failure
        if (responseText.find("FAIL") == 0):
            raise ValueError ("Invalid response from the array controller during sub-module scan") 
            return None

        # Loop through the responses
        for str in responseList:
            # Split into address and response
            pos = str.find (":")
            strAddr = str[:pos]
            strResponse = str[pos+1:]
            if ("FAIL" in strResponse):
                moduleList[ConType + ":???<" + strAddr + ">"] = "Module failed to respond correctly to identity scan"
            else:
                subDevice = self.getSubDevice (strAddr)
                subSerial = subDevice.sendCommand ("*serial?")
                if ("QTL" not in subSerial):
                    subSerial = "QTL" + subSerial
                moduleList[ConType+":" + arrayConnTarget + "<" + strAddr + ">"] = subSerial

        return moduleList


     

class subDevice(quarchDevice):

    def __init__(self, baseDevice, port):
        self.port = port
        self.connectionObj = baseDevice.connectionObj
        self.ConType = baseDevice.ConType
        self.baseDevice = baseDevice

    def sendCommand(self, CommandString, expectedResponse = True):
        portNumb = str(self.port)
        returnStr = ''
        
        # Run the base device command
        respStr = quarchDevice.sendCommand(self, CommandString + " <" + portNumb + ">")
        # Split into lines, remove the line number sections then reform the string (removing the wanted 'x.y:' section at the start of each line
        respLines = respStr.split('\n')
        for x in respLines:            
            pos = x.find(':')
            lineNum = x[:pos]
            returnStr += (x[pos+1:].strip() + "\r\n")
        returnStr = returnStr.strip()
        return returnStr

