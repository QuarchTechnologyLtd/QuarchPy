import logging
import os, os.path, sys
import inspect
import quarchpy.config_files
from enum import Enum

'''
Describes a unit for time measurement
'''
class TimeUnit(Enum):
    "UNSPECIFIED",
    "nS",
    "uS",
    "mS",
    "S",

'''
Described a precise time duration for settings
'''
class TimeValue:
    time_value = None
    time_unit = None

    def __init__ (self):
        time_value = 0
        time_unit = TimeUnit.UNSPECIFIED

'''
Describes a single range element if a module range parameter
'''
class ModuleRangeItem:
    min_value = 0
    max_value = 0
    step_value = 0
    unit = None

    def __init__ (self):
        min_value = 0
        max_value = 0
        step_value = 0
        unit = None

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
        str = ""
        for item in self.ranges:
            str = str + item.min_value + "," + item.max_value + "," + item.step_value + "," + item.unit + "|"
        return str

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

        # Check for out of rang values
        if (value < range_item.min_value):
            result = range_item.min_value
        elif (value > range_item.max_value):
            result = range_item.max_value
        # Else value is in range
        else:
            low_steps = int((float(value) / float(range_item.step_value)) + 0.5)
            low_value = int(low_steps * range_item.step_value)
            high_value = int(low_value + range_item.step_value)

        # Get the closest step
        if (abs(low_value - value) < abs(high_value - value)):
            result - low_value
        else:
            result - high_value

        return result

    '''
    Returns the closest allowable value to the given number
    '''
    def get_closest_value (self, value):
        valid_value = -sys.maxsize -1
        in_range = list()
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

        return possible_value

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
    def get_max_value (self):
        valid_value = sys.maxsize

        for i in self.ranges:
            if (i.min_value < valid_value):
                valid_value = i.min_value

        return valid_value

'''
Describes a switched signal on a breaaker module
'''
class BreakerModuleSignal:
    name = None
    parameters = None

    def __init__ (self):
        self.name = None
        self.parameters = dict ()

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
    name = None
    type = None

    def __init__ (self):
        self.name = None
        self.type = None

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
        return self.config_data["GENERAL"]

    def get_voltage_measurements(self):
        return self.config_data["MEASURE"]

    def __init__ (self):        
        self.config_data = dict ()


'''
Tries to locate configuration data for the given module and return a structure of device capabilities to help the user
control the module and understand what its features are
'''
def get_device_capabilities (idn_string = None, module_connection = None):
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
        logging.error("Invalid parameters, no module information given")
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
            logging.error("Unable to identify module - no module number")
        if (device_fw is None):
            logging.error("Unable to identify module - no firmware version")
            result = False
        if (device_fpga is None):
            logging.error("Unable to identify module - no FPGA version")
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
                                logging.debug("Located matching config file: " + i["Config_Path"])
                                config_matches.append (i)

            # Sort the config files into preferred order
            if (len(config_matches) > 0):
                config_matches = sort_config_headers (config_matches)
                return config_matches[0]["Config_Path"]
            else:
                logging.error("No matching config files were found for this module")
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
            logging.error("Config file parse failed, @CONFIG section not found")

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
                logging.error("Config line does not meet required format of x=y: " + line)
                return None
            else:
                elements[line[:pos]] = line[pos+1:]

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
        logging.debug("Part number did not contain the version :" + device_number)
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
            logging.debug("Part number in config file is not in the right format: " + dev)
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
        logging.debug("Part number did not contain the version :" + device_number)
        return False

    # Check that the part number is fully qualified (will not be the case if the serial number is not set)
    if ("?" in device_number):
        logging.debug("Part number is not fully qualified :" + device_number)
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
            logging.debug("Exclude part number in config file is not in the right format: " + dev)
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
                # Add signal to the section
                section_dict.append(signal)
            else:
                pos = line.find('=')
                line_value = line[pos+1:]
                line_name = line[:pos]
                section_dict[line_name] = line_value
    
    # Now build the appropriate module class
    # TODO: Assuming breaker for testing
    if (config_dict["HEADER"]["DeviceClass"] == "TorridonModule"):
        dev_caps = TorridonBreakerModule ()
        dev_caps.config_data = config_dict
        return dev_caps
    else:
        logging.error("Only 'TorridonModule' class devices are currently supported")
        return None

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
    new_item.min_value = parts[1]
    new_item.max_value = parts[2]
    new_item.step_value = parts[3]

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
