import sys
import platform
import time
import os
import sys
import logging
import platform
import inspect
import ctypes
from timeit import default_timer as timer

QUARCH_VENDOR_ID = 0x16D0
QUARCH_PRODUCT_ID1 = 0x0449         # This ID applies to MOST but not all Quarch products, add additional IDs as required

serialDict = {}

def importUSB(version = "None"):
    if os.name == 'nt': 
        #checking to see if the user has specified a version of dll's to import
        if (version != "None"):
            #checking to see if version entered was acceptable
            if (version != "64" and version != "32"):
                print ("Invalid version number")
                message = "FAIL"
            # add the specified DLLs' version to the path
            libusb1DLLFolder = os.path.realpath(os.path.abspath(os.path.split(inspect.getfile( inspect.currentframe() ))[0]) + "//usb_libs//" + "MS" + version + "//libusb-1.0.dll")
            if libusb1DLLFolder not in sys.path:
                sys.path.insert(0, libusb1DLLFolder)

            try:
                hllDll = ctypes.WinDLL (libusb1DLLFolder)
            except Exception as e:
                print ("Import failed on loading Windows libusb dll.")
                print ("Msg:" + str(e))
                message = "FAIL"

        #if no version was specified, uses default system version
        else:
            if "64 bit" in sys.version: 
                osVersion = "MS64"
            else:
                osVersion = "MS32"
            # add the DLLs to the path
            libusb1DLLFolder = os.path.realpath(os.path.abspath(os.path.split(inspect.getfile( inspect.currentframe() ))[0]) + "//usb_libs//" + osVersion + "//libusb-1.0.dll")
            if libusb1DLLFolder not in sys.path:
                sys.path.insert(0, libusb1DLLFolder)


            try:
                hllDll = ctypes.WinDLL (libusb1DLLFolder)
            except Exception as e:
                print ("Import failed on loading Windows libusb dll.")
                print ("Msg:" + str(e))
                message = "FAIL"
    else:
        pass

    # add the folder usb_libs to the path
    libusb1Folder = os.path.realpath(os.path.abspath(os.path.split(inspect.getfile( inspect.currentframe() ))[0]) + "//usb_libs")
    if libusb1Folder not in sys.path:
        sys.path.insert(0, libusb1Folder)

    #now that the DLLs are in the memory and the folder is in the path, import usb1
    import usb1
    return usb1

#usb1 = importUSB()

def getUSBDeviceSerialNo( context, device ):
    qDevice = TQuarchUSB_IF( context )
    qDevice.connection = device
    sNo = qDevice.GetSerialNumber()
    
    if sNo == 'NO_SERIAL':# or sNo == None:
        qDevice.OpenPort()
        # Delay required for array controllers with several modules. 

        time.sleep(0.02)

        dbgStr = qDevice.RunCommand("*serial?")
        qDevice.ClosePort()
        sNo = dbgStr.replace("\r\n$","")
    return sNo

def USB(SerID = ''):

    if "qtl" in SerID or "QTL" in SerID:
        SerID = SerID[3:]
        
    usb1 = importUSB()  
    context = usb1.USBContext()
    QquarchDevice = None
    quarchDevice = None
    
    for device in context.getDeviceList():
        if device.getVendorID() == QUARCH_VENDOR_ID:
            sNo = getUSBDeviceSerialNo( context,  device )
            if sNo is None:
                continue
            if sNo.strip().lower().replace("qtl","") in SerID.strip():  # comparison must look for sNo in SerID as SerID may contain<portNo>
                if quarchDevice == None:
                    quarchDevice = device
                    break

    if quarchDevice == None:
        if SerID.lower() != "list":
            logging.critical('Quarch device ' + SerID + ' not found!')
        return None
    else:
        QquarchDevice = TQuarchUSB_IF( context )
        QquarchDevice.connection = quarchDevice
        QquarchDevice.OpenPort()
        QquarchDevice.SetTimeout(2000)
    return QquarchDevice

