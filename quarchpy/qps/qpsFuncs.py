from fileinput import close
from threading import Thread, Lock, Event, active_count
from queue import Queue, Empty
import platform
from quarchpy.qis import isQisRunning, startLocalQis
from quarchpy.connection_specific.connection_QPS import QpsInterface
from quarchpy.connection_specific.jdk_j21_jres.fix_permissions import main as fix_permissions, find_java_permissions
from quarchpy.user_interface import *
import subprocess
import logging


def isQpsRunning(host='127.0.0.1', port=9822, timeout=0):
    """
    DEPRECATED: use is_qps_running() instead

    Checks if QPS (Quarch Power Studio) is running and has a working QIS (Quarch Interface Service) connection.

    Attempts to connect to the QPS interface and then verifies communication
    by checking QIS status and sending a basic command ($list).

    Args:
        host (str, optional): The hostname or IP address where QPS is expected to be running. Defaults to '127.0.0.1'.
        port (int, optional): The port number QPS is listening on. Defaults to 9822.
        timeout (int, optional): The maximum time in seconds to wait for QPS to respond during connection and command attempts.
                                 A value of 0 might imply a system default or potentially wait indefinitely depending on implementation. Defaults to 0.

    Returns:
        bool: True if QPS is running, connected to QIS, and responding correctly, False otherwise.
    """
    return is_qps_running(host, port, timeout)


def is_qps_running(host='127.0.0.1', port=9822, timeout=0):
    """
    Checks if QPS (Quarch Power Studio) is running and has a working QIS (Quarch Interface Service) connection.

    Attempts to connect to the QPS interface and then verifies communication
    by checking QIS status and sending a basic command ($list).

    Args:
        host (str, optional): The hostname or IP address where QPS is expected to be running. Defaults to '127.0.0.1'.
        port (int, optional): The port number QPS is listening on. Defaults to 9822.
        timeout (int, optional): The maximum time in seconds to wait for QPS to respond during connection and command attempts.
                                 A value of 0 might imply a system default or potentially wait indefinitely depending on implementation. Defaults to 0.

    Returns:
        bool: True if QPS is running, connected to QIS, and responding correctly, False otherwise.
    """
    my_qps = None  # Initialize QPS interface variable
    logging.debug("Checking if QPS is running")
    start_time = time.time()  # Record start time for timeout check

    # Attempt to establish a connection to the QPS interface
    while True:
        try:
            # Create an instance of the QPS communication interface
            my_qps = QpsInterface(host, port)
            # If connection successful, break the loop
            break
        except Exception as e:
            # Log any error during connection attempt
            logging.debug("Error when making QPS interface. QPS may not be running.")
            logging.debug(e)
            # Check if the timeout has been exceeded
            if timeout > 0 and (time.time() - start_time) > timeout:
                logging.debug("Timeout exceeded while trying to connect to QPS.")
                break
            # Small delay before retrying connection (optional, but can prevent tight loops)
            time.sleep(0.1)

    # If connection failed (my_qps is still None)
    if my_qps is None:
        logging.debug("QPS is not running or connection failed within timeout.")
        return False

    logging.debug("Checking if QPS reports a QIS connection")
    # Note: "$qis status" might report "connected" even if the connection was transient.
    retry_counter = 0
    max_retries = 5  # Number of times to check QIS status

    # Loop to check QIS status, allowing some time for connection establishment
    while retry_counter < max_retries:
        try:
            answer = my_qps.sendCmdVerbose(cmd="$qis status")
            if answer and answer.lower() == "connected":
                logging.debug("QPS Running With QIS Connected")
                break  # Exit loop if QIS is connected
            else:
                logging.debug(f"QIS status: '{answer}'. Waiting and retrying.")
                time.sleep(0.5)  # Wait before retrying
                retry_counter += 1
        except Exception as e:
            logging.error(f"Error sending $qis status command: {e}")
            logging.debug(f"QPS Running but QIS NOT found connected after {retry_counter} attempts.")
            # Clean up the QPS connection object if it was created
            if my_qps:
                del my_qps
            return False

    logging.debug("Checking if QPS/QIS comms are running using $list command")
    start_time = time.time()  # Reset start time for this check
    list_response = ""
    # Attempt to send the "$list" command to verify active communication
    while True:
        try:
            list_response = my_qps.sendCmdVerbose(cmd="$list")
            # If command successful, break the loop
            break
        except Exception as e:
            # Log error if command fails
            logging.debug(f"Error sending $list command: {e}")
            pass  # Continue looping until timeout
        # Check if timeout exceeded for this specific command
        if timeout > 0 and (time.time() - start_time) > timeout:
            logging.debug("Timeout exceeded while waiting for $list response.")
            break

    # Clean up the QPS connection object
    if my_qps:
        del my_qps

    # Check the response from "$list"
    # Expecting "1" for the first module, or specific "no device/module" messages if empty.
    if list_response and (list_response.startswith("1")
                          or "no device" in str(list_response).lower()
                          or "no module" in str(list_response).lower()):
        logging.debug("QPS and QIS are running and responding with valid $list info")
        return True
    else:
        # Log unexpected output from $list
        logging.debug("QPS did not return expected output from $list")
        logging.debug(f"$list response: '{list_response}'")
        return False


