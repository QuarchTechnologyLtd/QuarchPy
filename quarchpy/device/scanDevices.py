import time
import socket
import sys
import operator
import logging
import os

from sys import platform  # Used to check the operating system (e.g., 'win32', 'linux')

# Import configuration parsing utility
from quarchpy.config_files.quarch_config_parser import return_module_type_list
# Import user interface elements (specific names and the module itself)
from quarchpy.user_interface import *  # Imports functions like printText, requestDialog, listSelection
from quarchpy.user_interface import User_interface  # Imports the User_interface class

# Attempt to import USB connection specifics, handle potential errors
try:
    from quarchpy.connection_specific.connection_USB import importUSB  # Function to dynamically import USB library
except ImportError:
    # Print error if USB import fails, often due to architecture mismatch (e.g., 32-bit Python on 64-bit OS)
    printText("System Compatibility issue - Is your Python architecture consistent with the Operating System?")
    pass  # Allow execution to continue even if USB is unavailable

# Import base device classes and connection types
from quarchpy.device import quarchDevice, quarchArray
from quarchpy.connection_specific.connection_Serial import serialList, serial  # Serial port listing and interaction
from quarchpy.device.quarchArray import isThisAnArrayController  # Function to check if a device is an array controller
from quarchpy.connection_specific.connection_USB import TQuarchUSB_IF  # USB interface class
from quarchpy.connection_specific import connection_ReST, connection_TCP  # REST and TCP connection classes
from quarchpy.connection_specific.mDNS import MyListener  # mDNS listener class for Zeroconf discovery

'''
Merge two dictionaries and return the result.
'y' dictionary values overwrite 'x' dictionary values if keys overlap.
'''


def mergeDict(x, y):
    """Merges two dictionaries. If 'y' is None, returns 'x'."""
    if y is None:
        return x
    else:
        # Create a copy of x to avoid modifying the original
        merged = x.copy()
        # Update the copy with items from y
        merged.update(y)
        return merged


'''
Scan for Quarch modules across all available COM ports.
'''


def list_serial(debuPrint=False):
    """
    Scans system COM ports to find connected Quarch devices via Serial.

    Args:
        debuPrint (bool, optional): If True, prints debug information. Defaults to False.

    Returns:
        dict: A dictionary where keys are connection targets (e.g., "SERIAL:COM3")
              and values are the reported serial numbers (e.g., "QTL1826-01-001").
    """
    # Get a list of available serial ports [(port_name, description, hwid), ...]
    serial_ports = serialList.comports()
    serial_modules = dict()  # Dictionary to store found serial modules

    # Iterate through each detected serial port
    for i in serial_ports:
        port_name = i[0]
        logging.debug(f"Scanning for Quarch devices on: {port_name}")
        ser = None  # Ensure ser is defined before try block finishes
        try:
            # Attempt to open the serial port with standard Quarch settings
            ser = serial.Serial(port_name, 19200, timeout=0.5, write_timeout=0.5)
            # Send the command to request the serial number
            ser.write(b'*serial?\r\n')
            # Read the response (up to 64 bytes)
            s = ser.read(size=64)
            # Process the response: split lines, take the second line (usually the serial)
            if s and len(s.splitlines()) > 1:
                serial_module_bytes = s.splitlines()[1]
                # Decode bytes to string and clean up extraneous characters
                serial_module = serial_module_bytes.decode('ascii', errors='ignore').replace("'", "").replace("b", "")

                # Prepend "QTL" if missing (standard prefix)
                if "QTL" not in serial_module:
                    serial_module = "QTL" + serial_module

                # Basic validation: check if the format looks like a Quarch serial/enclosure number
                # (e.g., QTL1826-01-001 has dashes at positions 7 and 10)
                if len(serial_module) > 10 and serial_module[7] == "-" and serial_module[10] == "-":
                    # Store the device: key is "SERIAL:<port>", value is the serial number
                    connection_target = f"SERIAL:{port_name}"
                    serial_modules[connection_target] = serial_module
                    logging.debug(f"Located quarch module: {serial_module} on {port_name}")
            else:
                logging.debug(f"No valid response received from {port_name}")

        except Exception as err:
            # Log any errors during serial port communication
            logging.debug(f"Exception during serial scan on {port_name}: {err}")
            pass  # Continue to the next port even if one fails
        finally:
            # Ensure the serial port is closed if it was opened
            if ser and ser.is_open:
                ser.close()
            logging.debug(f"Finished scanning for Quarch devices on: {port_name}")

    return serial_modules


'''
Scan for all Quarch devices available over USB.
'''


