from __future__ import annotations
from typing import Optional, Tuple, Any, Union  # Added for type hinting in docstrings
import logging
import os
import re
import sys
import time

from quarchpy.qps import isQpsRunning
from quarchpy.qis import isQisRunning

from quarchpy.connection import QISConnection, PYConnection, QPSConnection
# Check Python version and set timeout exception
if sys.version_info.major == 2:
    try:
        import socket

        timeout_exception = socket.timeout
    except AttributeError as e:
        timeout_exception = None
        logging.error(f"Socket timeout unavailable: {e}")
else:
    timeout_exception = TimeoutError  # Python 3: Use built-in TimeoutError

# --- Main Device Class ---
class quarchDevice:
    """
    Allows control over a Quarch device, over a wide range of underlying
    connection methods. This is the core class used for control of all
    Quarch products.

    Attributes:
        ConString (str): The potentially modified connection string used.
        ConType (str): The specified connection type ('PY', 'QIS', 'QPS').
        timeout (int): The communication timeout in seconds.
        connectionObj (Optional[QISConnection, QPSConnection, PYConnection]): The underlying connection
            object (e.g., PYConnection, QISConnection instance). None if connection failed or is closed.
        ConCommsType (Optional[str]): The actual communication type determined
            by the connection object (e.g., 'USB', 'TCP'). Set for PY type.
        connectionName (Optional[str]): The target identifier determined by the
            connection object (e.g., 'QTL1234-01-001', '192.168.1.100'). Set for PY type.
        connectionTypeName (Optional[str]): Alias for ConCommsType. Set for PY type.
    """

    def __init__(self, ConString: str, ConType: str = "PY", timeout: str = "5"):
        """
        Initializes the quarchDevice, establishes the connection.

        Performs initial parameter validation, determines the connection type,
        delegates to specific helper methods to create the underlying connection
        object (PYConnection, QISConnection, or QPSConnection), and verifies
        the connection.

        Args:
            ConString (str): The connection string (e.g., "USB:ID", "TCP:IP", "QIS:ID").
            ConType (str, optional): The connection mode ('PY', 'QIS', 'QPS'). Defaults to "PY".
            timeout (str, optional): Communication timeout in seconds. Defaults to "5".

        Raises:
            ValueError: If ConString format is invalid or timeout is not numeric.
            ConnectionError: If establishing the connection fails.
            TimeoutError: If verifying the device on QIS/QPS times out.
            ImportError: If required underlying connection classes are missing.
        """
        # --- Initial setup and validation ---
        # Initialize all instance attributes first
        self.ConType = ""
        self.ConString = ""
        self.connectionTypeName = None
        self.connectionName = None
        self.ConCommsType = None
        self.connectionObj = None
        self.timeout = 5  # Default int timeout

        # Call helper to store and validate parameters
        self._store_and_validate_params(ConString, ConType, timeout)

        logging.debug(f"Initializing quarchDevice with ConString='{self.ConString}', ConType='{self.ConType}', Timeout='{self.timeout}'")
        con_type_upper = self.ConType.upper()

        # --- Delegate to specific initialization method ---
        if con_type_upper == "PY":
            self._initialize_py_connection()
        elif con_type_upper.startswith("QIS"):
            self._initialize_qis_connection()
        elif con_type_upper.startswith("QPS"):
            self._initialize_qps_connection()
        else:
            # Invalid ConType should have been caught by check_module_format
            raise ValueError(f"Invalid connection type '{self.ConType}'.")

        # --- Final connection verification ---
        self._verify_connection_object()
        logging.info(f"Connection successful: Type='{self.ConType}', Target='{getattr(self.connectionObj, 'ConnTarget', 'Unknown')}'")

    # --- Private Helper Methods ---

    def _store_and_validate_params(self, ConString: str, ConType: str, timeout: str):
        """
        Stores initial parameters and performs basic validation.

        Sets self.ConString (with lowercasing rule), self.ConType,
        validates and sets self.timeout (as int), and calls
        check_module_format to validate ConString format.

        Args:
            ConString (str): The raw connection string.
            ConType (str): The raw connection type.
            timeout (str): The raw timeout value.

        Raises:
            ValueError: If timeout is non-numeric or ConString format is invalid.
        """
        self.ConString = ConString
        # Lowercase unless serial
        if "serial" not in ConString.lower():
            self.ConString = ConString.lower()
        self.ConType = ConType
        self.connectionObj = None  # Ensure it's reset here
        self.timeout = int(timeout)

        # Use the globally defined check_module_format function
        if not check_module_format(self.ConString):
            raise ValueError(f"Module format is invalid for connection string: '{self.ConString}'")

    def _initialize_py_connection(self):
        """
        Initializes the connection using the PY (Pure Python) method.

        Handles colon formatting, resolves target using get_connection_target if
        applicable, creates the PYConnection object, stores connection details,
        and verifies communication with a '*tst?' command.

        Sets:
            self.connectionObj, self.ConCommsType, self.connectionName,
            self.connectionTypeName, self.ConString (potentially updated).

        Raises:
            ConnectionError: If connection fails or device doesn't respond correctly.
            ImportError: If PYConnection class is missing.
        """
        logging.debug("Attempting PY connection...")
        # Handle potential double colons
        numb_colons = self.ConString.count(":")
        if numb_colons == 2:
            logging.debug("Replacing '::' with ':' in ConString for PY connection.")
            self.ConString = self.ConString.replace('::', ':')

        # Resolve target if needed
        self._resolve_py_target()

        # Create PYConnection object
        try:
            # Store PYConnection object
            self.connectionObj = PYConnection(self.ConString)
            # Store connection details from the object
            self.ConCommsType = getattr(self.connectionObj, 'ConnTypeStr', None)
            self.connectionName = getattr(self.connectionObj, 'ConnTarget', None)
            self.connectionTypeName = self.ConCommsType  # Alias
            logging.debug(f"PY Connection details: Type='{self.connectionTypeName}', Target='{self.connectionName}'")
        except Exception as e_pyconn:
            logging.error(f"Failed to create PYConnection for '{self.ConString}': {e_pyconn}", exc_info=True)
            raise ConnectionError(f"Failed to establish PY connection for '{self.ConString}'") from e_pyconn

        # Verify communication with *tst?
        self._test_py_connection()

    def _resolve_py_target(self):
        """
        Attempts to resolve ConString target if needed for PY connections.

        If the ConString looks like a QTL identifier (contains 'qtl') but is
        not explicitly USB, it calls the external `get_connection_target`
        function to find the best actual connection string (e.g., a specific
        COM port or IP address) and updates `self.ConString` if found.

        Uses:
            self.ConString
            get_connection_target (imported function)

        Modifies:
            self.ConString (if target is resolved)
        """
        # Check conditions: contains 'qtl', not 'usb', and helper function exists
        if "qtl" in self.ConString.lower() and "usb" not in self.ConString.lower():
            from quarchpy.device import get_connection_target
            if get_connection_target is not None:
                try:
                    logging.debug(f"Attempting to resolve connection target for '{self.ConString}'...")
                    resolved_con_string = get_connection_target(self.ConString)
                    if resolved_con_string and "Fail" not in resolved_con_string:  # Check for failure string
                        logging.debug(f"Resolved '{self.ConString}' to '{resolved_con_string}'")
                        self.ConString = resolved_con_string  # Update if successful
                    else:
                        logging.warning(f"get_connection_target failed or returned empty for '{self.ConString}'. Using original.")
                except Exception as e_scan:
                    # Log error but continue with original ConString
                    logging.error(f"Error calling get_connection_target: {e_scan}. Using original ConString.")
            else:
                # Log if resolution needed but helper unavailable
                logging.warning("get_connection_target function not available, cannot resolve connection string.")

    def _test_py_connection(self):
        """
        Sends '*tst?' command to verify communication for PY connections.

        Checks if the response contains "OK" or "FAIL".
        Closes connection and raises ConnectionError
        if the test fails or times out.

        Raises:
            ConnectionError: If the command fails or the response is invalid.
        """
        try:
            # Use snake_case internally
            item = self.send_command("*tst?")
        except Exception as e_tst:
            logging.warning(f"Error sending *tst? during init: {e_tst}")
            # Raise a more specific error indicating communication failure
            raise ConnectionError("Module failed to respond to *tst? command during initialization.") from e_tst

        # Check if response indicates basic communication success
        response_ok = item is not None and ("OK" in item or "FAIL" in item)
        if not response_ok:
            logging.error(f"No valid module response to *tst? command! Received: '{item}'")
            try:
                self.close_connection()
            except Exception as close_err:
                logging.error(f"Error closing connection after *tst? failure: {close_err}")
            # Raise error indicating failed test
            raise ConnectionError(f"No valid module response to *tst? command! Received: '{item}'")
        logging.debug("*tst? check successful.")

    def _parse_server_details(self, default_port: int) -> Tuple[str, int]:
        """
        Parses host and port from self.ConType for QIS/QPS connection types.

        Expects self.ConType to be like "QIS" or "QIS:host:port".
        Returns defaults ('127.0.0.1', default_port) if parsing fails or is not applicable.

        Args:
            default_port (int): The default port number for the server type (QIS/QPS).

        Returns:
            tuple[str, int]: A tuple containing the host (str) and port (int).
        """
        host = '127.0.0.1'
        port = default_port
        con_type_upper = self.ConType.upper()
        # Determine prefix based on actual ConType start
        prefix = "QIS" if con_type_upper.startswith("QIS") else "QPS" if con_type_upper.startswith("QPS") else None

        if prefix:
            try:
                # Attempt to split ConType string like "QIS:host:port"
                _, host_parsed, port_str = self.ConType.split(':')
                port = int(port_str)  # Convert port part to integer
                host = host_parsed  # Use parsed host
            except ValueError:
                # Handles cases where split fails (not 3 parts) or int conversion fails
                # Only log warning if it looked like host/port were provided but were invalid
                if con_type_upper != prefix:
                    logging.warning(f"Could not parse host/port from ConType '{self.ConType}', using defaults {host}:{port}.")
            except Exception as e_parse:
                # Catch any other unexpected parsing errors
                logging.warning(f"Error parsing ConType '{self.ConType}': {e_parse}. Using defaults {host}:{port}.")
        return host, port

    def _prepare_server_con_string(self):
        """
        Formats self.ConString by replacing single ':' with '::' if needed.

        This is sometimes required for QIS/QPS connection libraries when only
        one colon is present in the identifier part (e.g., "TCP:ID" becomes "TCP::ID").

        Modifies:
            self.ConString
        """
        numb_colons = self.ConString.count(":")
        # Apply replacement only if exactly one colon exists
        if numb_colons == 1:
            logging.debug(f"Replacing single colon ':' with '::' in ConString '{self.ConString}' for server connection.")
            self.ConString = self.ConString.replace(':', '::')

    def _verify_server_device(self, server_conn_obj: Any, server_type: str):
        """
        Finds and verifies the target device on a QIS or QPS server.

        Repeatedly checks the server's device list for the target device
        (self.ConString), handling identification by QTL number or IP address.
        If identified by IP, resolves it to the device's actual connection string
        (e.g., "TYPE::QTL...") using _check_ip_in_qis_list. May trigger a
        network scan via the server connection object's scanIP method if needed.

        Args:
            server_conn_obj (Any): The specific QIS/QPS connection object
                                  (e.g., self.connectionObj.qis). Type hinted as Any
                                  as the exact type depends on the imported library.
            server_type (str): "QIS" or "QPS" for logging/error messages.

        Returns:
            bool: True if the device was successfully found and verified.
                  `self.ConString` may be updated as a side effect if resolved via IP.

        Raises:
            ValueError: If ConString is IP-based but contains no valid IP.
            TimeoutError: If the device cannot be found/verified within self.timeout.
            Exception: Propagates exceptions from server_conn_obj methods.
        """
        # --- Initialization ---
        logging.debug(f"Verifying device '{self.ConString}' on {server_type} server...")
        found = False
        connect_timeout = time.time() + self.timeout  # Calculate deadline

        # --- Main Verification Loop ---
        while time.time() < connect_timeout:
            # --- Get current list details ---
            try:
                list_details = server_conn_obj.get_list_details()  # Assumes method exists
                list_str_lower = "".join(list_details).lower()
            except Exception as e_list:
                logging.warning(f"Failed to refresh {server_type} list details during check: {e_list}")
                if time.time() >= connect_timeout:
                    break
                time.sleep(1)  # Wait before retrying list fetch
                continue  # Skip rest of loop iteration

            # --- Determine target type (IP or QTL) ---
            target_lower = self.ConString.lower()

            if "qtl" not in target_lower:
                # --- Target is likely IP Address ---
                ip_match = re.search(r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}", target_lower)
                if not ip_match:
                    raise ValueError(f"ConString '{self.ConString}' has no QTL and no valid IP for {server_type}.")
                target_ip = ip_match.group()

                # Call helper to find by IP (handles list check, scan, re-check)
                resolved_string = self._find_device_by_ip(server_conn_obj, server_type, list_details, target_ip)
                if resolved_string:
                    # Side effect: self.ConString was updated in helper
                    found = True
                    break  # Exit main loop
                # If _find_device_by_ip returns None, IP wasn't found in this iteration/scan attempt
            else:
                # --- Target is QTL Number ---
                if self._find_device_by_qtl(list_str_lower, target_lower):
                    found = True  # Found via QTL
                    break  # Exit main loop

            # --- Not found yet, wait before next iteration ---
            if time.time() >= connect_timeout:
                break  # Exit loop if timeout reached before sleeping
            logging.debug(f"Target '{self.ConString}' not found in {server_type} list yet. Waiting 1s before retry...")
            time.sleep(1)

        # --- Loop Finished: Final Check ---
        if not found:
            logging.error(f"Timeout: Could not find/verify module '{self.ConString}' in {server_type} within {self.timeout}s.")
            raise TimeoutError(f"Could not find module '{self.ConString}' in {server_type} within {self.timeout}s")

        logging.info(f"Successfully verified device '{self.ConString}' in {server_type}.")
        return True  # Indicate success

    def _find_device_by_ip(self, server_conn_obj, server_type, list_details, target_ip):
        """
        Attempts to find the device via IP, potentially resolving it and scanning.

        Checks the provided list, then optionally scans if not found and re-checks.
        Updates self.ConString if resolved via IP lookup.

        Args:
            server_conn_obj: The specific QIS/QPS connection object (e.g., self.connectionObj.qis).
            server_type (str): "QIS" or "QPS" for logging/error messages.
            list_details (list): The current list details from the server.
            target_ip (str): The IP address being searched for.

        Returns:
            str: The resolved ConString if found (and self.ConString is updated).
            None: If not found via IP lookup or scan within this attempt.

        Raises:
            Exceptions from underlying scanIP or get_list_details calls.
        """
        # 1. Check current list details for the IP
        resolved_con_string = _check_ip_in_qis_list(target_ip, list_details)
        if resolved_con_string:
            logging.info(f"Resolved IP {target_ip} to '{resolved_con_string}' from {server_type} list.")
            self.ConString = resolved_con_string  # Update instance ConString
            return resolved_con_string  # Return resolved string

        # 2. IP not in list, attempt network scan if possible
        logging.debug(f"IP {target_ip} not in {server_type} list, attempting network scan...")
        try:
            scan_method = getattr(server_conn_obj, 'scanIP', None)
            if not scan_method:
                logging.warning(f"scanIP method not found on {server_type} connection object.")
                return None  # Cannot scan

            scan_response = scan_method(target_ip)  # Scan using the target IP
            if "located" not in str(scan_response).lower():
                logging.debug(f"{server_type} scan for {target_ip} did not locate the device.")
                return None  # Scan didn't find it

            # 3. Scan located the device, now re-check the list after a delay
            logging.info(f"{server_type} located {target_ip} via scan. Re-checking list after delay...")
            # Use a shorter, fixed timeout for this re-check phase
            scan_recheck_timeout = time.time() + 20  # Allow 20s for list update
            time.sleep(2)  # Initial pause

            while time.time() < scan_recheck_timeout:
                current_list_details = server_conn_obj.get_list_details()  # Re-fetch
                resolved_con_string = _check_ip_in_qis_list(target_ip, current_list_details)
                if resolved_con_string:
                    logging.info(f"Resolved IP {target_ip} to '{resolved_con_string}' after scan.")
                    self.ConString = resolved_con_string  # Update instance ConString
                    return resolved_con_string  # Return resolved string
                # If not found yet, wait before checking again
                if time.time() >= scan_recheck_timeout:
                    break  # Check timeout before sleep
                logging.debug(f"IP {target_ip} still not resolved in {server_type} list post-scan, retrying...")
                time.sleep(1)

            # If loop finishes without finding, log it
            logging.warning(f"Device at {target_ip} was located by scan but did not appear resolvable in {server_type} list within timeout.")
            return None  # Not found even after scan

        except Exception as e_findIP:
            # Log errors during the scan process but don't necessarily stop verification yet
            logging.warning(f"Error during {server_type} scan/re-check for {target_ip}: {e_findIP}")
            return None  # Indicate IP search failed for this attempt

    @staticmethod
    def _find_device_by_qtl(list_str_lower, target_qtl_lower):
        """Checks if the target QTL identifier exists in the server list string."""
        if target_qtl_lower in list_str_lower:
            logging.debug(f"Found target QTL '{target_qtl_lower}' directly in server list.")
            return True
        return False

    def _initialize_qis_connection(self):
        """
        Initializes the connection using the QIS method.

        Parses host/port, prepares connection string, creates QISConnection object,
        verifies the device presence on the server using the common helper, and
        sets the device as default on the QIS server.

        Sets:
            self.connectionObj, self.ConString.

        Raises:
            ConnectionError: If connection or verification fails.
            TimeoutError: If verification times out.
            ImportError: If QISConnection class is missing.
        """
        logging.debug("Attempting QIS connection...")
        host, port = self._parse_server_details(default_port=9722)
        self._prepare_server_con_string()

        # Create QISConnection object
        try:
            # Assumes QISConnection is imported
            self.connectionObj = QISConnection(self.ConString, host, port)
            logging.debug(f"QISConnection object created for '{self.ConString}' via {host}:{port}")
        except Exception as e_qisconn:
            logging.error(f"Failed to create QISConnection: {e_qisconn}", exc_info=True)
            raise ConnectionError("Failed to establish QIS connection.") from e_qisconn

        # Verify device presence on the QIS server
        try:
            # Pass the QIS-specific sub-object (self.connectionObj.qis) to the helper
            self._verify_server_device(self.connectionObj.qis, "QIS")
        except TimeoutError as e_timeout:
            self.close_connection()  # Close object if verification failed
            raise e_timeout  # Re-raise timeout
        except Exception as e_qis_conn:
            self.close_connection()  # Close object if verification failed
            raise ConnectionError(f"Failed QIS device verification: {e_qis_conn}") from e_qis_conn

        # Set QIS default device
        try:
            set_default_cmd = f"$default {self.ConString}"
            logging.debug(f"Setting QIS default device: {set_default_cmd}")
            # Assumes sendAndReceiveCmd exists on QIS object
            response = self.connectionObj.qis.sendAndReceiveCmd(cmd=set_default_cmd)
            logging.debug(f"QIS set default response: {response}")
            if "fail" in response.lower():
                logging.warning(f"QIS command '$default {self.ConString}' failed.")
        except Exception as e_def:
            logging.warning(f"Error setting QIS default device: {e_def}")

    def _initialize_qps_connection(self):
        """
        Initializes the connection using the QPS method.

        Parses host/port, prepares connection string, creates QPSConnection object,
        and verifies the device presence on the server using the common helper.

        Sets:
            self.connectionObj, self.ConString (potentially updated).

        Raises:
            ConnectionError: If connection or verification fails.
            TimeoutError: If verification times out.
            ImportError: If QPSConnection class is missing.
        """
        logging.debug("Attempting QPS connection...")
        host, port = self._parse_server_details(default_port=9822)  # type: ignore[misc] # Private call ok
        self._prepare_server_con_string()  # type: ignore[misc] # Private call ok

        # Create QPSConnection object
        try:
            # Assumes QPSConnection is imported
            self.connectionObj = QPSConnection(host, port)
            logging.debug(f"QPSConnection object created via {host}:{port}")
        except Exception as e_qpsconn:
            logging.error(f"Failed to create QPSConnection: {e_qpsconn}", exc_info=True)
            raise ConnectionError("Failed to establish QPS connection.") from e_qpsconn

        # Verify device presence on the QPS server
        try:
            # Pass the QPS-specific sub-object (self.connectionObj.qps) to the helper
            self._verify_server_device(self.connectionObj.qps, "QPS")  # type: ignore[misc] # Private call ok
        except TimeoutError as e_timeout:
            self.close_connection()  # Close object if verification failed
            raise e_timeout  # Re-raise timeout
        except Exception as e_qps_conn:
            self.close_connection()  # Close object if verification failed
            raise ConnectionError(f"Failed QPS device verification: {e_qps_conn}") from e_qps_conn
        # QPS typically doesn't use/need a '$default' command

    def _verify_connection_object(self):
        """
        Performs final checks to ensure a valid connection object exists.

        Raises:
            ConnectionError: If self.connectionObj is None or lacks expected attributes.
        """
        if not self.connectionObj:
            # This should ideally be caught by specific init helpers, but acts as a final safeguard
            raise ConnectionError("Connection object (self.connectionObj) was not successfully created by initializer.")

    def __del__(self):
        """ Ensures the connection is closed when the object is garbage collected. """
        try:
            # Close all connections
            self.close_connection()
        except Exception as e_close:
            # Avoid errors during shutdown sequence
            if logging and logging.error:
                logging.error(f"Error during automatic connection close in destructor: {e_close}")

    # --- Public Methods (Wrappers + snake_case) ---

    # --- sendCommand ---
    def send_command(self, command_string: str, is_response_expected: bool = True) -> str:
        """
        Executes a text command on the connected device.

        Sends the command string via the appropriate underlying connection object
        (PY, QIS, or QPS) and returns the response. Handles QIS/QPS specific
        formatting or command routing as needed.

        Args:
            command_string (str): The text command to send (e.g., "*IDN?").
            is_response_expected (bool, optional): If False, the method may return
                faster as it doesn't wait for/read a response. Defaults to True.

        Returns:
            str: The response string from the device. Returns an empty string if
                 no response was expected or received, or if the underlying connection
                 returned None.

        Raises:
            ConnectionError: If the device is not connected, or if communication fails.
            TimeoutError: If the device response times out.
            NotImplementedError: If the method is called for an unsupported ConType.
        """
        logging.debug(f"{os.path.basename(__file__)}: {self.ConType[:3]} sending command: {command_string}")

        if not hasattr(self, 'connectionObj') or not self.connectionObj:
            raise ConnectionError("Connection object not available in send_command.")

        con_type_upper = self.ConType.upper()
        try:
            if con_type_upper.startswith("QIS"):
                # Use current ConString state (might have been updated)
                current_con_string = self.ConString
                numb_colons = current_con_string.count(":")
                if numb_colons == 1:
                    current_con_string = current_con_string.replace(':', '::')
                # Assumes QISConnection type for connectionObj
                response = self.connectionObj.qis.sendCommand(command_string, device=current_con_string, expectedResponse=is_response_expected)

            elif con_type_upper == "PY":
                # Assumes PYConnection type for connectionObj
                if hasattr(self.connectionObj, 'connection') and hasattr(self.connectionObj.connection, 'sendCommand'):
                    response = self.connectionObj.connection.sendCommand(command_string, expectedResponse=is_response_expected)
                else:
                    raise AttributeError("PYConnection object missing expected structure.")

            elif con_type_upper.startswith("QPS"):
                # Assumes QPSConnection type for connectionObj
                if command_string and command_string[0] != '$':
                    command_string = f"{self.ConString} {command_string}"  # Prepend target ID
                response = self.connectionObj.qps.sendCommand(command_string, is_response_expected)
            else:
                raise NotImplementedError(f"send_command not implemented for ConType {self.ConType}")

        except timeout_exception:  # Use platform specific timeout
            logging.error(f"Timeout sending command: '{command_string}'")
            raise TimeoutError(f"Timeout sending command: {command_string}")
        except Exception as e_cmd_exception:
            logging.error(f"Error sending command '{command_string}': {e_cmd_exception}", exc_info=True)
            raise ConnectionError(f"Error sending command '{command_string}'") from e_cmd_exception

        response_str = response if response is not None else ""  # Ensure string
        logging.debug(f"{os.path.basename(__file__)}: {self.ConType[:3]} received: {response_str[:100]}{'...' if len(response_str) > 100 else ''}")
        return response_str

    def sendCommand(self, CommandString: str, expectedResponse: bool = True) -> str:
        """
        DEPRECATED - Use send_command instead.

        Executes a text command on the connected device.

        Sends the command string via the appropriate underlying connection object
        (PY, QIS, or QPS) and returns the response. Handles QIS/QPS specific
        formatting or command routing as needed.

        Args:
            CommandString (str): The text command to send (e.g., "*IDN?").
            expectedResponse (bool, optional): If False, the method may return
                faster as it doesn't wait for/read a response. Defaults to True.

        Returns:
            str: The response string from the device. Returns an empty string if
                 no response was expected or received, or if the underlying connection
                 returned None.

        Raises:
            ConnectionError: If the device is not connected, or if communication fails.
            TimeoutError: If the device response times out.
            NotImplementedError: If the method is called for an unsupported ConType.
        """
        return self.send_command(CommandString, expectedResponse)

    # --- sendBinaryCommand ---
    def send_binary_command(self, cmd: bytes) -> bytes:
        """
        Sends a binary command and reads binary response (USB only).

        This method is typically used for low-level or USB-specific communication.
        It assumes a PY connection type with a specific underlying structure.

        Args:
            cmd (bytes): The binary command sequence to send.

        Returns:
            bytes: The binary data read back from the device.

        Raises:
            TypeError: If the connection type is not PY or the underlying
                       connection object structure is unexpected.
            ConnectionError: If communication fails.
        """
        # Check connection type and structure
        if self.ConType.upper() != "PY" or \
                not hasattr(self.connectionObj, 'connection') or \
                not hasattr(self.connectionObj.connection, 'Connection') or \
                not hasattr(self.connectionObj.connection.Connection, 'SendCommand') or \
                not hasattr(self.connectionObj.connection.Connection, 'BulkRead'):
            raise TypeError(f"send_binary_command requires a PY connection with a USB connection.")

        logging.debug("Sending binary command...")
        try:
            self.connectionObj.connection.Connection.SendCommand(cmd)
            response = self.connectionObj.connection.Connection.BulkRead()
        except Exception as e_binary_exception:
            logging.error(f"Error during binary command: {e_binary_exception}", exc_info=True)
            raise ConnectionError("Failed to send/receive binary command.") from e_binary_exception

        logging.debug("Received binary response.")
        return response if response is not None else b""  # Ensure bytes return

    def sendBinaryCommand(self, cmd: bytes) -> bytes:
        """
        DEPRECATED - Use send_binary_command instead.

        Sends a binary command and reads binary response (USB only).

        This method is typically used for low-level or USB-specific communication.
        It assumes a PY connection type with a specific underlying structure.

        Args:
            cmd (bytes): The binary command sequence to send.

        Returns:
            bytes: The binary data read back from the device.

        Raises:
            TypeError: If the connection type is not PY or the underlying
                       connection object structure is unexpected.
            ConnectionError: If communication fails.
        """
        return self.send_binary_command(cmd)

    # --- openConnection ---
    def open_connection(self) -> Any:
        """
        Opens or re-opens the connection to the module.

        Handles reopening logic based on the connection type (PY, QIS, QPS).
        For PY, it recreates the connection object. For QIS/QPS, it calls
        the underlying connect method.

        Returns:
            Any: For PY connections, returns the new PYConnection object.
                 For QIS/QPS, returns the result of the underlying connect call
                 (could be bool or other status). Returns True for successful QIS connect.

        Raises:
            AttributeError: If the connection object is missing expected methods (connect).
            ConnectionError: If reopening the connection fails.
            ValueError: If the connection type is not recognized.
        """
        logging.debug(f"Attempting to open {self.ConType[:3]} connection")
        con_type_upper = self.ConType.upper()

        try:
            if con_type_upper.startswith("QIS"):
                if hasattr(self.connectionObj, 'qis') and hasattr(self.connectionObj.qis, 'connect'):
                    self.connectionObj.qis.connect()
                    logging.info("QIS connect called.")
                    return True  # Assume success if no exception (original TODO noted lack of return check)
                else:
                    raise AttributeError("QIS connection object or connect method not found.")

            elif con_type_upper == "PY":
                # Recreate PYConnection (original logic, potentially risky)
                logging.warning("Recreating PYConnection in open_connection. Previous handles might linger.")
                if self.connectionObj and hasattr(self.connectionObj, 'connection') and hasattr(self.connectionObj.connection, 'close'):
                    try:
                        self.connectionObj.connection.close()  # Close old one first
                    except Exception as e_connection_exception:
                        logging.warning(f"Unable to close old PY Connection: {e_connection_exception}")
                        pass
                # Recreate (assumes PYConnection is imported)
                self.connectionObj = PYConnection(self.ConString)
                logging.info(f"PY Connection recreated for {self.ConString}")
                # Update internal details
                self.ConCommsType = getattr(self.connectionObj, 'ConnTypeStr', None)
                self.connectionName = getattr(self.connectionObj, 'ConnTarget', None)
                self.connectionTypeName = self.ConCommsType
                return self.connectionObj  # Return new object

            elif con_type_upper.startswith("QPS"):
                if hasattr(self.connectionObj, 'qps') and hasattr(self.connectionObj.qps, 'connect'):
                    result = self.connectionObj.qps.connect(self.ConString)
                    logging.info(f"QPS connect called for {self.ConString}. Result: {result}")
                    return result
                else:
                    raise AttributeError("QPS connection object or connect method not found.")

            else:
                raise ValueError("Connection type not recognised in open_connection")

        except Exception as e_conn:
            logging.error(f"Failed to open connection for {self.ConString} ({self.ConType}): {e_conn}", exc_info=True)
            raise ConnectionError(f"Failed to open connection for {self.ConString}") from e_conn

    def openConnection(self) -> Any:
        """
        DEPRECATED - Use open_connection instead.

        Opens or re-opens the connection to the module.

        Handles reopening logic based on the connection type (PY, QIS, QPS).
        For PY, it recreates the connection object. For QIS/QPS, it calls
        the underlying connect method.

        Returns:
            Any: For PY connections, returns the new PYConnection object.
                 For QIS/QPS, returns the result of the underlying connect call
                 (could be bool or other status). Returns True for successful QIS connect.

        Raises:
            AttributeError: If the connection object is missing expected methods (connect).
            ConnectionError: If reopening the connection fails.
            ValueError: If the connection type is not recognized.
        """
        return self.open_connection()

    # --- closeConnection ---
    def close_connection(self) -> str:
        """
        Closes the connection to the module.

        Handles closing logic based on connection type (PY, QIS, QPS).
        Clears the internal connection object reference upon successful close.

        Returns:
            str: "OK" on success, "FAIL" on failure or if no connection exists.
        """
        # This method contains the original logic from closeConnection
        logging.debug(f"Attempting to close {self.ConType[:3]} connection for {self.ConString}")
        con_type_upper = self.ConType.upper()
        closed_ok = False
        conn_obj_to_close = self.connectionObj  # Work with current object

        if conn_obj_to_close is None:
            logging.debug("No connection object exists to close.")
            return "OK"  # Nothing to do

        try:
            if con_type_upper.startswith("QIS"):
                if hasattr(conn_obj_to_close, 'qis') and hasattr(conn_obj_to_close.qis, 'closeConnection'):
                    if isQisRunning():
                        conn_obj_to_close.qis.closeConnection(conString=self.ConString)
                    closed_ok = True
                else:
                    logging.warning("QIS connection object or closeConnection method not found.")

            elif con_type_upper == "PY":
                if hasattr(conn_obj_to_close, 'connection') and hasattr(conn_obj_to_close.connection, 'close'):
                    conn_obj_to_close.connection.close()
                    closed_ok = True
                else:
                    logging.warning("PY connection object structure invalid for close.")

            elif con_type_upper.startswith("QPS"):
                if hasattr(conn_obj_to_close, 'qps') and hasattr(conn_obj_to_close.qps, 'disconnect'):
                    if isQpsRunning():
                        conn_obj_to_close.qps.disconnect(self.ConString)  # QPS uses disconnect
                    closed_ok = True
                else:
                    logging.warning("QPS connection object or disconnect method not found.")
            else:
                logging.error(f"Cannot close unknown connection type: {self.ConType}")

            if closed_ok:
                logging.info(f"Connection closed for {self.ConString}")
                self.connectionObj = None  # Clear reference only if close succeeded
                return "OK"
            else:
                logging.warning(f"Could not close connection for {self.ConString} - state uncertain.")
                return "FAIL"

        except Exception as e_close:
            logging.error(f"Error during close_connection for {self.ConString}: {e_close}", exc_info=True)
            # Do not clear self.connectionObj if close failed with exception
            return "FAIL"

    def closeConnection(self) -> str:
        """
        DEPRECATED - Use close_connection instead.

        Closes the connection to the module.

        Handles closing logic based on connection type (PY, QIS, QPS).
        Clears the internal connection object reference upon successful close.

        Returns:
            str: "OK" on success, "FAIL" on failure or if no connection exists.
        """
        return self.close_connection()

    # --- resetDevice ---
    def reset_device(self, timeout: int = 10) -> bool:
        """
        Issues a reset command and attempts recovery.

        Sends '*rst' to the device, handles connection type specifics (like
        closing PY connection), then attempts to reconnect within the timeout period.

        Args:
            timeout (int, optional): Seconds to wait for reconnection. Defaults to 10.

        Returns:
            bool: True if reset and reconnection were successful, False otherwise.

        Raises:
            ConnectionError: If sending the reset command fails initially (and connection exists).
        """
        logging.debug(f"{os.path.basename(__file__)}: sending command: *rst")
        original_con_string = self.ConString  # Store original target before potential modification
        original_con_type = self.ConType  # Store original type
        con_type_upper = self.ConType.upper()

        if not hasattr(self, 'connectionObj') or not self.connectionObj:
            logging.error("Cannot reset device, no connection object.")
            return False

        # --- Send Reset Command ---
        try:
            if con_type_upper.startswith("QIS"):
                current_con_string = original_con_string
                numb_colons = current_con_string.count(":")
                if numb_colons == 1:
                    current_con_string = current_con_string.replace(':', '::')
                self.connectionObj.qis.sendCmd(current_con_string, "*rst", expectedResponse=False)
            elif con_type_upper == "PY":
                self.connectionObj.connection.sendCommand("*rst", expectedResponse=False)
                self.connectionObj.connection.close()  # Close PY after reset
                self.connectionObj = None  # Clear potentially invalid object
            elif con_type_upper.startswith("QPS"):
                CommandString = f"{original_con_string} *rst"
                self.connectionObj.qps.sendCmdVerbose(CommandString, expectedResponse=False)
            else:
                logging.error(f"Reset not supported for connection type {self.ConType}")
                return False
            logging.debug("*rst command sent successfully.")

        except Exception as e_reset:
            logging.error(f"Error sending *rst command: {e_reset}", exc_info=True)
            # Attempt to close connection forcefully on error before recovery attempt?
            try:
                self.close_connection()
            except Exception as e_close:
                logging.warning(f"Unable to close current connection: {e_close}")
                pass
            # Return False as reset command itself failed
            return False

        # --- Recovery Attempt ---
        logging.debug(f"Attempting to reconnect to {original_con_string} after reset...")
        temp_device = None
        startTime = time.time()
        time.sleep(0.6)

        while temp_device is None:
            # Check timeout
            if (time.time() - startTime) > timeout:
                logging.critical(f"Reconnection failed to {original_con_string} within {timeout}s timeout.")
                self.connectionObj = None  # Ensure connectionObj is None if recovery failed
                return False
            try:
                # Calculate remaining timeout for the attempt
                remaining_timeout = max(1, timeout - int(time.time() - startTime))
                temp_device = get_quarch_device(original_con_string, ConType=original_con_type, timeout=str(remaining_timeout))
            except Exception as recon_e:
                logging.debug(f"Reconnect attempt failed: {recon_e}. Retrying...")
                time.sleep(0.2)

        # --- Recovery Successful ---
        logging.info(f"Successfully reconnected to {original_con_string} after reset.")
        # Replace the current connection object and potentially other details
        self.connectionObj = temp_device.connectionObj
        self.ConString = temp_device.ConString  # Update ConString (might have changed if resolved)
        self.ConType = temp_device.ConType  # Update ConType (should likely be same?)
        # Copy other relevant attributes if necessary
        self.timeout = temp_device.timeout
        if hasattr(temp_device, 'ConCommsType'):
            self.ConCommsType = temp_device.ConCommsType
        if hasattr(temp_device, 'connectionName'):
            self.connectionName = temp_device.connectionName
        if hasattr(temp_device, 'connectionTypeName'):
            self.connectionTypeName = temp_device.connectionTypeName

        time.sleep(1)
        return True

    def resetDevice(self, timeout: int = 10) -> bool:
        """
        DEPRECATED - Use reset_device instead.

        Issues a reset command and attempts recovery.

        Sends '*rst' to the device, handles connection type specifics (like
        closing PY connection), then attempts to reconnect within the timeout period.

        Args:
            timeout (int, optional): Seconds to wait for reconnection. Defaults to 10.

        Returns:
            bool: True if reset and reconnection were successful, False otherwise.

        Raises:
            ConnectionError: If sending the reset command fails initially (and connection exists).
        """
        return self.reset_device(timeout)

    # --- send_and_verify_command/sendAndVerifyCommand ---
    def send_and_verify_command(self, command_string: str, expected_response: str = "OK", exception: bool = True) -> bool:
        """
        Sends a command and verifies the response matches expected string.

        A convenience wrapper around `send_command`.

        Args:
            command_string (str): The text command to send.
            expected_response (str, optional): The exact string expected back from
                the device. Defaults to "OK". Comparison is case-sensitive.
            exception (bool, optional): If True, raises ValueError if the response
                does not match. If False, returns False on mismatch. Defaults to True.

        Returns:
            bool: True if the response matched `expected_response`, False otherwise
                  (only if `exception` is False).

        Raises:
            ValueError: If the response does not match `expected_response` and
                        `exception` is True.
            ConnectionError: If sending the command fails.
            TimeoutError: If the device times out responding.
        """
        responseStr = self.send_command(command_string)

        if responseStr != expected_response:
            error_msg = f"Command Sent: '{command_string}', Expected response: '{expected_response}', Response received: '{responseStr}'"
            logging.error(error_msg)
            if exception:
                raise ValueError(error_msg)
            else:
                return False
        else:
            logging.debug(f"Command '{command_string}' verified successfully (Response: '{expected_response}').")
            return True

    def sendAndVerifyCommand(self, commandString: str, responseExpected: str = "OK", exception: bool = True) -> bool:
        """
        DEPRECATED - Use send_and_verify_command instead.

        Sends a command and verifies the response matches expected string.

        A convenience wrapper around `send_command`.

        Args:
            commandString (str): The text command to send.
            responseExpected (str, optional): The exact string expected back from
                the device. Defaults to "OK". Comparison is case-sensitive.
            exception (bool, optional): If True, raises ValueError if the response
                does not match. If False, returns False on mismatch. Defaults to True.

        Returns:
            bool: True if the response matched `expected_response`, False otherwise
                  (only if `exception` is False).

        Raises:
            ValueError: If the response does not match `expected_response` and
                        `exception` is True.
            ConnectionError: If sending the command fails.
            TimeoutError: If the device times out responding.
        """
        return self.send_and_verify_command(commandString, responseExpected, exception)

    # --- get_runtime/getRuntime ---
    def get_runtime(self, command: str = "conf:runtimes?") -> Optional[int]:
        """
        Queries the device runtime and returns it as an integer in seconds.

        Handles potential "FAIL" responses and non-numeric/non-'s' terminated responses.

        Args:
            command (str, optional): The specific command to query runtime.
                Defaults to "conf:runtimes?". Can be overridden for different
                modules (e.g., PAM fixtures).

        Returns:
            Optional[int]: The runtime in seconds if successfully parsed, otherwise None.
        """
        runtime_str = self.send_command(command)

        if runtime_str is None:
            logging.error(f"Received None response for runtime command: {command}")
            return None

        # Use case-insensitive check for "fail"
        if "fail" in runtime_str.lower():
            logging.error(f"Runtime check failed (Command: {command}, Response: {runtime_str}), check FW/FPGA?")
            return None  # Return None on failure

        # Check if response ends with 's' and try conversion
        if isinstance(runtime_str, str) and runtime_str.endswith("s"):
            try:
                runtime_int = int(runtime_str[:-1])
                logging.debug(f"Runtime parsed as {runtime_int} seconds.")
                return runtime_int
            except ValueError:
                logging.error(f"Runtime response '{runtime_str}' not a valid int format.")
                return None
            except Exception as e_runtime:
                logging.error(f"Unexpected error parsing runtime '{runtime_str}': {e_runtime}", exc_info=True)
                return None
        else:
            # Log if format is unexpected
            logging.warning(f"Runtime response '{runtime_str}' did not end with 's' or was not string. Cannot parse as seconds.")
            return None

    def getRuntime(self, command: str = "conf:runtimes?") -> Optional[int]:
        """
        DEPRECATED - Use get_runtime instead.

        Queries the device runtime and returns it as an integer in seconds.

        Handles potential "FAIL" responses and non-numeric/non-'s' terminated responses.

        Args:
            command (str, optional): The specific command to query runtime.
                Defaults to "conf:runtimes?". Can be overridden for different
                modules (e.g., PAM fixtures).

        Returns:
            Optional[int]: The runtime in seconds if successfully parsed, otherwise None.
        """
        return self.get_runtime(command)