def startLocalQps(keepQisRunning=False, args=[], timeout=30, startQPSMinimised=True):
    """
    DEPRECATED: use start_local_qps() instead

    Starts a local instance of QPS.

    Optionally ensures QIS is running first. Constructs the command to launch
    QPS based on the operating system and architecture, handling Java paths,
    permissions, and command-line arguments. It monitors the launch process
    and waits for QPS and QIS to become responsive within a specified timeout.

    Args:
        keepQisRunning (bool, optional): If True, checks if QIS is running and starts it if not. Defaults to False.
        args (list, optional): A list of additional command-line arguments to pass to QPS upon launch. Defaults to [].
        timeout (int, optional): Maximum time in seconds to wait for QPS and QIS to start and respond. Defaults to 30.
        startQPSMinimised (bool, optional): If True, attempts to add the '-ccs=MIN' argument to start QPS minimised. Defaults to True.

    Raises:
        TimeoutError: If QPS or QIS fails to start and respond within the specified timeout.
        NotImplementedError: If run on an officially unsupported OS/architecture combination.
        # Note: Also implicitly raises exceptions from subprocess if the command fails catastrophically.

    Returns:
        None: The function executes the QPS launch process.
    """
    return start_local_qps(keepQisRunning, args, timeout, startQPSMinimised)


