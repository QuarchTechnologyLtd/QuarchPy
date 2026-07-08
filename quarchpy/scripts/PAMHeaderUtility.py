'''
Mikes Script to Generate a PAM Fixture Header

This script is lacking in input validation and the strings are all case sensitive
'''

__version__ = "1.1"

# Change History

# unversioned before 1.0

# 24/01/24 1.0 adds support for High Byte Power Control, and Fixed Shunt Values
# Both of these apply to external shunt PAM fixtures from FPGA 1.3 onwards

# Import other libraries used in the examples
import sys
import time
import math
from tkinter import filedialog
from tkinter import *
import argparse

import quarchpy
from quarchpy.device import userSelectDevice, quarchDevice
from quarchpy.user_interface import *
from quarchpy.utilities import TestCenter
import quarchpy.user_interface.user_interface

# Devices that will show up in the module scan dialog
scanFilterStr = ["QTL1999", "QTL1995", "QTL1944", "QTL2312","QTL2098","QTL3178","QTL3305","QTL3311"]

# Global variables
ui_mode = 'console'  # console by default

''' 
Opens the connection, call the selected example function(s) and closes the connection.
The constructor opens the connection by default.  You must always close a connection before you exit
'''
def main(args=[]):

    while True:

        printText("Quarch Header Utility v" + __version__ + "\n")
        actionList = [["Generate", "Generate an Address Hex file for Lattice Diamond"],
                      ["Program", "Program a PAM Fixture EEPROM"], ["Erase", "Erase a Pam Fixture EEPROM"],
                      ["Quit", "Quit"]]
        if args.ac == "":
            action = listSelection("Select an action", "Please select an action to perform", actionList, nice=True, tableHeaders=["Option", "Description"], indexReq=True)[1]
        else:
            action = args.ac
        if action == "Generate":
            generateHex(args.dfp, args.fp)
        elif action == "Program":
            device = args.dfp
            if device == "":
                device = requestDialog("Please input the PAM's serial number, leave blank for module selection screen")
            if device != "":
                device = "USB:" + device # assumes usb connection
            if args.userMode == "testcenter":
                logSimpleResult("Header Filepath: " + args.fp, True)
            ui_mode = args.userMode
            programHeader(device, args.ow, args.fp, args.ser)
        elif action == "Erase":
            device = args.dfp
            if device == "":
                device = requestDialog("Please input the PAM's serial number, leave blank for module selection screen")
            if device != "":
                device = "USB:" + device # assumes usb connection
            if args.userMode == "testcenter":
                logSimpleResult("Header Filepath: " + args.fp, True)
            ui_mode = args.userMode
            eraseHeader(device, args.ow, args.fp, args.ser)
        elif action == "Quit":
            return
        else:
            printText("Option not recognised, please re-enter")
        if args.ow != "":
            break