# --- Top-Level Function Definitions ---

def _check_ip_in_qis_list(ip_address: str, detailed_device_list: list) -> Optional[str]:
    """
    Checks if an IP address exists in a QIS/QPS device list detail output.

    Parses the list provided by the server to find an entry matching the IP
    address (specifically for TCP entries) and returns the corresponding
    full connection string (e.g., "TCP::QTL...") if found.

    Args:
        ip_address (str): The IP address to search for.
        detailed_device_list (list[str]): A list where each string is a line
            from the server's "$list details" or "$module list details" output.

    Returns:
        Optional[str]: The resolved connection string (e.g., "TCP::QTL...") if a
                       matching TCP entry is found, otherwise None.
    """
    # This function's logic remains unchanged
    if not detailed_device_list:
        return None

    for module_line in detailed_device_list:
        # Use regex to find IP pattern robustly
        ip_match = re.search(r"\bIP:(" + re.escape(ip_address) + r")\b", module_line)  # Match exact IP
        if ip_match:
            # Found the IP, check if it's a TCP entry
            if "tcp" in module_line.lower():
                # Try to extract the "TYPE::ID" part using regex or split
                conn_str_match = re.search(r"^\s*\d+\)\s+([A-Z]+::\S+)", module_line)  # Look for "N) TYPE::ID"
                if conn_str_match:
                    logging.debug(f"Resolved IP {ip_address} using regex to: {conn_str_match.group(1)}")
                    return conn_str_match.group(1)
                else:
                    # Fallback to original split method if regex fails
                    parts = module_line.split()
                    if len(parts) > 1 and "::" in parts[1]:
                        logging.debug(f"Resolved IP {ip_address} using split method to: {parts[1]}")
                        return parts[1]
                    else:
                        logging.warning(f"Found IP {ip_address} in TCP line, but couldn't extract TYPE::ID: {module_line}")
            else:
                logging.debug(f"IP {ip_address} found but not a TCP entry: {module_line}")

    # IP address not found in any relevant line
    return None


