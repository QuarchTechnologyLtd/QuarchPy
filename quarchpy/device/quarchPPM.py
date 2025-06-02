from .device import quarchDevice
import logging
import xml.etree.ElementTree as ET
from quarchpy.user_interface.user_interface import printText


class quarchPPM(quarchDevice):
    def __init__(self, originObj, skipDefaultSyntheticChannels=False):

        self.connectionObj = originObj.connectionObj
        self.ConString = originObj.ConString
        self.ConType = originObj.ConType
        self.fixture_definition = self.send_command("fix:chan:xml?")
        self.default_channels = None
        numb_colons = self.ConString.count(":")
        if numb_colons == 1:
            self.ConString = self.ConString.replace(':', '::')
        if not skipDefaultSyntheticChannels and self.ConType[:3].upper() == "QIS" and "FAIL:" not in self.fixture_definition:
            self.create_default_synthetic_channels()
 
    def startStream(self, fileName='streamData.txt', fileMaxMB=200000, streamName ='Stream With No Name', streamDuration = None, streamAverage = None, releaseOnData = False, separator=",", inMemoryData = None, outputFileHandle = None, useGzip = None):
        return self.connectionObj.qis.startStream(self.ConString, fileName, fileMaxMB, streamName, streamAverage, releaseOnData, separator, streamDuration, inMemoryData, outputFileHandle, useGzip)

    def streamRunningStatus(self):
        return self.connectionObj.qis.streamRunningStatus(self.ConString)

    def streamBufferStatus(self):
        return self.connectionObj.qis.streamBufferStatus(self.ConString)

    def streamInterrupt(self):
        return self.connectionObj.qis.streamInterrupt()

    def waitStop(self):
        return self.connectionObj.qis.waitStop()

    def streamResampleMode(self, streamCom, group=None):
        if streamCom.lower() == "off" or streamCom[0:-2].isdigit():
            cmd = "stream mode resample " + streamCom.lower()
            if group is not None:
                cmd = "stream mode resample group " + str(group) + " " + streamCom.lower()
            retVal = self.connectionObj.qis.sendAndReceiveCmd(cmd=cmd,
                                                              device=self.ConString)
            if "fail" in retVal.lower():
                logging.error(retVal)
        else:
            retVal = "Invalid resampling argument. Valid options are: off, [x]ms or [x]us."
            logging.error(retVal)
        return retVal

    def stopStream(self):
        return self.connectionObj.qis.stopStream(self)

    '''
    Simple function to check the output mode of the power module, setting it to 3v3 if required
    then enabling the outputs if not already done.  This will result in the module being turned on
    and supplying power
    '''
    def setupPowerOutput(myModule):
        # Output mode is set automatically on HD modules using an HD fixture, otherwise we will chose 5V mode for this example
        outModeStr = myModule.send_command("config:output Mode?")
        if "DISABLED" in outModeStr:
            try:
                drive_voltage = raw_input(
                    "\n Either using an HD without an intelligent fixture or an XLC.\n \n>>> Please select a voltage [3V3, 5V]: ") or "3V3" or "5V"
            except NameError:
                drive_voltage = input(
                    "\n Either using an HD without an intelligent fixture or an XLC.\n \n>>> Please select a voltage [3V3, 5V]: ") or "3V3" or "5V"

            myModule.send_command("config:output:mode:" + drive_voltage)

        # Check the state of the module and power up if necessary
        powerState = myModule.send_command("run power?")
        # If outputs are off
        if "OFF" in powerState or "PULLED" in powerState:  # PULLED comes from PAM
            # Power Up
            printText("\n Turning the outputs on:"), myModule.send_command("run:power up"), "!"

    '''
    Parses the fixture XML and extracts the synthetic channels specified by the instrument defaults.
    This function reads the fixture XML structure and looks for channels under the SyntheticChannels node,
    extracting the relevant information (number, function, enable status, etc.).
    '''

    def parse_synthetic_channels_from_instrument(self):
        # Parse the XML data from the fixture_definition (which is an XML string) to get the root element
        root = ET.fromstring(self.fixture_definition)

        # Initialize an empty list to hold all parsed synthetic channels
        synthetic_channels = []

        # Loop over each 'Channel' element found within 'SyntheticChannels' in the XML tree
        for channel in root.findall(".//SyntheticChannels/Channel"):
            # Extract values of interest from each channel, using XPath queries to find the relevant parameters
            number = channel.find(".//Param[Name='Number']/Value")
            function = channel.find(".//Param[Name='Function']/Value")
            enable = channel.find(".//Param[Name='Enable']/Value")
            enabled_by_default = channel.find(".//Param[Name='EnabledByDefault']/Value")
            visible_by_default = channel.find(".//Param[Name='VisibleByDefault']/Value")

            # Convert values from XML to appropriate data types (number is an integer, others are strings or booleans)
            number = int(number.text) if number is not None else 0
            function = function.text if function is not None else ""
            enable = enable.text.lower() == 'true' if enable is not None else False
            enabled_by_default = enabled_by_default.text.lower() == 'true' if enabled_by_default is not None else False
            visible_by_default = visible_by_default.text.lower() == 'true' if visible_by_default is not None else False

            # Create an instance of the SyntheticChannel class with the extracted information
            synthetic_channel = SyntheticChannel(number, function, enable, enabled_by_default, visible_by_default)

            # Append the newly created SyntheticChannel object to the list of channels
            synthetic_channels.append(synthetic_channel)

        # Return the list of synthetic channels extracted from the XML
        return synthetic_channels

    '''
    Sends the set of synthetic channels to the device.
    This method iterates through the list of synthetic channels and sends the appropriate
    commands to a QIS/QPS-based device to create the channels. 
    '''

    def send_synthetic_channels(self, channels):
        # Loop through each channel in the provided list of channels
        for channel in channels:
            # Send a command to the device to create a stream with the channel's function
            result = self.send_command("stream create channel " + channel.function)

            # If the command result is not "OK", raise an exception with an error message
            if result != "OK":
                raise Exception(f"Command failed for channel {channel.number}: {channel.function} = {result}")

    '''
    Creates the default synthetic channels based on the fixture XML.
    This method first parses the synthetic channels from the instrument and sends them to the device.
    '''

    def create_default_synthetic_channels(self):
        # The fixture XML and synthetic channels are only parsed once per connection.
        # If the fixture is replaced or changed, this info should be refreshed via an API call.
        # This stores the default channels in the class for later use to avoid re-parsing multiple times.
        self.default_channels = self.parse_synthetic_channels_from_instrument()

        # Sends the parsed default synthetic channels to the device.
        # This could be part of the device initialization process, with an option to skip it using a flag.
        self.send_synthetic_channels(self.default_channels)

        # The following commented-out example shows how to manually send a command for a specific synthetic channel.
        # Example: This command calculates the RMS current for the neutral line.
        # self.send_command("stream create channel chan(Neutral_RMS,A) rms(100ms,chan(Neutral,A))")

'''
Class representing a SyntheticChannel.
Each synthetic channel is characterized by a number, function, enable status, 
whether it's enabled by default, and whether it's visible by default.
'''

class SyntheticChannel:
    def __init__(self, number, function, enable, enabled_by_default, visible_by_default):
        self.number = number  # The unique number identifier for the synthetic channel
        self.function = function  # The function or behavior of the channel (e.g., RMS calculation)
        self.enable = enable  # Whether the channel is currently enabled
        self.enabled_by_default = enabled_by_default  # Whether the channel is enabled by default
        self.visible_by_default = visible_by_default  # Whether the channel is visible by default

    def __repr__(self):
        # Provide a readable string representation of the synthetic channel, useful for debugging or logging
        return (f"SyntheticChannel(Number={self.number}, Function='{self.function}', "
                f"Enable={self.enable}, EnabledByDefault={self.enabled_by_default}, "
                f"VisibleByDefault={self.visible_by_default})")