'''
'''
class Descriptor:

    appliesTo = ""
    words = []
    success = False

    def __init__(self, inputFile, carrierSerial=None, device=None):

        # --- NEW: Data structures for validation ---
        class DescriptorRequirements:
            VERSION_REQUIREMENTS = {
                0: {"Applies to", "Carrier Product", "Carrier Version", "Base Sample Rate (Hz)", "Product Name",
                    "Group", "Channel"},
                1: {"Applies to", "Carrier Product", "Carrier Version", "Carrier Serial", "Product Name", "Group",
                    "Channel"},
                2: {"Applies to", "Carrier Product", "Carrier Version", "Carrier Serial", "Architecture",
                    "Product Name", "Group", "Channel", "Power Control Supported", "Channel Enables Supported"}
            }
            EXTERNAL_SHUNT_REQUIREMENTS = {"Fixed Shunts", "High Byte Power Control"}

        # -------------------------------------------

        # Prompt for filename
        printText("\n>>> Select a quarch header text file")
        # Request user to select a jtag file
        root = Tk()
        root.withdraw()

        if inputFile == "":
            inputFile = filedialog.askopenfilename(initialdir="P:/CPLD/", title="Select text file",
                                                   filetypes=(("Quarch Header Description files", "*.txt"),
                                                              ("all files", "*.*")))
        else:
            self.inputFile = inputFile

        programData = ""
        # If nothing was selected
        if inputFile == "":
            printText("Input file dialog cancelled")
            return

        f = open(inputFile, "r")
        s = f.read()
        # all fields are on seperate lines
        lines = s.split("\n")

        headerVersion = 1
        architecture = ""
        groups = []
        channels = []
        shunts = []
        stringTable = []
        channelEnables = False
        powerControl = False
        fixedShunts = False
        highBytePowerControl = False

        # --- NEW: Track keys found in the file ---
        found_keys = set()

        for x in lines:
            # remove all leading and trailing white space / carriage return / newline
            x = str(x).strip()
            # x is now one line
            # ignore blank lines and comments
            if x != '' and x[0] != "#":
                # split the line on :
                tokens = x.split(":")

                # --- NEW: Normalize aliased keys and add to found set ---
                key = tokens[0].strip()
                if key == "Product": key = "Carrier Product"
                if key == "Version": key = "Carrier Version"
                found_keys.add(key)

                if tokens[0] == "Header Version":
                    headerVersion = int(tokens[1])
                    printText("Header Version:" + str(headerVersion))

                # Applies to is checked against the fixture FPGA part number
                elif tokens[0] == "Applies to":
                    self.appliesTo += tokens[1]
                    # Strip the QTL if it's there:
                    if self.appliesTo[:3] == "QTL":
                        self.appliesTo = self.appliesTo[3:]
                    printText("Applies to:" + str(self.appliesTo))

                # Architecture is used to distinguish between 2 channel, 4 channel and external shunt Fixtures
                elif tokens[0] == "Architecture":
                    if headerVersion < 2:
                        printText("Architecture is not supported in headers ealier than version 2")
                    elif tokens[1] not in ["2-Channel", "4-Channel", "External Shunt", "USB-C", "Other"]:
                        printText("Architecture line not valid:" + x)
                    else:
                        architecture = tokens[1]
                        printText("Architecture:" + architecture)

                # Carrier Product and Carrier Part are valid for all header versions
                elif tokens[0] == "Product" or tokens[0] == "Carrier Product":
                    productNumber = tokens[1]
                    printText("Product:" + productNumber)
                elif tokens[0] == "Version" or tokens[0] == "Carrier Version":
                    versionNumber = tokens[1]
                    printText("Version:" + versionNumber)

                # Carrier Serial is valid for headers from version 1
                elif tokens[0] == "Carrier Serial":
                    if headerVersion < 1:
                        printText("Carrier Serial is not supported in headers earlier than version 1")
                    else:
                        # If no serial is provided then take whatever the file specifies
                        if (carrierSerial is None or not carrierSerial.startswith("QTL")):
                            serialNumber = tokens[1]
                            if serialNumber == 'FFFF':
                                if device is not None:
                                    serialNumber = device.sendCommand("fix serial?")
                                if 'QTL' not in serialNumber:
                                    serialNumber = requestDialog("Unable to get the carrier serial number.",
                                                                 "Please provide the carrier serial number or leave blank to clear.\r\nThis is the product serial number of the board the mezzanine is plugged into\r\n in the form QTLxxxx-xx-xxx")
                                    if serialNumber == '':
                                        serialNumber = 'FFFF'
                                    else:
                                        serialSection = serialNumber.split("-")[-1]
                                        serialNumber = serialSection.zfill(4)
                                else:
                                    serialSection = serialNumber.split("-")[-1]
                                    serialNumber = serialSection.zfill(4)
                            printText("Serial:" + serialNumber)
                        else:
                            printText("Carrier Serial supplied was: " + carrierSerial)
                            # Pad the section to 4 chars long
                            serialSection = carrierSerial.split("-")[-1]
                            serialNumber = serialSection.zfill(4)
                            printText("Serial:" + serialNumber)

                # Base Sample rate is only valid for version 0
                elif tokens[0] == "Base Sample Rate (Hz)":
                    if headerVersion > 0:
                        printText("Base Sample Rate is not supported in headers later than version 0")
                    else:
                        baseSampleRate = int(tokens[1])
                        printText("Base Sample Rate (Hz):" + str(baseSampleRate))

                # Product Name
                elif tokens[0] == "Product Name":
                    productName = tokens[1]
                    stringTable.append(productName)
                    printText("Product Name:" + productName)

                # Groups
                elif tokens[0] == "Group":
                    params = tokens[1].split(",")
                    groups.append(params)
                    printText("Group:" + str(params))

                # Channels
                elif tokens[0] == "Channel":
                    params = tokens[1].split(",")
                    channels.append(params)
                    # add the channel name to the string table if it isn't already there
                    if params[0] in stringTable:
                        pass
                    else:
                        stringTable.append(params[0])
                    # add the units to the string table if they aren't already there
                    if params[1] in stringTable:
                        pass
                    else:
                        stringTable.append(params[1])
                    printText("Channel:" + str(params))

                # Shunts
                elif tokens[0] == "Shunt":
                    params = tokens[1].split(",")
                    shunts.append(params)
                    printText("Shunt:" + str(params))

                # The Power Control bit is valid for headers from version 2
                elif tokens[0] == "Power Control Supported":
                    if headerVersion < 2:
                        printText("Power Control is not supported in headers ealier than version 2")
                    elif tokens[1] not in ["Y", "N"]:
                        printText("Power Control line not valid:" + x)
                    else:
                        if tokens[1] == "Y":
                            powerControl = True
                        else:
                            powerControl = False
                        printText("Power Control: " + str(powerControl))

                # The Channel Enables bit is valid for headers from version 2
                elif tokens[0] == "Channel Enables Supported":
                    if headerVersion < 2:
                        printText("Channel Enables are not supported in headers ealier than version 2")
                    elif tokens[1] not in ["Y", "N"]:
                        printText("Channel Enable line not valid:" + x)
                    else:
                        if tokens[1] == "Y":
                            channelEnables = True
                        else:
                            channelEnables = False
                        printText("Channel Enables: " + str(channelEnables))

                # The Fixed Shunt bit is valid for headers from version 2
                elif tokens[0] == "Fixed Shunts":
                    if headerVersion < 2 or architecture != "External Shunt":
                        printText(
                            "Fixed Shunts are not supported in headers ealier than version 2 or on fixtures other than external shunt")
                    elif tokens[1] not in ["Y", "N"]:
                        printText("Fixed Shunts line not valid:" + x)
                    else:
                        if tokens[1] == "Y":
                            fixedShunts = True
                        else:
                            fixedShunts = False
                        printText("Fixed Shunts: " + str(fixedShunts))

                # The High Byte Power Control bit is valid for headers from version 2
                elif tokens[0] == "High Byte Power Control":
                    if headerVersion < 2 or architecture != "External Shunt":
                        printText(
                            "High Byte Power Control is not supported in headers ealier than version 2 or on fixtures other than external shunt")
                    elif tokens[1] not in ["Y", "N"]:
                        printText("High Byte Power Control line not valid:" + x)
                    else:
                        if tokens[1] == "Y":
                            highBytePowerControl = True
                        else:
                            highBytePowerControl = False
                        printText("High Byte Power Control: " + str(highBytePowerControl))

                else:
                    printText("Line not recognised:" + x)

        # --- NEW: Validate required fields based on Header Version ---
        if headerVersion in DescriptorRequirements.VERSION_REQUIREMENTS:
            required_keys = DescriptorRequirements.VERSION_REQUIREMENTS[headerVersion]
            missing_keys = required_keys - found_keys

            if missing_keys:
                printText(
                    f"\nERROR: Description file missing required fields for v{headerVersion}:\n  -> {', '.join(missing_keys)}\n")
                self.success = False
                return  # Halt parsing
        else:
            printText(f"\nERROR: Unsupported Header Version {headerVersion}\n")
            self.success = False
            return

        # --- NEW: Validate conditional fields (e.g., External Shunt) ---
        if headerVersion >= 2 and architecture == "External Shunt":
            missing_conditional = DescriptorRequirements.EXTERNAL_SHUNT_REQUIREMENTS - found_keys
            if missing_conditional:
                printText(
                    f"\nERROR: Description file missing required fields for External Shunt architecture:\n  -> {', '.join(missing_conditional)}\n")
                self.success = False
                return
        # -------------------------------------------------------------

        # concatenate all strings and terminate them all with a null character
        stringTable = "\0".join(stringTable)
        stringTable += "\0"

        if headerVersion == 0:

            # Add Header Version
            versionReg = 0x0000

            # add Carrier Product Number (convert int to BCD)
            self.words.append(int(productNumber[0],16)*2**12 + int(productNumber[1],16)*2**8 + int(productNumber[2],16)*2**4 + int(productNumber[3],16))

            # add Carrier Version (convert int to BCD)
            self.words.append(int(versionNumber[0],16)*2**12 + int(versionNumber[1],16)*2**8 + int(versionNumber[2],16)*2**4 + int(versionNumber[3],16))

            # add Base Sample Rate
            ## first word is 4 digit Coefficient (A in AX10^B)
            ## how many times do we need to divide the sample rate by 10 before it fits in one word ( <= 65535 )
            coefficient = int(baseSampleRate)
            exponent = 0
            while coefficient > ((2**16)-1):
                exponent += 1
                coefficient = coefficient/10
            coefficient = int(coefficient)
            self.words.append(coefficient)
            self.words.append(exponent)

            # add channel count
            self.words.append(len(channels))
        
            # add channels
            for thisChannel in channels:
                # add name index
                self.words.append(stringTable.index("\0" + thisChannel[0] + "\0")+1)
                # add units index
                self.words.append(stringTable.index("\0" + thisChannel[1] + "\0")+1)
                # add group/precision/width
                group = int(thisChannel[2])
                precision = int(thisChannel[3])
                # if precision is negative, turn it to 16 bit two's complement
                if precision < 0:
                    precision = 16 + precision
                width = int(thisChannel[4])
                self.words.append(int((group*(2**12)) + (precision*(2**8)) + width))
            
            # add name string size
            self.words.append(len(stringTable))

            # add name string
            # iterate through each pair of characters in the table
            for i in range(0,len(stringTable)-1,2):
                word = ord(stringTable[i])*2**8 + ord(stringTable[i+1])
                self.words.append(word)
            # if there is an odd character)
            if len(stringTable) % 2 == 1:
               word = ord(stringTable[-1:])*2**8
               self.words.append(word)
            self.success = True;

        elif headerVersion == 1:

            # Add Header Version
            versionReg = 0x0001
            self.words.append(versionReg)

            # add Carrier Product Number (convert int to BCD)
            self.words.append(int(productNumber[0],16)*2**12 + int(productNumber[1],16)*2**8 + int(productNumber[2],16)*2**4 + int(productNumber[3],16))

            # add Carrier Version (convert int to BCD)
            self.words.append(int(versionNumber[0],16)*2**12 + int(versionNumber[1],16)*2**8 + int(versionNumber[2],16)*2**4 + int(versionNumber[3],16))

            # add Carrier Serial (Usually 0xFFFF) (convert int to BCD)
            self.words.append(int(serialNumber[0],16)*2**12 + int(serialNumber[1],16)*2**8 + int(serialNumber[2],16)*2**4 + int(serialNumber[3],16))

            # add Group Count
            result = len(groups)
            self.words.append(result)

            # add Implemented word for each group
            # run through channel data and add a '0' or a '1' for each channel depending on implemented status
            # create implemented array with an entry for each group
            implemented = [0]*len(groups) # creates an array with leng(groups) with each entry set to 0
            index = [0]*len(groups)
            for thisChannel in channels:
                channelGroup = int(thisChannel[2])
                # check the group is valid
                if channelGroup < len(groups):
                    # look for "nN" so assume a channel is implemented unless we see that it isn't
                    if thisChannel[5].lower() != "n":
                        # set the appropriate channel bit
                        implemented[channelGroup] = setBit(implemented[channelGroup],index[channelGroup])
                    # increment the bit index
                    index[channelGroup] += 1
                else:
                    printText("invalid group in channel data")
            for thisGroup in groups:
                self.words.append(implemented[int(thisGroup[0])])

            # add Sample Rate for each group
            for thisGroup in groups:
                ## add Group Sample Rate
                ## first word is 4 digit Coefficient (A in AX10^B)
                ## how many times do we need to divide the sample rate by 10 before it fits in one word ( <= 65535 )
                coefficient = int(thisGroup[1])
                exponent = 0
                while coefficient > ((2**16)-1):
                    exponent += 1
                    coefficient = coefficient/10
                coefficient = int(coefficient)
                self.words.append(coefficient)
                self.words.append(exponent)
        
            # add channels
            for thisChannel in channels:
                # If this channel is implemented
                if thisChannel[5].lower() != "n":
                    # add name index
                    self.words.append(stringTable.index("\0" + thisChannel[0] + "\0")+1)
                    # add units index
                    self.words.append(stringTable.index("\0" + thisChannel[1] + "\0")+1)
                    # add group/precision/width
                    group = int(thisChannel[2])
                    precision = int(thisChannel[3])
                    # if precision is negative, turn it to 16 bit two's complement
                    if precision < 0:
                        precision = 16 + precision
                    width = int(thisChannel[4])
                    self.words.append(int((group*(2**12)) + (precision*(2**8)) + width))

            # add name string size
            self.words.append(len(stringTable))

            # add name string
            # iterate through each pair of characters in the table
            for i in range(0,len(stringTable)-1,2):
                word = ord(stringTable[i])*2**8 + ord(stringTable[i+1])
                self.words.append(word)
            # if there is an odd character)
            if len(stringTable) % 2 == 1:
               word = ord(stringTable[-1:])*2**8
               self.words.append(word)
            self.success = True;

        elif headerVersion == 2:

            # Add Header Version and Architecture
            versionReg = 0x0002
            if architecture == "4-Channel":
                versionReg += 0x0100
            elif architecture == "External Shunt":
                versionReg += 0x0200
            elif architecture == "USB-C":
                versionReg += 0x0300
            self.words.append(versionReg)

            # add Carrier Product Number (convert int to BCD)
            self.words.append(int(productNumber[0],16)*2**12 + int(productNumber[1],16)*2**8 + int(productNumber[2],16)*2**4 + int(productNumber[3],16))

            # add Carrier Version (convert int to BCD)
            self.words.append(int(versionNumber[0],16)*2**12 + int(versionNumber[1],16)*2**8 + int(versionNumber[2],16)*2**4 + int(versionNumber[3],16))

            # add Carrier Serial (Usually 0xFFFF) (convert int to BCD)
            self.words.append(int(serialNumber[0],16)*2**12 + int(serialNumber[1],16)*2**8 + int(serialNumber[2],16)*2**4 + int(serialNumber[3],16))

            # add Group Count and optional features
            result = len(groups) # group count is in bits 3..0
            if powerControl == True:
                result += 2**4 # set bit 4
            if channelEnables == True:
                result += 2**5  # set bit 5
            if fixedShunts == True:
                result += 2**6  # set bit 6
            if highBytePowerControl == True:
                result += 2**7  # set bit 7
            self.words.append(result)

            # add Implemented word for each group
            # run through channel data and add a '0' or a '1' for each channel depending on implemented status
            # create implemented array with an entry for each group
            implemented = [0]*len(groups) # creates an array with leng(groups) with each entry set to 0
            index = [0]*len(groups)
            for thisChannel in channels:
                channelGroup = int(thisChannel[2])
                # check the group is valid
                if channelGroup < len(groups):
                    # look for "nN" so assume a channel is implemented unless we see that it isn't
                    if thisChannel[5].lower() != "n":
                        # set the appropriate channel bit
                        implemented[channelGroup] = setBit(implemented[channelGroup],index[channelGroup])
                        
                    # increment the bit index
                    index[channelGroup] += 1
                else:
                    printText("invalid group in channel data")
            for thisGroup in groups:
                self.words.append(implemented[int(thisGroup[0])])

            # add Sample Rate for each group
            for thisGroup in groups:
                ## add Group Sample Rate
                ## first word is 4 digit Coefficient (A in AX10^B)
                ## how many times do we need to divide the sample rate by 10 before it fits in one word ( <= 65535 )
                coefficient = int(thisGroup[1])
                exponent = 0
                while coefficient > ((2**16)-1):
                    exponent += 1
                    coefficient = coefficient/10
                coefficient = int(coefficient)
                self.words.append(coefficient)
                self.words.append(exponent)
        
            # add channels
            for thisChannel in channels:
                # If this channel is implemented
                if thisChannel[5].lower() != "n":
                    # add name index
                    self.words.append(stringTable.index("\0" + thisChannel[0] + "\0")+1)
                    # add units index
                    self.words.append(stringTable.index("\0" + thisChannel[1] + "\0")+1)
                    # add group/precision/width
                    group = int(thisChannel[2])
                    precision = int(thisChannel[3])
                    # if precision is negative, turn it to 16 bit two's complement
                    if precision < 0:
                        precision = 16 + precision
                    width = int(thisChannel[4])
                    self.words.append(int((group*(2**12)) + (precision*(2**8)) + width))

            # add name string size
            self.words.append(len(stringTable))

            # add name string
            # iterate through each pair of characters in the table
            for i in range(0,len(stringTable)-1,2):
                word = ord(stringTable[i])*2**8 + ord(stringTable[i+1])
                self.words.append(word)
            # if there is an odd character)
            if len(stringTable) % 2 == 1:
               word = ord(stringTable[-1:])*2**8
               self.words.append(word)

            # add shunt values, the values use the standard format for resistance 22.7 ohms = "22r7", 3milliohms = "0r003", 10 Megaohms = 10000000r
            for thisChannel in channels:
                # search for this channel in the shunts list
                matches = [sublist for sublist in shunts if sublist[:2] == thisChannel[:2]]
                if len(matches) == 0:
                    # no shunt value found for this channel, add zeros
                    self.words.append(0)
                elif len(matches) > 1:
                    printText("multiple channels found matching shunt " + thisChannel[:2])
                    # error, add zeros
                    self.words.append(0)
                else:
                    this_string = matches[0][2]
                    # check the string comprises only numeric digits and the letter r
                    if all(char.isdigit() or char.lower() == 'r' for char in this_string):
                        fraction = False
                        shunt_value = 0
                        mult = 1
                        for index,char in enumerate(this_string):
                            if char.isdigit():
                                if fraction:
                                    shunt_value = shunt_value + float(char)*mult
                                    mult = mult / 10
                                else:
                                    shunt_value = shunt_value*mult + int(char)
                                    mult = mult * 10
                            else:
                                fraction = True
                                mult = 0.1
                    else:
                        printText("invalid shunt value found " + this_string)

                    # convert resistor value to hex code
                    # get the lsb magnitude and round it
                    lsb = math.log10(shunt_value)
                    # if lsb is positive round up
                    if lsb > 0:
                        lsb = math.ceil(lsb)
                    # if lsb is negative, round down
                    else:
                        lsb = math.floor(lsb)
                    
                    shunt_value = shunt_value / 10**lsb

                    # convert negative lsb to 4 bit 2's complement
                    if lsb < 0:
                        lsb = 16 + lsb

                    hex_value= (int(shunt_value)*2**4) + lsb
                    self.words.append(hex_value)

            self.success = True;

        else:

            printText("This script only supports headers upto version 2")



