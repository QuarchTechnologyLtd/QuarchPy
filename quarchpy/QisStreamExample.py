'''
AN-012 - Application note demonstrating control of power modules via QIS

Automating via QIS is a lower overhead that running QPS (Quarch Power Studio) in full but still
provides easy access to data for custom processing.  This example uses quarchpy functions to 
stream data from a quarch power module and dump it into a CSV file.

There are several examples that run in series, these can be commented out if you want to simplify the actions:

simpleStreamExample() - This example streams data to a csv file
averageStreamExample() - This example uses software averaging to create a csv file with an exact sample rate


QIS is distributed as part of the Quarchpy python package and does not require seperate install

########### VERSION HISTORY ###########

15/10/2018 - Pedro Cruz     - First Version
12/05/2012 - Matt Holsey    - Bug fixed - check stream is stopped before continuing with script
25/01/2023 - Andy Norrie    - Updated and reviewed for latest feature set and best practice

########### REQUIREMENTS ###########

1- Python (3.x recommended)
    https://www.python.org/downloads/
2- Java 8, with JaxaFX
    https://quarch.com/support/faqs/java/
3- Quarchpy python package
    https://quarch.com/products/quarchpy-python-package/
4- Quarch USB driver (Required for USB connected devices on windows only)
    https://quarch.com/downloads/driver/
5- Check USB permissions if using Linux:
    https://quarch.com/support/faqs/usb/

########### INSTRUCTIONS ###########

1. Connect a PPM/PAM device via USB or LAN and power it up
2. Run the script and follow any instructions on the terminal

####################################
'''


# Import other libraries used in the examples
import time     # Used for sleep commands
import logging  # Optionally used to create a log to help with debugging

from quarchpy.device import *
from quarchpy.qis import *
from quarchpy.user_interface.user_interface import quarchSleep

'''
Select the device you want to connect to here!
'''

def main():

    # If required you can enable python logging, quarchpy supports this and your log file
    # will show the process of scanning devices and sending the commands.  Just comment out
    # the line below.  This can be useful to send to quarch if you encounter errors
    # logging.basicConfig(filename='example.log', encoding='utf-8', level=logging.DEBUG)

    print ("\n\nQuarch application note example: AN-012")
    print ("---------------------------------------\n\n")

    # Start QIS (if it is already running, skip this step and also avoid closing it at the end)
    print ("Starting QIS...\n")
    closeQisAtEndOfTest=False
    if isQisRunning() == False:
        startLocalQis(headless=True)
        closeQisAtEndOfTest=True

    # Connect to the localhost QIS instance
    myQis = QisInterface()
    print ("QIS Version: " + myQis.sendAndReceiveCmd(cmd='$version'))

    # Ask the user to select a module to use, via the console.
    myDeviceID = myQis.GetQisModuleSelection()
    print ("Module Selected: " + myDeviceID + "\n")

    # If you know the name of the module you would like to talk to then you can skip module selection and hardcode the string.
    #myDeviceID = "USB:QTL1999-05-005"

    # Connect to the module
    myQuarchDevice = getQuarchDevice(myDeviceID, ConType = "QIS")

    # Convert the base device class to a power device, which provides additional controls, such as data streaming
    myPowerDevice = quarchPPM(myQuarchDevice)

    # This ensures the latest stream header is used, even for older devices.  This will soon become the default, but is in here for now
    # as is ensures the output CSV is in the latest format with units added to the row headers.
    myPowerDevice.sendCommand ("stream mode header v3")

    # These are optional commands which create additional channels in the output for power (current * voltage) and total power
    # (sum of individual power channels).  This can be useful if you don't want to calculate it in post processing
    #myPowerDevice.sendCommand ("stream mode power enable")
    #myPowerDevice.sendCommand ("stream mode power total enable")

    # Power (Current * Voltage) and Total Power (sum of individual power channels) are enabled by default to save calculating during post-processing.
    # To disable these additional power channels uncomment the following command:
    #myPowerDevice.sendCommand ("stream mode power disable")

    # Select one or more example functions to run, you can comment any of these out if you do not want to run them
    simpleStreamExample (myPowerDevice)
    #averageStreamExample (myPowerDevice)

    if closeQisAtEndOfTest==True:
        closeQis()