def start_local_qps(keep_qis_running=False, args=[], timeout=30, start_qps_minimised=True):
    """
    Starts a local instance of QPS.

    Optionally ensures QIS is running first. Constructs the command to launch
    QPS based on the operating system and architecture, handling Java paths,
    permissions, and command-line arguments. It monitors the launch process
    and waits for QPS and QIS to become responsive within a specified timeout.

    Args:
        keep_qis_running (bool, optional): If True, checks if QIS is running and starts it if not. Defaults to False.
        args (list, optional): A list of additional command-line arguments to pass to QPS upon launch. Defaults to [].
        timeout (int, optional): Maximum time in seconds to wait for QPS and QIS to start and respond. Defaults to 30.
        start_qps_minimised (bool, optional): If True, attempts to add the '-ccs=MIN' argument to start QPS minimised. Defaults to True.

    Raises:
        TimeoutError: If QPS or QIS fails to start and respond within the specified timeout.
        NotImplementedError: If run on an officially unsupported OS/architecture combination.
        # Note: Also implicitly raises exceptions from subprocess if the command fails catastrophically.

    Returns:
        None: The function executes the QPS launch process.
    """
    # Step 1: Handle QIS dependency
    if keep_qis_running:
        if not isQisRunning():  # Check if QIS is already running
            logging.info("QIS not running. Starting local QIS.")
            startLocalQis()  # Start QIS if not running

    # Step 2: Prepare arguments
    # Join the list of arguments into a single space-separated string
    args_str = " ".join(args)
    # Add argument to start minimised if requested and not already present
    # TODO: Verify QPS version compatibility for -ccs=MIN (original comment mentioned QPS 1.38)
    if start_qps_minimised:
        if "-ccs" not in args_str.lower():
            args_str += " -ccs=MIN"

    # Step 3: Store current directory and determine paths
    # Record current working directory to restore it later
    current_dir = os.getcwd()

    # Determine the base path for Java JREs bundled with quarchpy
    # Assumes a specific directory structure relative to this file (qpsFuncs.py)
    # __file__ -> qpsFuncs.py path -> quarchpy dir -> connection_specific -> jdk_j21_jres
    base_path = os.path.dirname(os.path.abspath(__file__))  # Directory of this file
    base_path, junk = os.path.split(base_path)  # Go up one level (to quarchpy)
    java_base_path = os.path.join(base_path, "connection_specific", "jdk_j21_jres")
    # Enclose java path in quotes for command line robustness
    java_base_path_quoted = f'"{java_base_path}'  # Opening quote, closing quote added per OS later

    # Determine the path to the qps.jar file
    qps_base_path = base_path  # Starting from the same base path

    # Step 4: Check OS and Architecture
    current_os = platform.system()  # e.g., "Windows", "Linux", "Darwin" (macOS)
    current_arch = platform.machine().lower()  # e.g., "x86_64", "amd64", "aarch64", "arm64"

    # Check for officially unsupported combinations and warn/exit
    if (current_os == "Linux" and current_arch == "aarch64") or (current_os == "Darwin" and current_arch == "arm64"):
        logging.warning(f"The system [{current_os}, {current_arch}] is not officially supported.")
        logging.warning("Please contact Quarch support for running QuarchPy on this system.")
        # Consider raising an error instead of just returning
        # raise NotImplementedError(f"Unsupported platform: {current_os} {current_arch}")
        return  # Exit the function if unsupported

    # Step 5: Check and fix Java permissions (especially needed on Linux/macOS)
    try:
        permissions_ok, message = find_java_permissions()
        if not permissions_ok:
            logging.warning(message)
            logging.warning("Not having correct permissions may prevent Quarch Java 21 Programs from launching.")
            # Check if running interactively before prompting
            if sys.stdout.isatty():  # Basic check for interactive terminal
                logging.warning("Run \"python -m quarchpy.run permission_fix\" to fix this.")
                user_input = input("Would you like to attempt to auto-run the fix now? (Y/N): ")
                if user_input.lower() == "y":
                    try:
                        fix_permissions()  # Attempt to fix permissions
                        permissions_ok, message = find_java_permissions()  # Re-check
                        time.sleep(0.5)  # Short pause
                        if not permissions_ok:
                            logging.warning("Attempt to fix permissions was unsuccessful. Please fix manually or run the command above.")
                        else:
                            logging.info("Attempt to fix permissions was successful. Continuing.")
                    except Exception as fix_err:
                        logging.error(f"Error occurred during permission fix attempt: {fix_err}")
                else:
                    logging.warning("Skipping automatic permission fix. QPS launch might fail.")
            else:
                logging.warning("Running in non-interactive mode. Please run 'python -m quarchpy.run permission_fix' manually if QPS fails to start.")

    except Exception as perm_check_err:
        logging.error(f"Could not check or fix Java permissions: {perm_check_err}")

    # Step 6: Determine the specific qps.jar path
    # Flag to indicate if a single QPS build is used across OSes or if specific builds exist
    is_single_qps_build = True  # Set based on actual packaging

    if is_single_qps_build:
        # Assumes a single qps.jar located in a path like 'connection_specific/QPS/win-amd64/'
        # Adjust the sub-path 'win-amd64' if the single build is located elsewhere
        qps_jar_path = os.path.join(qps_base_path, "connection_specific", "QPS", "win-amd64", "qps.jar")
    else:
        # Determine QPS path based on OS and architecture
        qps_sub_dir = ""
        if current_os == "Windows":  # Typically uses amd64
            qps_sub_dir = "win-amd64"
        elif current_os == "Linux":
            if current_arch == "x86_64":
                qps_sub_dir = "lin-amd64"
            elif current_arch == "aarch64":  # Note: Previously warned as unsupported
                qps_sub_dir = "lin-arm64"
        elif current_os == "Darwin":
            if current_arch == "x86_64":
                qps_sub_dir = "mac-amd64"
            elif current_arch == "arm64":  # Note: Previously warned as unsupported
                qps_sub_dir = "mac-arm64"

        # If a valid sub-directory was determined, construct the path
        if qps_sub_dir:
            qps_jar_path = os.path.join(qps_base_path, "connection_specific", "QPS", qps_sub_dir, "qps.jar")
        else:
            # Fallback or error if OS/Arch combination is unexpected but wasn't caught earlier
            logging.error(f"Cannot determine QPS path for unexpected platform: {current_os} {current_arch}. Defaulting to Windows path.")
            qps_jar_path = os.path.join(qps_base_path, "connection_specific", "QPS", "win-amd64", "qps.jar")

    # Check if the determined qps.jar file actually exists
    if not os.path.exists(qps_jar_path):
        logging.error(f"QPS JAR file not found at expected path: {qps_jar_path}")
        # Restore original directory before raising error
        os.chdir(current_dir)
        raise FileNotFoundError(f"qps.jar not found at {qps_jar_path}")

    # Step 7: Change directory and construct the launch command
    # QPS might expect to be run from its own directory
    qps_jar_dir = os.path.dirname(qps_jar_path)
    logging.debug(f"Changing working directory to: {qps_jar_dir}")
    os.chdir(qps_jar_dir)

    # Construct the OS-specific command string
    java_exe_path = ""
    path_sep = ""
    jre_sub_dir = ""

    if current_os == "Windows":
        path_sep = "\\"
        jre_sub_dir = "win_amd64_jdk_21_jre"
    elif current_os == "Linux":
        path_sep = "/"
        if current_arch == "x86_64":
            jre_sub_dir = "lin_amd64_jdk_21_jre"
        elif current_arch == "aarch64":  # Potentially unsupported
            jre_sub_dir = "lin_arm64_jdk_21_jre"
    elif current_os == "Darwin":
        path_sep = "/"
        if current_arch == "x86_64":
            jre_sub_dir = "mac_amd64_jdk_21_jre"
        elif current_arch == "arm64":  # Potentially unsupported
            jre_sub_dir = "mac_arm64_jdk_21_jre"

    # Build the full path to the java executable if a JRE sub-directory was found
    if jre_sub_dir:
        java_exe_path = f'{java_base_path_quoted}{path_sep}{jre_sub_dir}{path_sep}bin{path_sep}java"'  # Add closing quote
    else:
        # Fallback or error - cannot determine Java path
        logging.error(f"Cannot determine Java JRE path for platform: {current_os} {current_arch}")
        # Restore directory and raise error
        os.chdir(current_dir)
        raise RuntimeError(f"Unsupported platform for bundled JRE: {current_os} {current_arch}")

    # Final command combines Java executable, -jar option, qps.jar (relative path now), and arguments
    command = f'{java_exe_path} -jar qps.jar {args_str}'
    logging.info(f"Executing QPS launch command: {command}")

    # Step 8: Execute the command and monitor
    process = None
    start_launch_time = time.time()

    # Determine how to launch based on logging requirements and OS
    if "-logging=ON" in args_str:
        # If logging to terminal is enabled, run in a way that keeps the terminal visible
        logging.info("'-logging=ON' detected. Launching QPS in a visible window.")
        if current_os == "Windows":
            # Popen with shell=True can work, but might hide the window depending on context.
            # Using 'start' might be better if a separate window is always desired.
            # For simplicity, using Popen as in the original code.
            process = subprocess.Popen(command, shell=True)
        else:  # Linux/macOS
            # Run the command and keep the terminal open after QPS exits (useful for debugging)
            command_with_pause = command + "; exec bash"  # Keeps shell open
            # Using run might wait, consider Popen if backgrounding is needed immediately.
            # Original used run, keeping that behavior.
            subprocess.run(command_with_pause, shell=True, check=False)  # Don't check return code here
            # Note: With run, we can't easily monitor the QPS process directly afterwards in this script.
            # The logic below assumes Popen was used and 'process' is populated.
            # If run is used, the is_qps_running check might need adjustment or might fail if QPS exits immediately.
            # For consistency, let's stick to Popen for non-logging case monitoring.
            # If -logging=ON is used, we assume the user monitors the separate window.
            # We won't perform the usual timeout checks in this case.
            logging.warning("Launched with -logging=ON. Skipping timeout checks. Monitor the QPS window.")
            process = None  # Set process to None as we aren't monitoring it here

    else:
        # Launch QPS in the background, capturing stdout/stderr
        logging.info("Launching QPS with stdout/stderr capture.")
        try:
            # Use text=True for Python 3 for automatic decoding of stdout/stderr
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, shell=True, bufsize=1, universal_newlines=True)
        except FileNotFoundError:
            logging.error(f"Error: Command not found. Ensure Java path is correct and permissions are set: {java_exe_path}")
            os.chdir(current_dir)  # Restore directory
            raise
        except Exception as popen_err:
            logging.error(f"Failed to start QPS process: {popen_err}")
            os.chdir(current_dir)  # Restore directory
            raise

    # Step 9: Wait for QPS/QIS to become ready (only if not using -logging=ON)
    if process:  # Only monitor if we launched with Popen and captured streams
        qps_ready = False
        qis_ready = False
        while True:
            current_time = time.time()
            # Check if timeout exceeded
            if current_time - start_launch_time > timeout:
                # Attempt to terminate the process if it's still running
                if process.poll() is None:  # Check if process hasn't terminated
                    logging.warning("Timeout reached. Terminating QPS process.")
                    process.terminate()
                    try:
                        process.wait(timeout=5)  # Wait a bit for termination
                    except subprocess.TimeoutExpired:
                        logging.warning("Process did not terminate gracefully. Killing.")
                        process.kill()
                # Read any remaining output after termination attempt
                _get_std_msg_and_err_from_QPS_process(process)
                # Restore directory before raising error
                os.chdir(current_dir)
                if not qps_ready:
                    raise TimeoutError(f"QPS failed to launch and respond via is_qps_running within timeout of {timeout} sec.")
                else:  # QPS was ready, but QIS wasn't
                    raise TimeoutError(f"QPS launched but QIS did not respond via isQisRunning within timeout of {timeout} sec.")

            # Check for QPS readiness if not already confirmed
            if not qps_ready:
                # Read any initial output from QPS process (non-blocking)
                _get_std_msg_and_err_from_QPS_process(process)
                # Check if QPS is connectable and responsive
                if is_qps_running(timeout=1):  # Use a short timeout for the check
                    logging.debug(f"QPS detected as running after {current_time - start_launch_time:.2f}s")
                    qps_ready = True
                else:
                    # If QPS check fails, see if the process terminated unexpectedly
                    if process.poll() is not None:
                        logging.error("QPS process terminated unexpectedly.")
                        _get_std_msg_and_err_from_QPS_process(process)  # Read final output
                        os.chdir(current_dir)
                        raise RuntimeError("QPS process terminated unexpectedly during startup.")

            # Check for QIS readiness if QPS is ready but QIS is not
            if qps_ready and not qis_ready:
                if isQisRunning():  # Check if QIS is running
                    logging.debug(f"QIS detected as running after {current_time - start_launch_time:.2f}s")
                    qis_ready = True
                else:
                    # Read any more output while waiting for QIS
                    _get_std_msg_and_err_from_QPS_process(process)

            # If both are ready, break the loop
            if qps_ready and qis_ready:
                logging.info("QPS and QIS successfully started and detected.")
                break

            # Wait a short interval before the next check
            time.sleep(0.2)

    # Step 10: Restore original working directory
    logging.debug(f"Restoring working directory to: {current_dir}")
    os.chdir(current_dir)

    # Function completes successfully if it reaches here
    return


