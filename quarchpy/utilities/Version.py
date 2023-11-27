"""
A utility class for versioning.
"""

import re

try:
    from typing import List
except ImportError:
    List = list  # For Python 2 compatibility

class Version:
    """
    Support for Python package version numbering.
    """

    @staticmethod
    def major_number(version_number_string):
        """ Returns the version major number. """
        major = int(Version.major_minor_patch_numbers(version_number_string)[0])
        return major

    @staticmethod
    def minor_number(version_number_string):
        """ Returns the version minor number. """
        minor = int(Version.major_minor_patch_numbers(version_number_string)[1])
        return minor

    @staticmethod
    def patch_number(version_number_string):
        """ Returns the version patch number. """
        patch = int(Version.major_minor_patch_numbers(version_number_string)[2])
        return patch

    @staticmethod
    def major_minor_patch_numbers(version_number_string):
        """ Returns the version patch number. """
        v_list = re.split(r"\.", version_number_string)
        return v_list

    @staticmethod
    def is_v1_ge_v2(v1, v2):
        """ Returns true if v1 >= v2, else false. """
        v1_version_list = Version.major_minor_patch_numbers(v1)
        v2_version_list = Version.major_minor_patch_numbers(v2)
        v1_version_number = int(''.join(v1_version_list))
        v2_version_number = int(''.join(v2_version_list))
        if v1_version_number >= v2_version_number:
            return True
        return False