'''
This example streams measurement data to file, by default in the same folder as the script
'''
def simpleStreamExample(module):
    # Prints out connected module information
    print ("Running QIS SIMPLE STREAM Example")
    print ("Module Name: " + module.sendCommand ("hello?"))

    # Sets for a manual record trigger, so we can start the stream from the script
    print ("Set manual Trigger: " + module.sendCommand ("record:trigger:mode manual"))
    # Use 4k averaging (around 1 measurement every 32mS)
    #print ("Set averaging: " + module.sendCommand ("record:averaging 32k"))
    print ("Set averaging: " + module.sendCommand ("record:averaging 0"))

    # In this example we write to a fixed path
    print ("\nStarting Recording!")
    module.startStream('Stream.csv')
    #module.startStream('Stream_4uS.csv')

    # Delay for 30 seconds while the stream is running.  You can also continue
    # to run your own commands/scripts here while the stream is recording in the background
    print ("\nWait a while, for a period of data to record\n")
    #quarchSleep(30)
    quarchSleep(10)

    # Check the stream status, so we know if anything went wrong during the capture period
    print ("Checking the stream is running (all data has been captured)")
    streamStatus = module.streamRunningStatus()
    if ("Stopped" in streamStatus):
        if ("Overrun" in streamStatus):
            print ('\tStream interrupted due to internal device buffer has filled up')
        elif ("User" in streamStatus):
            print ('\tStream interrupted due to max file size has being exceeded')
        else:
            print("\tStopped for unknown reason")
    else:
        print("\tStream ran correctly")

    # Stop the stream.  This function is blocking and will wait until all remaining data has
    # been downloaded from the module
    print ("\nStopping the stream...")
    module.stopStream()

    print ("\nQIS SIMPLE STREAM Example - Complete!\n\n")



'''
This example is identical to the simpleStream() example, except that we use the additional QIS
averaging system to re-sample the stream to an arbitrary timebase
'''
def averageStreamExample(module):
    # Prints out connected module information
    print ("Running QIS RESAMPLING Example")
    print ("Module Name: " + module.sendCommand ("hello?"))

    # Sets for a manual record trigger, so we can start the stream from the script
    print ("Set manual Trigger: " + module.sendCommand ("record:trigger:mode manual"))
    # Use 16k averaging as this is a bit faster than we require
    print ("Set averaging: " + module.sendCommand ("record:averaging 16k"))

    # SET RESAMPLING HERE
    # This tells QIS to re-sample the data at a new timebase of 1 samples per second
    # Software averaging ensures that every sample of data is averaged, ensuring no data is lost
    print ("Setting QIS resampling to 1000mS")
    module.streamResampleMode ("1000ms")

    # In this example we write to a fixed path
    print ("\nStarting Recording!")
    module.startStream('Stream1_resampled.csv', '1000', 'Example stream to file with resampling')

    # Delay for 30 seconds while the stream is running.  You can also continue
    # to run your own commands/scripts here while the stream is recording in the background
    print ("\nWait a while, for a period of data to record\n")
    #quarchSleep(30)
    quarchSleep(8)

    # Check the stream status, so we know if anything went wrong during the capture period
    print ("Checking the stream is running (all data has been captured)")
    streamStatus = module.streamRunningStatus()
    if ("Stopped" in streamStatus):
        if ("Overrun" in streamStatus):
            print ('\tStream interrupted due to internal device buffer has filled up')
        elif ("User" in streamStatus):
            print ('\tStream interrupted due to max file size has being exceeded')            
        else:
            print("\tStopped for unknown reason")
    else:
        print("\tStream ran correctly")

    # Stop the stream.  This function is blocking and will wait until all remaining data has
    # been downloaded from the module
    module.stopStream()

    print ("\nQIS RESAMPLING Example - Complete!\n\n")

# Calling the main() function
if __name__=="__main__":
    main()