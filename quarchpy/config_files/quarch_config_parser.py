import logging
logger = logging.getLogger(__name__)
import os, os.path, sys
import re
import inspect
import xml.etree.ElementTree as ET
import quarchpy.config_files
from enum import Enum

'''
Describes a unit for time measurement
'''
class TimeUnit(Enum):
    UNSPECIFIED = "UNSPECIFIED"
    nS = "nS"
    uS = "uS"
    mS = "mS"
    S = "S"

'''
Described a precise time duration for settings
'''
class TimeValue:
    def __init__ (self, time_value=0, time_unit=TimeUnit.UNSPECIFIED):
        self.time_value = time_value
        self.time_unit = time_unit

    def __repr__(self):
        return f"{self.time_value}{self.time_unit.value}"


'''
Describes which side(s) of a signal can be driven, and to which level(s)
'''
class DriveLevel(Enum):
    NONE = "None"
    LOW = "Low"
    HIGH = "High"
    BOTH = "Both"


'''
Represents a versioned feature support flag, as used in the module "sig:xml?" Features block.
A version of 0 (or a false/absent flag) means the feature is not present. A positive version
means the feature is present using that version's semantics - a higher version may add or
restructure how the feature works, not just indicate "more support".
'''
class FeatureSupport:
    def __init__(self, version=0):
        self.version = int(version) if version else 0

    @property
    def present(self):
        return self.version > 0

    def __bool__(self):
        return self.present

    def __repr__(self):
        return f"FeatureSupport(version={self.version})"


'''
Parses a boolean-ish config/XML value ("true"/"false", "1"/"0", "yes"/"no") into a bool
'''
def _parse_bool(value):
    if value is None:
        return False
    return str(value).strip().lower() in ("true", "1", "yes")


'''
Parses a config/XML numeric string into an int, or a float if it has a decimal point.
Returns the original value unchanged if it cannot be parsed as a number.
'''
def _parse_numeric(value):
    try:
        text = str(value).strip()
        return float(text) if ("." in text) else int(text)
    except (TypeError, ValueError):
        return value


'''
Parses a DriveLevel value ("None"/"Low"/"High"/"Both") from config/XML text
'''
def _parse_drive_level(value):
    if value is None:
        return DriveLevel.NONE
    text = str(value).strip().lower()
    for level in DriveLevel:
        if level.value.lower() == text:
            return level
    return DriveLevel.NONE


'''
Parses a feature support value, which may be a simple boolean flag (legacy .qfg style) or a
version number (sig:xml style), into a FeatureSupport. False/0/absent all mean "not present".
'''
def parse_feature_support(value):
    if value is None:
        return FeatureSupport(0)
    text = str(value).strip().lower()
    if text in ("", "false", "0", "none"):
        return FeatureSupport(0)
    if text in ("true", "yes"):
        return FeatureSupport(1)
    try:
        return FeatureSupport(int(float(text)))
    except ValueError:
        logger.debug("Unrecognised feature support value: " + str(value))
        return FeatureSupport(0)


_TIME_UNIT_LOOKUP = {unit.value.lower(): unit for unit in TimeUnit}

'''
Parses a time string such as "50nS" or "500mS" into a TimeValue
'''
def parse_time_value(text):
    match = re.match(r"^\s*(-?\d+(?:\.\d+)?)\s*([a-zA-Z]+)\s*$", text or "")
    if not match:
        logger.debug("Unrecognised time value: " + str(text))
        return TimeValue(0, TimeUnit.UNSPECIFIED)

    value_str, unit_str = match.groups()
    unit = _TIME_UNIT_LOOKUP.get(unit_str.lower(), TimeUnit.UNSPECIFIED)
    value = float(value_str) if "." in value_str else int(value_str)
    return TimeValue(value, unit)

'''
Describes a single range element if a module range parameter
'''
class ModuleRangeItem:
    def __init__ (self):
        self.min_value = 0
        self.max_value = 0
        self.step_value = 0
        self.unit = None