'''
This function reads a text description of a PAM fixture and converts it into an addressed hex file suitable for Lattice Diamond RAM initialisation
'''
def generateHex(outputFile = "", inputFile = ""):
    
    thisDescriptor = Descriptor(inputFile)
    if thisDescriptor.success == False:
        return

    #outputFile = "P:\CPLD\QTL2529 SFF Drive Power Measurement Fixture\Trunk\Fixture Description.mem"
    if outputFile == "":
        outputFile = filedialog.asksaveasfilename(initialdir = "P:/CPLD/",title = "Select mem file",filetypes = (("Lattice Memory Initialization File","*.mem"),("all files","*.*")))
    # Check if dialog was cancelled
    if outputFile == "":
        printText("Output file dialog cancelled")
        return
    f = open(outputFile,"w",newline='\n')
    f.write("//Generated by PAMHeaderGenerator " + time.asctime() + "\n")
    f.write("#Format=AddrHex" + "\n")
    f.write("#Depth=512" + "\n")
    f.write("#Width=16" + "\n")
    f.write("#AddrRadix=3" + "\n")
    f.write("#DataRadix=3" + "\n")
    f.write("#Data" + "\n")

    newLine = True
    # write words to file
    for i in range(0,len(thisDescriptor.words)):
        # If we're starting a new line
        if newLine == True:
            # write the address first, pad to 3 hex characters
            f.write('{:03x}'.format(i).upper() + ":")
            newLine = False
        #write the word
        f.write('{:04x}'.format(thisDescriptor.words[i]).upper())
        # if we're on the last word of the line
        if ((i + 1) % 16) == 0 or i == len(thisDescriptor.words)-1:
            f.write("\n")
            newLine = True
        else:
            f.write(" ")

