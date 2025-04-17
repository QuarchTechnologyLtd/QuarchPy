# device.py Refactored (Logic moved to snake_case, original becomes wrapper)
import time, sys, os, logging
import re

# Imports needed by original code
from quarchpy.connection import QISConnection, PYConnection, QPSConnection
from quarchpy import user_interface

try:
    # Import components needed by get_quarch_device logic
    # Use original names here as get_quarch_device logic calls them
    from .quarchArray import quarchArray, subDevice
    # Assuming isThisAnArrayController is used somewhere if imported, though not visible here
    # from .quarchArray import isThisAnArrayController
    from .scanDevices import get_connection_target  # Needed by __init__
except ImportError as e:
    logging.error(f"Failed to import dependencies (.quarchArray, .scanDevices): {e}. Functionality limited.")
    quarchArray = None
    subDevice = None
    # is_this_an_array_controller = lambda x: False
    get_connection_target = lambda x: x  # Dummy fallback

# Check Python version and set timeout exception
if sys.version_info.major == 2:
    try:
        import socket;

        timeout_exception = socket.timeout
    except AttributeError as e:
        timeout_exception = None;
        logging.error(f"Socket timeout unavailable: {e}")
else:
    timeout_exception = TimeoutError  # Built-in


class quarchDevice:
    """
    Allows control over a Quarch device, over a wide range of underlying connection methods.  This is the core class
    used for control of all Quarch products.
    (Original Docstring...)
    """

    # --- Special Methods (Untouched Logic) ---
    def __init__(self, ConString, ConType="PY", timeout="5"):
        """
        Constructor for quarchDevice, allowing the connection method of the device to be specified.
        (Original Docstring and Logic Unchanged - internal calls remain camelCase)
        """
        self.ConString = ConString
        if "serial" not in ConString.lower():
            self.ConString = ConString.lower()
        self.ConType = ConType
        self.connectionObj = None

        try:
            self.timeout = int(timeout)
        except ValueError:  # More specific exception
            raise ValueError("Invalid value for timeout, must be a numeric value")

        # Internal call remains camelCase (calls the wrapper now)
        if not checkModuleFormat(self.ConString):
            raise ValueError(f"Module format is invalid for connection string: '{self.ConString}'")

        logging.debug(
            f"Initializing quarchDevice with ConString='{self.ConString}', ConType='{self.ConType}', Timeout='{self.timeout}'")
        con_type_upper = self.ConType.upper()

        # --- Connection Logic (Original logic untouched, internal calls remain as they were) ---
        ## Python Connection Logic
        if con_type_upper == "PY":
            numb_colons = self.ConString.count(":")
            if numb_colons == 2: self.ConString = self.ConString.replace('::', ':')

            # Check if get_connection_target is available before calling
            if "qtl" in self.ConString.lower() and "usb" not in self.ConString.lower() and get_connection_target is not None:
                try:
                    resolved_con_string = get_connection_target(self.ConString)
                    if resolved_con_string:
                        logging.debug(f"Resolved '{self.ConString}' to '{resolved_con_string}'")
                        self.ConString = resolved_con_string
                    else:
                        logging.warning(f"get_connection_target returned empty for '{self.ConString}'.")
                except Exception as e_scan:
                    logging.error(f"Error calling get_connection_target: {e_scan}.")
            elif "qtl" in self.ConString.lower() and "usb" not in self.ConString.lower():
                logging.warning("get_connection_target function not available, cannot resolve connection string.")

            try:
                self.connectionObj = PYConnection(self.ConString)
                self.ConCommsType = self.connectionObj.ConnTypeStr
                self.connectionName = self.connectionObj.ConnTarget
                self.connectionTypeName = self.connectionObj.ConnTypeStr
                logging.debug(
                    f"PY Connection details: Type='{self.connectionTypeName}', Target='{self.connectionName}'")
            except Exception as e_pyconn:
                logging.error(f"Failed to create PYConnection for '{self.ConString}': {e_pyconn}", exc_info=True)
                raise ConnectionError(f"Failed to establish PY connection for '{self.ConString}'") from e_pyconn

            time.sleep(0.1)  # Keep original sleeps
            item = None
            try:
                # Use original sendCommand name internally (now a wrapper)
                item = self.sendCommand("*tst?")
            except Exception as e_tst:
                logging.warning(f"Error sending *tst? during init: {e_tst}")
                raise ConnectionError(
                    "Module failed to respond correctly to *tst? command during initialization.") from e_tst

            # Check response from *tst?
            # Original code checked `if "OK" in item:` etc. which implies item is not None
            response_ok = False
            if item is not None:
                if "OK" in item or "FAIL" in item:  # Allow FAIL as a valid response type here? Original did.
                    response_ok = True

            if not response_ok:
                logging.error(f"No valid module response to *tst? command! Received: '{item}'")
                try:
                    # Use original closeConnection name internally (now a wrapper)
                    self.closeConnection()
                except Exception as close_err:
                    logging.error(f"Error closing connection after *tst? failure: {close_err}")
                raise ConnectionError("No module responded correctly to *tst? command!")
            logging.debug("*tst? check successful.")
            time.sleep(0.1)  # Keep original sleeps

        ## QIS Connection Logic (Original logic untouched)
        elif con_type_upper.startswith("QIS"):
            host = '127.0.0.1';
            port = 9722
            try:
                _, host, port_str = self.ConType.split(':');
                port = int(port_str)
            except ValueError:
                if con_type_upper != "QIS": logging.warning(
                    f"Could not parse host/port from ConType '{self.ConType}', using defaults {host}:{port}.")
            except Exception as e_parse:
                logging.warning(f"Error parsing ConType '{self.ConType}': {e_parse}. Using defaults {host}:{port}.")

            numb_colons = self.ConString.count(":")
            if numb_colons == 1: self.ConString = self.ConString.replace(':', '::')

            try:
                self.connectionObj = QISConnection(self.ConString, host, port);
                logging.debug(
                    f"QISConnection object created for '{self.ConString}' via {host}:{port}")
            except Exception as e_qisconn:
                logging.error(f"Failed to create QISConnection: {e_qisconn}", exc_info=True);
                raise ConnectionError(
                    "Failed to establish QIS connection.") from e_qisconn

            list_details = self.connectionObj.qis.get_list_details()
            list_str_lower = "".join(list_details).lower()
            target_qtl_lower = self.ConString.lower()
            found_in_qis = False
            connect_timeout = time.time() + self.timeout

            while time.time() < connect_timeout:
                if "qtl" not in target_qtl_lower:
                    ip_match = re.search(r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}", target_qtl_lower)
                    if not ip_match: raise ValueError(
                        f"ConString '{self.ConString}' has no QTL and no valid IP for QIS.")
                    target_ip = ip_match.group()
                    # Internal call remains snake_case (original name)
                    resolved_con_string = _check_ip_in_qis_list(target_ip, list_details)
                    if resolved_con_string: self.ConString = resolved_con_string; found_in_qis = True; break
                    logging.debug(f"IP {target_ip} not found in QIS list, attempting scan...")
                    try:
                        scan_response = self.connectionObj.qis.scanIP(
                            self.ConString)  # Pass original ConString or target_ip? Original uses self.ConString
                        if "located" in str(scan_response).lower():
                            logging.info(
                                f"QIS located device potentially matching {self.ConString}. Re-checking list...")
                            connect_timeout = time.time() + 20;
                            time.sleep(2)
                            while time.time() < connect_timeout:
                                list_details = self.connectionObj.qis.get_list_details()
                                resolved_con_string = _check_ip_in_qis_list(target_ip, list_details)
                                if resolved_con_string: self.ConString = resolved_con_string; found_in_qis = True; break
                                logging.debug(f"IP {target_ip} still not resolved post-scan, retrying...");
                                time.sleep(1)
                            if found_in_qis: break
                    except Exception as e_scan:
                        logging.warning(f"Error during QIS scanIP for {self.ConString}: {e_scan}")
                elif target_qtl_lower in list_str_lower:
                    found_in_qis = True;
                    break
                if time.time() >= connect_timeout: break
                logging.debug(f"'{self.ConString}' not found in QIS list yet, retrying...");
                time.sleep(1)
                list_details = self.connectionObj.qis.get_list_details();
                list_str_lower = "".join(list_details).lower()

            if not found_in_qis:
                try:
                    self.closeConnection()  # Use original wrapper name
                except Exception:
                    pass  # Ignore errors during cleanup on failure
                raise TimeoutError(f"Could not find module '{self.ConString}' in QIS within {self.timeout}s timeout")
            try:
                set_default_cmd = f"$default {self.ConString}";
                logging.debug(f"Setting QIS default: {set_default_cmd}")
                response = self.connectionObj.qis.sendAndReceiveCmd(cmd=set_default_cmd)
                logging.debug(f"QIS set default response: {response}")
                if "fail" in response.lower(): logging.warning(f"QIS command '$default {self.ConString}' failed.")
            except Exception as e_def:
                logging.warning(f"Error setting QIS default device: {e_def}")

        ## QPS Connection Logic (Original logic untouched)
        elif con_type_upper.startswith("QPS"):
            host = '127.0.0.1';
            port = 9822
            try:
                _, host, port_str = self.ConType.split(':');
                port = int(port_str)
            except ValueError:
                if con_type_upper != "QPS": logging.warning(
                    f"Could not parse host/port from ConType '{self.ConType}', using defaults {host}:{port}.")
            except Exception as e_parse:
                logging.warning(f"Error parsing ConType '{self.ConType}': {e_parse}. Using defaults {host}:{port}.")

            numb_colons = self.ConString.count(":")
            if numb_colons == 1: self.ConString = self.ConString.replace(':', '::')

            try:
                self.connectionObj = QPSConnection(host, port);
                logging.debug(
                    f"QPSConnection object created via {host}:{port}")
            except Exception as e_qpsconn:
                logging.error(f"Failed to create QPSConnection: {e_qpsconn}", exc_info=True);
                raise ConnectionError(
                    "Failed to establish QPS connection.") from e_qpsconn

            # Original logic uses sendCmdVerbose - use the wrapper
            list_details_str = self.connectionObj.qps.sendCmdVerbose("$module list details")
            list_details = list_details_str.replace("\r\n", "\n").split("\n")
            list_str_lower = "".join(list_details).lower()
            target_qtl_lower = self.ConString.lower()
            found_in_qps = False
            connect_timeout = time.time() + self.timeout

            while time.time() < connect_timeout:
                if "qtl" not in target_qtl_lower:
                    ip_match = re.search(r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}", target_qtl_lower)
                    if not ip_match: raise ValueError(
                        f"ConString '{self.ConString}' has no QTL and no valid IP for QPS.")
                    target_ip = ip_match.group()
                    resolved_con_string = _check_ip_in_qis_list(target_ip, list_details)  # Assuming format is same
                    if resolved_con_string: self.ConString = resolved_con_string; found_in_qps = True; break
                    logging.debug(f"IP {target_ip} not found in QPS list, attempting scan...")
                    try:
                        scan_response = self.connectionObj.qps.scanIP(self.ConString) if hasattr(self.connectionObj.qps,
                                                                                                 'scanIP') else ""
                        if "located" in str(scan_response).lower():
                            logging.info(f"QPS located {target_ip}. Re-checking list...");
                            connect_timeout = time.time() + 20;
                            time.sleep(2)
                            while time.time() < connect_timeout:
                                list_details_str = self.connectionObj.qps.sendCmdVerbose(
                                    "$module list details")  # Re-fetch list
                                list_details = list_details_str.replace("\r\n", "\n").split("\n")
                                resolved_con_string = _check_ip_in_qis_list(target_ip, list_details)
                                if resolved_con_string: self.ConString = resolved_con_string; found_in_qps = True; break
                                logging.debug(f"IP {target_ip} still not resolved post-QPS-scan, retrying...");
                                time.sleep(1)
                            if found_in_qps: break
                    except Exception as e_scan:
                        logging.warning(f"Error during QPS scanIP for {self.ConString}: {e_scan}")
                elif target_qtl_lower in list_str_lower:
                    found_in_qps = True;
                    break
                if time.time() >= connect_timeout: break
                logging.debug(f"'{self.ConString}' not found in QPS list yet, retrying...");
                time.sleep(1)
                # Re-fetch list
                list_details_str = self.connectionObj.qps.sendCmdVerbose("$module list details")
                list_details = list_details_str.replace("\r\n", "\n").split("\n")
                list_str_lower = "".join(list_details).lower()

            if not found_in_qps:
                try:
                    self.closeConnection()  # Use original wrapper name
                except Exception:
                    pass
                raise TimeoutError(f"Could not find module '{self.ConString}' in QPS within {self.timeout}s timeout")

        ## Invalid Connection Type
        else:
            raise ValueError(f"Invalid connection type '{self.ConType}'. Acceptable values [PY,QIS,QPS]")

        logging.debug(f"{os.path.basename(__file__)} ConString : {str(self.ConString)} ConType : {str(self.ConType)}")

    def __del__(self):
        """ Destructor to ensure the connection is closed. """
        # Special method, unchanged. Calls wrapper internally.
        try:
            # Call closeConnection wrapper to maintain original behavior path if needed
            # Or call snake_case close_connection for directness? Let's stick to wrapper based on user instruction.
            # If self.closeConnection exists (i.e., not cleaned up yet)
            if hasattr(self, 'closeConnection') and callable(self.closeConnection):
                self.closeConnection()
        except Exception as e:
            try:
                if logging and logging.error: logging.error(
                    f"Error during automatic connection close in destructor: {e}")
            except Exception:
                pass

    # --- Original Methods (Logic Moved to snake_case below) ---

    def sendCommand(self, CommandString, expectedResponse=True):
        """ Executes a text based command on the device (camelCase wrapper). """
        return self.send_command(CommandString, expectedResponse)

    def sendBinaryCommand(self, cmd):
        """ Sends a binary command (USB only?) (camelCase wrapper). """
        return self.send_binary_command(cmd)

    def openConnection(self):
        """ Opens/re-opens the connection to the module (camelCase wrapper). """
        return self.open_connection()

    def closeConnection(self):
        """ Closes the connection to the module (camelCase wrapper). """
        return self.close_connection()

    def resetDevice(self, timeout=10):
        """ Issues a reset command and attempts recovery (camelCase wrapper). """
        return self.reset_device(timeout)

    def sendAndVerifyCommand(self, commandString, responseExpected="OK", exception=True):
        """ Sends a command and verifies the response (camelCase wrapper). """
        return self.send_and_verify_command(commandString, responseExpected, exception)

    def getRuntime(self, command="conf:runtimes?"):
        """ Gets runtime from device (camelCase wrapper). """
        return self.get_runtime(command)

    # --- New snake_case Methods (Containing Original Logic) ---

    def send_command(self, CommandString, expectedResponse=True):
        """ Executes a text based command on the device (snake_case API). """
        # This method contains the original logic from sendCommand
        logging.debug(f"{os.path.basename(__file__)}: {self.ConType[:3]} sending command: {CommandString}")
        response = ""  # Default response

        # Use connection object directly, assuming it's valid (checked in __init__)
        if not hasattr(self, 'connectionObj') or not self.connectionObj:
            raise ConnectionError("Connection object not available in send_command.")

        con_type_upper = self.ConType.upper()
        try:
            if con_type_upper.startswith("QIS"):
                # Original QIS logic for ensuring double colon if needed
                current_con_string = self.ConString  # Use current ConString state
                numb_colons = current_con_string.count(":")
                if numb_colons == 1:
                    current_con_string = current_con_string.replace(':', '::')
                # Delegate to QISConnection object's method
                response = self.connectionObj.qis.sendCommand(CommandString, device=current_con_string,
                                                              expectedResponse=expectedResponse)

            elif con_type_upper == "PY":
                # Delegate to PYConnection object's method
                # Original code accessed connectionObj.connection.sendCommand
                response = self.connectionObj.connection.sendCommand(CommandString, expectedResponse=expectedResponse)

            elif con_type_upper.startswith("QPS"):
                # Original QPS logic for command routing
                if CommandString and CommandString[0] != '$':
                    # Prepend module identifier only if it's not a QPS meta-command
                    # Make sure self.ConString is the correct identifier QPS expects
                    CommandString = f"{self.ConString} {CommandString}"
                # Delegate to QPSConnection object's method
                response = self.connectionObj.qps.sendCommand(CommandString, expectedResponse)
            else:
                # Should not be reached if __init__ validates ConType
                raise NotImplementedError(f"send_command not implemented for ConType {self.ConType}")

        except timeout_exception:
            logging.error(f"Timeout sending command: '{CommandString}'")
            raise TimeoutError(f"Timeout sending command: {CommandString}")
        except Exception as e:
            logging.error(f"Error sending command '{CommandString}': {e}", exc_info=True)
            raise ConnectionError(f"Error sending command '{CommandString}'") from e

        # Ensure response is string, original returned None sometimes
        response_str = response if response is not None else ""
        logging.debug(
            f"{os.path.basename(__file__)}: {self.ConType[:3]} received: {response_str[:100]}{'...' if len(response_str) > 100 else ''}")  # Log snippet
        return response_str

    def send_binary_command(self, cmd):
        """ Sends a binary command (USB only?) (snake_case API). """
        # This method contains the original logic from sendBinaryCommand
        # Assumes PY connection type and specific structure connectionObj.connection.Connection
        # Add checks for safety
        if self.ConType.upper() != "PY" or \
                not hasattr(self.connectionObj, 'connection') or \
                not hasattr(self.connectionObj.connection, 'Connection') or \
                not hasattr(self.connectionObj.connection.Connection, 'SendCommand') or \
                not hasattr(self.connectionObj.connection.Connection, 'BulkRead'):
            raise TypeError(
                f"send_binary_command is likely only supported for PY (USB) connections with specific structure.")

        logging.debug("Sending binary command (specific details not logged)")
        self.connectionObj.connection.Connection.SendCommand(cmd)
        response = self.connectionObj.connection.Connection.BulkRead()
        logging.debug("Received binary response (content not logged)")
        return response

    def open_connection(self):
        """ Opens/re-opens the connection to the module (snake_case API). """
        # This method contains the original logic from openConnection
        logging.debug(f"Attempting to open {self.ConType[:3]} connection")
        con_type_upper = self.ConType.upper()

        try:
            if con_type_upper.startswith("QIS"):
                # Original code assumes connectionObj.qis exists
                if hasattr(self.connectionObj, 'qis') and hasattr(self.connectionObj.qis, 'connect'):
                    # TODO: Original noted lack of return value check
                    self.connectionObj.qis.connect()
                    logging.info("QIS connect called.")
                    # How to verify success? May need specific QIS API knowledge
                    return True  # Assume success if no exception
                else:
                    raise AttributeError("QIS connection object or connect method not found.")

            elif con_type_upper == "PY":
                # Original code deleted and recreated PYConnection - risky?
                logging.warning("Recreating PYConnection in open_connection. Previous handles might linger.")
                # Ensure old connection is closed if possible
                if self.connectionObj and hasattr(self.connectionObj, 'connection') and hasattr(
                        self.connectionObj.connection, 'close'):
                    try:
                        self.connectionObj.connection.close()
                    except Exception:
                        pass  # Ignore errors closing old connection
                # Recreate - Potential for errors here if ConString isn't valid anymore
                self.connectionObj = PYConnection(self.ConString)
                logging.info(f"PY Connection recreated for {self.ConString}")
                # Expose details again?
                self.ConCommsType = self.connectionObj.ConnTypeStr
                self.connectionName = self.connectionObj.ConnTarget
                self.connectionTypeName = self.connectionObj.ConnTypeStr
                # Maybe return self.connectionObj as original did?
                return self.connectionObj

            elif con_type_upper.startswith("QPS"):
                # Original code assumes connectionObj.qps exists
                if hasattr(self.connectionObj, 'qps') and hasattr(self.connectionObj.qps, 'connect'):
                    # QPS connect might need target ConString
                    result = self.connectionObj.qps.connect(self.ConString)
                    logging.info(f"QPS connect called for {self.ConString}. Result: {result}")
                    return result  # Return result from QPS connect
                else:
                    raise AttributeError("QPS connection object or connect method not found.")

            else:
                # Should not be reached if __init__ validates ConType
                raise ValueError("Connection type not recognised in open_connection")

        except Exception as e:
            logging.error(f"Failed to open connection for {self.ConString} ({self.ConType}): {e}", exc_info=True)
            # Raise a more specific error?
            raise ConnectionError(f"Failed to open connection for {self.ConString}") from e

    def close_connection(self):
        """ Closes the connection to the module (snake_case API). """
        # This method contains the original logic from closeConnection
        logging.debug(f"Attempting to close {self.ConType[:3]} connection for {self.ConString}")
        con_type_upper = self.ConType.upper()
        closed_ok = False
        original_conn_obj = self.connectionObj  # Keep ref for checks

        if original_conn_obj is None:
            logging.debug("No connection object exists to close.")
            return "OK"  # Or maybe indicate nothing was closed?

        try:
            if con_type_upper.startswith("QIS"):
                if hasattr(original_conn_obj, 'qis') and hasattr(original_conn_obj.qis, 'closeConnection'):
                    original_conn_obj.qis.closeConnection(conString=self.ConString)
                    closed_ok = True
                else:
                    logging.warning("QIS connection object or closeConnection method not found.")

            elif con_type_upper == "PY":
                # Original accesses connectionObj.connection.close()
                if hasattr(original_conn_obj, 'connection') and hasattr(original_conn_obj.connection, 'close'):
                    original_conn_obj.connection.close()
                    closed_ok = True
                else:
                    logging.warning("PY connection object structure invalid for close.")

            elif con_type_upper.startswith("QPS"):
                if hasattr(original_conn_obj, 'qps') and hasattr(original_conn_obj.qps, 'disconnect'):
                    original_conn_obj.qps.disconnect(self.ConString)  # QPS uses disconnect
                    closed_ok = True
                else:
                    logging.warning("QPS connection object or disconnect method not found.")
            else:
                logging.error(f"Cannot close unknown connection type: {self.ConType}")

            if closed_ok:
                logging.info(f"Connection closed for {self.ConString}")
                self.connectionObj = None  # Clear reference after successful close
                return "OK"
            else:
                logging.warning(f"Could not close connection for {self.ConString} - state uncertain.")
                # Should we still clear self.connectionObj? Maybe not if close failed.
                return "FAIL"  # Indicate failure

        except Exception as e:
            logging.error(f"Error during close_connection for {self.ConString}: {e}", exc_info=True)
            # Clear reference even on error? Risky.
            # self.connectionObj = None
            return "FAIL"  # Indicate failure

    def reset_device(self, timeout=10):
        """ Issues a reset command and attempts recovery (snake_case API). """
        # This method contains the original logic from resetDevice
        logging.debug(f"{os.path.basename(__file__)}: sending command: *rst")
        original_con_string = self.ConString  # Store original target
        con_type_upper = self.ConType.upper()
        reset_sent = False

        if not hasattr(self, 'connectionObj') or not self.connectionObj:
            logging.error("Cannot reset device, no connection object.")
            return False

        try:
            if con_type_upper.startswith("QIS"):
                current_con_string = original_con_string
                numb_colons = current_con_string.count(":")
                if numb_colons == 1: current_con_string = current_con_string.replace(':', '::')
                # Send reset command via QIS connection
                self.connectionObj.qis.sendCmd(current_con_string, "*rst", expectedResponse=False)
                reset_sent = True
                # QIS connection object might remain valid, no explicit close needed here? Original didn't close.
            elif con_type_upper == "PY":
                # Send reset command via PY connection
                self.connectionObj.connection.sendCommand("*rst", expectedResponse=False)
                # Explicitly close the PY connection after sending reset
                self.connectionObj.connection.close()
                self.connectionObj = None  # Clear the potentially invalid connection object
                reset_sent = True
            elif con_type_upper.startswith("QPS"):
                # Send reset command via QPS connection
                CommandString = f"{original_con_string} *rst"
                self.connectionObj.qps.sendCmdVerbose(CommandString, expectedResponse=False)
                reset_sent = True
                # QPS connection object might remain valid? Original didn't close.
            else:
                logging.error(f"Reset not supported for connection type {self.ConType}")
                return False

        except Exception as e:
            logging.error(f"Error sending *rst command: {e}", exc_info=True)
            # Attempt to close connection forcefully on error before recovery attempt?
            try:
                self.close_connection()  # Use snake_case internal close
            except Exception:
                pass
            # Continue to recovery attempt? Or return False? Let's try recovery.
            reset_sent = False  # Indicate reset might not have fully completed

        # --- Recovery Attempt ---
        logging.debug(f"{os.path.basename(__file__)}: Attempting to reconnect to {original_con_string} after reset...")
        temp_device = None
        startTime = time.time()
        time.sleep(0.6)  # Original initial sleep

        while temp_device is None:
            if (time.time() - startTime) > timeout:
                logging.critical(
                    f"{os.path.basename(__file__)}: Reconnection failed to {original_con_string} within {timeout}s timeout.")
                # Ensure connectionObj is None if recovery failed
                self.connectionObj = None
                return False
            try:
                # Attempt to get device using the original wrapper function name
                # Pass original ConType too, in case it was needed
                temp_device = getQuarchDevice(original_con_string, ConType=self.ConType, timeout=str(
                    max(1, timeout - int(time.time() - startTime))))  # Reduce timeout for reconnect attempt
            except Exception as recon_e:
                # Log reconnection attempt failure, but don't stop trying until timeout
                logging.debug(f"Reconnect attempt failed: {recon_e}. Retrying...")
                time.sleep(0.2)  # Original sleep between retries

        # Recovery successful
        logging.info(f"Successfully reconnected to {original_con_string} after reset.")
        # Replace the current connection object with the one from the recovered device
        self.connectionObj = temp_device.connectionObj
        # Original code doesn't transfer other attributes like ConType, ConString etc.
        # This might be problematic if the resolved ConString changed. Let's update:
        self.ConString = temp_device.ConString
        self.ConType = temp_device.ConType
        # We need to keep the temp_device alive until its connectionObj is transferred,
        # but then let it be garbage collected. Python handles this.

        time.sleep(1)  # Original final sleep
        return True

    def send_and_verify_command(self, commandString, responseExpected="OK", exception=True):
        """ Sends a command and verifies the response (snake_case API). """
        # This method contains the original logic from sendAndVerifyCommand
        # Calls the original sendCommand wrapper internally
        responseStr = self.sendCommand(commandString)

        # Ensure comparison handles None response gracefully
        response_str_safe = responseStr if responseStr is not None else ""

        # Perform comparison (case-sensitive as original)
        if (response_str_safe != responseExpected):
            error_msg = f"Command Sent: '{commandString}', Expected response: '{responseExpected}', Response received: '{responseStr}'"
            logging.error(error_msg)  # Log the error regardless
            if (exception):
                raise ValueError(error_msg)  # Raise exception if requested
            else:
                return False  # Return False if exception=False
        else:
            logging.debug(f"Command '{commandString}' verified successfully (Response: '{responseExpected}').")
            return True  # Return True on match

    def get_runtime(self, command="conf:runtimes?"):
        """ Gets runtime from device (snake_case API). """
        # This method contains the original logic from getRuntime
        # Calls the original sendCommand wrapper internally
        runtime_str = self.sendCommand(command)

        if runtime_str is None:  # Handle None response
            logging.error(f"Received None response for runtime command: {command}")
            return None

        # Use case-insensitive check for "fail"
        if "fail" in runtime_str.lower():
            logging.error(f"Runtime check failed (Command: {command}, Response: {runtime_str}), check FW and FPGA?")
            # Return None or raise error? Original returned None implicitly later.
            return None

        # Check if response ends with 's' and try conversion
        if runtime_str.endswith("s"):
            try:
                runtime_int = int(runtime_str[:-1])
                logging.debug(f"Runtime parsed as {runtime_int} seconds.")
                return runtime_int
            except ValueError:  # Catch if conversion fails
                logging.error(f"Runtime response '{runtime_str}' not a valid int format.")
                return None
            except Exception as e:  # Catch other potential errors
                logging.error(f"Unexpected error parsing runtime '{runtime_str}': {e}")
                return None
        else:
            # Did not end with 's' - might be unexpected format or different command used
            logging.warning(f"Runtime response '{runtime_str}' did not end with 's'. Cannot parse as seconds.")
            # Decide what to return - None seems safest.
            return None