'''
Describes a range of values which can be applied to the settings on a module
This is generally a time value, but can be anything
'''
class ModuleRangeParam:
    ranges = None
    range_unit = None

    def __init__ (self):
        self.ranges = list()
        self.range_unit = None

    def __repr__ (self):
        return "|".join (
            f"{item.min_value},{item.max_value},{item.step_value},{item.unit}" for item in self.ranges)

    '''
    Adds a new range item, which is verified to match any existing items
    '''
    def add_range (self, new_range_item):
        valid = True        

        if (self.range_unit is None):
            self.range_unit = new_range_item.unit
        # For additional ranges, verify the unit is the same
        else:
            if (new_range_item.unit != self.range_unit):
                valid = False

        # Add the new range if all is OK
        if (valid):
            self.ranges.append (new_range_item)
            return True
        else:
            return False

    '''
    Internal method to find the closest value within a given range
    '''
    def _get_closest_value (self, range_item, value):

        # Check for out of range values
        if (value < range_item.min_value):
            return range_item.min_value
        elif (value > range_item.max_value):
            return range_item.max_value

        # Else value is in range - find the closest step
        low_steps = int((float(value) / float(range_item.step_value)) + 0.5)
        low_value = int(low_steps * range_item.step_value)
        high_value = int(low_value + range_item.step_value)

        if (abs(low_value - value) < abs(high_value - value)):
            return low_value
        else:
            return high_value

    '''
    Returns the closest allowable value to the given number
    '''
    def get_closest_value (self, value):
        valid_value = -sys.maxsize -1
        running_error = sys.maxsize
        curr_error = 0
        possible_value = 0

        if (self.ranges is None or len(self.ranges) == 0):
            raise ValueError ("No ranges available to check against")
        else:
            # Loop through the ranges
            for i in self.ranges:
                # Find the closest value in this range
                possible_value = self._get_closest_value (i, value)
                curr_error = abs(possible_value - value)

                # Store if it is closer than the previous tests
                if (curr_error < running_error):
                    running_error = curr_error
                    valid_value = possible_value

        return valid_value

    '''
    Returns the largest allowable value
    '''
    def get_max_value (self):
        valid_value = -sys.maxsize -1

        for i in self.ranges:
            if (i.max_value > valid_value):
                valid_value = i.max_value

        return valid_value

    '''
    Returns the smallest allowable value
    '''
    def get_min_value (self):
        valid_value = sys.maxsize

        for i in self.ranges:
            if (i.min_value < valid_value):
                valid_value = i.min_value

        return valid_value

'''
Describes a switched signal on a breaker module
'''
class BreakerModuleSignal:
    def __init__ (self):
        self.name = None
        self.signal_type = None            # e.g. "Switched"
        self.glitch_present = False        # can this signal be glitched
        self.drive_present = False         # can this signal be actively driven
        self.drive_host = DriveLevel.NONE      # can the host side be driven, and to which level(s)
        self.drive_device = DriveLevel.NONE    # can the device side be driven, and to which level(s)
        self.drive_monitor = False         # can the driven state be read back
        self.monitor_host = False          # can the host side state be monitored
        self.monitor_device = False        # can the device side state be monitored
        self.parameters = dict ()          # any other/legacy key-value data not modelled above

'''
Describes a signal group on a breaker module
'''
class BreakerSignalGroup:
    name = None
    signals = None

    def __init__ (self):
        self.name = None
        self.signals = list ()

'''
Describes control sources on a breaker module
'''
class BreakerSource:
    name = None
    parameters = None

    def __init__ (self):
        self.name = None
        self.parameters = dict ()

'''
Describes control sources on a breaker module
'''
class VoltageMeasurements:
    def __init__ (self):
        self.name = None
        self.type = None
        self.unit = None       # e.g. "mV"
        self.nominal = None    # nominal/expected value, in the given unit

'''
Describes the module-level feature-support flags on a breaker module (the "Features" block
of the sig:xml? response). Each Supports* field is a FeatureSupport - falsy/version 0 means
not present, a positive version indicates the feature is present with that version's behaviour.
'''
class BreakerFeatures:
    def __init__ (self):
        self.supports_bounce = FeatureSupport()
        self.supports_drive = FeatureSupport()
        self.supports_triggering = FeatureSupport()
        self.supports_lane_width = FeatureSupport()
        self.max_lane_width = 0
        self.supports_glitch = FeatureSupport()

'''
Describes the glitch engine capabilities of a breaker module (the "Glitch_Engine" block of
the sig:xml? response, or the "@GLITCH" section of a .qfg file)
'''
class GlitchEngine:
    def __init__ (self):
        self.length_limits = None      # ModuleRangeParam
        self.cycle_limits = None       # ModuleRangeParam
        self.multipliers = list ()     # list[TimeValue]
        self.prbs_ratios = list ()     # list[str], e.g. "1:2".."1:65536"
        self.parameters = dict ()      # any other/legacy key-value data not modelled above

'''
Describes a Torridon hot-swap/breaker module and all its capabilities
'''
class TorridonBreakerModule:
    config_data = None

    def get_signals(self):
        return self.config_data["SIGNALS"]

    def get_signal_groups(self):
        return self.config_data["SIGNAL_GROUPS"]

    def get_sources(self):
        return self.config_data["SOURCES"]

    def get_general_capabilities(self):
        # Always a plain dict of legacy ad hoc key/value flags. For .qfg-sourced capabilities this is
        # read directly from the file's @GENERAL section. For XML-sourced capabilities, sig:xml? has
        # no equivalent ad hoc section, so only the flags with a confirmed equivalence to a Features
        # value are synthesised here
        return self.config_data["GENERAL"]

    def get_features(self):
        # Structured, versioned Supports* feature flags from the sig:xml? "Features" block.
        # Returns None for .qfg-sourced capabilities, which have no equivalent data.
        return self.config_data.get ("FEATURES")

    def get_header(self):
        # Identifying/matching metadata. Always present for .qfg-sourced capabilities. For
        # XML-sourced capabilities only DeviceClass is known - sig:xml? is read directly from an
        # already-connected module, so it carries none of the file-matching metadata (device
        # numbers, firmware/FPGA version ranges, description) a .qfg header exists to provide.
        return self.config_data.get ("HEADER", dict ())

    def get_voltage_measurements(self):
        return self.config_data["MEASURE"]

    def get_glitch_engine(self):
        return self.config_data.get ("GLITCH")

    def __init__ (self):
        self.config_data = dict ()


