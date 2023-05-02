#!/usr/bin/python
"""
Implements a simple time class to simplify working with large time values
"""
import logging


class TimeValue:
    """
    Describes a precise time duration for settings
    """
    
    time_value = None
    time_unit = None
    valid_units = ["ps", "ns", "us", "ms", "s"]

    def __init__ (self, from_time_string=None, from_time_value=0, from_time_unit=None):
        self.time_value = from_time_value
        self.time_unit = from_time_unit
        
        # Setup from a time unit string if one is specified
        if (from_time_string != None):
            # Try to find the split between numbers and units
            from_time_string = from_time_string.strip()
            for i in range( len(from_time_string) ):
                if (from_time_string[i].isalpha()):
                    split_char = i
                    break
                    
            # Fail if we can't find the 2 sections
            if (split_char == 0 or split_char >= len(from_time_string)):
                logging.error("Invalid time string, could not find the unit: " + from_time_string)
                raise Exception ("Invalid time string, could not find the unit: " + from_time_string)
            
            # Get the time value as a number
            time_str = from_time_string[:split_char].strip()
            self.time_value = int(time_str)
            
            # Get the unit for the time
            unit_str = from_time_string[split_char:].strip()
            if (unit_str.lower() not in self.valid_units):
                logging.error("Invalid time string, unit is not recognised: " + unit_str)
                raise Exception ("Invalid time string, unit is not recognised: " + unit_str)
            self.time_unit = unit_str.lower()
            
    def __str__(self):
        if (self.time_value == None or self.time_unit == None):
            logging.error("ERROR - Null Time Value, cannot return as string")
            return "ERROR - Null Time Value"
        else:
            return str(self.time_value) + str(self.time_unit)
            
        
            