#==============================================================================================================

'''
This function reads a text description of a PAM fixture and writes it into a PAM Fixture EEPROM
'''
def programHeader(deviceString = "", response = "", inputFile = "", carrierSerial=None):

    if deviceString == "":
        printText ("Requesting user selection of PAM")
        deviceString = userSelectDevice(scanFilterStr=scanFilterStr, nice=True,message="Select PAM controller")
    if deviceString == "quit":
        sys.exit(0)
    try:
        printText ("Connecting to PAM: " + deviceString)
        myPpmDevice = quarchDevice(deviceString)
        # Test command to make sure we are working
        response = myPpmDevice.sendCommand ("conf def state")
        if not response.startswith ("OK"): 
            logSimpleResult("PAM communication check", "false")
        else:
            logSimpleResult("PAM communication check", "true")
        # Check the Mezzanine is present
        response = myPpmDevice.sendCommand ("read 0xafff")
        if "0x0000" in response:
            logSimpleResult("Mezzanine communication check", "false")
            raise ValueError("Mezzanine communication check failed, exiting")
        else:
            logSimpleResult("Mezzanine communication check", "true")
    except:
        printText("Failed to connect to "+str(deviceString))
        logSimpleResult("PAM communication check", "false")
        if ui_mode == "testcenter":
            logSimpleResult("Failed to connect to "+str(deviceString), False)
        sys.exit(0)
    thisDescriptor = Descriptor(inputFile, carrierSerial, myPpmDevice)
    printText("Module Selected: " + deviceString)
    # Verify we are connected to the correct fixture
    fixtureId = myPpmDevice.sendCommand("read 0xaffe")[2:]
    fileId = thisDescriptor.words[1]
    # if fixtureId not in thisDescriptor.appliesTo:
    #     printText("This description file does not support the current part number: QTL" + '{:04X}'.format(int(fixtureId,16)))
    #     if response != "Yes":
    #         response = showYesNoDialog("","Would you like to overwrite the fixture?")
    #     if response != "Yes":
    #         printText("Exiting.......")
    #         return
    # Disable fixture write protection
    myPpmDevice.sendCommand("write 0xa100 0xaa55")
    myPpmDevice.sendCommand("write 0xa100 0x55aa")

    # Write to the fixture RAM
    printText("writing values to the fixture...")
    for x in range (0, 255):
        # if we have valid data
        if x < len(thisDescriptor.words):
            myPpmDevice.sendCommand("write " + '0x{:4X}'.format(0xa400 + x) + " " + '0x{:04X}'.format(thisDescriptor.words[x]))
        # Else write 0000's
        else:
            myPpmDevice.sendCommand("write " + '0x{:4X}'.format(0xa400 + x) + " 0x0000")
        progressBar(x,254)

    # write the RAM to EEPROM
    printText("\nprogramming EEPROM",end='')
    myPpmDevice.sendCommand("write 0xa200 0x0400")
    myPpmDevice.sendCommand("write 0xa200 0x0000")
    # wait for write to finish
    while(checkBit(myPpmDevice.sendCommand("read 0xa200"),12)):
        time.sleep(1)
        printText(".",end='')
    printText("\nprogram complete")

    #read back from EEPROM and verify

    # read back
    printText("reading back the EEPROM",end='')
    myPpmDevice.sendCommand("write 0xa200 0x0800")
    myPpmDevice.sendCommand("write 0xa200 0x0000")

    # wait for read to finish
    while(checkBit(myPpmDevice.sendCommand("read 0xa200"),12)):
        time.sleep(1)
        printText(".",end='')
    printText("\nread complete")

    Verified = True
    # Read from the fixture RAM
    printText("reading values from the fixture...")
    for x in range (0, 255):
        
        readValue = myPpmDevice.sendCommand("read " + '0x{:4X}'.format(0xa400 + x))

        if x < len(thisDescriptor.words):
            fileValue = '0x{:04X}'.format(thisDescriptor.words[x])
        # Else read 0000's
        else:
            fileValue = '0x{:04X}'.format(0)

        # if we have valid data
        if readValue != fileValue:
            printText("                                                                                                   \r",end='')   # clear the percentage bar
            printText("Verification failure at " + '0x{:4X}'.format(0xa400 + x) + ", read: " + readValue + ", expected: " + fileValue)
            Verified = False
        progressBar(x,254)

    if Verified == True:
        logSimpleResult ("Fixture Verification", "true")
    else:
        logSimpleResult ("Fixture Verification", "false")
        storeResult ("Verification failed on fixture")
        