# --- checkModuleFormat / check_module_format ---
def check_module_format(ConString: str) -> bool:
    """
    Checks the basic validity of a connection string format.

    Verifies presence of ':', checks against allowed connection types,
    and validates the number of colons or sub-device format.

    Args:
        ConString (str): The connection string to validate.

    Returns:
        bool: True if the format seems valid, False otherwise.

    Note:
        Uses a specific list of allowed connection types defined within.
        May recursively call itself to validate controller part of sub-device strings.
    """
    if not ConString:
        return True  # Allow empty
    if ':' not in ConString:
        logging.warning("check_module_format: Connection string missing ':'.")
        return False

    ConnectionTypes = ["USB", "SERIAL", "TELNET", "REST", "TCP"]
    conTypeSpecified = ConString[:ConString.find(':')]

    correctConType = False
    for value in ConnectionTypes:
        if value.lower() == conTypeSpecified.lower():
            correctConType = True
            break

    if not correctConType:
        logging.warning(f"Invalid connection type specified ('{conTypeSpecified}'). Use one of {ConnectionTypes}")
        logging.warning(f"Invalid connection string: {ConString}")
        return False

    numb_colons = ConString.count(":")

    # Check sub-device format first
    if "<" in ConString and ">" in ConString:
        match = re.match(r"^[A-Z]+:[^<>:]+<\d+>$", ConString, re.IGNORECASE)
        if match:
            controller_part = ConString.split('<')[0]
            if check_module_format(controller_part):  # Recursive call
                return True
            else:
                logging.warning(f"Invalid controller part '{controller_part}' in '{ConString}'")
        else:
            logging.warning(f"Invalid sub-device syntax: '{ConString}'")
        # If sub-device checks failed, return False
        return False
    else:
        # Not a sub-device, check original strict colon count (1 or 2)
        if numb_colons > 2 or numb_colons <= 0:
            logging.warning(f"Invalid number of colons ({numb_colons}) in module string (expected 1 or 2).")
            logging.warning(f"Invalid connection string: {ConString}")
            return False

    # Passed basic checks
    return True