'''
Tries to locate configuration data for the given module and return a structure of device capabilities to help the user
control the module and understand what its features are.

Newer modules support the "sig:xml?" command, which returns a richer, self-describing capability
set directly from the module. This is tried first (when a module_connection is available); modules
which do not support it return a response starting "FAIL", in which case we fall back to matching
a local .qfg config file, as used for older modules.
'''
def get_device_capabilities (idn_string = None, module_connection = None):
    if (module_connection is not None):
        xml_response = None
        try:
            xml_response = module_connection.sendCommand ("sig:xml?")
        except Exception as e:
            logger.debug ("sig:xml? command failed, falling back to config file lookup: " + str(e))

        if (xml_response is not None and not xml_response.strip().upper().startswith ("FAIL")):
            try:
                return parse_config_xml (xml_response)
            except ET.ParseError as e:
                logger.error ("Failed to parse sig:xml? response, falling back to config file lookup: " + str(e))

    # Get config data and fail if none is found
    file_path = get_config_path_for_module (idn_string = idn_string, module_connection = module_connection)
    if (file_path is None):
        raise ValueError ("No configuration data found for the given module")

    return parse_config_file (file_path)

'''
Returns the path to the most recent config file that is compatible with the given module.  Module information can be passed in as
an existing IDN string from the "*IDN?" command or via an open connection to the module
'''
def get_config_path_for_module (idn_string = None, module_connection = None):
    device_number = None
    device_fw = None
    device_fpga = None
    result = True

    # Check for invalid parameters
    if (idn_string is None and module_connection is None):
        logger.error("Invalid parameters, no module information given")
        result = False
    else:
        # Prefer IDN string, otherwise use the module connection to get it now
        if (idn_string is None):
            idn_string = module_connection.sendCommand ("*IDN?")

        # Split the string into lines and run through them to locate the parts we need
        idn_lines = idn_string.upper().split("\n")
        for i in idn_lines:
            # Part number of the module
            if "PART#:" in i:
                device_number = i[6:].strip()
            # Firmware version
            if "PROCESSOR:" in i:
                device_fw = i[10:].strip()
                pos = device_fw.find (",")
                if (pos == -1):
                    device_fw = None
                else:
                    device_fw = device_fw[pos+1:].strip()
            # FPGA version
            if "FPGA 1:" in i:
                device_fpga = i[7:].strip()
                pos = device_fpga.find (",")
                if (pos == -1):
                    device_fpga = None
                else:
                    device_fpga = device_fpga[pos+1:].strip()
            else:
                device_fpga = 0.0

        # Log the failure if we did not get all the info needed
        if (device_number is None):
            result = False
            logger.error("Unable to identify module - no module number")
        if (device_fw is None):
            logger.error("Unable to identify module - no firmware version")
            result = False
        if (device_fpga is None):
            logger.error("Unable to identify module - no FPGA version")
            result = False

        # If we got all the data, use it to find the config file
        config_matches = list()
        if (result == False):
            raise FileNotFoundError()
        else:
            # Get all config files as a dictionary of their basic header information
            config_file_header = get_config_file_headers ()

            # Loop through each config file header
            for i in config_file_header:
                # If the part number can be used with this config file
                if (check_part_number_matches(i, device_number)):
                    # Check if the part number is not seperately excluded
                    if (check_part_exclude_matches(i, device_number) == False):
                        # Check Firmware can be used with this config file
                        if (check_fw_version_matches(i, device_fw)):
                            # Check if FPGA version matches
                            if (check_fpga_version_matches(i, device_fpga)):
                                # Store this as a matching config file for the device
                                logger.debug("Located matching config file: " + i["Config_Path"])
                                config_matches.append (i)

            # Sort the config files into preferred order
            if (len(config_matches) > 0):
                config_matches = sort_config_headers (config_matches)
                return config_matches[0]["Config_Path"]
            else:
                logger.error("No matching config files were found for this module")
                return None

# Attempts to parse every file on the system to check for errors in the config files or the parser
def test_config_parser (level=1):
    # Get all config files as a dictionary of their basic header information
    config_file_header = get_config_file_headers ()
    for i in config_file_header:
        print ("CONFIG:" + i["Config_Path"])
        dev_caps = parse_config_file (i["Config_Path"])
        if (dev_caps is None):
            print ("Module not parsed!")
        else:
            if (type(dev_caps) is TorridonBreakerModule):
                print (dev_caps.config_data["HEADER"]["DeviceDescription"])
        print("")