def list_USB(debuPrint=False):
    """
    Scans system USB devices to find connected Quarch modules.

    Args:
        debuPrint (bool, optional): If True, prints debug information. Defaults to False.

    Returns:
        dict: A dictionary where keys are connection targets (e.g., "USB:QTL1826-01-001")
              and values are the reported serial or enclosure numbers.
              May contain "USB:???" : "LOCKED MODULE" for inaccessible devices.
    """
    QUARCH_VENDOR_ID = 0x16d0
    QUARCH_PRODUCT_ID1 = 0x0449  # Standard Quarch USB Product ID

    usb_modules = dict()  # Dictionary to store found USB modules
    hdList = []  # List to store devices needing enclosure number check (e.g., PPMs)
    usb_permission_error = False  # Flag for potential Linux/macOS permission issues

    # Dynamically import and initialize the USB library context
    try:
        usb1 = importUSB()
        if usb1 is None:
            logging.error("Failed to import USB library.")
            return usb_modules  # Cannot proceed without USB library
        context = usb1.USBContext()
        usb_list = context.getDeviceList()
    except Exception as e:
        logging.error(f"Failed to initialize USB context or get device list: {e}")
        return usb_modules  # Cannot proceed

    if debuPrint: printText(f"Raw USB device list: {usb_list}")

    # Iterate through all detected USB devices
    for i in usb_list:
        i_handle = None  # Ensure handle is defined
        try:
            # Check if the device matches Quarch Vendor and Product IDs
            if (i.device_descriptor.idVendor == QUARCH_VENDOR_ID and
                    i.device_descriptor.idProduct == QUARCH_PRODUCT_ID1):

                logging.debug(f"Attempting to open USB handle to potential Quarch module: {i}")
                # Attempt to open the device handle
                i_handle = i.open()

                # Get the serial number string descriptor (index 3)
                module_sn_raw = i_handle.getASCIIStringDescriptor(3)
                module_sn = module_sn_raw.strip()

                # Prepend "QTL" if missing
                if "QTL" not in module_sn:
                    module_sn = "QTL" + module_sn

                # Check if this module type requires enclosure number lookup (e.g., PPMs)
                if any(model in module_sn for model in ["1944", "2098"]):
                    hdList.append(i)  # Add device object to list for later processing
                    # Don't add to usb_modules yet, wait for enclosure number

                else:
                    # Standard module, use serial number directly
                    connection_target = f"USB:{module_sn}"
                    usb_modules[connection_target] = module_sn
                    logging.debug(f"Located USB module: {module_sn}")

                if debuPrint:
                    # Print other descriptors if debugging
                    desc2 = i_handle.getASCIIStringDescriptor(2)  # Usually Product String
                    desc1 = i_handle.getASCIIStringDescriptor(1)  # Usually Manufacturer String
                    printText(f"Descriptors for {module_sn}: SN='{module_sn_raw}', Prod='{desc2}', Manu='{desc1}'")

        except Exception as err:
            logging.debug(f"USB exception during device processing: {err}")
            # Handle specific errors
            if "LIBUSB_ERROR_ACCESS [-3]" in str(err):
                logging.warning(f"USB Access Error for device {i}. Device may be in use or permissions lacking.")
                # Check for missing udev rule on non-Windows platforms
                if platform != "win32" and not os.path.isfile("/etc/udev/rules.d/20-quarchmodules.rules"):
                    usb_permission_error = True  # Set flag to show warning later
                usb_modules["USB:???"] = "LOCKED MODULE"  # Mark as inaccessible
            elif "LIBUSB_ERROR_PIPE" in str(err):
                logging.warning(f"USB Pipe Error for device {i}. Could indicate communication issue.")
                usb_modules["USB:???"] = "COMMUNICATION ERROR"
            elif "LIBUSB_ERROR_NO_DEVICE" in str(err):
                logging.warning(f"USB No Device Error for device {i}. Device may have been disconnected.")
                # Don't add to dict if it disappeared
            else:
                # Generic locked/error state
                usb_modules["USB:???"] = "LOCKED MODULE"

        finally:
            # Ensure the handle is closed if it was opened
            if i_handle:
                try:
                    logging.debug(f"Closing USB handle to module: {i}")
                    i_handle.close()
                except Exception as close_err:
                    # Log error on closing but continue
                    logging.error(f"Exception on closing USB port {i}: {close_err}")

    # --- Process devices requiring enclosure number lookup ---
    # Iterate through the list of devices identified as needing enclosure numbers
    for module_device_obj in hdList:
        QquarchDevice = None  # Interface object
        try:
            # Create a USB interface instance using the existing context
            QquarchDevice = TQuarchUSB_IF(context)
            # Assign the device object (not handle) to the interface
            QquarchDevice.connection = module_device_obj
            # Open the port using the interface logic
            QquarchDevice.OpenPort()
            time.sleep(0.02)  # Short delay sometimes needed after opening
            QquarchDevice.SetTimeout(2000)  # Set command timeout

            # Query the device for serial and enclosure numbers
            serialNo = QquarchDevice.RunCommand("*serial?").replace("\r\n", "").strip()
            enclNo = QquarchDevice.RunCommand("*enclosure?").replace("\r\n", "").strip()

            # Construct the enclosure number string (e.g., QTL1944-01-001)
            encl_target_val = "QTL" + enclNo
            connection_target = f"USB:{encl_target_val}"

            # Add the enclosure number entry to the dictionary
            usb_modules[connection_target] = encl_target_val
            logging.debug(f"Located USB module (using enclosure no): {encl_target_val}")

            # --- Clean up potential duplicate serial number entry ---
            # (The initial loop might have added a serial-based entry before identifying it needed enclosure lookup)
            # This part seems slightly redundant given the logic in the first loop, but acts as a safeguard.
            keyToFind = f"USB:QTL{serialNo}"
            if keyToFind in usb_modules and keyToFind != connection_target:
                logging.debug(f"Removing potentially redundant serial entry {keyToFind}")
                del usb_modules[keyToFind]

        except Exception as encl_err:
            logging.error(f"Failed to get enclosure number for {module_device_obj}: {encl_err}")
            # Add a placeholder if enclosure lookup fails
            usb_modules[f"USB:ENCL_ERR_{serialNo or '???'}"] = "ENCLOSURE LOOKUP FAILED"
        finally:
            # Ensure the port is closed via the interface object
            if QquarchDevice and QquarchDevice.deviceHandle:
                QquarchDevice.ClosePort()
                QquarchDevice.deviceHandle = None  # Clear the handle reference

    # If a permission error was flagged on Linux/macOS, show a helpful warning
    if usb_permission_error:
        logging.warning("Potential permission error accessing Quarch module(s) via USB.")
        logging.warning("If unknown, run 'sudo python3 -m quarchpy.run debug --fixusb' to add necessary udev rules.")

    return usb_modules


'''
List all Quarch devices found over LAN, using a UDP broadcast scan.
Can also perform a targeted lookup if ipAddressLookup is provided.
'''