# Original checkModuleFormat function, kept for compatibility, now calls snake_case version
def checkModuleFormat(ConString: str) -> bool:
    """
    DEPRECATED - Use check_module_format instead.

    Checks the basic validity of a connection string format.

    Verifies presence of ':', checks against allowed connection types,
    and validates the number of colons or sub-device format.

    Args:
        ConString (str): The connection string to validate.

    Returns:
        bool: True if the format seems valid, False otherwise.

    Note:
        Uses a specific list of allowed connection types defined within.
        May recursively call itself to validate controller part of sub-device strings.
    """
    return check_module_format(ConString)


# --- getQuarchDevice / get_quarch_device ---
def get_quarch_device(connectionTarget: str, ConType: str = "PY", timeout: str = "5") -> 'Union[quarchDevice, subDevice]':
    """
    Creates and returns a quarchDevice or subDevice instance.

    Parses the connectionTarget, determines if it's a standard device or a
    sub-device (e.g., "TYPE:ID<PORT>"), and instantiates the appropriate
    quarchDevice or subDevice object via the quarchArray class if needed.h

    Args:
        connectionTarget (str): The connection string for the target device
            or sub-device.
        ConType (str, optional): The connection type hint ('PY', 'QIS', 'QPS', etc.)
            used when creating the base quarchDevice instance if not a sub-device.
            Defaults to "PY". Note: For sub-devices, the controller connection
            currently defaults to "PY" internally based on original logic.
        timeout (str, optional): The connection timeout in seconds as a string.
            Defaults to "5".

    Returns:
        quarchDevice | subDevice | Any: An instance representing the connected device.
                                        Type hinted as Any because subDevice type might vary.

    Raises:
        ImportError: If quarchArray components are needed but not found.
        ValueError: If the connectionTarget format is invalid.
        ConnectionError: If connecting to the device or controller fails.
        RuntimeError: For other unexpected errors during connection/instantiation.
    """
    # Import quarchArray
    from .quarchArray import quarchArray

    # Original check for sub-device format using __contains__
    if isinstance(connectionTarget, str) and connectionTarget.__contains__("<") and connectionTarget.__contains__(">"):
        logging.debug(f"Detected sub-device format for {connectionTarget}")
        myDevice = None  # Ensure defined in this scope
        myArrayController = None  # Ensure defined
        try:
            controller_target_str, portNumberPart = connectionTarget.split("<")
            portNumberStr = portNumberPart[:-1]  # Remove '>'

            # Validate port number
            if not portNumberStr.isdigit():
                raise ValueError(f"Invalid port number '{portNumberStr}' in sub-device string")
            portNumber = int(portNumberStr)

            # Validate controller part using the wrapper function (internal call)
            if not check_module_format(controller_target_str):
                raise ValueError(f"Invalid controller part format: '{controller_target_str}'")

            logging.debug(f"Connecting to controller '{controller_target_str}' first...")
            myDeviceBase = quarchDevice(controller_target_str, ConType="PY", timeout=timeout)

            logging.debug("Wrapping controller device with quarchArray...")
            myArrayController = quarchArray(myDeviceBase)

            logging.debug(f"Getting subDevice for port {portNumber}...")
            mySubDevice = myArrayController.getSubDevice(portNumber)

            myDevice = mySubDevice  # Return the subDevice instance
            logging.info(f"Successfully connected to sub-device: {connectionTarget}")
        except (ImportError, ValueError, ConnectionError, RuntimeError) as e_device_error:
            # Catch specific known errors and re-raise
            logging.error(f"Failed to get sub-device '{connectionTarget}': {e_device_error}", exc_info=True)
            raise  # Re-raise the caught exception
        except Exception as e_device_error:
            # Catch any other unexpected errors
            logging.error(f"Unexpected error getting sub-device '{connectionTarget}': {e_device_error}", exc_info=True)
            # Wrap in RuntimeError
            raise RuntimeError(f"Unexpected error getting sub-device '{connectionTarget}'") from e_device_error

    else:
        # Standard device connection
        logging.debug(f"Standard device connection for: {connectionTarget}")
        # Use passed ConType and timeout
        myDevice = quarchDevice(connectionTarget, ConType=ConType, timeout=timeout)
        logging.info(f"Successfully connected to standard device: {connectionTarget}")

    return myDevice