'''                
Processes all config files to get a list of dictionaries of basic header information
'''
def get_config_file_headers ():

    # Get the path to the config files folder
    folder_path = os.path.dirname (os.path.abspath(quarchpy.config_files.__file__))
    files_found = list()
    config_headers = list()

    # Iterate through all files, including and recursive folders
    for search_path, search_subdirs, search_files in os.walk(folder_path):
        for name in search_files:
            if (".qfg" in name.lower()):
                files_found.append (os.path.join(search_path, name))

    # Now parse the header section of each file into the list of dictionaries
    for i in files_found:
        read_file = open (i, "r")
        next_line, read_point = read_config_line (read_file)
        if ("@CONFIG" in next_line):
            # Read until we find the @HEADER section
            while ("@HEADER" not in next_line):
                next_line, read_point = read_config_line (read_file)
            # Parse the header section data
            new_config = parse_section_to_dictionary (read_file)
            # Store the file path as an item
            new_config["Config_Path"] = i
            config_headers.append (new_config)
        else:
            logger.error("Config file parse failed, @CONFIG section not found")

    return config_headers

'''
Reads the next line of the file which contains usable data, skips blank lines and comments
'''
def read_config_line (read_file):
    while(True):
        start_pos = read_file.tell()
        line = read_file.readline ()

        if (line == ''):
            return None,0
        else:
            line = line.strip()
            if (len(line) > 0):
                if (line[0] != '#'):
                    return line, start_pos

'''
Reads the next section of the file (up to the next @ line) into a dictionary
'''
def parse_section_to_dictionary (read_file):
    elements = dict()

    # Read until we find the end
    while(True):
        # Read a line and the read point in the file
        line, start_pos = read_config_line (read_file)
        # If this is the start of a new section, set the file back one line and stop
        if (line.find ('@') == 0):
            read_file.seek (start_pos)
            break
        # Else we parse the line into a new dictionary item
        else:
            pos = line.find ('=')
            if (pos == -1):
                logger.error("Config line does not meet required format of x=y: " + line)
                return None
            else:
                elements[line[:pos].strip()] = line[pos+1:].strip()

    return elements


'''
Returns true of the config header is allowed for use on a module with the given part number
'''
def check_part_number_matches(config_header, device_number):

    # Strip down to the main part number, removing the version
    pos = device_number.find ("-")
    if (pos != -1):
        pos = len(device_number) - pos
        short_device_number = device_number[:-pos]
    # Fail on part number not including the version section
    else:
        logger.debug("Part number did not contain the version :" + device_number)
        return False

    # Loop through the allowed part numbers
    allowed_device_numbers = config_header["DeviceNumbers"].split(",")
    for dev in allowed_device_numbers:
        pos = dev.find('-');
        if (pos != -1):
            pos = len(dev) - pos
            short_config_number = dev[:-pos]
            if ("xx" in dev):
                any_version = True;
            else:
                any_version = False;               
        # Fail if config number is invalid
        else:
            logger.debug("Part number in config file is not in the right format: " + dev)
            return False;

        # Return true if we find a number that matches in full, or one which matches in part and the any_version flag was present in the config file
        if (device_number == dev or (short_device_number == short_config_number and any_version)):
            return True

    # False as the fallback if no matching part numbers were found
    return False

'''
Returns true of the config header does not contain an exclusion for the given device number
'''
def check_part_exclude_matches(config_header, device_number):

    # Strip down to the main part number, removing the version
    pos = device_number.find ("-")
    if (pos != -1):
        pos = len(device_number) - pos
        short_device_number = device_number[:-pos]
    # Fail on part number not including the version section
    else:
        logger.debug("Part number did not contain the version :" + device_number)
        return False

    # Check that the part number is fully qualified (will not be the case if the serial number is not set)
    if ("?" in device_number):
        logger.debug("Part number is not fully qualified :" + device_number)
        return False

    # Loop through the excluded part numbers
    allowed_device_numbers = config_header["DeviceNumbersExclude"].split(",")
    for dev in allowed_device_numbers:
        # Skip blanks (normally due to no part numbers specified)
        if (len(dev) == 0):
            continue

        pos = dev.find('-');
        if (pos != -1):
            pos = len(dev) - pos
            short_config_number = dev[:-pos]
            if ("xx" in dev):
                any_version = True;
            else:
                any_version = False;               
        # Fail if config number is invalid
        else:
            logger.debug("Exclude part number in config file is not in the right format: " + dev)
            return False;

        # Return true if we find a number that matches in full, or one which matches in part and the any_version flag was present in the config file
        if (device_number == dev or (short_device_number == short_config_number and any_version)):
            return True

    # False as the fallback if no matching part numbers were found
    return False

