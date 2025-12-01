# QuarchPy Quick Start (Absolute Basics)

Copy/paste the code below into a file (e.g. `quick_start.py`) and run it with Python 3.
It:
1. Prints a header
2. Scans for devices (USB / Serial / LAN)
3. Lets you select one
4. Connects to the selected device

Make sure you have:
- Installed `quarchpy` (`pip install quarchpy`)
- Installed drivers (USB on Windows) or set permissions (Linux udev) if needed.

```python
import logging
from quarchpy.device import scanDevices, getQuarchDevice
from quarchpy.user_interface import userSelectDevice

def main():
    # If required you can enable python logging, quarchpy supports this and your log file
    # will show the process of scanning devices and sending the commands.  Just comment out
    # the line below.  This can be useful to send to quarch if you encounter errors
    # logging.basicConfig(filename='example.log', encoding='utf-8', level=logging.DEBUG)
    
    print("Quarch application note example: AN-006")
    print("---------------------------------------\n\n")

    # Scan for quarch devices over all connection types (USB, Serial and LAN)
    print("Scanning for devices...\n")
    deviceList = scanDevices('all', favouriteOnly=False)

    # You can work with the deviceList dictionary yourself, or use the inbuilt 'selector' functions to help
    # Here we use the user selection function to display the list on screen and return the module connection string
    # for the selected device
    moduleStr = userSelectDevice(
        deviceList,
        additionalOptions=["Rescan", "All Conn Types", "Quit"],
        nice=True
    )
    if moduleStr == "quit":
        return 0

    # If you know the name of the module you would like to talk to then you can skip module selection and hardcode the string.
    # moduleStr = "USB:QTL1999-05-005"

    # Create a device using the module connection string
    print("\n\nConnecting to the selected device")
    myDevice = getQuarchDevice(moduleStr)

    try:
        # Basic identify commands (optional)
        print("\nDevice Name:", myDevice.sendCommand("hello?"))
        print("\nFull Identity:\n", myDevice.sendCommand("*idn?"))
    finally:
        # Always close the connection
        myDevice.closeConnection()
        print("\nConnection closed.")

if __name__ == "__main__":
    main()
```

Run:
```bash
python quick_start.py
```