# Original getQuarchDevice function, kept for compatibility, now calls snake_case version
def getQuarchDevice(connectionTarget: str, ConType: str = "PY", timeout: str = "5") -> 'Union[quarchDevice, subDevice]':
    """
    DEPRECATED - Use get_quarch_device instead.

    Creates and returns a quarchDevice or subDevice instance.

    Parses the connectionTarget, determines if it's a standard device or a
    sub-device (e.g., "TYPE:ID<PORT>"), and instantiates the appropriate
    quarchDevice or subDevice object via the quarchArray class if needed.

    Args:
        connectionTarget (str): The connection string for the target device
            or sub-device.
        ConType (str, optional): The connection type hint ('PY', 'QIS', 'QPS', etc.)
            used when creating the base quarchDevice instance if not a sub-device.
            Defaults to "PY". Note: For sub-devices, the controller connection
            currently defaults to "PY" internally based on original logic.
        timeout (str, optional): The connection timeout in seconds as a string.
            Defaults to "5".

    Returns:
        quarchDevice | subDevice | Any: An instance representing the connected device.
                                        Type hinted as Any because subDevice type might vary.

    Raises:
        ImportError: If quarchArray components are needed but not found.
        ValueError: If the connectionTarget format is invalid.
        ConnectionError: If connecting to the device or controller fails.
        RuntimeError: For other unexpected errors during connection/instantiation.
    """
    return get_quarch_device(connectionTarget, ConType, timeout)