'''
This function reads a text description of a PAM fixture and writes it into a PAM Fixture EEPROM
'''
def eraseHeader(deviceString = "", response = "", inputFile = "", carrierSerial=None):

    if deviceString == "":
        printText ("Requesting user selection of PAM")
        deviceString = userSelectDevice(scanFilterStr=scanFilterStr, nice=True,message="Select PAM controller")
    if deviceString == "quit":
        sys.exit(0)
    try:
        printText ("Connecting to PAM: " + deviceString)
        myPpmDevice = quarchDevice(deviceString)
        # Test command to make sure we are working
        response = myPpmDevice.sendCommand ("conf def state")
        if not response.startswith ("OK"): 
            logSimpleResult("PAM communication check", "false")
        else:
            logSimpleResult("PAM communication check", "true") 
    except:
        printText("Failed to connect to "+str(deviceString))
        logSimpleResult("PAM communication check", "false")
        if ui_mode == "testcenter":
            logSimpleResult("Failed to connect to "+str(deviceString), False)
        sys.exit(0)
    printText("Module Selected: " + deviceString)
    # Disable fixture write protection
    myPpmDevice.sendCommand("write 0xa100 0xaa55")
    myPpmDevice.sendCommand("write 0xa100 0x55aa")

    # Write to the fixture RAM
    printText("writing blank values to the fixture (0xFF)...")
    for x in range (0, 255):
        myPpmDevice.sendCommand("write " + '0x{:4X}'.format(0xa400 + x) + " 0xFFFF")
        progressBar(x,254)

    # write the RAM to EEPROM
    printText("\nprogramming EEPROM",end='')
    myPpmDevice.sendCommand("write 0xa200 0x0400")
    myPpmDevice.sendCommand("write 0xa200 0x0000")
    # wait for write to finish
    while(checkBit(myPpmDevice.sendCommand("read 0xa200"),12)):
        time.sleep(1)
        printText(".",end='')
    printText("\nprogram complete")

    #read back from EEPROM and verify

    # read back
    printText("reading back the EEPROM",end='')
    myPpmDevice.sendCommand("write 0xa200 0x0800")
    myPpmDevice.sendCommand("write 0xa200 0x0000")

    # wait for read to finish
    while(checkBit(myPpmDevice.sendCommand("read 0xa200"),12)):
        time.sleep(1)
        printText(".",end='')
    printText("\nread complete")

    Verified = True
    # Read from the fixture RAM
    printText("reading values from the fixture...")
    for x in range (0, 255):
        
        readValue = myPpmDevice.sendCommand("read " + '0x{:4X}'.format(0xa400 + x))

        fileValue = '0xFFFF'

        # if we have valid data
        if readValue != fileValue:
            printText("                                                                                                   \r",end='')   # clear the percentage bar
            printText("Verification failure at " + '0x{:4X}'.format(0xa400 + x) + ", read: " + readValue + ", expected: " + fileValue)
            Verified = False
        progressBar(x,254)

    if Verified == True:
        logSimpleResult ("Fixture Erase", "true")
        printText("now power cycle the fixture")
    else:
        logSimpleResult ("Fixture Erase", "false")
        storeResult ("Erase failed on fixture")
