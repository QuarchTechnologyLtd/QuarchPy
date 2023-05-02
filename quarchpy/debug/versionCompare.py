"""
Provides functions to compare quarchpy versions

"""

import pkg_resources
from pkg_resources import parse_version, get_distribution
import re
import logging
from quarchpy.debug.SystemTest import get_quarchpy_version

def requiredQuarchpyVersion (requiredVersion):
    """
    Checks if the given (required) version is present.  This is used by example scripts to ensure the features they use
    are supported by the installed package version
    
    Parameters
    ----------
    requiredVersion : str
        String representation of the minimum quarchpy version required
        
    Returns
    -------
    safe_to_run : bool
        True if the minimum version requirement is met, otherwise false
    
    """

    # Check for internal dev versions of quarchpy
    currentVersion =get_quarchpy_version()
    if "dev" in currentVersion.lower():
        logging.warning("Using Dev version of quarchpy: Allowing continue")
        return True
    requiredVersion=requiredVersion.split(".")
    currentVersion =currentVersion.split(".")

    # Parse the version to numbers
    i = 0
    for x in requiredVersion:
        requiredVersion[i] = int(x)
        i+=1
    i= 0
    for x in currentVersion:
        currentVersion[i] = int(x)
        i+=1

    # Check each part of the numbers for the minimum version
    if currentVersion[0] < requiredVersion[0]:
        raise ValueError("Current quarchpy version " + str(currentVersion) + " is not high enough, upgrade to " + str(
            requiredVersion) + " or above.")
        return False
    elif currentVersion[0] > requiredVersion[0]:
        return True
    else:
        if currentVersion[1] < requiredVersion[1]:
            raise ValueError(
                "Current quarchpy version " + str(currentVersion) + " is not high enough, upgrade to " + str(
                    requiredVersion) + " or above.")
            return False
        elif currentVersion[1] > requiredVersion[1]:
            return True
        else:
            if currentVersion[2] < requiredVersion[2]:
                raise ValueError(
                    "Current quarchpy version " + str(currentVersion) + " is not high enough, upgrade to " + str(
                        requiredVersion) + " or above.")
                return False
            elif currentVersion[2] > requiredVersion[2]:
                return True
            else: 
                return True