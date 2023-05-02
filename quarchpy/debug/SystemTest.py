from quarchpy import *
from quarchpy.device import *
import pkg_resources
from pkg_resources import parse_version, get_distribution
import os
import platform
import time
import sys
import subprocess
from quarchpy._version import __version__
# TODO: Move this code to a seperate system_test function so it can be called from other places.  Only argument handling should be done in main

def test_communication():
    print("")
    print("DEVICE COMMUNICATION TEST")
    print("-------------------------")
    print("")
    deviceList = scanDevices('all', favouriteOnly=False)
    print("Devices visible:\r\n" + str(deviceList))
    print("")
    moduleStr = userSelectDevice(deviceList, nice=True, additionalOptions=["Rescan", "Quit", "All Conn Types"])
    if moduleStr == "quit":
        print("User selected quit")
        return 0
    print("Selected module is: " + moduleStr)
    # Create a device using the module connection string
    myDevice = getQuarchDevice(moduleStr)
    QuarchSimpleIdentify(myDevice)
    # Close the module before exiting the script
    myDevice.closeConnection()

def test_system_info():
    print("")
    print("SYSTEM INFORMATION")
    print("------------------")
    print("OS Name: " + os.name)
    print("Platform System: " + platform.system())
    print("Platform: " + platform.platform())
    if "nt" in os.name: print("Platform Architecture: " + platform.architecture()[0])
    print("Platform Release:  " + platform.release())
    try:
        print("Quarchpy Version: " + get_quarchpy_version())
    except:
        print("Unable to detect Quarchpy version")
    try:
        print("Quarchpy Location: " + pkg_resources.get_distribution("quarchpy").location)
    except:
        print("Unable to detect Quarchpy location")
    try:
        print("Python Version: " + sys.version)
    except:
        print("Unable to detect Python version")
    try:
        print("QIS version number: " + get_QIS_version())
    except:
        print("Unable to detect QIS version")
    try:
        javaVersion = bytes(subprocess.check_output(['java', '-version'], stderr=subprocess.STDOUT)).decode()
        print("Java Version: " + str(javaVersion))
    except:
        print("Unable to detect java version"
              "If Java is not installed then QIS and QPS will NOT run")
    try:
        javaLocation = get_java_location()
        print("Java Location: " + str(javaLocation))
    except:
        print("Unable to detect java location"
              "If Java is not installed then QIS and QPS will NOT run")

    # Scan for all quarch devices on the system

def QuarchSimpleIdentify(device1):
    """
    Prints basic identification test data on the specified module, compatible with all Quarch devices

    Parameters
    ----------
    device1: quarchDevice
        Open connection to a quarch device
        
    """
    # Print the module name
    print("MODULE IDENTIFY TEST")
    print("--------------------")
    print("")
    print("Module Name: "),
    print(device1.sendCommand("hello?"))
    print("")
    # Print the module identify and version information
    print("Module Identity Information: ")
    print(device1.sendCommand("*idn?"))

def get_QIS_version():
    """
    Returns the version of QIS.  This is the version of QIS currenty running on the local system if one exists.
    Otherwise the local version within quarchpy will be exectued and its version returned.

    Returns
    -------
    version: str
        String representation of the QIS version number
        
    """

    qis_version = ""
    my_close_qis = False
    if isQisRunning() == False:
        my_close_qis = True
        startLocalQis(headless=True)
        
    myQis = qisInterface()
    qis_version = myQis.sendAndReceiveCmd(cmd="$version")
    if "No Target Device Specified" in qis_version:
        qis_version = myQis.sendAndReceiveCmd(cmd="$help").split("\r\n")[0]
    if my_close_qis:
        myQis.sendAndReceiveCmd(cmd = "$shutdown")
    return qis_version

def get_java_location():
    """
    Returns the location of java.

    Returns
    -------
    location: str
        String representation of the java location.
    """
    if "windows" in platform.platform().lower():
        location = bytes(subprocess.check_output(['where', 'java'], stderr=subprocess.STDOUT)).decode()
    elif "linux" in platform.platform().lower():
        location = bytes(subprocess.check_output(['whereis', 'java'], stderr=subprocess.STDOUT)).decode()
    else:
        location = "Unable to detect OS to check java version."
    return location

def get_quarchpy_version():
    try:
       return __version__
    except:
        return "Unknown"

def fix_usb():
    content_to_write = "SUBSYSTEM==\"usb\", ATTRS{idVendor}==\"16d0\", MODE=\"0666\"" \
                       "SUBSYSTEM==\"usb_device\", ATTRS{idVendor}==\"16d0\", MODE=\"0666\""

    if "centos" in str(platform.platform()).lower():
        content_to_write = "SUBSYSTEM==\"usb\", ATTRS{idVendor}==\"16d0\", MODE=\"0666\", GROUP=*\n " \
                           "SUBSYSTEM==\"usb_device\", ATTRS{idVendor}==\"16d0\", MODE=\"0666\", GROUP=*"

    destination = "/etc/udev/rules.d/20-quarchmodules.rules"

    f = open("/etc/udev/rules.d/20-quarchmodules.rules", "w")
    f.write(content_to_write)
    f.close()

    os.system("udevadm control --reload")
    os.system("udevadm trigger")

    print("USB rule added to file : /etc/udev/rules.d/20-quarchmodules.rules")


def main (args=None):
    """
    Main function to allow the system test to be called direct from the command line
    """
    bool_test_system_info = True
    bool_test_communication = True
    bool_fixusb=False
    if args is not None and len(args)>0:
        for arg in args:
            if "--fixusb" in str(arg).lower():
                bool_fixusb=True
                # todo: Should we still be running the debug info stuff after this?
            if "--skipsysteminfo" in str(arg).lower():
                bool_test_system_info=False
            if "--skipcommstest" in str(arg).lower():
                bool_test_communication=False

    if bool_fixusb:
        fix_usb()
    if bool_test_system_info:
        test_system_info()
    if bool_test_communication:
        test_communication()


if __name__ == "__main__":
    main([])
    #main(["--skipSystemInfo","--skipCommsTest"])
    #main(["--fixusb"])