#==============================================================================================================

def setBit(hexString,bit):
    return hexString | 2**bit

def checkBit(hexString,bit):
    if (int(hexString,16) & 2**bit) > 0:
        return True
    else:
        return False

def updateCRC(crcVal,thisByte):
    crcVal ^= (thisByte << 8)
    crcVal &= 0xFFFF

    # Update CRC for this byte
    for i in range (0,8,1):
        if (crcVal & 0x8000) > 0:
            crcVal = (crcVal<<1) ^ 0x8005
        else:
            crcVal <<= 1
        crcVal &= 0xFFFF

    return crcVal

def highByte(thisWord):
    return ((thisWord >> 8) & 0xFF)

def lowByte(thisWord):
    return (thisWord & 0XFF)

def parse_arguments():
    parser = argparse.ArgumentParser(description="PAM Header Utility")
    parser.add_argument("--ac", nargs="?", type=str, default="", help="Please choose the action. Generate or Program.")
    parser.add_argument("--fp", nargs="?", type=str, default="", help="Please provide the path of the input file.")
    parser.add_argument("--dfp", nargs="?", type=str, default="", help="Please provide the path of the output file or the device you would like to program.")
    parser.add_argument("--ow", nargs="?", type=str, default="", help="Would you like to overwrite the file? [Yes|No]")
    parser.add_argument("--ser", nargs="?", type=str, default="", help="Would you like to specify a fixture serial number")
    parser.add_argument('-u', '--userMode', help=argparse.SUPPRESS, choices=['console', 'testcenter'], type=str.lower, default='console')  # Passes the output to testcenter instead of the console Internal Use
    args = parser.parse_args()

    return args

if __name__== "__main__":
    args = parse_arguments()
    thisInterface = User_interface(args.userMode)
    uiMode = args.userMode
    #if uiMode == "testcenter": TestCenter.setup("Quarch_Internal", "Internal", "Login=-", "Password=-")
    main(args)
   