def list_network(target_conn="all", debugPring=False, lanTimeout=1, ipAddressLookup=None):
    """
    Scans the local network for Quarch devices using UDP broadcast/lookup.

    Args:
        target_conn (str, optional): Filters discovery by connection type ("all", "tcp", "rest", "telnet"). Defaults to "all".
        debugPring (bool, optional): If True, prints debug information. Defaults to False. (Typo in original name)
        lanTimeout (int, optional): Timeout in seconds for waiting for UDP responses. Defaults to 1.
        ipAddressLookup (str, optional): If provided, performs a targeted lookup for this specific IP address first. Defaults to None.

    Returns:
        dict: A dictionary where keys are connection targets (e.g., "TCP:192.168.1.100", "REST:192.168.1.101")
              and values are the reported serial or enclosure numbers.
    """
    retVal = {}  # Dictionary to store all found network modules
    lan_modules = dict()  # Temp dictionary for results from a single interface iteration
    specifiedDeviceResponse = None  # Stores response from direct IP lookup via UDP
    moduleFoundByIP = None  # Stores module name if found via direct IP lookup

    # --- Get list of local IP addresses for broadcasting ---
    try:
        # socket.gethostbyname_ex returns (hostname, aliaslist, ipaddrlist)
        hostname, _, ipList_raw = socket.gethostbyname_ex(socket.gethostname())
        # Add empty string to potentially bind to 'any' interface if needed, though binding specific IPs is generally preferred.
        ipList = ipList_raw + [""]  # Use specific local IPs for binding
        logging.debug(f"Local Hostname: {hostname}, Interfaces for broadcast binding: {ipList}")
    except socket.gaierror as e:
        logging.error(f"Could not get local host IP addresses: {e}. Network scan may fail.")
        ipList = [""]  # Fallback to attempting 'any' interface

    # --- Iterate through each local interface IP for binding ---
    for ip in ipList:
        mySocket = None  # Ensure socket is defined
        logging.debug(f"Attempting UDP broadcast/listen on interface bound to IP: {ip or 'ANY'}")
        try:
            # Create UDP socket
            mySocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            # Allow broadcasting
            mySocket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            # Set timeout for receiving responses
            mySocket.settimeout(lanTimeout)
            # Bind to the specific local IP and a chosen ephemeral port (or OS assigned if 0)
            # Port 56732 seems arbitrarily chosen here.
            bind_port = 56732
            mySocket.bind((ip, bind_port))
            logging.debug(f"Socket bound successfully to {ip}:{bind_port}")

            # --- Targeted IP Lookup (if requested) ---
            if ipAddressLookup:
                # Attempt direct UDP discovery, then REST/TCP fallback via lookupDevice
                logging.debug(f"Performing targeted lookup for IP: {ipAddressLookup}")
                # lookupDevice attempts UDP send/recv, then REST/TCP if UDP fails
                # It updates lan_modules directly if REST/TCP succeeds.
                specifiedDeviceResponse, moduleFoundByIP = lookupDevice(str(ipAddressLookup).strip(), mySocket,
                                                                        lan_modules, moduleFoundByIP)
                # specifiedDeviceResponse will contain UDP response bytes if UDP lookup worked

            # --- UDP Broadcast Discovery ---
            broadcast_ip = '255.255.255.255'  # Standard broadcast address
            discovery_port = 30303  # Quarch discovery port
            discovery_message = b'Discovery: Who is out there?\0\n'
            logging.debug(f"Sending UDP broadcast discovery message to {broadcast_ip}:{discovery_port}")
            mySocket.sendto(discovery_message, (broadcast_ip, discovery_port))

            # --- Receive UDP Responses ---
            while True:
                network_module_info = {}  # Dictionary to parse individual response
                msg_received = None
                sender_ip = None
                try:
                    # Wait for a response packet
                    msg_received_raw, sender_address = mySocket.recvfrom(256)  # Buffer size 256
                    msg_received = msg_received_raw  # Keep raw bytes
                    sender_ip = sender_address[0]  # Get sender IP
                    logging.debug(f"Received UDP response from {sender_ip}")

                except socket.timeout:
                    # Expected timeout when no more devices respond
                    logging.debug(f"UDP receive timeout on interface {ip}. No more responses.")
                    # Check if a targeted device response was captured earlier
                    if specifiedDeviceResponse:
                        logging.debug("Processing stored response from targeted UDP lookup.")
                        msg_received = specifiedDeviceResponse[0]  # Use stored bytes
                        sender_ip = specifiedDeviceResponse[1][0]  # Use stored IP
                        specifiedDeviceResponse = None  # Clear stored response
                    else:
                        break  # Exit receive loop for this interface
                except Exception as e:
                    logging.error(f"Error receiving UDP data on interface {ip}: {e}")
                    break  # Exit receive loop on other errors

                # --- Parse Received UDP Payload ---
                # The payload uses key-value pairs, often with non-ASCII keys.
                # Original code splits by \r\n and handles keys differently based on position/content.
                try:
                    # Split the payload by \r\n, ignore trailing empty element
                    splits = msg_received.split(b"\r\n")
                    if splits[-1] == b'': del splits[-1]

                    for idx, line_bytes in enumerate(splits):
                        # Heuristic parsing based on original code's logic:
                        # First two lines: index is line number (0, 1), value is decoded string
                        # Subsequent lines: index is first byte (key), value is remaining bytes
                        if idx <= 1:
                            key = str(idx)  # Use line number as key
                            try:
                                value = line_bytes.decode('ascii', errors='ignore')  # Decode value
                            except:
                                value = repr(line_bytes)  # Fallback representation
                        else:
                            if line_bytes:  # Ensure line is not empty
                                key_byte = line_bytes[0]
                                value_bytes = line_bytes[1:]
                                # Represent key byte as hex string (e.g., '\\x8a') or integer string
                                key = f"\\x{key_byte:02x}" if key_byte >= 128 else str(key_byte)
                                try:
                                    value = value_bytes.decode('ascii', errors='ignore')  # Decode value
                                except:
                                    value = repr(value_bytes)  # Fallback representation
                            else:
                                continue  # Skip empty lines
                        network_module_info[key] = value

                    if not network_module_info:
                        logging.warning(f"Could not parse UDP response from {sender_ip}: {msg_received}")
                        continue  # Skip to next response

                    # Extract user-friendly serial/enclosure number
                    module_name = get_user_level_serial_number(network_module_info)
                    if not module_name:
                        logging.warning(f"Could not extract module name from parsed UDP info: {network_module_info}")
                        continue  # Skip if no name found

                    logging.debug(f"Parsed UDP info from {sender_ip}: Name='{module_name}', Raw={network_module_info}")

                    # Prepend "QTL" if missing
                    module_name_str = module_name  # Already a string from get_user_level_serial_number
                    if not module_name_str.startswith("QTL"):
                        module_name_str = "QTL" + module_name_str

                    # --- Check Capabilities and Filter by target_conn ---
                    target_conn_lower = target_conn.lower()

                    # Telnet Check (Key \x8a or 138)
                    if target_conn_lower in ["all", "telnet"] and (
                            network_module_info.get("\\x8a") or network_module_info.get("138")):
                        conn_target = f"TELNET:{sender_ip}"
                        lan_modules[conn_target] = module_name_str
                        logging.debug(f"Found Telnet module: {module_name_str} at {sender_ip}")

                    # REST Check (Key \x84 or 132)
                    if target_conn_lower in ["all", "rest"] and (
                            network_module_info.get("\\x84") or network_module_info.get("132")):
                        conn_target = f"REST:{sender_ip}"
                        lan_modules[conn_target] = module_name_str
                        logging.debug(f"Found REST module: {module_name_str} at {sender_ip}")

                    # TCP Check (Key \x85 or 133)
                    if target_conn_lower in ["all", "tcp"] and (
                            network_module_info.get("\\x85") or network_module_info.get("133")):
                        conn_target = f"TCP:{sender_ip}"
                        lan_modules[conn_target] = module_name_str
                        logging.debug(f"Found TCP module: {module_name_str} at {sender_ip}")

                except Exception as parse_err:
                    logging.error(f"Error parsing UDP response from {sender_ip}: {parse_err}, Raw={msg_received}")
                    continue  # Skip this packet

        except socket.error as sock_err:
            # Log errors related to socket creation or binding
            logging.error(f"Socket error on interface {ip}: {sock_err}")
        except Exception as net_err:
            # Log other general exceptions during network operations
            logging.error(f"Unexpected error during network scan on interface {ip}: {net_err}")
        finally:
            # Ensure the socket is closed
            if mySocket:
                mySocket.close()
                logging.debug(f"Socket closed for interface {ip}")

    # --- Final Report for Targeted Lookup ---
    if ipAddressLookup:
        if moduleFoundByIP:
            printText(f"Targeted IP Scan successful for {ipAddressLookup}: Found module {moduleFoundByIP}")
        else:
            # Check if it was found via REST/TCP fallback which updates lan_modules directly
            found_in_dict = False
            for k, v in lan_modules.items():
                if ipAddressLookup in k:
                    printText(
                        f"Targeted IP Scan successful for {ipAddressLookup}: Found module {v} via fallback ({k.split(':')[0]})")
                    found_in_dict = True
                    break
            if not found_in_dict:
                printText(f"Targeted IP Scan failed: No module found at {ipAddressLookup} via UDP, REST, or TCP.")

    logging.debug("Finished UDP-based network scan.")
    # Update the main return dictionary with results found in this scan
    retVal.update(lan_modules)
    return retVal