class TQuarchUSB_IF:
    lockUSBStr = '\x02\x00\x00\x01\x04\x01'
    unlockUSBStr = '\x02\x00\x00\x01\x03\x00'

    def __init__( self, context ):
        self.connection = None
        self.deviceHandle = None
        self.lastError = ''
        self.timeout = 1000
        self.lastWriteByteCount = 0
        self.interface = 0
        self.isOpen = 0
        self.QCmdEP = 0
        self.QCmdEPSize = 64

        self.Manufacturer = ""
        self.Product = ""
        self.SerialNumber = ""
        self.VenderId = 0
        self.ProductId = 0

        self.idnFamily = ""
        self.idnName = ""
        self.idnPartNo = ""
        self.idnProcessor = ""
        self.idnBootLoader = ""
        self.idnFPGA = ""
        self.idnSerialNumber = ""
        self.idnEnclosure = ""

        self.iPartNo = 0
        self.iVersionHi = 0
        self.iVersionLow = 0

        self.usbContext = context
        self.last_command_time = timer()

    def __del__( self ):
        self.ClosePort()
        self.connection = None

    # sets the timout value used for USB messaging in ms
    def SetTimeout( self, timeout ):
        self.timeout = timeout

    # TODO: This is a very strange parser.  Each IDN response line is in standard form and should be split into lines and each line parsed
    # by checking its string.  This method will fail for newer module with larger number of IDN string, or different ordering
    def GetIdn( self ):
        state = 0
        item = 0
        val1 = ""

        idn = self.RunCommand( '*idn?' )
        for c in idn:
            if state == 0:
                if c == ":":                # skip until ':'
                    state = 1
            elif state == 1:                # skip spaces
                if c != " ":
                    state = 2
                    val1 = c                # first character of data
            elif state == 2:
                if c in "\r\n":             # end of string
                    if item == 0:
                        self.idnFamily = val1
                    if item == 1:
                        self.idnName = val1
                    if item == 2:
                        self.idnPartNo = val1
                    if item == 3:
                        self.idnProcessor = val1
                    if item == 4:
                        self.idnBootLoader = val1
                    if item == 5:
                        self.idnFPGA = val1
                    if item == 6:
                        self.idnSerialNumber = val1
                    if item == 7:
                        self.idnEnclosure = val1

                    item = item + 1
                    state = 0
                else:
                    val1 = val1 + c         # build string

        if self.idnPartNo != "":            # extract numeric representation of part # from string
            try:
                self.iPartNo = int( self.idnPartNo[3:self.idnPartNo.index('-')] )
            except:
                self.iPartNo = -1

        if self.idnProcessor != "":         # extract numeric representation of Version Hi.Low
            try:
                self.iVersionHi = int( self.idnProcessor[self.idnProcessor.index(',') +1:self.idnProcessor.index('.')] )
            except:
                self.iVersionHi = -1
            try:
                self.iVersionLow = int( self.idnProcessor[self.idnProcessor.index('.') +1:] )
            except:
                self.iVersionLow = -1

    def GetExtendedInfo( self ):
        try:
            self.Manufacturer = self.connection.getManufacturer()
        except Exception as e:
            logging.debug(e)
            self.Manufacturer = "Error"

        try:
            self.Product = self.connection.getProduct()
        except Exception as e:
            logging.debug(e)
            self.Product = "Error"
        try:
            self.SerialNumber = self.connection.getSerialNumber()
        except Exception as e:
            logging.debug(e)
            self.SerialNumber = "Error"
        self.VenderId = self.connection.device_descriptor.idVendor
        self.ProductId = self.connection.device_descriptor.idProduct

        if self.IsPortOpen():
            self.GetIdn()

    # opens a USB connection to the Quarch device and locks the device into USB mode
    def OpenPort(self):
        if self.connection == None:
            self.lastError = 'Open: device Not Assigned'
            return 0

        self.deviceHandle = self.connection.open()

        if self.deviceHandle is not None:
            # don't know if this linux/kernal check is required!
            if platform.system() == 'Linux':
                if self.deviceHandle.kernelDriverActive( self.interface ):
                    self.deviceHandle.detachKernelDriver( self.interface )

            self.deviceHandle.claimInterface( self.interface )

            # Existing Quarch code loops to the final EP and uses it for commands, this code block recreates the process
            quarchEP = 0
            for config in self.connection.iterConfiguations():
                if config.getConfigurationValue() == 1:
                    for intf in config.iterInterfaces():
                        for intfsetting in intf.iterSettings():
                            if intfsetting.getNumber() == 0:
                                for ep in intfsetting.iterEndpoints():
                                    epAddr = ep.getAddress()
                                    if (epAddr > quarchEP) and (epAddr < 0x80):
                                        quarchEP = epAddr

            if quarchEP != 0:
                self.QCmdEP = quarchEP          # should be 2 for PPM, 1 for all others

            self.QCmdEPSize = self.connection.getMaxPacketSize(self.QCmdEP )
            if self.QCmdEPSize > 64:
                self.isOpen = 1
            else:

                try:
                    # attempt unLock before Lock to free previously disconnected devices
                    if sys.version[0] == '3':
                        self.lastWriteByteCount = self.deviceHandle.bulkWrite( endpoint= self.QCmdEP, data=self.unlockUSBStr.encode('utf-8'), timeout=self.timeout )
                    else:
                        self.lastWriteByteCount = self.deviceHandle.bulkWrite( endpoint= self.QCmdEP, data=self.unlockUSBStr, timeout=self.timeout )
                    retLineStr = self.deviceHandle.bulkRead( self.QCmdEP, self.QCmdEPSize, self.timeout )
                    if sys.version[0] == '3':
                        self.lastWriteByteCount = self.deviceHandle.bulkWrite( endpoint= self.QCmdEP, data=self.lockUSBStr.encode('utf-8'), timeout=self.timeout )
                    else:
                        self.lastWriteByteCount = self.deviceHandle.bulkWrite( endpoint= self.QCmdEP, data=self.lockUSBStr, timeout=self.timeout )
                except:
                    self.lastError = 'Open: Lock Write Fail'
                    return 0

                try:
                    retLineStr = self.deviceHandle.bulkRead( self.QCmdEP, self.QCmdEPSize, self.timeout )
                except:
                    self.lastError = 'Open: Lock Read Reply Fail'
                    return 0

                try:
                    if format(retLineStr[2], '02x') != '01':
                        self.lastError = 'Open: Failed to Lock Device'
                        return 0
                    else:
                        self.lastError = ''
                        self.isOpen = 1
                except: # To make connection backwards compatable
                    if retLineStr[2] != '\x01':
                        self.lastError = 'Open: Failed to Lock Device'
                        return 0
                    else:
                        self.lastError = ''
                        self.isOpen = 1
            self.GetExtendedInfo()
            return 1
        else:
            self.lastError = 'Open: Get Device Handle Failed'
            return 0

    # closes the USB connection to the Quarch device after first unlocking the device from USB mode
    def ClosePort(self):



        if self.deviceHandle is not None:
            if not self.QCmdEPSize > 64:  # If this is and Pic32
                try:
                    if sys.version[0] == '3':
                        self.lastWriteByteCount = self.deviceHandle.bulkWrite(endpoint=self.QCmdEP,
                                                                              data=self.unlockUSBStr.encode('utf-8'),
                                                                              timeout=self.timeout)
                    else:
                        self.lastWriteByteCount = self.deviceHandle.bulkWrite(endpoint=self.QCmdEP, data=self.unlockUSBStr,
                                                                              timeout=self.timeout)
                except:
                    self.lastError = 'Close: Unlock Write Fail'
                    return 0

                try:
                    retLineStr = self.deviceHandle.bulkRead(self.QCmdEP, self.QCmdEPSize, self.timeout)

                    if sys.version[0] == '2':
                        if retLineStr[2] != '\x01':
                            self.lastError = 'Close: Failed to Unlock Device'
                    else:
                        if format(retLineStr[2], '02x') != '01':
                            self.lastError = 'Close: Failed to Unlock Device'

                except:
                    self.lastError = 'Close: Unlock Read Reply Fail'
                    return 0

            try:

                self.deviceHandle.releaseInterface(self.interface)

            except:

                self.lastError = 'Close: Device Close Failed'
                return 0

            self.lastError = ''
            self.isOpen = 0
            self.deviceHandle = None
            return 1


        else:
            self.lastError = 'Close: Device Was Not Open'
            return 0

    def IsPortOpen(self):
        return self.isOpen

    def SendCommand( self, command ):
        if self.isOpen == 0:
            logging.debug(os.path.basename(__file__) + ".SendCommand: Device is not open, cannot send!")
            self.lastError = 'RunCommand: Device Not Open'
            return -1
        try:
            pad = '\0' * (64 - len(command))
            if sys.version[0] == '3':                
                self.lastWriteByteCount = self.deviceHandle.bulkWrite( endpoint= self.QCmdEP, data= (str(command + pad)).encode('utf-8'), timeout=self.timeout )
            else:
                self.lastWriteByteCount = self.deviceHandle.bulkWrite( endpoint= self.QCmdEP, data= command + pad, timeout=self.timeout )
            return self.lastWriteByteCount
        except:
            logging.error(os.path.basename(__file__) + ".SendCommand: Exception during bulkWrite process")
            return -1

    def BulkReadEPTout( self, ep, n, timeOut ):
        try:
            return self.deviceHandle.bulkRead( ep, n, timeOut )
        except:
            logging.error(os.path.basename(__file__) + ".BulkReadEPTout: Exception during bulkRead process")
            return ''

    def BulkReadEP( self, ep, n ):
        return self.BulkReadEPTout( ep, n, self.timeout )

    def BulkRead( self ):
        return self.BulkReadEP( self.QCmdEP, self.QCmdEPSize )

    def BulkReadN( self, n ):
        try:

            return self.BulkReadEP( self.QCmdEP, n )
        except:
            return ''

    def WriteZeroPacketCmd( self ):
        try:
            if sys.version[0] == '3':
                return self.deviceHandle.bulkWrite( self.QCmdEP, bytes('',encoding='utf-8'), 0 )
            else:
                return self.deviceHandle.bulkWrite( self.QCmdEP, 0, 0 )
        except:
            return ''

    def clean_and_flush_stuck_usb_comms (self):
        """
        USB comms can become stuck if a command is sent out too quickly after the end of the previous one
        If this is the case, the module response buffer contains data which needs flushed. This command
        triggers a buffer return and performs a full read of all data.  If  possible, it returns the 
        response of the previous command which caused the stuck buffer.
        
        """

        response = ''
        flushed_response = ''

        # Send a command packet, to force the command processer to restart. Junk command used so it will return FAIL.... on all modules
        bytes_written = self.SendCommand ("HEZZ0?")

        # Loop until all data is read back
        while True:
            # Read a response line, using a fixed (short) timeout as no uncertain command processing will be required on the module
            # Keep reading until we hit a timeout (meaning no more to return). Split off the data before the first '>' which should 
            # be the response to the last command which failed to return
            try:
                retLineStr = self.deviceHandle.bulkRead( self.QCmdEP, self.QCmdEPSize, 250 )            
            except Exception as ex:                
                break

            if sys.version[0] == '3':
                retLineStr = retLineStr.decode('utf-8').strip('\0').strip() + ('\r\n')
            else:
                retLineStr = retLineStr.strip('\0').strip() + '\r\n'
            
            # Exit if we find the cursor (confirmed last packet)
            pos = retLineStr.find('>')
            if (pos == -1):
                # Add response line to response string
                response = response + retLineStr
            else:
                flushed_response = response

        # Sometimes the cursor from the flushed command may be missing, causing the real and junk response to be concatenated here.
        # Find and cut off any appended FAIL... to handle this
        pos = flushed_response.rfind('FAIL')
        if (pos > 0):
            flushed_response = flushed_response[0:pos]
        else:
            flushed_response = ""
        return flushed_response

    def FetchCmdReplyTOut( self, timeout ):
        response = ''
        self.lastError = ''
        retLineStr = ''

        # Loop until response is complete
        while True:
            # Read response line
            try:
                retLineStr = self.deviceHandle.bulkRead( self.QCmdEP, self.QCmdEPSize, timeout )
            # Exception can be due to device connection lost, or a temporary glitch that we can recover from
            except Exception as ex:
                logging.error(os.path.basename(__file__) + ".FetchCmdReplyTOut: bulkRead exception (" + str(ex) + ") during response read: " + response)
                
                # Run a cleanup process and see if we can recover the response
                flushed_response = self.clean_and_flush_stuck_usb_comms ()
                if flushed_response != "":
                    response = flushed_response


                self.lastError = 'Run: Read Error'
                break
            if sys.version[0] == '3':
                retLineStr = retLineStr.decode('utf-8').strip('\0').strip() + ('\r\n')
            else:
                retLineStr = retLineStr.strip('\0').strip() + '\r\n'

            # Add response line to response string
            if (retLineStr.find('>\r\n') == 0):
                break
            else:
                response = response + retLineStr    # we need to remove '>' char
                                                    # Exit if we find the cursor (confirmed last packet)

        return response

    def FetchCmdReply( self ):
        return self.FetchCmdReplyTOut( self.timeout )

    # sends command to device.
    #   on success: returns the device response
    #   on error: returns ''
    def RunCommand( self, command, expectedResponse = True ):      #, timeout ):

        # Track the time since we last sent a command to this module
        if (timer() - self.last_command_time < 0.015):
            time.sleep (0.015)

        # Transmit the command
        length = self.SendCommand( command )
        if  length == -1:
            logging.error(os.path.basename(__file__) + ".RunCommand: SendCommand failed for command: " + command)
            return ''
        elif (length != 64):
            logging.error(os.path.basename(__file__) + ".RunCommand: Unexpected number of bytes reported as sent")

        if expectedResponse:
            # Read all the data back
            rep_str = self.FetchCmdReply()
        else:
            return
        # Note the time the command completed, so we can track the minimum delay
        self.last_command_time = timer()
        return rep_str

    def VerboseSendCmd( self, cmd ):
        print (cmd),
        print (" --" + self.RunCommand( cmd )),

    # issues a Quarch standard 'hello?' command to the attached device and verifies a reply is received
    def CheckComms(self):
        if self.isOpen:
            response = self.RunCommand( 'hello?' )
            if response == '':
                self.lastError = 'CheckComms: No Reply From Device'
                return 0
            else:
                self.lastError = ''
                return 1
        else:
            self.lastError = 'CheckComms: Device Connection is Not Open'
            return 0

    # return the error generated by the last function to return a 0, or '' in the case of RunCommand
    def GetLastError(self):
        return self.lastError


    #
    # Helper to return serial number
    #
    def GetSerialNumber(self):
        
        try:
            NeedToClose = False
            serialNum = str(self.connection.getSerialNumber())

            if serialNum in serialDict:
                retString = serialDict[serialNum]

            else:
                if '1944' in serialNum or '2098' in serialNum:

                    if (self.isOpen == False):
                        self.OpenPort()
                        NeedToClose = True                    
        
                    dump = self.idnEnclosure
                    retString = self.idnEnclosure
                            
                    if (NeedToClose == True):
                        pass
                        #self.ClosePort()
                    
                    serialDict[serialNum] = retString
                
                else:
                    serialDict[serialNum] = serialNum
                    retString = serialNum
        except:
            retString = None
                
        return retString


    def DebugDump( self ):
        if self.connection == None:
            self.lastError = 'DebugDump: device Not Assigned'
            return 0

        print ('device_descriptor       ', self.connection.device_descriptor)
        print ('')
        print ('     bLength            ', self.connection.device_descriptor.bLength)
        print ('     bDescriptorType    ', self.connection.device_descriptor.bDescriptorType)
        print ('     bcdUSB             ', self.connection.device_descriptor.bcdUSB)
        print ('     bDeviceClass       ', self.connection.device_descriptor.bDeviceClass)
        print ('     bDeviceSubClass    ', self.connection.device_descriptor.bDeviceSubClass)
        print ('     bDeviceProtocol    ', self.connection.device_descriptor.bDeviceProtocol)
        print ('     bMaxPacketSize0    ', self.connection.device_descriptor.bMaxPacketSize0)
        print ('     idVendor            %04x' % self.connection.device_descriptor.idVendor)
        print ('     idProduct           %04x' % self.connection.device_descriptor.idProduct)
        print ('     bcdDevice          ', self.connection.device_descriptor.bcdDevice)
        print ('     iManufacturer      ', self.connection.device_descriptor.iManufacturer)
        print ('     iProduct           ', self.connection.device_descriptor.iProduct)
        print ('     iSerialNumber      ', self.connection.device_descriptor.iSerialNumber)
        print ('     bNumConfigurations ', self.connection.device_descriptor.bNumConfigurations)

        print ('')
        print ('Port List :             ', self.connection.getPortNumberList())
        print ('getDeviceAddress        ', self.connection.getDeviceAddress())
        print ('getMaxPacketSize0       ', self.connection.getMaxPacketSize0())
        print ('getMaxPacketSize 1      ', self.connection.getMaxPacketSize( 1 ))
        print ('getMaxISOPacketSize 1   ', self.connection.getMaxISOPacketSize( 1 ))
        print ('getDeviceSpeed          ', self.connection.getDeviceSpeed())

        self.GetExtendedInfo()

        print ('')
        print ('Manufacturer            ', self.Manufacturer)
        print ('Product                 ', self.Product)
        print ('SerialNumber            ', self.SerialNumber)

        self.lastError = ''
        return 1

class USBConn:
    def __init__(self, ConnTarget):
        
        self.Connection = USB(ConnTarget)
        if self.Connection is None:
            raise ValueError("The requested module is not connected to this system.")

    def close(self):
        self.Connection.ClosePort()
        return True
    
    def sendCommand(self, Command, expectedResponse = True):
        Result = self.Connection.RunCommand(Command, expectedResponse)
        if expectedResponse:
            #endPos = Result.find('>') # This is clipped at a lower level to allow for XML data
            #Result = Result[0:endPos]
            Result = Result.strip()
            return Result
        else:
            pass