'''
Checks that the firmware version on the config header allows the version on the device
'''
def check_fw_version_matches(config_header, device_fw):
    if float(device_fw) >= float(config_header["MinFirmwareRequired"]):
        return True
    else:
        return False

'''
Checks that the FPGA version on the config header allows the version on the device
'''
def check_fpga_version_matches(config_header, device_fpga):
    if (float(device_fpga) >= float(config_header["MinFpgaRequired"])):
        return True
    else:
        return False

'''
Sorts a list of config headers into order, where the highest firmware version file is at the top of the list
This is the one which would normally be chosen
'''
def sort_config_headers (config_matches):
    return sorted (config_matches, key=lambda i: i["MinFirmwareRequired"], reverse=True)

def parse_config_file (file):

    config_dict = dict ()
    section_dict = dict ()
    section_name = None
    read_file = open (file, "r")
    
    # Start with the first line, as this is not useful info anyway
    line, read_pos = read_config_line (read_file)
    # Loop through the file, reading all lines
    while (True):
        line, read_pos = read_config_line (read_file)
        if (line is None):
            config_dict[section_name] = section_dict
            break

        # If this is the start of the first section, store its name
        if ("@" in line and section_name is None):
            section_name = line[1:]
        # If a new section, store the old one first
        elif ("@" in line):
            config_dict[section_name] = section_dict           
            section_name = line[1:]
            section_dict = dict ()
        # Else this must be a standard data line
        else:
            # Special case for module signals, create as a BreakerSignal class type
            if ("SIGNALS" in section_name):

                # Change to a list for signals
                if (len(section_dict) == 0):
                    section_dict = list()

                signal = BreakerModuleSignal ()
                line_value = line.split(',')
                # Loop to add the optional parameters
                for i in line_value:
                    pos = i.find('=')
                    line_param = i[pos+1:]
                    line_name = i[:pos]
                    if ("Name" in line_name):
                        signal.name = line_param
                    elif (line_name == "Type"):
                        signal.signal_type = line_param
                    elif (line_name in ("GlitchEnable_Present", "GlitchPresent")):
                        signal.glitch_present = _parse_bool (line_param)
                    elif (line_name in ("DrivePresent", "SignalDrive_Present")):
                        signal.drive_present = _parse_bool (line_param)
                    elif (line_name == "DriveHost"):
                        signal.drive_host = _parse_drive_level (line_param)
                    elif (line_name == "DriveDevice"):
                        signal.drive_device = _parse_drive_level (line_param)
                    elif (line_name == "DriveMonitor"):
                        signal.drive_monitor = _parse_bool (line_param)
                    elif (line_name == "MonitorHost"):
                        signal.monitor_host = _parse_bool (line_param)
                    elif (line_name == "MonitorDevice"):
                        signal.monitor_device = _parse_bool (line_param)
                    elif (line_name == "SignalMonitor_Present"):
                        # .qfg files only carry a single monitor-present flag with no host/device
                        # split, unlike sig:xml?'s MonitorHost/MonitorDevice - apply it to both,
                        # since that is the closest faithful (if less precise) equivalent.
                        monitor_present = _parse_bool (line_param)
                        signal.monitor_host = monitor_present
                        signal.monitor_device = monitor_present
                    else:
                        signal.parameters[line_name] = line_param
                # Add signal to the section
                section_dict.append(signal)
            # Special case for module signal groups
            elif ("SIGNAL_GROUPS" in section_name):

                # Change to a list for signals groups
                if (len(section_dict) == 0):
                    section_dict = list()

                group = BreakerSignalGroup ()
                # Get the name of the group
                pos = line.find(',')
                line_group = line[pos+1:]
                line_header = line[:pos]
                pos = line_header.find('=')
                line_param = line_header[pos+1:]
                line_name = line_header[:pos]
                group.name = line_param
                # Get the list of signals
                pos = line_group.find('=')
                line_param = line_group[pos+1:].strip('\"')
                group.signals = line_param.split (',')                     
                # Add group to the section
                section_dict.append(group)
            # Special case for module sources
            elif ("SOURCE_START" in section_name):  
                read_file.seek(read_pos)
                sources = parse_breaker_sources_section(read_file)
                config_dict["SOURCES"] = sources
            elif ("MEASURE" in section_name):
                # Change to a list for signals
                if (len(section_dict) == 0):
                    section_dict = list()

                signal = VoltageMeasurements()
                line_value = line.split(',')
                # Loop to add the optional parameters
                for i in line_value:
                    pos = i.find('=')
                    line_param = i[pos + 1:]
                    line_name = i[:pos]
                    if ("Name" in line_name):
                        signal.name = line_param
                    elif ("Type" in line_name):
                        signal.type = line_param
                    elif ("Unit" in line_name):
                        signal.unit = line_param
                    elif ("Nominal" in line_name):
                        signal.nominal = line_param
                # Add signal to the section
                section_dict.append(signal)
            # Special case for the glitch engine section
            elif ("GLITCH" in section_name):
                if not isinstance (section_dict, GlitchEngine):
                    section_dict = GlitchEngine ()

                pos = line.find('=')
                line_value = line[pos+1:]
                line_name = line[:pos]

                if (line_name in ("GlitchLength_Limits", "GlitchCycle_Limits")):
                    new_range = parse_limits_string (line_value)
                    attr_name = "length_limits" if line_name == "GlitchLength_Limits" else "cycle_limits"
                    range_param = getattr (section_dict, attr_name)
                    if (range_param is None):
                        range_param = ModuleRangeParam ()
                        setattr (section_dict, attr_name, range_param)
                    range_param.add_range (new_range)
                elif (line_name == "GlitchMultiplier_Settings"):
                    section_dict.multipliers = [parse_time_value (v) for v in line_value.split(',') if v]
                elif (line_name == "GlitchPrbs_Settings"):
                    section_dict.prbs_ratios = [v for v in line_value.split(',') if v]
                else:
                    section_dict.parameters[line_name] = line_value
            else:
                pos = line.find('=')
                line_value = line[pos+1:].strip()
                line_name = line[:pos].strip()
                section_dict[line_name] = line_value
    
    # Now build the appropriate module class
    # Assuming breaker for testing
    if (config_dict["HEADER"]["DeviceClass"] == "TorridonModule"):
        dev_caps = TorridonBreakerModule ()
        dev_caps.config_data = config_dict
        return dev_caps
    else:
        logger.error("Only 'TorridonModule' class devices are currently supported")
        return None

