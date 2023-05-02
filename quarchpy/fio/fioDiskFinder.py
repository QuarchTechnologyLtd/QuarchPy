from AbsDiskFinder import AbsDiskFinder
import os
import psutil

class fioDiskFinder (AbsDiskFinder):

    def returnDisk(self):

        deviceList = findDevices()



        deviceList = formatDevList(deviceList)

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


    def findDevices(self):
        templ = "%5s    %-17s %8s %8s %8s %5s%% %9s  %5s    %-15s"
        print(templ % ("INDEX", "Device", "Total", "Used", "Free", "Use ", "Type",
                       "Mount", "Opts"))

        index = 0

        # removes the host drive with this param
        deviceList = psutil.disk_partitions()

        print (deviceList)

        for idx, part in enumerate(deviceList):
            if os.name == 'nt':
                if 'cdrom' in part.opts or part.fstype == '':
                    # skip cd-rom drives with no disk in it; they may raise
                    # ENOENT, pop-up a Windows GUI error for a non-ready
                    # partition or just hang.
                    continue
            usage = psutil.disk_usage(part.mountpoint)

            print(templ % (
                idx,
                part.device,
                bytes2human(usage.total),
                bytes2human(usage.used),
                bytes2human(usage.free),
                int(usage.percent),
                part.fstype,
                part.mountpoint,
                part.opts))

        return deviceList


    def formatList(self, deviceList):
        newDevList = []

        for idx, dev in enumerate(deviceList):
            driveInfo = {
                "DRIVE": None,
                "MOUNT": None,
                "OPTS": None,
            }

            DevInfo = str(dev)

            DevInfo.strip()
            a = dev.device
            b = dev.mountpoint
            c = dev.opts

            driveInfo.update(dict(zip(['DRIVE', 'MOUNT', 'OPTS'], [a, b, c])))
            newDevList.append(driveInfo)

        return newDevList

    def bytes2human(n):
        # http://code.activestate.com/recipes/578019
        # >>> bytes2human(10000)
        # '9.8K'
        # >>> bytes2human(100001221)
        # '95.4M'
        symbols = ('K', 'M', 'G', 'T', 'P', 'E', 'Z', 'Y')
        prefix = {}
        for i, s in enumerate(symbols):
            prefix[s] = 1 << (i + 1) * 10
        for s in reversed(symbols):
            if n >= prefix[s]:
                value = float(n) / prefix[s]
                return '%.1f%s' % (value, s)
        return "%sB" % n