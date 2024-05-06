import time, sys, os ,logging

from quarchpy.connection import QISConnection, PYConnection, QPSConnection
from quarchpy import user_interface
import re

# Check Python version
if sys.version_info.major == 2:
    # Python 2: Use socket.timeout
    try:
        import socket
        timeout_exception = socket.timeout
    except AttributeError as e:
        timeout_exception = None
        logging.error("Socket timeout is not available in this Python version. "+str(e))
else:
    # Python 3: Use built-in TimeoutError
    timeout_exception = TimeoutError

class quarchDevice:
    """
    Allows control over a Quarch device, over a wide range of underlying connection methods.  This is the core class
    used for control of all Quarch products.
    
    """

    def __init__(self, ConString, ConType="PY", timeout="5"):
        """
        Constructor for quarchDevice, allowing the connection method of the device to be specified.
        
        Parameters
        ----------
        ConString : str
            
            Connection string, specifying the underlying connection type and module identifier. The underlying
            connection must be supported both by the connection type and the target module.
            
            Example:
            USB:QTL1743             - USB connection with given part number
            USB:QTL1743-03-015      - USB connection with fully qualified serial number
            SERIAL:COM4             - Serial connection with COM port (ttyS0 for linux)
            TCP:192.168.1.55        - LAN(TCP) connection to IP address
            TELNET:QTL1079-03-004   - LAN(TELNET) connection to netBIOS name (must resolve to IP address)
            REST:192.168.1.60       - LAN(REST) connection to IP address
            
        ConType : {'PY', 'QIS', 'QPS'}
            
            Specifies the software type which runs the connection:
            PY  -   (Default) Connection is run via pure Python code
            
            QIS -   Power modules only, connection run via QIS (Quarch Instrument Server) for easy power capture in raw formats. 
                    Serial is not supported. IP and port can be specified to connect to a QIS instance running at another location "QIS:192.168.1.100:9722"
                    
            QPS -   Power modules only, connection run via QPS (Quarch Power Studio) for automated power capture and analysis within thr QPS graphical environment. 
                    Serial is not supported. IP and port can be specified to connect to a QPS instance running at another location "QPS:192.168.1.100:9822"
        
        timeout : str, optional
            
            Timeout in seconds for the device to respond.
            
        """
        
        self.ConString = ConString
        if "serial" not in ConString.lower():
            self.ConString = ConString.lower()
        self.ConType = ConType        

        try:
            self.timeout = int(timeout)
        except:
            raise Exception("Invalid value for timeout, must be a numeric value")

        if checkModuleFormat(self.ConString) == False:
            raise Exception("Module format is invalid!")

        # Initializes the object as a python or QIS connection
        ## Python
        if self.ConType.upper() == "PY":

            # replacing colons
            numb_colons = self.ConString.count(":")
            if numb_colons == 2:
                self.ConString = self.ConString.replace('::', ':')

            if self.ConString.lower().find("qtl") != -1 and self.ConString.lower().find("usb") ==-1:
                from .scanDevices import get_connection_target
                self.ConString = get_connection_target(self.ConString)

            # Create the connection object
            self.connectionObj = PYConnection(self.ConString)
            self.ConCommsType = self.connectionObj.ConnTypeStr

            # Exposes the connection type and module for later use.
            self.connectionName = self.connectionObj.ConnTarget
            self.connectionTypeName = self.connectionObj.ConnTypeStr

            time.sleep(0.1)
            item = None
            item = self.connectionObj.connection.sendCommand("*tst?")
            if "OK" in item:
                pass
            elif "FAIL" in item:
                pass
            elif item is not None:
                pass
            else:
                raise Exception("No module responded to *tst? command!")
            time.sleep(0.1)

        ## QIS
        # ConType may be QIS only or QIS:ip:port [:3] checks if the first 3 letters are QIS.
        elif self.ConType[:3].upper() == "QIS":
            try: # If host and port are specified.
                QIS, host, port = self.ConType.split(':') # Extract QIS, host and port.
                port = int(port) # QIS port should be an int.
            except:  # If host and port are not specified.
                host = '127.0.0.1'
                port = 9722

            numb_colons = self.ConString.count(":")
            if numb_colons == 1:
                self.ConString = self.ConString.replace(':', '::')
            # Creates the connection object.
            self.connectionObj = QISConnection(self.ConString, host, port)

            list = self.connectionObj.qis.getDeviceList()
            list_str = "".join(list).lower()

            timeout = time.time() + int(timeout) # now + n seconds
            # check for device in list, has a timeout
            while time.time() < timeout: # look for the connection string in qis $list details

                # Check if it's a module's QTL number
                if "qtl" not in self.ConString.lower():

                    # If not, check if it contains a valid IP address format
                    ip_address = re.search(r"[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}", self.ConString)
                    if not ip_address:
                        raise ValueError("ConString " + self.ConString + " does not contain a valid QTL number or IP address")
                    # Attempt to get QTL number from qis "$list details"
                    temp_str = _check_ip_in_qis_list(ip_address.group(), self.connectionObj.qis.get_list_details())
                    if temp_str:
                        # If found
                        self.ConString = temp_str
                        break

                    logging.debug("Did not find ip address in list details, attempt targetted qis scan")

                    # If it's not present in the list already, then try scanning for it via qis
                    # Scan is purposefully after initial check! 09/03/2023
                    # Valid response example "Located device: 192.168.1.3"
                    if "located" in str(self.connectionObj.qis.scanIP(self.ConString)).lower():
                        # Note - Qis takes a moment or 2 to add this newly located device to the $list 21/03/23
                        timeout += 20   # Extend the timeout as the drive was located
                        while time.time() < timeout:
                            # try find the QTL from ipaddress
                            temp_str = _check_ip_in_qis_list(ip_address.group(), self.connectionObj.qis.get_list_details())
                            if temp_str:
                                # If the item is found, break out of this loop
                                self.ConString = temp_str
                                break
                            time.sleep(1)   # Slow down the poll
                        else:
                            # if it's not found, continue and allow program to timeout
                            continue
                        # Break out of both loops
                        break

                elif str(self.ConString).lower() in str(list_str).lower():
                    # If we have QTL device, and it's in list, nothing more needs done.
                    break
                else:
                    time.sleep(1)
                    list = self.connectionObj.qis.getDeviceList()
                    list_str = "".join(list).lower()
            else: # If we didn't hit a 'break' condition in the above loop, then it timed out
                raise timeout_exception("Could not find module " + self.ConString + " from Qis within specified time")

            self.connectionObj.qis.sendAndReceiveCmd(cmd="$default " + self.ConString)

        ## QPS
        elif self.ConType[:3].upper() == "QPS":
            try:
                # Extract QPS, host and port.
                QPS, host, port = self.ConType.split(':')
                # QPS port should be an int.
                port = int(port)
            # If host and port are not specified.
            except:
                host = '127.0.0.1'
                port = 9822

            numb_colons = self.ConString.count(":")
            if numb_colons == 1:
                self.ConString = self.ConString.replace(':', '::')

            self.connectionObj = QPSConnection(host, port)
            list = self.connectionObj.qps.sendCmdVerbose("$module list details").replace("\r\n","\n").split("\n")
            list_str = "".join(list).lower()

            timeout = time.time() + int(timeout) # now + n seconds
            # check for device in list, has a timeout
            while time.time() < timeout: # look for the connection string in QPS $list details

                # Check if it's a module's QTL number
                if "qtl" not in self.ConString.lower():

                    # If not, check if it contains a valid IP address format
                    ip_address = re.search(r"[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}", self.ConString)
                    if not ip_address:
                        raise ValueError("ConString " + self.ConString + " does not contain a valid QTL number or IP address")

                    # Attempt to get QTL number from QPS "$list details"
                    temp_str = _check_ip_in_qis_list(ip_address.group(), list)
                    if temp_str:
                        # If found
                        self.ConString = temp_str
                        break

                    logging.debug("Did not find ip address in list details, attempt targetted QPS scan")

                    # If it's not present in the list already, then try scanning for it via QPS
                    # Scan is purposefully after initial check! 09/03/2023
                    # Valid response example "Located device: 192.168.1.3"

                    if "located" in str(self.connectionObj.qps.scanIP(self.ConString)).lower():
                        # Note - QPS takes a moment or 2 to add this newly located device to the $list 21/03/23
                        timeout += 20   # Extend the timeout as the drive was located
                        while time.time() < timeout:
                            # try find the QTL from ipaddress
                            temp_str = _check_ip_in_qis_list(ip_address.group(), self.connectionObj.qps.get_list_details())
                            if temp_str:
                                # If the item is found, break out of this loop
                                self.ConString = temp_str
                                break
                            time.sleep(1)   # Slow down the poll
                        else:
                            # if it's not found, continue and allow program to timeout
                            continue
                        # Break out of both loops
                        break

                elif str(self.ConString).lower() in str(list_str).lower():
                    # If we have QTL device, and it's in list, nothing more needs done.
                    break
                else:
                    time.sleep(1)
                    list = self.connectionObj.qps.getDeviceList()
                    list_str = "".join(list).lower()
            else: # If we didn't hit a 'break' condition in the above loop, then it timed out
                raise timeout_exception("Could not find module " + self.ConString + " from QPS within specified time")






            ## Neither PY or QIS, connection cannot be created.
        else:
            raise ValueError("Invalid connection type. Acceptable values [PY,QIS,QPS]")

        logging.debug(os.path.basename(__file__) + " ConString : " + str(self.ConString) + " ConType : " + str(self.ConType))


    # def setCanStream(self):
    # ask module name if = name in list
    # TODO: The connectionObj should be an instance of a common base class such that the IF block here is not needed
    def sendCommand(self, CommandString, expectedResponse = True):
        """
        Executes a text based command on the device.  This is the primary way of controlling a device.  The full command set available to use
        is found in the technical manual for the device.
        
        Parameters
        ----------
        CommandString : str

            The text based command string to send to the device
        
        Returns
        -------
        command_response : str or None

            The response text from the module.  Multiline responses will be seperated with LF. Some commands
            do not return a response and None will be returned

        """

        # send command to log
        logging.debug(os.path.basename(__file__) + ": "+self.ConType[:3]+" sending command: " + CommandString)

        if self.ConType[:3].upper() == "QIS":

            numb_colons = self.ConString.count(":")
            if numb_colons == 1:
                self.ConString = self.ConString.replace(':', '::')

            response = self.connectionObj.qis.sendCommand(CommandString, device=self.ConString, expectedResponse=expectedResponse)
            # send response to log
            logging.debug(os.path.basename(__file__) + ": "+self.ConType[:3]+" received: " + response)
            return response

        elif self.ConType.upper() == "PY":
            response = self.connectionObj.connection.sendCommand(CommandString, expectedResponse=expectedResponse)
            # send response to log
            logging.debug(os.path.basename(__file__) + ": "+self.ConType[:3]+" received: " + response)
            return response

        elif self.ConType[:3].upper() == "QPS":
            # If "$" CMD is for QPS, else its for the specific module. Since QPS can talk to many modules we must added the conString.
            if CommandString[0] != '$':
                CommandString = self.ConString + " " + CommandString

            response = self.connectionObj.qps.sendCommand(CommandString, expectedResponse)
            # send response to log
            logging.debug(os.path.basename(__file__) + ": "+self.ConType[:3]+" received: " + response)
            return response


    # Only works for usb
    # TODO: Can this be marked '_' for private use only
    def sendBinaryCommand(self, cmd):
        self.connectionObj.connection.Connection.SendCommand(cmd)
        return self.connectionObj.connection.Connection.BulkRead()


    # TODO: Not using class hierarchy based connectionObj, recreation of PYConnection may not release the previous handle in time.
    # QPS and QIS actions are different despite the underlying connection being the same!
    def openConnection(self):
        """
        Opens the connection to the module.  This will be open by default on creation of quarchDevice but this
        allows re-opening if required.
        
        """
        
        logging.debug("Attempting to open " + self.ConType[:3] + " connection")

        if self.ConType[:3] == "QIS":
            self.connectionObj.qis.connect() #todo should have a return val so that failed connections are caught.

        elif self.ConType == "PY":
            del self.connectionObj
            self.connectionObj = PYConnection(self.ConString)
            return self.connectionObj

        elif self.ConType[:3] == "QPS":
            return self.connectionObj.qps.connect(self.ConString)

        else:
            raise Exception("Connection type not recognised")


    # TODO: Not using class hierarchy based connectionObj. QPS and QIS actions are different despite the underlying connection being the same!
    def closeConnection(self):
        """
        Closes the connection to the module, freeing the module for other uses.  This should always be called whern you are finished with a device.
        
        """
        
        logging.debug("Attempting to close " + self.ConType[:3] + " connection")

        if self.ConType[:3] == "QIS":
            #self.connectionObj.qis.disconnect()
            self.connectionObj.qis.closeConnection(conString=self.ConString)
        elif self.ConType == "PY":
            self.connectionObj.connection.close()

        elif self.ConType[:3] == "QPS":
            self.connectionObj.qps.disconnect(self.ConString)

        return "OK"


    # TODO: Not using class hierarchy based connectionObj.
    def resetDevice(self, timeout=10):
        """
        Issues a power-on-reset command to the device.  Attempts to recover the connection to the module after reset.
        Function halts until the timeout is complete or the module is found
        
        Parameters
        ----------
        timeout : int
            
            Number of seconds to wait for the module to re-enumerate and become available
            
        Returns
        -------
        result : bool
        
            True if the device was found and reconnected, false if it was not and we timed out
        
        """

        # send command to log
        logging.debug(os.path.basename(__file__) + ": sending command: *rst" )

        if self.ConType[:3] == "QIS":

            numb_colons = self.ConString.count(":")
            if numb_colons == 1:
                self.ConString = self.ConString.replace(':', '::')

            retval = self.ConString
            self.connectionObj.qis.sendCmd(self.ConString, "*rst", expectedResponse = False)
            logging.debug(os.path.basename(__file__) + ": connecting back to " + retval)

        elif self.ConType == "PY":
            retval = self.ConString
            self.connectionObj.connection.sendCommand("*rst" , expectedResponse = False)
            self.connectionObj.connection.close()
            logging.debug(os.path.basename(__file__) + ": connecting back to " + retval)
            #pos fix for making new connectionObj. Works for py connection but more complex for qis & qps
            #self.connectionObj = PYConnection(self.ConString)

        elif self.ConType[:3] == "QPS":
            # checking if the command string passed has a $ as first char
            retval = self.ConString
            CommandString = self.ConString + " " + "*rst"
            self.connectionObj.qps.sendCmdVerbose(CommandString, expectedResponse = False)
            logging.debug(os.path.basename(__file__) + ": connecting back to " + retval)

        #TODO: Idealy we want to call an openConnection() funct to set the connectionObj to the new value not creating a new obj

        temp = None
        startTime = time.time()
        time.sleep(0.6) #most devices are visable again after 0.6 seconds.
        while temp == None:
            try:
                #user_interface.printText("Restart time is : " + str(time.time() - startTime) + "  timeout is : " + str(timeout))
                temp = getQuarchDevice(retval)
            except:
                time.sleep(0.2) # wait before trying again if not timed out.
                if (time.time() - startTime) > timeout:                    
                    logging.critical(os.path.basename(__file__) + ": connection failed to " + retval)
                    return False

        self.connectionObj = temp.connectionObj
        time.sleep(1) #Must wait before sending a command to device. If done instantly device errors out "device busy"
        return True
    

    def sendAndVerifyCommand(self, commandString, responseExpected="OK", exception=True):
        """
        Sends a command to the device and verifies the response is as expected.  This is a simple
        wrapper of sendCommand and helps write cleaner code in test scripts.
        
        Parameters
        ----------
        commandString : str
            
            The text command to send to the device
            
        commandString : str, optional
            
            The expected text response from the module.
            
        exception : bool, optional
        
            If True, an exception is raised on mismatch.  If False, we just return False
            
        Returns
        -------
        result : bool
        
            True if we matched the response, False if we did not
            
        Raises
        ------
        ValueError
            If the response does not match AND the exception parameter is set to True
        
        """
        
        responseStr = self.sendCommand(commandString)
        if (responseStr != responseExpected):
            if (exception):
                raise ValueError("Command Sent: " + commandString + ", Expected response: " + responseExpected + ", Response received: " + responseStr)
            else:
                return False
        else:
            return True


    def getRuntime(self, command="conf:runtimes?"):
        '''

        :param command: can be overridden to ask for PAM fixture runtime
        :return:
        '''
        runtime = self.sendCommand(command)
        if runtime.lower().__contains__("fail"):
            logging.error("runtime check failed, check FW and FPGA are up to date")
        # if the response matches [int]s then the result was valid, return digits, (otherwise return None)
        if runtime.endswith("s"):
            try :
                runtime = int(runtime[:-1])
                return runtime
            except:
                logging.error("runtime response not a valid int : " + str(runtime))
        else:
            return None


