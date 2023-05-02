#!/usr/bin/env python
'''
This contains useful functions to help with disk target selection

Ensure installation of wmi and pywin32

########### VERSION HISTORY ###########

13/08/2018 - Andy Norrie    - First version, based on initial work from Pedro Leao
'''

from quarchpy.disk_test.iometerDiskFinder import iometerDiskFinder

def getDiskTargetSelection (purpose = "iometer"):

    driveInfo = {}

    """
    device will be a dictionary including the following parameters
        NAME
        DRIVE
        //Any additional that others use
    """
    """
    if purpose.lower() is "fio":

        fioObject = fioDiskFinder()
        disk = fioObject.returnDisk()
        printText (driveInfo) #change to logging if uncommented
    """

    if purpose.lower() == "iometer":
        iometerObject = iometerDiskFinder()
        driveInfo = iometerObject.returnDisk()

    return driveInfo