'''
Parses a single <...Limits> element (e.g. <SourceDelay_Limits>) containing one or more
<LimitsRange> children into a ModuleRangeParam
'''
def _parse_xml_range_param (limits_elem):
    range_param = ModuleRangeParam ()
    for range_elem in limits_elem.findall ("LimitsRange"):
        item = ModuleRangeItem ()
        item.unit = range_elem.findtext ("Unit")
        item.min_value = _parse_numeric (range_elem.findtext ("StartTime"))
        item.max_value = _parse_numeric (range_elem.findtext ("EndTime"))
        item.step_value = _parse_numeric (range_elem.findtext ("StepSize"))
        range_param.add_range (item)
    return range_param

'''
Parses the XML returned by the "sig:xml?" command into a TorridonBreakerModule, using the same
signal/source/measurement/glitch-engine classes as parse_config_file() for SIGNALS, SIGNAL_GROUPS,
SOURCES, GLITCH and MEASURE - so callers using those accessors do not need to care whether
capabilities came from the module directly or a .qfg file.

Two sections cannot be made equivalent, since sig:xml? (read from an already-connected module) does
not carry the same information as a .qfg file
'''
def parse_config_xml (xml_string):
    root = ET.fromstring (xml_string)
    config_dict = dict ()

    # --- Header ---
    # sig:xml? is read directly from an already-connected module, so unlike a .qfg file it carries
    # none of the file-matching metadata (device numbers, firmware/FPGA version ranges, description).
    # DeviceClass is set because this function only ever builds a TorridonBreakerModule, matching the
    # one DeviceClass parse_config_file() currently supports.
    config_dict["HEADER"] = {
        "DeviceClass": "TorridonModule",
        "DeviceDescription": None,
        "DeviceNumbers": None,
        "MinFirmwareRequired": None,
        "MinFpgaRequired": None,
    }

    # --- Features ---
    features = BreakerFeatures ()
    features_elem = root.find ("Features")
    if (features_elem is not None):
        features.supports_bounce = parse_feature_support (features_elem.findtext ("SupportsBounce"))
        features.supports_drive = parse_feature_support (features_elem.findtext ("SupportsDrive"))
        features.supports_triggering = parse_feature_support (features_elem.findtext ("SupportsTriggering"))
        features.supports_lane_width = parse_feature_support (features_elem.findtext ("SupportsLaneWidth"))
        features.max_lane_width = int (features_elem.findtext ("MaxLaneWidth") or 0)
        features.supports_glitch = parse_feature_support (features_elem.findtext ("SupportsGlitch"))
    config_dict["FEATURES"] = features

    # --- General capabilities ---
    # Synthesised from confirmed equivalences with legacy .qfg @GENERAL flags:
    general = dict ()
    # HotPlugRead_Present and HostPowerTriggering_Present are true for any module that answers
    # sig:xml? at all - reaching this point already means that is the case.
    general["HotPlugRead_Present"] = "true"
    general["HostPowerTriggering_Present"] = "true"
    # Triggering_Present <-> SupportsTriggering having a non-zero (present) version
    if (features.supports_triggering.present):
        general["Triggering_Present"] = "true"
    # HighResTiming_Present <-> SupportsBounce at version 2 (or higher - a later version implies at
    # least what version 2 provides, per the "higher version = newer/restructured" versioning rule)
    if (features.supports_bounce.version >= 2):
        general["HighResTiming_Present"] = "true"
    config_dict["GENERAL"] = general

    # --- Signals ---
    signals = list ()
    signals_elem = root.find ("Signals")
    if (signals_elem is not None):
        for sig_elem in signals_elem.findall ("Signal"):
            signal = BreakerModuleSignal ()
            signal.name = sig_elem.findtext ("Name")
            signal.signal_type = sig_elem.findtext ("Type")
            signal.glitch_present = _parse_bool (sig_elem.findtext ("GlitchPresent"))
            signal.drive_present = _parse_bool (sig_elem.findtext ("DrivePresent"))
            signal.drive_host = _parse_drive_level (sig_elem.findtext ("DriveHost"))
            signal.drive_device = _parse_drive_level (sig_elem.findtext ("DriveDevice"))
            signal.drive_monitor = _parse_bool (sig_elem.findtext ("DriveMonitor"))
            signal.monitor_host = _parse_bool (sig_elem.findtext ("MonitorHost"))
            signal.monitor_device = _parse_bool (sig_elem.findtext ("MonitorDevice"))
            signals.append (signal)
    config_dict["SIGNALS"] = signals

    # --- Signal Groups ---
    groups = list ()
    groups_elem = root.find ("Groups")
    if (groups_elem is not None):
        for group_elem in groups_elem.findall ("Group"):
            group = BreakerSignalGroup ()
            group.name = group_elem.findtext ("Name")
            group_signals_elem = group_elem.find ("Signals")
            if (group_signals_elem is not None):
                group.signals = [s.text for s in group_signals_elem.findall ("Signal")]
            groups.append (group)
    config_dict["SIGNAL_GROUPS"] = groups

    # --- Sources ---
    sources = list ()
    sources_elem = root.find ("Sources")
    if (sources_elem is not None):
        for source_elem in sources_elem.findall ("Source"):
            source = BreakerSource ()
            source.name = source_elem.findtext ("Name")
            source.parameters["Type"] = source_elem.findtext ("Type")
            source.parameters["Number"] = source_elem.findtext ("Number")
            default_delay = source_elem.findtext ("DefaultDelay")
            if (default_delay is not None):
                source.parameters["DefaultDelay"] = default_delay

            delay_limits_elem = source_elem.find ("SourceDelay_Limits")
            if (delay_limits_elem is not None):
                source.parameters["SourceDelay_Limits"] = _parse_xml_range_param (delay_limits_elem)

            bounce_elem = source_elem.find ("SourceBounce")
            if (bounce_elem is not None):
                for limits_tag in ("BounceLength_Limits", "BouncePeriod_Limits", "BounceDuty_Limits"):
                    limits_elem = bounce_elem.find (limits_tag)
                    if (limits_elem is not None):
                        source.parameters[limits_tag] = _parse_xml_range_param (limits_elem)

            sources.append (source)
    config_dict["SOURCES"] = sources

    # --- Glitch Engine ---
    glitch = GlitchEngine ()
    glitch_elem = root.find ("Glitch_Engine")
    if (glitch_elem is not None):
        length_limits_elem = glitch_elem.find ("GlitchLength_Limits")
        if (length_limits_elem is not None):
            glitch.length_limits = _parse_xml_range_param (length_limits_elem)
        cycle_limits_elem = glitch_elem.find ("GlitchCycle_Limits")
        if (cycle_limits_elem is not None):
            glitch.cycle_limits = _parse_xml_range_param (cycle_limits_elem)
        multipliers_elem = glitch_elem.find ("GlitchMultipliers")
        if (multipliers_elem is not None):
            glitch.multipliers = [parse_time_value (v.text) for v in multipliers_elem.findall ("Value")]
        prbs_elem = glitch_elem.find ("GlitchPrbs")
        if (prbs_elem is not None):
            glitch.prbs_ratios = [v.text for v in prbs_elem.findall ("Value")]
    config_dict["GLITCH"] = glitch

    # --- Measurements ---
    measurements = list ()
    measurements_elem = root.find ("Measurements")
    if (measurements_elem is not None):
        for m_elem in measurements_elem.findall ("Measurement"):
            measurement = VoltageMeasurements ()
            measurement.type = m_elem.findtext ("Type")
            measurement.name = m_elem.findtext ("Name")
            measurement.unit = m_elem.findtext ("Unit")
            measurement.nominal = m_elem.findtext ("Nominal")
            measurements.append (measurement)
    config_dict["MEASURE"] = measurements

    dev_caps = TorridonBreakerModule ()
    dev_caps.config_data = config_dict
    return dev_caps