def _check_ip_in_qis_list(ip_address, detailed_device_list):
    """
    Checks if the IP address is in qis device list
    :param detailed_device_list: list formatted return from qis command "$list details"
    :return String : return contype and constring for module if it's in list, else None
    """
    # logging.debug(f"List details from Qis : \n{str(''.join(detailed_device_list))}")

    for module in detailed_device_list:
        # Use generator expression to filter word starting with 'IP:' in the qis module string this is to prevent a similar ip from being selected e.g. 192.168.1.1 and 192.168.1.12
        module_ip_address = next((word[3:] for word in module.split() if word.startswith('IP:')), "")
        # Note for future developers : Restricted this to only TCP modules, not RESt
        if ip_address == module_ip_address and "tcp" in module.lower():
            # '1) REST::QTL2312-01-009 IP:192.168.1.5 Port:80 NBName:2312-01-009     Stream:No Name:Power Analysis Module'
            # Split on spaces and grab second element ("tcp::qtl2312-01-009")
            ret_string = module.split()[1]
            return ret_string

    # If the ip address wasn't found, then return none
    return None


# TODO: Can we make this an '_' internal function?
def checkModuleFormat(ConString):
    ConnectionTypes = ["USB", "SERIAL", "TELNET", "REST", "TCP"]  # acceptable conTypes

    conTypeSpecified = ConString[:ConString.find(':')]

    correctConType = False
    for value in ConnectionTypes:
        if value.lower() == conTypeSpecified.lower():
            correctConType = True

    if not correctConType:
        logging.warning("Invalid connection type specified in Module string, use one of [USB|SERIAL|TELNET|REST|TCP]")
        logging.warning("Invalid connection string: " + ConString)
        return False

    numb_colons = ConString.count(":")
    if numb_colons > 2 or numb_colons <= 0:
        logging.warning("Invalid number of colons in module string")
        logging.warning("Invalid connection string: " + ConString)
        return False

    return True


def getQuarchDevice(connectionTarget, ConType="PY", timeout="5"):
    '''creates a quarch device to be returned. Handles sub devices in quarch arrays.  '''
    from .quarchArray import quarchArray
    if connectionTarget.__contains__("<") and connectionTarget.__contains__(">"):
        connectionTarget, portNumber = connectionTarget.split("<")
        portNumber = portNumber[:-1]
        myDevice = quarchDevice(connectionTarget, ConType="PY", timeout="5")
        myArrayController = quarchArray(myDevice)
        mySubDevice = myArrayController.getSubDevice(portNumber)
        myDevice = mySubDevice
    else:
        myDevice = quarchDevice(connectionTarget, ConType=ConType, timeout=timeout)
    return myDevice