def reader(stream, q, source, lock, stop_flag):
    '''
    Used to read output and place it in a queue for multithreaded reading
    :param stream:
    :param q:
    :param source:
    :param lock: The lock for the queue
    :param stop_flag: Flag to exit the loop and close the thread
    :return: None
    '''
    while not stop_flag.is_set():
        line = stream.readline()
        if not line:
            break
        with lock:
            q.put((source, line.strip()))


def _get_std_msg_and_err_from_QPS_process(process):
    '''
    Uses multithreading to check for stderr and stdmsg passed by the process that launches QPS
    This allows the user to understand why QPS might not have appeared.
    :param process: The Process Used to launch QPS
    :return: None
    '''
    # Read back stdmsg and stderr in seperate threads so they are non blocking
    q = Queue()
    lock = Lock()
    stop_flag = Event()

    t1 = Thread(target=reader, args=[process.stdout, q, 'stdout', lock, stop_flag])
    t2 = Thread(target=reader, args=[process.stderr, q, 'stderr', lock, stop_flag])
    t1.start()
    t2.start()
    counter = 0
    # check for stderr or stdmsg from the queue
    while counter <= 3:  # If 3 empty reads from the queue then move on to see if QPS is running.
        try:
            source, line = q.get(timeout=1)  # Wait for 1 second for new lines
            counter = 0
            if source == "stderr":
                logging.error(f"{source}: {line}")
            else:
                printText(f"{source}: {line}")
        except Empty:
            counter += 1
    stop_flag.set()  #Close the threads and return to the main loop where QPS is check to see if its started yet