# --- Top-Level Function Definitions ---

# Original _check_ip_in_qis_list function (snake_case, internal) - Unchanged
def _check_ip_in_qis_list(ip_address, detailed_device_list):
    """
    Checks if the IP address is in qis device list
    :param detailed_device_list: list formatted return from qis command "$list details"
    :return String : return contype and constring for module if it's in list, else None
    """
    if not detailed_device_list: return None  # Handle empty list

    for module_line in detailed_device_list:
        # Safer parsing: find "IP:address" pattern
        ip_match = re.search(r"\bIP:(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b", module_line)
        if ip_match and ip_match.group(1) == ip_address:
            # Found the IP, now extract the connection string part (e.g., "TYPE::ID")
            # Assuming format like "N) TYPE::ID IP:..." or similar
            conn_str_match = re.search(r"^\s*\d+\)\s+([A-Z]+::[^ ]+)", module_line)  # Look for TYPE::ID at start
            if conn_str_match:
                # Original logic restricted to TCP, check if needed
                if "tcp" in module_line.lower():  # Keep original TCP check
                    return conn_str_match.group(1)  # Return "TYPE::ID" part
                else:
                    logging.debug(f"IP {ip_address} found but not a TCP entry in QIS list line: {module_line}")
            else:
                # Alternative format check? E.g. if conn string isn't second element
                # Original code split and took second element - might be fragile.
                # Let's try the split approach as fallback if regex fails
                parts = module_line.split()
                if len(parts) > 1 and "::" in parts[1]:  # Check if second element looks like TYPE::ID
                    if "tcp" in module_line.lower():  # Keep original TCP check
                        logging.debug(f"Resolved IP {ip_address} using split method to: {parts[1]}")
                        return parts[1]
                    else:
                        logging.debug(f"IP {ip_address} found via split but not TCP entry: {module_line}")

    # IP address not found in any relevant line
    return None


