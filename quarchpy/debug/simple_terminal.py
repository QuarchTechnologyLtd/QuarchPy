"""
This is a very simple terminal program for basic communication to quarch modules.
Feel free to expand and add your own features to this.

########### VERSION HISTORY ###########

26/11/2020 - Stuart Boon     - First Version

########### INSTRUCTIONS ###########
Select the module you would like to talk to.
Type desired command
Read response
"""
from quarchpy import *
from quarchpy.device import *
from quarchpy.user_interface import*
from quarchpy._version import __version__ as quarchpyVersion
def main():
    print(quarchpyVersion)
    moduleStr = userSelectDevice(nice=True, additionalOptions=["rescan","all conn types", "quit"])
    #moduleStr = "TCP:1999-05-005"
    if moduleStr == "quit":
        return 0
    print("Selected module is: " + moduleStr)
    # Create a device using the module connection string
    #moduleStr = "REST:1995-05-005"
    myDevice = getQuarchDevice(moduleStr)

    while True:
        user_input = requestDialog("","Send command to " + str(moduleStr) + " :")
        #Dollar commands are to be handled by the terminal
        if user_input.startswith("$"):
            if "$shutdown" in user_input.lower().replace(" ",""):
                print("Have a nice day!")
                break
            elif "$close connection" in user_input.lower():
                myDevice.closeConnection()
                return 0
            pass
        #All other commands are passed to the module
        else:
            print(myDevice.sendCommand(user_input))



if __name__ == "__main__":
    while True:
        main()