def closeQps(host='127.0.0.1', port=9822):
    """
    DEPRECATED: use close_qps() instead

    Connects to a QPS instance and sends the shutdown command (camelCase wrapper).

    Instantiates a QpsInterface object for the specified host and port,
    sends the '$shutdown' command, deletes the interface object, and waits
    briefly to allow the shutdown process to initiate before returning.

    Args:
        host (str, optional):
            The IP address or hostname of the QPS instance.
            Defaults to '127.0.0.1'.
        port (int, optional):
            The port number of the QPS instance.
            Defaults to 9822.

    Returns:
        None
    """
    return close_qps(host, port)

def close_qps(host='127.0.0.1', port=9822):
    """
    Connects to a QPS instance and sends the shutdown command (snake_case API).

    Instantiates a QpsInterface object for the specified host and port,
    sends the '$shutdown' command, deletes the interface object, and waits
    briefly to allow the shutdown process to initiate before returning.

    Args:
        host (str, optional):
            The IP address or hostname of the QPS instance.
            Defaults to '127.0.0.1'.
        port (int, optional):
            The port number of the QPS instance.
            Defaults to 9822.

    Returns:
        None

    Raises:
        ImportError: If QpsInterface cannot be imported.
        Exception: If connecting to QPS or sending the command fails.
    """
    myQps = None  # Initialize
    try:
        logging.info(f"Connecting to QPS at {host}:{port} to send shutdown...")
        myQps = QpsInterface(host, port)
        logging.info("Sending $shutdown command to QPS.")
        response = myQps.sendCmdVerbose("$shutdown")
        logging.debug(f"QPS shutdown response: {response}")
    except Exception as e:
        logging.error(f"Error during close_qps execution: {e}", exc_info=True)
        # Re-raise the error to indicate failure
        raise
    finally:
        # Ensure object reference is removed
        # Note: del doesn't guarantee immediate cleanup in Python, but matches original
        if myQps is not None:
            del myQps
            logging.debug("QpsInterface object reference deleted.")

    # Original comment noted sleep is needed for subsequent checks
    logging.debug("Waiting 1 second after sending QPS shutdown...")
    time.sleep(1)
    logging.info("close_qps finished.")


