import re
import time
import sys
wmi = None #global variable to inport WMI
from sys import platform
from subprocess import check_output
from quarchpy.disk_test.AbsDiskFinder import AbsDiskFinder
from quarchpy.user_interface import*
# Only load these when required, as they are not standard modules and may not be needed for many users



class iometerDiskFinder (AbsDiskFinder):


    def __init__(self):
        global wmi
        if platform == "win32":
            try:
                import wmi as newImport
                wmi = newImport
            except ImportError:
                raise ImportError ("'wmi' module required, please install this")
            try:
                import win32file, win32api
            except ImportError:
                raise ImportError ("'pywin32' module required, please install this")
            
    def returnDisk(self):        

        deviceList = self.findDevices()

        myDeviceID = self.formatList(deviceList)

        return myDeviceID


    def findDevices(self):
        # Get available physical disks
        diskList = self.getAvailableDisks("OS")
        # Get available mapped drives
        driveList = self.getAvailableDrives()
        # Combine into a single list
        deviceList = driveList + diskList

        return deviceList

    def formatList(self, deviceList):
        # printText selection dialog
        printText ("\n\n ########## STEP 2 = Select a target drive. ##########\n")
        printText (' ------------------------------------------------------------------')
        printText (' |  {:^5}  |  {:^10}  |  {:^35}  |'.format("INDEX", "VOLUME", "DESCRIPTION"))
        printText (' ------------------------------------------------------------------')

        templ = " |  %5s  |  %10s  |  %35s  |"

        for idx,i in enumerate(deviceList):
            printText (templ % (str(idx + 1), i.get("DRIVE"), i.get("NAME")))

            printText(' ------------------------------------------------------------------')

        # Get user to select the target
        try:
            drive_index = int(raw_input("\n>>> Enter the index of the target device: ")) - 1
        except NameError:
            drive_index = int(input("\n>>> Enter the index of the target device: ")) - 1

        # Verify the selection
        if (drive_index > -1):
            myDeviceID = deviceList[drive_index]
        else:
            myDeviceID = None

        return myDeviceID


    '''
    Gets a list of available host drives, excluding the one the host os running on if specified
    '''
    def getAvailableDisks(self,hostDrive):
        driveList = []

        diskNum = 0

        diskScan = wmi.WMI()

        # Loop through disks
        for disk in diskScan.Win32_diskdrive(["Caption", "DeviceID", "FirmwareRevision"]):
            driveInfo = {
                "NAME": None,
                "DRIVE": None,
                "FW_REV": None,
            }

            DiskInfo = str(disk)

            # Try to get the disk caption
            DiskInfo.strip()
            a = re.search('Caption = "(.+?)";', DiskInfo)
            if a:
                diskName = a.group(1)

            # Try to get the disk ID
            b = re.search('DRIVE(.+?)";', DiskInfo)
            if b:
                if b == "":
                    b = "\"\""
                diskId = b.group(1)

                # Try to get the disk FW
            diskFw = None
            c = re.search('FirmwareRevision = "(.+?)";', DiskInfo)
            if c:
                diskFw = c.group(1)

                # Skip if this is our host drive!
            if (diskName != hostDrive):
                # Append drive info to array
                driveInfo.update(dict(zip(['NAME', 'DRIVE', 'FW_REV'], [diskName, diskId, diskFw])))
                # driveInfo = collections.OrderedDict(driveInfo)
                driveList.append(driveInfo)

        # Return the list of drives
        return driveList


    '''
    Gets a list of available drive letters, excluding the current drive
    '''
    def getAvailableDrives(self):
        import win32file, win32api
        # return string of logicaldisks' specified attributes
        RList = check_output("wmic logicaldisk get caption, Description")

        # decode if python version 3
        if sys.version_info.major == 3:
            RList = str(RList, "utf-8")

        # split into readable items
        RList_Lines = RList.split("\n")

        RList_MinusNetwork = []

        # appaend all drives to list that are not network drives
        for item in RList_Lines:
            if "Network Connection" not in item:
                if len(item) > 0:
                    RList_MinusNetwork.append(item[0:item.find("  ")])

        # remove column headers
        del RList_MinusNetwork[0]

        # function call to remove every occurance of \r in list
        RList_MinusNetwork = self.remove_values_from_list(RList_MinusNetwork, "\r")

        RL_DrivesAndVolumeInfo = []

        # call function to return volume name of each drive (if available)
        for i in RList_MinusNetwork:
            i = i.replace(":", "://")
            try:
                win32api.GetVolumeInformation('C://')
                tempVar = win32api.GetVolumeInformation(i)
                tempVar2 = win32api.GetVolumeInformation(i)[0]

                RL_DrivesAndVolumeInfo.append(win32api.GetVolumeInformation(i)[0])
                RL_DrivesAndVolumeInfo.append(i)
                time.sleep(0.1)
            except:
                continue

        driveList = []

        try:
            for i in xrange(0, len(RL_DrivesAndVolumeInfo), 2):
                driveInfo = {
                    "NAME": None,
                    "DRIVE": None,
                    "FW_REV": None,
                }
                driveInfo.update(
                    dict(zip(['NAME', 'DRIVE', 'FW_REV'], [RL_DrivesAndVolumeInfo[i], RL_DrivesAndVolumeInfo[i + 1], ""])))
                # driveInfo = collections.OrderedDict(driveInfo)
                driveList.append(driveInfo)
        except:
            for i in range(0, len(RL_DrivesAndVolumeInfo), 2):
                driveInfo = {
                    "NAME": None,
                    "DRIVE": None,
                    "FW_REV": None,
                }
                driveInfo.update(
                    dict(zip(['NAME', 'DRIVE', 'FW_REV'], [RL_DrivesAndVolumeInfo[i], RL_DrivesAndVolumeInfo[i + 1], ""])))
                # driveInfo = collections.OrderedDict(driveInfo)
                driveList.append(driveInfo)

        return driveList


    '''
    Simple function to remove a given item from a list
    '''


    def remove_values_from_list(self, the_list, val):
        return [value for value in the_list if value != val]