# Parses the sources section of a Torridon breaker module, returning a list of sources
def parse_breaker_sources_section(file_access):
    new_source = None
    sources = list()
    first_source = True

    while(True):
        line, read_pos = read_config_line (file_access)

        # If the start of a source
        if ("@SOURCE_START" in line or first_source):
            # If first source, step back on line as we have consumed the first param already
            if (first_source):
                file_access.seek (read_pos)
                first_source = False
            # Parse the basic sections of the source info
            new_source = BreakerSource ()
            parse_source_basic_section (file_access, new_source)
            continue
        # Bounce sections describe pin-bounce abilities
        elif ("@SOURCE_BOUNCE" in line):
            parse_source_bounce_section (file_access, new_source)
            continue
        elif ("@SOURCE_END" in line):
            if (new_source is not None):
                sources.append (new_source)
                new_source = None
        # If the start of a new section
        elif ("@" in line):
            # Return the file to the line as if we had not read it
            file_access.seek(read_pos)
            # Exit the source parsing loop
            break

    return sources

# Parses the 'general' section, present for all sources
def parse_source_basic_section(file_access, source):

    while(True):
        line, read_pos = read_config_line (file_access)

        if ("@" not in line):
            # Limits sections need parsed into a limits object
            if ("_Limits" in line):
                pos = line.find('=')
                line_param = line[pos+1:]
                line_name = line[:pos]
                line_param = parse_limits_string (line_param)
                # If we've seen a limit section for this already
                if (line_name in source.parameters):
                    # Combine the limits
                    source.parameters[line_name].add_range (line_param)
                # Else start a new range
                else:
                    new_range = ModuleRangeParam ()
                    new_range.add_range (line_param)
                    source.parameters[line_name] = new_range
            # Else add as dictionary item
            else:
                pos = line.find('=')
                line_param = line[pos+1:]
                line_name = line[:pos]                
                
                if ("Name" in line_name):
                    source.name = line_param
                else:
                    source.parameters[line_name] = line_param
        else:
            break
    # Jump file back a line                               
    file_access.seek (read_pos)