def GetQpsModuleSelection(QpsConnection, favouriteOnly=True, additionalOptions=['rescan', 'all con types', 'ip scan'], scan=True):
    """
    Presents a UI to the user to select a QPS-connected module (snake_case API).

    Handles scanning for devices via the provided QpsConnection object,
    optionally filters/sorts the list, presents options to the user (including
    rescanning or specifying an IP), and returns the connection string of the
    selected device or an action string ('quit', 'rescan', etc.).

    Args:
        QpsConnection (QpsInterface): # Assuming type based on context
            An active connection object to the QPS instance.
        favouriteOnly (bool, optional):
            If True, attempts to sort/filter the device list to show preferred
            connection types first (USB > TCP > SERIAL > etc.) and only one
            entry per unique device ID. Defaults to True.
        additionalOptions (list[str], optional):
            A list of action strings to present as options in the selection UI
            in addition to the device list.
            Defaults to ['rescan', 'all con types', 'ip scan'].
        scan (bool, optional):
            Whether to perform a scan via the QpsConnection object initially.
            Defaults to True.

    Returns:
        str: The connection string (e.g., "TCP::QTLXXXX") of the selected device,
             or a string indicating a chosen action (e.g., 'rescan', 'quit', 'ip scan', 'all con types').
             Returns "quit" on failure or cancellation.

    Raises:
        AttributeError: If QpsConnection object is missing 'getDeviceList'.
        Exception: Can be raised by UI functions or if list processing fails.

    Notes:
        - Relies on UI functions listSelection, requestDialog, printText,
          and potentially User_interface class being available and functional.
        - Assumes specific return formats from QpsConnection.getDeviceList.
    """
    return get_qps_module_selection(QpsConnection, favouriteOnly, additionalOptions, scan)


