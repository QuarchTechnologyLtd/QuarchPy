'''
########### REQUIREMENTS ###########

1- Python (3.x recommended)
    https://www.python.org/downloads/
2- Quarchpy python package
    https://quarch.com/products/quarchpy-python-package/
3- Quarch USB driver (Required for USB connected devices on windows only)
    https://quarch.com/downloads/driver/
4- Check USB permissions if using Linux:
    https://quarch.com/support/faqs/usb/

########### INSTRUCTIONS ###########

Update to the latest quarcypy (python -m pip install quarchpy --upgrade) to get the latest configuration files
Connect any Quarch breaker/hot-plug module and run the script

####################################
'''
import logging

from quarchpy.config_files import *
from quarchpy.device import *


def main(filepath=None):
    # set arguments as global variables
    global fp, f
    fp = ""
    f = ""
    if filepath != None:
        fp = clean_string(filepath)
        try:
            f = open(fp, "x")
        except FileExistsError:
            userinput = input("File already exists! Would you like to overwrite the file? y|n\n")
            if userinput in {"N", "n", "NO", "No", "no"}:
                return 0
            else:
                print("\nFile at {} is being overwritten...\n".format(fp))
                f = open(fp, "w")
        except FileNotFoundError:
            print("Filepath is incorrect! Please fix it.")
            return 0



    logText("\n\n---------------------------------------")
    logText("Module Debug Command")
    logText("---------------------------------------\n\n")

    # Scan for quarch devices over all connection types (USB, Serial and LAN)
    logText("Scanning for devices...\n")
    deviceList = scanDevices('all', favouriteOnly=False)

    # You can work with the deviceList dictionary yourself, or use the inbuilt 'selector' functions to help
    # Here we use the user selection function to display the list on screen and return the module connection string
    # for the selected device
    moduleStr = userSelectDevice(deviceList, additionalOptions=["Rescan", "All Conn Types", "Quit"], nice=True)
    if moduleStr == "quit":
        return 0

    # If you know the name of the module you would like to talk to then you can skip module selection and hardcode the string.
    # moduleStr = "USB:QTL1743-01-001"

    # Create a device using the module connection string
    logText("\n\nConnecting to the selected device")
    my_device = getQuarchDevice(moduleStr)

    file = None
    try:
        # Find the correct config file for the connected module (breaker modules only for now)
        # We're passing the module connection here, the idn_string can be supplied instead if the module is not currently attached (simulation/demo mode)
        file = get_config_path_for_module(module_connection=my_device)
    except FileNotFoundError as err:
        logging.error(f"Config file not found for module : {moduleStr}\nExiting Script")
        my_device.closeConnection()
        return

    # Parse the file to get the device capabilities
    dev_caps = parse_config_file(file)

    if not dev_caps:
        logging.error(f"Could not parse config file for {moduleStr}\nExiting Script")
        my_device.closeConnection()
        return
    logText("\nCONFIG FILE LOCATED:")
    logText(file)
    logText("\n")

    # Print module status i.e,
    logText("\nModule Status\n===================\n")

    # Print the module identify and version information
    logText("\nModule Identity Information:\n")
    logText(my_device.sendCommand("*IDN?"))
    logText("\n")

    # Print the test state of the module
    logText("\nModule Self Test:")
    logText(my_device.sendCommand("*TST?"))
    logText("\n")

    # Print the power state of the module
    logText("Power State of Module:")
    logText(my_device.sendCommand("RUN:POWER?"))
    logText("\n")

    for key, value in dev_caps.get_general_capabilities().items():
        if key == "GlitchState_Read_Present" and value == "true":
            # Print glitch status of the module
            logText("Glitch Status:")
            logText(my_device.sendCommand("run:glitch?"))
            logText("\n")

            # Print additional glitch information
            logText("\nGlitch Engine\n===================\n")
            logText("Glitch Length: ", "end")
            logText(my_device.sendCommand("glitch:length?"))
            logText("\nGlitch Cycle Length: ", "end")
            logText(my_device.sendCommand("glitch:cycle:length?"))
            logText("\nPRBS Ratio: ", "end")
            logText(my_device.sendCommand("glitch:prbs?"))
            logText("\n")
        if key == "SignalMonitor_Present" and value == "true":
            logText("\nSignal Monitoring\n===================\n")
            for sig in dev_caps.get_signals():
                for key, value in sig.parameters.items():
                    if key == "SignalMonitor_Present" and value == "true":
                        logText(sig.name, "end")
                        logText(", Host Monitor: " + my_device.sendCommand("sig:{}:stat:host?".format(sig.name)), "end")
                        logText(", Device Monitor: " + my_device.sendCommand("sig:{}:stat:dev?".format(sig.name)), "end")
                        logText("\n")

    # Print the list of signals on the module, and the capability flags for each signal
    # This can be used to iterate a test over every signal in a module
    logText("\nSignal Setup\n===================\n")
    for sig in dev_caps.get_signals():
        logText(sig.name, "end")
        for key, value in sig.parameters.items():
            logText(", Source:" + my_device.sendCommand("sig:{}:sour?".format(sig.name)), "end")
            if key == "GlitchEnable_Present" and value == "true":
                logText(", Glitch Enable: " + my_device.sendCommand("sig:{}:glit:ena?".format(sig.name)), "end")
            if key == "SignalDrive_Present" and value == "true":
                logText(", Drive Open:" + my_device.sendCommand("sig:{}:dri:ope?".format(sig.name)), "end")
                logText(", Drive Closed:" + my_device.sendCommand("sig:{}:dri:clo?".format(sig.name)), "end")
        logText("\n")
    logText("\n")

    logText("\nVoltage Measurements\n===================\n")
    for volt in dev_caps.get_voltage_measurements():
        if volt.type == "Voltage":
            logText(volt.name + ": " + my_device.sendCommand("meas:volt {}".format(volt.name + "?")), "end")
        else:
            logText(volt.name + " Self Test: " + my_device.sendCommand("meas:volt:self {}".format(volt.name + "?")), "end")
        logText("\n")
    logText("\n")

    logText("\nSource Status\n===================\n")
    for source in dev_caps.get_sources():
        logText(source.name, "end")
        for key, value in source.parameters.items():
            sourcename = source.name[7:]
            if key == "Type" and value == "TIMED":
                logText(", Delay: " + my_device.sendCommand("sour:" + sourcename + ":delay?"), "end")
            if key == "SourceEnable_Present" and value == "true":
                logText(", Source: " + my_device.sendCommand("sour:" + sourcename + ":state?"), "end")
            if key == "SourceBounce_Present" and value == "true":
                logText(", Bounce: " + my_device.sendCommand("sour:" + sourcename + ":boun:mode?"), "end")
                logText(", Bounce-Length: " + my_device.sendCommand("sour:" + sourcename + ":boun:len?"), "end")
                logText(", Bounce-Period: " + my_device.sendCommand("sour:" + sourcename + ":boun:per?"), "end")
                logText(", Bounce-Duty: " + my_device.sendCommand("sour:" + sourcename + ":boun:duty?"), "end")
        logText("\n")

    logText("Finished script. \nClosing module connection.")
    if fp != "":
        f.close()
    my_device.closeConnection()

"""
    Logs text to terminal and file (if specified)

    Args:
        text (str): The input string to be logged.

"""
def logText(text, end=""):
    if fp != "":
        f.write(text)
    if end != "":
        print(text, end="")
    else:
        print(text)

"""
    Removes unwanted characters and whitespace from a string.

    Args:
        text (str): The input string to be cleaned.

    Returns:
        str: The cleaned string.
"""
def clean_string(text):
    cleaned_text = text.replace('"','')
    cleaned_text = cleaned_text.replace(" ", "")
    cleaned_text = cleaned_text.strip()
    return cleaned_text

def parse_arguments(argstring):
    import argparse

    parser = argparse.ArgumentParser(description='Module Debug parameters')
    parser.add_argument('-f', '--filepath', help='Choose filepath for debug log.', type=str.lower)

    args, extra_args = parser.parse_known_args(argstring)

    if len(extra_args) > 0:
        print("\nUnknown Argument(s): \n")
        print(*extra_args, sep=", ")
        print("\nList of Available Arguments: \n\n -f <file_path>\n")
        return 0

    return main(filepath=args.filepath)

if __name__ == "__main__":
    main()