def get_user_level_serial_number(network_modules_dict):
    """
    Extracts the user-facing serial/enclosure number from parsed UDP discovery data.
    Handles special cases for multi-module units (e.g., PPMs).

    Args:
        network_modules_dict (dict): The dictionary parsed from a UDP response payload.
                                     Keys are string representations of byte codes (e.g., '134', '\\x86').

    Returns:
        str: The extracted serial number, enclosure number, or enclosure+port number.
             Returns an empty string if no suitable identifier is found.
    """
    # List of QTL numbers known to be multi-module units requiring port info
    list_of_multi_module_units = ["1995"]  # Add other QTL models if needed

    module_name = ""  # Initialize default empty name

    # Prefer Enclosure Number + Port for specific multi-module units
    enclosure_key = '134' if '134' in network_modules_dict else '\\x86' if '\\x86' in network_modules_dict else None
    port_key = '135' if '135' in network_modules_dict else '\\x87' if '\\x87' in network_modules_dict else None

    if enclosure_key:
        enclosure_num = network_modules_dict.get(enclosure_key, "").strip()
        if enclosure_num:
            # Check if this enclosure type needs port info
            needs_port = any(model in enclosure_num for model in list_of_multi_module_units)
            if needs_port and port_key:
                port_num = network_modules_dict.get(port_key, "").strip()
                if port_num:
                    module_name = f"{enclosure_num}-{port_num}"  # Format: Enclosure-Port
                else:
                    module_name = enclosure_num  # Fallback if port key present but no value
            else:
                module_name = enclosure_num  # Use enclosure number directly

    # Fallback to Serial Number if enclosure info wasn't used or found
    if not module_name:
        serial_key = '131' if '131' in network_modules_dict else '\\x83' if '\\x83' in network_modules_dict else None
        if serial_key:
            module_name = network_modules_dict.get(serial_key, "").strip()

    return module_name


def lookupDevice(ipAddressLookup, mySocket, lan_modules, module_found):
    """
    Attempts to discover a specific device by IP address.
    First tries UDP, then falls back to REST and TCP connections if UDP fails.
    Updates lan_modules directly if found via REST/TCP.

    Args:
        ipAddressLookup (str): The target IP address string.
        mySocket (socket.socket): An active UDP socket (used for UDP attempt).
        lan_modules (dict): The dictionary to potentially add REST/TCP findings to.
        module_found (str or None): The name of the module if already found (passed through).

    Returns:
        tuple: (specifiedDeviceResponse, module_found)
               - specifiedDeviceResponse (tuple or None): The (data, address) tuple from UDP recvfrom if successful, else None.
               - module_found (str or None): The module name if found via any method.
    """
    udp_response = None  # Store potential UDP response
    ip_clean = str(ipAddressLookup).strip().replace("\r\n", "")  # Clean up IP address string
    discovery_port = 30303
    discovery_message = b'Discovery: Who is out there?\0\n'

    # --- 1. Attempt Targeted UDP Discovery ---
    try:
        current_timeout = mySocket.gettimeout()
        logging.debug(f"Sending targeted UDP discovery to {ip_clean}:{discovery_port} (Timeout: {current_timeout}s)")
        mySocket.sendto(discovery_message, (ip_clean, discovery_port))
        # Wait for a specific response from the target IP
        udp_response = mySocket.recvfrom(256)  # Wait for response
        logging.debug(f"Received targeted UDP response from {udp_response[1][0]}")
        # Note: Parsing and adding to lan_modules happens in the calling function (list_network)
        # We just need to return the raw response here. Module name extraction happens later.
        # We don't know the module_found name yet just from UDP response bytes.
        return udp_response, module_found  # Return raw UDP response, pass module_found through

    except socket.timeout:
        logging.debug(f"Timeout waiting for targeted UDP response from {ip_clean}.")
        # Continue to REST/TCP fallback
    except Exception as e:
        logging.error(f"Error during targeted UDP lookup for {ip_clean}: {e}")
        # Continue to REST/TCP fallback

    # --- 2. Attempt REST Connection (if UDP failed) ---
    if udp_response is None:  # Only try if UDP didn't get a response
        logging.debug(f"UDP failed for {ip_clean}, attempting REST connection.")
        try:
            restCon = connection_ReST.ReSTConn(ip_clean)
            # Prioritize enclosure number, fallback to serial
            identity = restCon.sendCommand("*enclosure?")
            if "fail" in identity.lower():
                identity = restCon.sendCommand("*serial?")
            # Check if a valid response was received
            if "fail" not in identity.lower() and identity:
                identity_clean = "QTL" + identity if not identity.startswith("QTL") else identity
                conn_target = f"REST:{ip_clean}"
                lan_modules[conn_target] = identity_clean  # Add directly to the dict
                module_found = identity_clean  # Update module found status
                logging.info(f"Found module {identity_clean} via REST at {ip_clean}")
                # No need to return anything specific here, dict is updated, loop continues
            else:
                logging.debug(f"REST connection to {ip_clean} succeeded but failed to get identity.")
        except Exception as e:
            logging.debug(f"Error during REST connection attempt to {ip_clean}: {e}")
            # Continue to TCP fallback

    # --- 3. Attempt TCP Connection (if UDP/REST failed or didn't find) ---
    if module_found is None:  # Only try if REST didn't find it either
        logging.debug(f"UDP/REST failed for {ip_clean}, attempting TCP connection.")
        # Original code had commented-out threading attempt for timeout, implementing direct attempt
        try:
            tcpCon = connection_TCP.TCPConn(ip_clean)  # TCPConn likely handles its own timeout
            # Prioritize enclosure number, fallback to serial
            identity = tcpCon.sendCommand("*enclosure?")
            if "fail" in identity.lower():
                identity = tcpCon.sendCommand("*serial?")
            # Check if a valid response was received
            if "fail" not in identity.lower() and identity:
                identity_clean = "QTL" + identity if not identity.startswith("QTL") else identity
                conn_target = f"TCP:{ip_clean}"
                lan_modules[conn_target] = identity_clean  # Add directly to the dict
                module_found = identity_clean  # Update module found status
                logging.info(f"Found module {identity_clean} via TCP at {ip_clean}")
            else:
                logging.debug(f"TCP connection to {ip_clean} succeeded but failed to get identity.")
            tcpCon.closeConnection()  # Explicitly close TCP connection
        except Exception as e:
            logging.debug(f"Error during TCP connection attempt to {ip_clean}: {e}")

    # Return None for UDP response (as it failed), and the potentially updated module_found status
    return None, module_found


