"""Two ways to use the scan-with-details functions.

test_one   - select a module, then talk to it from a prompt.
test_two   - scan once, print everything the scan found out about every
             module, then hand that same list to the selection function
             instead of letting it scan again.
"""

from quarchpy.device import (DeviceInfo, getQuarchDevice,
                             scanDevicesWithDetails,
                             userSelectDeviceWithDetails)


def test_one():
    """Select a module and send it commands."""
    for device in userSelectDeviceWithDetails():
        print("Selected: " + str(device.connection_target))
        print("  firmware: " + str(device.firmware))
        print("  fpga:     " + str(device.fpga_1))
        myDevice = getQuarchDevice(device.connection_target)
        idnResponse = myDevice.send_command("*IDN?").replace("\r\n", " | ")
        print("  *IDN?:    " + idnResponse)
        cmd = ""
        while cmd != "$shutdown":
            cmd = input(">")
            print(myDevice.send_command(cmd))
        myDevice.close_connection()


def printEverythingKnown(device):
    """Prints every field the scan filled in for one module.

    Anything the module did not report is shown too, so it is obvious which
    details are missing rather than simply absent from the output.
    """
    print(str(device.connection_target or "no connection target"))

    for name, value in sorted(vars(device).items()):
        if name in ("network", "device_info"):
            continue  # handled below
        print("    {0:<26}: {1}".format(name, value))

    # fpgas is a property, so it is not in vars()
    print("    {0:<26}: {1}".format("fpgas (all reported)", device.fpgas))
    print("    {0:<26}: {1}".format("has_fixture", device.has_fixture))

    network = vars(device.network)
    if any(value is not None for value in network.values()):
        print("    network:")
        for name, value in sorted(network.items()):
            print("        {0:<22}: {1}".format(name, value))
    else:
        print("    {0:<26}: {1}".format("network", "none (found over USB)"))

    if device.device_info:
        print("    announce packet:")
        for name, value in sorted(device.device_info.items()):
            print("        {0:<22}: {1}".format(name, value))


def test_two():
    """Scan once, show everything found, then select from that same list."""
    print("Scanning...")
    discovered_devices = scanDevicesWithDetails()

    print("")
    print("Found " + str(len(discovered_devices)) + " module(s)")
    print("")

    for device in discovered_devices:
        printEverythingKnown(device)
        print("")

    # Pass the devices in so the selection does not scan a second time.
    selected = userSelectDeviceWithDetails(discovered_devices=discovered_devices)

    print("")
    print("Selected " + str(len(selected)) + " module(s):")
    for device in selected:
        print("    " + str(device.connection_target) +
              "   FW " + str(device.firmware) +
              "   FPGA " + str(device.fpga_1))


if __name__ == "__main__":
    test_one()
    test_two()
