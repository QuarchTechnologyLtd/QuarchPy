"""
This is a very simple terminal program for basic communication to quarch modules.
Feel free to expand and add your own features to this.

########### VERSION HISTORY ###########

26/11/2020 - Stuart Boon  - First Version

########### INSTRUCTIONS ###########
Select the module you would like to talk to.
Type desired command
Read response
"""
from typing import Optional

from quarchpy import *
from quarchpy.device import *
from quarchpy.user_interface import *
from quarchpy._version import __version__ as quarchpyVersion
from typing import Union


def main():
    printText("Quarchpy v" + str(quarchpyVersion))
    myDevice: Union[quarchDevice, subDevice, str] = ""
    while myDevice != "shutdown":  #Main loop
        moduleStr = userSelectDevice(nice=True, additionalOptions=["Rescan", "All Conn Types", "Specify IP Address", "Quit"])
        #moduleStr = "TCP:1999-05-005"
        if moduleStr == "quit":
            return 0
        printText("Selected module is: " + moduleStr)
        # Create a device using the module connection string
        # moduleStr = "REST:1995-05-005"
        myDevice = get_quarch_device(moduleStr)

        while myDevice is not None and myDevice != "shutdown":  # CMD parsing loop
            user_input = requestDialog("", "Send command to " + str(moduleStr) + " :")
            # Dollar commands are to be handled by the terminal
            if user_input.startswith("$"):
                if "$shutdown" == user_input.lower().replace(" ", "").strip():
                    printText("Have a nice day!")
                    myDevice = "shutdown"
                elif "$close connection" == user_input.lower().strip():
                    myDevice.close_connection()
                    myDevice = ""
                elif "$rst module" == user_input.lower().strip():
                    printText("Reset successful :" + str(myDevice.reset_device()))
                pass

            #All other commands are passed to the module
            else:
                printText(myDevice.send_command(user_input))
    return None


if __name__ == "__main__":
    main()
