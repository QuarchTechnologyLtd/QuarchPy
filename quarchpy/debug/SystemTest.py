import os
import platform
import sys
import subprocess

from quarchpy import *
from quarchpy.device import *
from quarchpy.connection_specific.jdk_jres.fix_permissions import main as fix_permissions, find_java_permissions

try:
    from importlib.metadata import distribution
except:
    try:
        from importlib_metadata import distribution
    except Exception as e:
        print("Failed to import distribution from importlib_metadata")

from quarchpy.device import *
from quarchpy.connection_specific.jdk_jres.fix_permissions import main as fix_permissions, find_java_permissions
from quarchpy.qis.qisFuncs import isQisRunning, startLocalQis
from quarchpy.connection_specific.connection_QIS import QisInterface
from quarchpy._version import __version__

def _test_communication():
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
    myDevice = get_quarch_device(moduleStr)
    QuarchSimpleIdentify(myDevice)
    # Close the module before exiting the script
    myDevice.close_connection()


def _test_system_info():
    print("")
    print("SYSTEM INFORMATION")
    print("------------------")
    print("OS Name: " + os.name)
    print("Platform System: " + platform.system())
    print("Platform: " + platform.platform())

    if "nt" in os.name:
        print("Platform Architecture: " + platform.architecture()[0])
    else:
        print(str(bytes(subprocess.check_output(['cat', '/etc/os-release'], stderr=subprocess.STDOUT)).decode()))
    print("Platform Release:  " + platform.release())

    print("\nPYTHON\n------")
    try:
        print("Python Version: " + sys.version)
    except:
        print("Unable to detect Python version")
    try:
        print("Quarchpy Version: " + get_quarchpy_version())
    except:
        print("Unable to detect Quarchpy version")
    try:
        print("Quarchpy info Location: " + str(distribution("quarchpy")._path))
    except Exception as e:
        print(e)
        print("Unable to detect Quarchpy location")

    print("python:  ")
    try:
        temp1 = bytes(subprocess.check_output(['python', '-m', 'pip', 'show', 'quarchpy'], stderr=subprocess.STDOUT)).decode()
        print(temp1)
    except:
        print("Unable to detect Quarchpy at this location")

    if "nt" not in os.name:
        print("sudo python:  ")
        try:
            temp2 = bytes(subprocess.check_output(['sudo', 'python', '-m', 'pip', 'show', 'quarchpy'], stderr=subprocess.STDOUT)).decode()
            print(temp2)
        except:
            print("Unable to detect Quarchpy at this location")

        print("python3:  ")
        try:
            temp3 = bytes(subprocess.check_output(['python3', '-m', 'pip', 'show', 'quarchpy'], stderr=subprocess.STDOUT)).decode()
            print(temp3)
        except:
            print("Unable to detect Quarchpy at this location")

        print("sudo python3:  ")
        try:
            temp4 = bytes(subprocess.check_output(['sudo', 'python3', '-m', 'pip', 'show', 'quarchpy'], stderr=subprocess.STDOUT)).decode()
            print(temp4)
        except:
            print("Unable to detect Quarchpy at this location")


    print("\nJAVA\n----")
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
    try:
        execute_permissions, message=find_java_permissions()
        print("Execute Permissions: ",execute_permissions, "\n",message)
    except:
        print("Unable to get j21 java permissions")
    try:
        print("\nQIS version number: " + get_QIS_version())
    except Exception as e:
        print("\nUnable to detect QIS version. Exception:" +str(e))


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
    print(device1.send_command("hello?"))
    print("")
    # Print the module identify and version information
    print("Module Identity Information: ")
    idn_info = device1.send_command("*idn?")
    print(idn_info)
    if "fixture" in idn_info.lower():
        print("\nFixture Identity Information: ")

        fixture_info = device1.send_command("fix idn?")
        print(fixture_info)


def get_QIS_version():
    """
    Returns the version of QIS.  This is the version of QIS currenty running on the local system if one exists.
    Otherwise the local version within quarchpy will be exectued and its version returned.

    Returns
    -------
    version: str
        String representation of the QIS version number
    """

    qis_version = "" # stub
    my_close_qis = False # Only close QIS if we opened it.
    try:
        qisRunning=isQisRunning()
    except Exception as e:
        print("Exception occurred while checking if qis was already running. Error:\n"+str(e))

    if qisRunning == False:
        my_close_qis = True
        startLocalQis(headless=True)

    myQis = QisInterface()
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
    content_to_write = "SUBSYSTEM==\"usb\", ATTRS{idVendor}==\"16d0\", MODE=\"0666\"\n" \
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
        _test_system_info()
    if bool_test_communication:
        _test_communication()



if __name__ == "__main__":
    main([])
    #find_java_permissions()
    #main(["--skipSystemInfo","--skipCommsTest"])
    #main(["--fixusb"])