"""
Contains classes and functions for processing stream headers
to get the detail of the stream
"""

import xml.etree.ElementTree as ET                          # XML parser
from quarchpy.utilities.TimeValue import TimeValue          # Time object helper class
import logging                                              # Used for debug logging calls

class StreamChannelInfo:
    """
    Holds information on a single device channel, as parsed from the stream header information
    """

    channel_hw_group_id = None
    channel_name = None
    channel_group = None
    channel_units = None
    channel_max_val = None
    
    
class StreamGroupInfo:
    """
    Holds information on a single device hardware group, as parsed from the stream header information
    """

    group_hw_id = None
    group_channel_count = None
    group_frequency = None
    group_channels = None
    
    
class StreamHeaderInfo:
    """
    Holds the raw header information data and allows access to its various elements
    in a simple way
    """

    # Raw header data from QIS
    header_raw_xml = None
    device_period = None
    header_version = None
    data_valid = False
    device_channels = []    
    device_groups = []    
    
    
    def __init__ (self, stream_header = None):
        """
        Constructor taking optional stream header text
        
        Parameters
        ----------
        stream_header : str, optional
            Stream header as supplied from the 'stream text header command'            
        """    
        
        # If we have been given a header, process it
        if (stream_header != None):
            init_from_stream_header (stream_header, header_version)
        
        
    def init_from_stream_header (self, stream_header):
        """
        Sets up the info class from stream header text, as supplied from the QIS
        stream text header command
        
        Parameters
        ----------
        stream_header : str
            Stream header text data          
        """         
            
        # Store the raw header data to query later
        header_raw_xml = stream_header
        
        # Check if its an XML header
        if('?xml version=' not in header_raw_xml):
            # Old format header so limited data we can obtain
            logging.error("Stream header version not supported (not XML) or invalid data supplied")
            raise Exception ("Stream header version not supported (not XML) or invalid data supplied");
        else:           
            # Parse XML into structured format
            xml_root = ET.fromstring(header_raw_xml)
            
            # Get the header version number as an integer
            try:
                param_string = xml_root.find('.//version').text
                if ('V' in param_string):
                    param_string = param_string[1:]
                    self.header_version = int(param_string)                    
                else:
                    logging.error('Unexpected version string found: ' + param_string)
            except Exception as e:
                logging.error('Exception while parsing stream header XML for header version.')
                raise e
                
            # Get the device period (will not be present on multi-rate modules, those are handled has part of group parsing)
            param_string = xml_root.find('.//devicePeriod')
            if param_string != None:
                self.device_period = TimeValue (from_time_string=param_string.text)
            else:
                # Older versions had a fixed uS unit, so fail back to check for this
                param_string = xml_root.find('.//devicePerioduS')
                if param_string != None:
                    self.device_period = TimeValue (from_time_string=param_string.text)                
                    
            # Parse the groups, this will only be present on multi-rate modules
            
            
            # Parse the grouped elements
            for section in xml_root.iter():
                # Signals presented in the stream
                if (section.tag == "channels"):
                    for chan in section:
                        # Avoid children that are not named channels
                        if (chan.find('.//name') is not None):
                            # Create a new channel and add it to the main list
                            new_channel = StreamChannelInfo()
                            # HW group ID only exists in multi-rate devices, so set group to 0 if none is found
                            new_channel.channel_hw_group_id = chan.find('.//groupId')
                            if (new_channel.channel_hw_group_id == None):
                                new_channel.channel_hw_group_id = 0
                            else:
                                new_channel.channel_hw_group_id = int(new_channel.channel_hw_group_id.text)
                            new_channel.channel_name = chan.find('.//name').text
                            new_channel.channel_group = chan.find('.//group').text
                            new_channel.channel_units = chan.find('.//units').text
                            new_channel.max_value = int(chan.find('.//maxTValue').text)    
                            self.device_channels.append (new_channel)
                # Groups (only present on multi-rate devices)
                if (section.tag == "groups"):
                    fastest_freq = 0
                    for group in section:
                        # Create a new group and add it to the main list
                        new_group = StreamGroupInfo()
                        new_group.group_hw_id = group.find('.//groupId').text                        
                        # Sampling frequency is calculated from a base and exponent
                        group_base = int(group.find('.//sampleRateBase').text)
                        group_exponent = int(group.find('.//sampleRateExponent').text)
                        self.group_frequency = int(group_base*(10^group_exponent))                        
                        self.device_groups.append (new_group)

                        # Track the fastest group frequency
                        if (self.group_frequency > fastest_freq):
                            fastest_freq = self.group_frequency

                # TODO - Update the device period with the fastest group frequency if groups were found
                
                                
            
    def init_from_qis_device (self, open_qis_device):
        """
        Sets up the info class from a quaech device that is attached
        via QIS and so the header can be requested direct from the instrument
        
        Parameters
        ----------
        open_qis_device : quarchDevice
            Open connection to a quarch streaming device via QIS
        """ 
        
        # Ensure we get the latest XML header format, even for older devices
        open_qis_device.sendCommand ("stream mode header v3")
        # Get and process the header data from the device
        header_dump = open_qis_device.sendCommand ("stream text header")
        self.init_from_stream_header (header_dump)
        
            
    
    def get_device_period (self):
        """
        Returns the sample rate of the stream (of the fastest group for multi-rate streams)
        
        Returns
        -------
        device_period : TimeValue
            Sample rate time object including time unit    
        """    
    
        return self.device_period
        
    def get_header_version (self):
        """
        Returns the header version number
        
        Returns
        -------
        header_version : int
            Version number of the stream text header data    
        """    
    
        return self.header_version
        
        
        
        