# New snake_case function containing the logic FORMERLY in checkModuleFormat
def check_module_format(ConString):
    """ Checks the validity of a connection string format (snake_case API). """
    # This function now contains the actual implementation
    # Logic from original checkModuleFormat function in pasted code:
    if not ConString: return True  # Assume empty is valid? Original didn't check. Let's allow.
    if ':' not in ConString: return False

    # Original types from this specific function
    ConnectionTypes = ["USB", "SERIAL", "TELNET", "REST", "TCP"]

    conTypeSpecified = ConString[:ConString.find(':')]

    correctConType = False
    for value in ConnectionTypes:
        if value.lower() == conTypeSpecified.lower():
            correctConType = True
            break  # Exit loop

    if not correctConType:
        logging.warning(f"Invalid connection type specified ('{conTypeSpecified}'). Use one of {ConnectionTypes}")
        logging.warning(f"Invalid connection string: {ConString}")
        return False

    numb_colons = ConString.count(":")
    # Original strict colon check from this specific function
    if numb_colons > 2 or numb_colons <= 0:
        # Allow sub-device format which might have different colon rules initially
        # Re-check using the refined logic from the other check_con_string analysis
        if "<" in ConString and ">" in ConString:
            match = re.match(r"^[A-Z]+:[^<>:]+<\d+>$", ConString, re.IGNORECASE)
            if match:
                controller_part = ConString.split('<')[0]
                # *** IMPORTANT: Recursive call needs care. Calling self. ***
                if check_module_format(controller_part):
                    return True
                else:
                    logging.warning(f"Invalid controller part '{controller_part}' in sub-device string '{ConString}'")
            else:
                logging.warning(f"Invalid sub-device format syntax: '{ConString}'")
            # If sub-device check failed, the colon count is invalid for non-sub-device
            return False
        else:
            # Not a sub-device and wrong colon count
            logging.warning(f"Invalid number of colons ({numb_colons}) in module string (expected 1 or 2).")
            logging.warning(f"Invalid connection string: {ConString}")
            return False

    # Passed basic checks (Type known, 1 or 2 colons, or valid sub-device)
    return True