def getSerialNumberFromConnectionTarget(connectionTarget):
    """
    DEPRECATED: Prefer get_connection_target or directly use scan results.

    Finds the serial number for a given full connection target string
    (e.g., "USB:QTL1826-...") by performing a full device scan.

    Args:
        connectionTarget (str): The full connection target string (e.g., "TCP:192.168.1.100").

    Returns:
        str or None: The serial/enclosure number associated with the target,
                     or None if the target is not found in a new scan.
    """
    logging.warning(
        "getSerialNumberFromConnectionTarget is deprecated and performs a full scan. Use scan results directly.")
    # Perform a full scan (non-favourite mode to get all possibilities)
    myDict = scanDevices(favouriteOnly=False)
    # Iterate through the scan results
    for k, v in myDict.items():
        # If the key (connection target) matches the input
        if k == connectionTarget:
            return v  # Return the value (serial/enclosure number)
    # Return None if no match was found
    return None


def get_connection_target(module_string, scan_dictionary=None, connection_preference=None, include_conn_type=True):
    """
    Finds the preferred connection target (e.g., "TCP:192.168.1.1") for a given module identifier.

    Searches a provided scan dictionary or performs a new scan. Uses a preference
    order if multiple connection types are available for the same module.

    Args:
        module_string (str):
            The identifier of the module. Can be just the serial/enclosure number
            (e.g., "QTL1995-01-001", "1995-01-001") or include a type prefix
            (e.g., "TCP:QTL1995-01-001", "USB:1995-01-001"). The prefix is used
            as a filter if present.
        scan_dictionary (dict, optional):
            A pre-existing dictionary from scanDevices() to search within, avoiding a rescan.
            Defaults to None (triggers a new scan).
        connection_preference (list[str], optional):
            Order of preferred connection types if multiple are found for the same module.
            Defaults to ["USB", "TCP", "SERIAL", "REST", "TELNET"].
        include_conn_type (bool, optional):
            If True, returns the full target string including the type prefix (e.g., "TCP:192...").
            If False, returns only the address/identifier part (e.g., "192...").
            Defaults to True.

    Returns:
        str: The preferred connection target string found, or "Fail Module Not Found".
    """
    logging.debug(f"Getting connection target for module identifier: {module_string}")
    # Default connection preference order
    if connection_preference is None:
        connection_preference = ["USB", "TCP", "SERIAL", "REST", "TELNET"]

    # Normalize input string format (handle QIS/QPS double colons)
    module_string_norm = module_string.replace("::", ":")

    # --- Parse input module_string ---
    delimiter_pos = module_string_norm.find(":")
    requested_con_type = None
    serial_number_part = ""
    if delimiter_pos == -1:
        # No connection type prefix found, use the whole string as the identifier
        serial_number_part = module_string_norm.lower()
    else:
        # Split into connection type and identifier
        requested_con_type = module_string_norm[:delimiter_pos].upper()  # Use uppercase for matching preference list
        serial_number_part = module_string_norm[delimiter_pos + 1:].lower()

    # Remove "qtl" prefix from identifier if present for broader matching
    serial_number_clean = serial_number_part.replace("qtl", "")
    logging.debug(f"Parsed: Requested Type='{requested_con_type}', Identifier='{serial_number_clean}'")

    # --- Scan for devices if dictionary not provided ---
    if scan_dictionary is None:
        logging.debug("No scan dictionary provided, performing scan...")
        # Scan non-favourite mode to see all connections, filter by the identifier part
        scan_dictionary = scanDevices(favouriteOnly=False, filterStr=[serial_number_clean])
        if not scan_dictionary:
            logging.warning(f"Scan did not find any devices matching identifier '{serial_number_clean}'")
            return "Fail Module Not Found"

    # --- Find matching connections ---
    matching_connections = {}  # Store found connections {conn_type: conn_target}
    for conn_target, module_id_found in scan_dictionary.items():
        # Clean the found module ID (serial/enclosure) for comparison
        module_id_clean = module_id_found.lower().replace("qtl", "")
        # Check if the identifier part matches
        if serial_number_clean == module_id_clean:
            # Extract connection type from the found target string
            found_con_type = conn_target.split(":")[0].upper()
            # Store the full connection target, keyed by its type
            matching_connections[found_con_type] = conn_target

    if not matching_connections:
        logging.warning(f"Identifier '{serial_number_clean}' not found in scan results.")
        return "Fail Module Not Found"

    logging.debug(f"Found matching connections for '{serial_number_clean}': {matching_connections}")

    # --- Select the best connection based on filter or preference ---
    best_target = None
    if requested_con_type:
        # If a specific type was requested, use that if available
        if requested_con_type in matching_connections:
            best_target = matching_connections[requested_con_type]
            logging.debug(f"Using requested connection type '{requested_con_type}': {best_target}")
        else:
            logging.warning(
                f"Requested type '{requested_con_type}' not found, though other types exist: {list(matching_connections.keys())}")
            return "Fail Module Not Found"  # Strict: if requested type not found, fail.
    else:
        # No specific type requested, use the preference order
        for pref_type in connection_preference:
            if pref_type in matching_connections:
                best_target = matching_connections[pref_type]
                logging.debug(f"Using preferred connection type '{pref_type}': {best_target}")
                break  # Stop at the first preferred match found
        # If no preferred types were found (shouldn't happen if matching_connections is not empty)
        if best_target is None:
            best_target = list(matching_connections.values())[0]  # Fallback to first available
            logging.debug(f"Using first available connection type: {best_target}")

    # --- Format the output ---
    if not include_conn_type and best_target:
        # Remove the connection type prefix if requested
        del_pos = best_target.find(":")
        if del_pos != -1:
            ret_val = best_target[del_pos + 1:]
        else:
            ret_val = best_target  # Should not happen with standard format
    else:
        ret_val = best_target  # Return the full target string

    return ret_val if ret_val else "Fail Module Not Found"


'''
Helper function for scanDevices to filter results based on module type.
'''