# Parses a limit string into a ModuleRangeValue class                
def parse_limits_string (limit_text):
    new_item = ModuleRangeItem ()

    parts = limit_text.split(',')
    new_item.unit = parts[0]
    new_item.min_value = _parse_numeric (parts[1])
    new_item.max_value = _parse_numeric (parts[2])
    new_item.step_value = _parse_numeric (parts[3])

    return new_item

# Parse out the bounce parameter section, for sources with pin-bounce
def parse_source_bounce_section (file_access, source):
    while(True):
        line, read_pos = read_config_line (file_access)

        if ("@" not in line):
            # Limits sections need parsed into a limits object
            if ("_Limits" in line):
                pos = line.find('=')
                line_param = line[pos+1:]
                line_name = line[:pos]
                line_param = parse_limits_string (line_param)
                # If we've seen a limit section for this already
                if (line_name in source.parameters):
                    # Combine the limits
                    source.parameters[line_name].add_range (line_param)
                # Else start a new range
                else:
                    new_range = ModuleRangeParam ()
                    new_range.add_range (line_param)
                    source.parameters[line_name] = new_range
            # Else add as dictionary item
            else:
                pos = line.find('=')
                line_param = line[pos+1:]
                line_name = line[:pos]                                               
                source.parameters[line_name] = line_param
        else:
            break

    # Jump file back a line                               
    file_access.seek(read_pos)


# will return a list of QTLXXXX numbers for each module type
def return_module_type_list(module_type=None):
    current_path = os.path.dirname(os.path.abspath(__file__))
    only_dirs = [f for f in os.listdir(current_path) if os.path.isdir(os.path.join(current_path, f))]
    # only_dirs = ['Cable_Modules', 'Card_Modules', 'Drive_Modules', 'Power_Margining', 'Switch_Modules']

    if any(str(module_type).lower() in str(s).lower() for s in only_dirs):

        # capitalizing first letter - Linux path is case sensitive
        module_type = str(module_type).capitalize()
        post_fix = "_Modules"
        if module_type in "power":
            post_fix = "_Margining"

        # e.g. "card" + "_modules" > Not case sensitive
        module_type_path = os.path.join(current_path, module_type + post_fix)

        # getting all files from specified directory
        onlyfiles = [os.path.join(module_type_path, f) for f in os.listdir(module_type_path) if os.path.isfile(os.path.join(module_type_path, f))]

        filtered_modules = []
        # Grabbing first 7 character (QTLXXXX) for list without duplicates
        # [filtered_modules.append(f[:7]) for f in onlyfiles if f[:7] not in filtered_modules]

        for item in onlyfiles:
            x = parse_config_file(item)
            if x.config_data['HEADER']['DeviceNumbers'][:7] not in filtered_modules:
                filtered_modules.append(x.config_data['HEADER']['DeviceNumbers'][:7])

        return filtered_modules

def return_module_signals(module_connection=None, idn_string=None):

    config_path = get_config_path_for_module(idn_string=idn_string, module_connection=module_connection)
    parsed_file = parse_config_file(config_path)

    signals = []
    for item in parsed_file.config_data["SIGNALS"]:
        signals.append(item.name)

    # Future may need signal groups too
    # signal_groups = []
    # for item in parsed_file.config_data["SIGNAL_GROUPS"]:
    #     signal_groups.append(item)

    return signals