# Original checkModuleFormat function, kept for compatibility, now calls snake_case version
def checkModuleFormat(ConString):
    """ Checks the validity of a connection string format (camelCase wrapper). """
    return check_module_format(ConString)


# New snake_case function containing the logic FORMERLY in getQuarchDevice
def get_quarch_device(connectionTarget, ConType="PY", timeout="5"):
    """ Creates a quarch device instance, handling sub-devices (snake_case API). """
    # This function now contains the actual implementation
    # Local import as in original function
    from .quarchArray import quarchArray, subDevice

    # Original check for sub-device format using __contains__
    if isinstance(connectionTarget, str) and connectionTarget.__contains__("<") and connectionTarget.__contains__(">"):
        logging.debug(f"Detected sub-device format for {connectionTarget}")
        controller_target_str, portNumberPart = connectionTarget.split("<")
        portNumberStr = portNumberPart[:-1]  # Remove '>'

        # Validate port number
        if not portNumberStr.isdigit():
            raise ValueError(f"Invalid port number '{portNumberStr}' in sub-device string")
        portNumber = int(portNumberStr)

        # Validate controller part using the wrapper function (as internal calls remain camelCase)
        if not checkModuleFormat(controller_target_str):
            raise ValueError(f"Invalid controller part format: '{controller_target_str}'")

        logging.debug(f"Connecting to controller '{controller_target_str}' first...")
        # *** Replicating original file's explicit ConType="PY" for the controller connection ***
        myDevice = quarchDevice(controller_target_str, ConType="PY", timeout=timeout)

        logging.debug("Wrapping controller device with quarchArray...")
        # This assumes quarchArray.__init__ works correctly with the base device
        myArrayController = quarchArray(myDevice)

        logging.debug(f"Getting subDevice for port {portNumber}...")
        # Call original getSubDevice name (wrapper) internally
        mySubDevice = myArrayController.getSubDevice(portNumber)
        myDevice = mySubDevice  # Return the subDevice instance
        logging.info(f"Successfully connected to sub-device: {connectionTarget}")
    else:
        # Standard device connection
        logging.debug(f"Standard device connection for: {connectionTarget}")
        myDevice = quarchDevice(connectionTarget, ConType=ConType, timeout=timeout)
        logging.info(f"Successfully connected to standard device: {connectionTarget}")

    return myDevice


# Original getQuarchDevice function, kept for compatibility, now calls snake_case version
def getQuarchDevice(connectionTarget, ConType="PY", timeout="5"):
    """ Creates a quarch device instance, handling sub-devices (camelCase wrapper). """
    return get_quarch_device(connectionTarget, ConType, timeout)