def filter_module_type(module_type_filter, found_devices_dict):
    """
    Filters a dictionary of found devices based on predefined module types (e.g., 'Cable', 'Power').

    Uses configuration files (via `return_module_type_list`) to determine which
    QTL model numbers belong to the specified `module_type_filter`.

    Args:
        module_type_filter (str): The category to filter by (e.g., 'Cable', 'Card', 'Drive', 'Power', 'Switch').
        found_devices_dict (dict): The dictionary {connection_target: module_id} to filter.

    Returns:
        dict: A new dictionary containing only the devices matching the filter type.
              Returns an empty dictionary if the filter type is invalid or yields no matches.
    """
    # Get the list of QTL model numbers (e.g., "qtl1826") associated with the filter type from config
    accepted_qtl_numbers = return_module_type_list(module_type_filter)
    if not accepted_qtl_numbers:
        logging.warning(f"No QTL numbers defined for module type filter: '{module_type_filter}'")
        return {}  # Return empty if filter type is unknown or has no entries

    # Normalize QTL numbers to lowercase for case-insensitive comparison
    accepted_qtl_numbers_lower = [x.lower() for x in accepted_qtl_numbers]
    filtered_devices = {}

    # Iterate through the devices found by the main scan
    for key, value in found_devices_dict.items():
        value_str = str(value).lower()
        # Check if the module ID contains "qtl"
        if "qtl" in value_str:
            try:
                # Extract the QTL model number part (e.g., "qtl1826" from "qtl1826-01-001")
                qtl_start_index = value_str.index("qtl")
                qtl_end_index = value_str.find("-", qtl_start_index)
                # Handle cases where there might not be a dash (though unlikely for standard format)
                qtl_num = value_str[qtl_start_index:qtl_end_index] if qtl_end_index != -1 else value_str[
                                                                                               qtl_start_index:]

                # Check if the extracted QTL number matches any in the accepted list for the filter type
                if qtl_num in accepted_qtl_numbers_lower:
                    filtered_devices[key] = value  # Add matching device to the filtered dictionary
            except ValueError:
                # Handle potential errors if "qtl" is present but format is unexpected
                logging.debug(f"Could not parse QTL number from module ID: '{value}'")
                continue

    return filtered_devices


def scan_mDNS(mdnsListener, zeroconf=None):
    """
    Initializes and starts an mDNS service browser using the Zeroconf library.

    Args:
        mdnsListener (MyListener): An instance of the mDNS listener class that handles service discovery events.
        zeroconf (Zeroconf, optional): An existing Zeroconf instance. If None, a new one is created. Defaults to None.

    Returns:
        ServiceBrowser: The created Zeroconf ServiceBrowser object.
    """
    from zeroconf import ServiceBrowser, Zeroconf  # Local import inside function

    # Create a new Zeroconf instance if one wasn't provided
    if zeroconf is None:
        zeroconf = Zeroconf()

    listener = mdnsListener  # Use the provided listener instance
    # Create a service browser looking for HTTP services on the local network
    # Quarch devices often advertise a web interface via _http._tcp.local.
    browser = ServiceBrowser(zeroconf, "_http._tcp.local.", listener)
    logging.debug("mDNS Service Browser initialized for _http._tcp.local.")
    # The browser runs in the background (often using threads managed by Zeroconf)
    # The listener's methods (add_service, remove_service) will be called as services appear/disappear.
    return browser


'''
Scans for Quarch modules across the given interface(s).
Combines USB, Serial, Network (UDP), and mDNS discovery methods.
Allows filtering and selection of preferred connection types.
'''