def get_qps_module_selection(qps_connection: QpsInterface, favourite_only=True, additional_options=['rescan', 'all con types', 'ip scan'], scan=True):
    """
    Presents a UI to the user to select a QPS-connected module (snake_case API).

    Handles scanning for devices via the provided QpsConnection object,
    optionally filters/sorts the list, presents options to the user (including
    rescanning or specifying an IP), and returns the connection string of the
    selected device or an action string ('quit', 'rescan', etc.).

    Args:
        qps_connection (QpsInterface): # Assuming type based on context
            An active connection object to the QPS instance.
        favourite_only (bool, optional):
            If True, attempts to sort/filter the device list to show preferred
            connection types first (USB > TCP > SERIAL > etc.) and only one
            entry per unique device ID. Defaults to True.
        additional_options (list[str], optional):
            A list of action strings to present as options in the selection UI
            in addition to the device list.
            Defaults to ['rescan', 'all con types', 'ip scan'].
        scan (bool, optional):
            Whether to perform a scan via the QpsConnection object initially.
            Defaults to True.

    Returns:
        str: The connection string (e.g., "TCP::QTLXXXX") of the selected device,
             or a string indicating a chosen action (e.g., 'rescan', 'quit', 'ip scan', 'all con types').
             Returns "quit" on failure or cancellation.

    Raises:
        AttributeError: If QpsConnection object is missing 'getDeviceList'.
        Exception: Can be raised by UI functions or if list processing fails.

    Notes:
        - Relies on UI functions listSelection, requestDialog, printText,
          and potentially User_interface class being available and functional.
        - Assumes specific return formats from QpsConnection.getDeviceList.
    """
    # This function now contains the actual implementation
    favourite = favourite_only
    ip_address = None
    devList = []  # Initialize

    while True:  # Loop handles rescans/IP input
        printText("QPS scanning for devices...")  # Use imported printText
        tableHeaders = ["Module"]  # For 'nice' UI mode

        # --- Scan Step ---
        try:
            if ip_address is None:
                devList = qps_connection.getDeviceList(scan=scan)
            else:
                devList = qps_connection.getDeviceList(scan=scan, ipAddress=ip_address)
        except Exception as e:
            logging.error(f"Error getting device list from QPS: {e}")
            devList = ["FAIL: Error scanning"]  # Indicate failure in list

        # --- Handle No Devices Found ---
        # Check more robustly for empty or failure indication
        if not devList or (isinstance(devList, list) and len(devList) > 0 and ("no device" in devList[0].lower() or "no module" in devList[0].lower() or "FAIL:" in devList[0])):
            printText("No devices found by QPS.")
            # Force user to choose an action if no devices found
            action = None
            try:
                # Internal call uses original name listSelection
                action = listSelection(title="No Devices Found", message="Scan did not find any devices.",
                                       selectionList="",
                                       additionalOptions="Specify IP Address=ip scan,Rescan All=rescan,Quit=quit")
            except Exception as e_ui:
                logging.error(f"UI Error (listSelection): {e_ui}")
                return "quit"

            if action is None or action.lower() == 'quit':
                return "quit"
            elif action.lower() == 'rescan':
                ip_address = None
                favourite = True
                continue
            elif action.lower() == 'ip scan':
                # Request IP address
                ip_address = requestDialog("Please input IP Address of the module you would like to connect to: ")
                if not ip_address:
                    return "quit"  # User cancelled
                favourite = False
                continue
            else:
                return "quit"  # Unknown action

        # --- Filter/Sort Devices ---
        # Removes rest devices
        devList = [x for x in devList if isinstance(x, str) and "rest" not in x.lower()]

        # Apply favourite sorting/filtering
        if favourite:
            index = 0
            sortedDevList = []
            conPref = ["USB", "TCP", "SERIAL", "TELNET"]  # Original preferred order (excluding REST)
            # Create a copy to avoid modifying list while iterating indirectly
            tempDevList = list(devList)
            processed_indices = set()

            # Sort by preferred connection type prefix
            for pref in conPref:
                for i, device in enumerate(tempDevList):
                    if i not in processed_indices and device.upper().startswith(pref + ":"):
                        sortedDevList.append(device)
                        processed_indices.add(i)
            # Add remaining devices not matching prefixes
            for i, device in enumerate(tempDevList):
                if i not in processed_indices:
                    sortedDevList.append(device)

            # Filter to one entry per unique device identifier (part after TYPE::)
            favConDevList = []
            seen_ids = set()
            for device_string in sortedDevList:
                try:
                    # Robustly extract ID, handle cases without '::'
                    device_id_part = device_string.split("::", 1)[1] if "::" in device_string else \
                        device_string.split(":", 1)[1] if ":" in device_string else device_string
                except IndexError:
                    device_id_part = device_string  # Fallback

                if device_id_part not in seen_ids:
                    favConDevList.append(device_string)
                    seen_ids.add(device_id_part)
            devList = favConDevList  # Use the filtered favourite list

        # --- Prepare for UI ---
        message = "Select a quarch module"
        devList_for_ui = devList  # Default for listSelection if not TestCenter

        # Handle specific UI environment if needed (TestCenter example)
        # Check if User_interface class/instance exists before accessing attributes
        tc_mode = False
        if User_interface and hasattr(User_interface, 'instance') and User_interface.instance is not None:
            if getattr(User_interface.instance, 'selectedInterface', None) == "testcenter":
                tc_mode = True
                # Format for TestCenter's expected listSelection format
                tempString = ""
                for module in devList:
                    tempString += f"{module}={module},"  # VALUE=DISPLAY format
                devList_for_ui = tempString.rstrip(',')  # Remove trailing comma

        # --- Present Selection UI ---
        myDeviceID = None
        # Request user to select device
        myDeviceID = listSelection(title=message, message=message, selectionList=devList_for_ui,
                                   additionalOptions=additional_options, nice=True, tableHeaders=tableHeaders,
                                   indexReq=True)

        # --- Process Selection ---
        if myDeviceID is None:  # Handle UI cancellation
            return "quit"

        # Check if the response is one of the additionalOptions (actions)
        # Set it to new variable so it's a little clearer
        action_chosen = myDeviceID.lower()

        # Handle Actions
        if action_chosen == 'rescan':
            ip_address = None
            favourite = True
            continue
        elif action_chosen == 'all con types':
            printText('Displaying all connection types...')
            ip_address = None
            favourite = False
            continue
        elif action_chosen == 'ip scan':
            new_ip = requestDialog("Please input IP Address of the module you would like to connect to: ")
            if not new_ip:
                return "quit"  # User cancelled
            ip_address = new_ip
            favourite = False
            scan = True
            continue
        elif action_chosen == 'quit':
            return "quit"
        else:
            # Assume device was selected
            return myDeviceID