def scanDevices(target_conn="all", lanTimeout=1, scanInArray=True, favouriteOnly=True, filterStr=None,
                module_type_filter=None, ipAddressLookup=None):
    """
    Performs a comprehensive scan for Quarch devices across multiple interfaces.

    Args:
        target_conn (str, optional): Specifies which connection types to scan
                                     ("all", "usb", "serial", "tcp", "rest", "telnet"). Defaults to "all".
        lanTimeout (int, optional): Timeout in seconds for network UDP scan responses. Defaults to 1.
        scanInArray (bool, optional): If True, attempts to connect to found array controllers
                                      and scan their sub-modules. Defaults to True.
        favouriteOnly (bool, optional): If True, filters results to show only one preferred
                                        connection type per unique device. Defaults to True.
        filterStr (list[str], optional): A list of substrings. Only devices whose serial/enclosure
                                         number contains one of these substrings will be returned.
                                         Defaults to None (no filtering).
        module_type_filter (str, optional): Filters results by device category (e.g., 'Power', 'Cable').
                                            Uses configuration files. Defaults to None.
        ipAddressLookup (str, optional): If provided, performs a targeted network lookup for this IP.
                                         Defaults to None.

    Returns:
        dict: A dictionary of found devices {connection_target: module_id}, sorted by module_id.
              Format depends on favouriteOnly and filtering options.
    """
    foundDevices = dict()  # Master dictionary for all findings
    scannedArrays = list()  # Keep track of arrays already scanned to avoid loops

    # --- Initialize mDNS Scanning ---
    # Get singleton instance of listener and zeroconf to manage background threads
    mdns_listener = MyListener().get_instance()
    zeroconf_instance = mdns_listener.get_zeroconf()
    # Start a new browser for this scan cycle. It will use the persistent listener.
    browser = scan_mDNS(mdns_listener, zeroconf_instance)
    # Pass the target connection filter to the listener so it knows which protocols to record from mDNS results
    mdns_listener.target_conn = target_conn.lower()
    # Small delay to allow mDNS browser to start finding services
    time.sleep(0.1)  # Adjust as needed, depends on network speed

    # --- Perform Scans based on target_conn ---
    target_conn_lower = target_conn.lower()

    # Scan USB if requested or 'all'
    if target_conn_lower in ["all", "usb"]:
        logging.debug("Scanning USB...")
        foundDevices = mergeDict(foundDevices, list_USB())

    # Scan Serial if requested or 'all'
    if target_conn_lower in ["all", "serial"]:
        logging.debug("Scanning Serial...")
        foundDevices = mergeDict(foundDevices, list_serial())

    # Scan Network (UDP/mDNS) if requested or 'all'
    if target_conn_lower in ["all", "tcp", "rest", "telnet"]:
        logging.debug(f"Scanning Network (UDP/mDNS) for target: {target_conn_lower}...")
        try:
            # Perform UDP scan (broadcast or targeted)
            udp_results = list_network(target_conn_lower, ipAddressLookup=ipAddressLookup, lanTimeout=lanTimeout)
            foundDevices = mergeDict(foundDevices, udp_results)
            # Get results found via mDNS by the listener
            mdns_results = mdns_listener.get_found_devices()
            foundDevices = mergeDict(foundDevices, mdns_results)
        except Exception as e:
            logging.error(f"Network scan (UDP/mDNS) failed: {e}", exc_info=True)
            logging.warning("Check network connection and firewall settings.")

    # --- Scan Inside Array Controllers (Optional) ---
    if scanInArray:
        logging.debug("Scanning inside detected Array Controllers...")
        # Create a copy of keys to iterate over, as dict may change size during iteration
        current_keys = list(foundDevices.keys())
        for k in current_keys:  # k = Connection target (e.g., "USB:QTL1826...")
            # Check if device with this connection target exists and hasn't been scanned yet
            if k in foundDevices and k not in scannedArrays:
                v = foundDevices[k]  # v = Module ID (e.g., "QTL1826...")
                scannedArrays.append(k)  # Mark as scanned to prevent recursion
                # Check if the module ID indicates it's an array controller
                if isThisAnArrayController(v):
                    logging.info(f"Detected Array Controller: {v} ({k}). Attempting to scan sub-modules.")
                    myQuarchDevice = None
                    myArrayControler = None
                    try:
                        # Connect to the array controller
                        myQuarchDevice = quarchDevice(k)
                        myArrayControler = quarchArray(myQuarchDevice)
                        # Use the array controller object to scan its sub-modules
                        submodule_scan_results = myArrayControler.scanSubModules()
                        logging.debug(f"Sub-modules found in {k}: {submodule_scan_results}")
                        # Merge the sub-module results into the main dictionary
                        foundDevices = mergeDict(foundDevices, submodule_scan_results)
                    except Exception as e:
                        # Log error if connection or scan fails
                        logging.error(f"Failed to scan array controller {k}: {e}", exc_info=True)
                        # Mark the device as potentially in use if connection failed
                        if "DEVICE IN USE" not in foundDevices.get(k, ""):  # Avoid double marking
                            foundDevices[k] = f"{v} (ARRAY SCAN FAILED)" if v else "DEVICE IN USE (ARRAY SCAN FAILED)"
                    finally:
                        # Ensure the connection to the array controller is closed
                        if myArrayControler:
                            try:
                                myArrayControler.closeConnection()
                            except:
                                pass  # Ignore errors on close
                        elif myQuarchDevice:
                            try:
                                myQuarchDevice.closeConnection()
                            except:
                                pass

    # --- Filter for Favourite Connection Only (Optional) ---
    if favouriteOnly:
        logging.debug("Filtering for favourite connection type per device...")
        # Define the preference order for connection types
        conPref = ["USB", "TCP", "SERIAL", "REST", "TELNET"]
        # Temporary dict to store devices found, keyed by module ID
        devices_by_id = {}
        # Iterate through all found connections, grouping by module ID
        for conn_target, module_id in foundDevices.items():
            if module_id not in devices_by_id:
                devices_by_id[module_id] = []
            devices_by_id[module_id].append(conn_target)

        # Dictionary to store the single favourite connection per device
        favConFoundDevices = {}
        # Iterate through each unique module ID found
        for module_id, connection_list in devices_by_id.items():
            best_conn_found = None
            # Find the best connection based on preference order
            for pref_type in conPref:
                for conn_target in connection_list:
                    if conn_target.startswith(pref_type + ":"):
                        best_conn_found = conn_target
                        break  # Stop checking this module once preferred type is found
                if best_conn_found:
                    break  # Stop checking preference types for this module
            # If no preferred connection found (e.g., only unknown type), take the first one
            if not best_conn_found and connection_list:
                best_conn_found = connection_list[0]

            # Add the favourite connection to the result dictionary
            if best_conn_found:
                favConFoundDevices[best_conn_found] = module_id

        foundDevices = favConFoundDevices  # Overwrite with filtered list

    # --- Sort Results Alphabetically by Module ID (Value) ---
    try:
        # Sort items based on the value (module ID), then convert back to dict
        sorted_items = sorted(foundDevices.items(), key=operator.itemgetter(1))
        foundDevices = dict(sorted_items)
    except Exception as sort_err:
        logging.warning(f"Could not sort found devices: {sort_err}")

    # --- Apply Substring Filter (Optional) ---
    if filterStr is not None and isinstance(filterStr, list):
        logging.debug(f"Applying filter strings: {filterStr}")
        filteredDevices = {}
        filter_str_lower = [f.lower() for f in filterStr]  # Lowercase for case-insensitive match
        for k, v in foundDevices.items():
            v_lower = v.lower()
            # Include locked modules always, or if module ID contains any filter string
            if "locked module" in v_lower or "device in use" in v_lower or \
                    any(f_str in v_lower for f_str in filter_str_lower):
                filteredDevices[k] = v
        foundDevices = filteredDevices  # Overwrite with filtered list

    # --- Apply Module Type Filter (Optional) ---
    if module_type_filter:
        logging.debug(f"Applying module type filter: {module_type_filter}")
        # Use the helper function to filter based on QTL number ranges from config
        foundDevices = filter_module_type(module_type_filter, foundDevices)

    # --- Clean up mDNS ---
    # Cancel the browser to stop background mDNS activity for this scan cycle
    logging.debug("Cancelling mDNS browser...")
    browser.cancel()
    # Note: The listener and zeroconf instance persist via the MyListener singleton for next scan.

    logging.info(f"Scan complete. Found {len(foundDevices)} device connections matching criteria.")
    return foundDevices


'''
Prints out a list of Quarch devices nicely onto the terminal, numbering each unit.
'''


def listDevices(scanDictionary):
    """
    Prints a formatted, numbered list of devices from a scan dictionary.

    Args:
        scanDictionary (dict): The dictionary {connection_target: module_id} from scanDevices.
    """
    if not scanDictionary:
        printText("No quarch devices found to display")
    else:
        printText("\nAvailable Quarch Devices:")
        printText("-" * 50)
        x = 1
        # Iterate through the sorted dictionary (assuming it's sorted by scanDevices)
        for k, v in scanDictionary.items():
            # Format: Number - ModuleID (padded)   ConnectionType:Address/Port
            # Adjust padding based on expected lengths
            printText('{0:>3}'.format(str(x)) + " - " + '{0:<25}'.format(v) + "\t" + k)
            x += 1
        printText("-" * 50)


'''
Requests the user to select one of the devices in the given list via console interaction.
'''


def userSelectDevice(scanDictionary=None, scanFilterStr=None, favouriteOnly=True, message=None, title=None, nice=False,
                     additionalOptions=None, target_conn="all"):
    """
    Presents a list of scanned devices to the user for selection via console.

    Handles scanning, displaying options (including rescan, specify IP, quit),
    and returning the user's choice.

    Args:
        scanDictionary (dict, optional): Pre-scanned device dictionary. If None, performs scan. Defaults to None.
        scanFilterStr (list[str], optional): Substring filter for scanning. Defaults to None.
        favouriteOnly (bool, optional): Scan/display only favourite connections. Defaults to True.
        message (str, optional): Prompt message for the user. Defaults to "Please select a quarch device".
        title (str, optional): Title for the selection prompt. Defaults to "Select a Device".
        nice (bool, optional): If True, attempts to use a formatted table UI (availability depends
                               on quarchpy.user_interface implementation). Defaults to False.
        additionalOptions (list or str, optional): Extra options for the user menu.
                                                  Format depends on 'nice'. Defaults are provided.
        target_conn (str, optional): Connection type filter for scanning. Defaults to "all".

    Returns:
        str: The connection target string of the selected device (e.g., "USB:QTL..."),
             or a control string ("quit", "rescan", "specify ip address").
    """
    # Force non-nice mode if running under TestCenter context
    if User_interface.instance is not None and User_interface.instance.selectedInterface == "testcenter":
        nice = False

    # Set default messages if not provided
    if message is None: message = "Please select a quarch device from the list"
    if title is None: title = "Quarch Device Selection"

    ip_address = None  # Stores IP if user chooses to specify one
    user_choice = None  # Stores the final validated user selection

    # Loop until a valid device is selected or user quits
    while user_choice is None:
        # --- Scan for devices if needed ---
        if scanDictionary is None:
            printText("Scanning for devices...")
            # Perform scan with current filters/options
            current_scan_dict = scanDevices(filterStr=scanFilterStr,
                                            favouriteOnly=favouriteOnly,
                                            target_conn=target_conn,
                                            ipAddressLookup=ip_address)
            # If IP lookup was used, clear it for the next potential rescan
            ip_address = None
        else:
            # Use the provided dictionary
            current_scan_dict = scanDictionary
            # Prevent infinite loop if passed-in dict is bad/empty
            scanDictionary = None  # Ensure rescan happens next time if selection fails

        # Handle case where no devices are found
        if not current_scan_dict:
            current_scan_dict["***No Devices Found***"] = "***No Devices Found***"  # Placeholder for display

        # --- Prepare and Display Options ---
        user_selection_raw = ""  # Raw string input from user
        if nice:
            # --- Nice UI Formatting ---
            if additionalOptions is None:
                additionalOptions = ["Specify IP Address", "Rescan", "Quit"]
            # Format scan results for table display [[ModuleID, ConnTarget], ...]
            scan_list_for_table = [[v, k] for k, v in current_scan_dict.items()]
            # Format additional options for table display [[Option, Option], ...]
            additional_options_for_table = [[opt, opt] for opt in additionalOptions]

            try:
                # Use the listSelection function with table formatting
                # Expects return format like [index, [col1, col2], ConnTarget] when indexReq=True
                selection_result = listSelection(title, message, scan_list_for_table,
                                                 additionalOptions=additional_options_for_table,
                                                 indexReq=True, nice=nice,
                                                 tableHeaders=["Module", "Connection"])
                # Extract the connection target (assumed to be 3rd element based on original code comment)
                user_selection_raw = selection_result[2] if selection_result and len(
                    selection_result) > 2 else "quit"  # Default to quit on error
            except Exception as e:
                logging.error(f"Error during 'nice' listSelection: {e}. Falling back to text mode.")
                nice = False  # Disable nice mode for next attempt
                user_selection_raw = "rescan"  # Force rescan in text mode

        # --- Standard Text UI Formatting ---
        if not nice:  # Either originally false or fell back from nice mode error
            if additionalOptions is None:
                # Format for standard listSelection: "Display=Value" pairs, comma-separated
                additionalOptions = "Specify IP Address=Specify IP Address,Rescan=Rescan,Quit=Quit"
            # Format scan results: "ConnTarget=ModuleID: ConnType" pairs, comma-separated
            devices_string_list = []
            for k, v in current_scan_dict.items():
                conn_type = k.split(":")[0] if ":" in k else "UNKNOWN"
                # Display format: "QTL1826...(USB:COM3)" = "USB:COM3" (Value is ConnTarget)
                display_text = f"{v} ({k})"
                devices_string_list.append(f"{display_text}={k}")
            devices_string = ','.join(devices_string_list)

            # Get user input using standard text listSelection
            user_selection_raw = listSelection(title=title, message=message, selectionList=devices_string,
                                               additionalOptions=additionalOptions)

        # --- Process User Response ---
        selection_lower = user_selection_raw.lower().strip()

        if selection_lower == 'quit':
            logging.info("User selected Quit.")
            return "quit"
        elif selection_lower == 'rescan':
            logging.info("User selected Rescan.")
            scanDictionary = None  # Clear dictionary to force rescan
            favouriteOnly = True  # Reset favourite filter on rescan
            continue  # Go back to start of loop
        # Original code had 'all conn types' but wasn't in default options - adding for completeness
        elif selection_lower == 'all conn types':
            logging.info("User selected All Connection Types.")
            scanDictionary = None
            favouriteOnly = False  # Disable favourite filter
            continue
        elif selection_lower == 'specify ip address':
            logging.info("User selected Specify IP Address.")
            try:
                # Prompt user for IP address
                ip_address_input = requestDialog("Enter IP Address of the Quarch module:")
                if ip_address_input:  # Check if user entered something
                    # Basic validation (optional, could add regex)
                    socket.inet_aton(ip_address_input)  # Raises error if invalid format
                    ip_address = ip_address_input  # Store valid IP for next scan
                    scanDictionary = None  # Force rescan using the IP
                    favouriteOnly = False  # Show all results for the specific IP
                    logging.info(f"Scanning for specified IP: {ip_address}")
                else:
                    logging.info("User cancelled IP address input.")
                continue  # Rescan with or without IP
            except socket.error:
                printText("Invalid IP address format. Please try again.")
                continue  # Ask again or rescan
            except Exception as e:
                logging.error(f"Error requesting IP Address: {e}")
                continue  # Rescan
        else:
            # Assume user selected a device connection target string
            # Validate if the returned string is actually one of the keys in the last scan
            if user_selection_raw in current_scan_dict:
                logging.info(f"User selected device: {user_selection_raw}")
                user_choice = user_selection_raw  # Valid selection, exit loop
            elif "***No Devices Found***" in user_selection_raw:
                printText("No devices were found. Please check connections and Rescan or Quit.")
                scanDictionary = None  # Force rescan
                continue
            else:
                # Should not happen if listSelection returns correctly, but handle unexpected input
                printText(f"Invalid selection '{user_selection_raw}'. Please try again.")
                scanDictionary = None  # Force rescan
                continue

    # Return the validated device connection target string
    return user_choice
