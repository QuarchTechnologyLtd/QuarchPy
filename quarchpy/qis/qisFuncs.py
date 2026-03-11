"""

Contains general functions for starting and stopping QIS processes

"""

import os, sys
import socket
import time, platform
from subprocess import CompletedProcess, Popen
from threading import Thread, Lock, Event
from queue import Queue, Empty
from typing import Optional, List, Tuple, Union

import quarchpy_binaries

from quarchpy.connection_specific.connection_QIS import QisInterface
from quarchpy.connection_specific.jdk_jres.fix_permissions import main as fix_permissions, find_java_permissions
from quarchpy.install_qps import find_qps
from quarchpy.user_interface import requestDialog
from quarchpy.user_interface.user_interface import printText
import subprocess
import logging
logger = logging.getLogger(__name__)


def isQisRunning(port: int = 9722):
    """
    Checks if an instance of QIS is running and responding.

    Args:
        port (int): The TCP port number used to attempt a connection
            with the QIS interface. QIS defaults to 9722.

    Returns:
        bool: True if a connection to the QIS interface was successfully
            established; False otherwise.
    """

    qisRunning = False
    myQis = None
    # Attempt to connect to QIS
    try:
        myQis = QisInterface(connectionMessage=False, port=port)
        if (myQis is not None):
            #if we can connect to qis, it's running
            qisRunning = True
    except:
        #if there's no connection to qis, an exception will be caught
        pass
    if (qisRunning is False):
        logger.debug("QIS is not running")
        return False
    else:
        logger.debug("QIS is running")
        return True


def isQisRunningAndResponding(timeout=2, port: int = 9722):
    """
    Checks if QIS is running and responding to a version command.

    This function first verifies if the QIS service is reachable on the
    specified port, then attempts to validate the connection by sending
    a `$version` command and checking for a valid response string.

    Args:
        timeout (int, optional): The total time in seconds to wait for a
            valid response from the service. Defaults to 2.
        port (int, optional): The TCP port number to connect to.
            Defaults to 9722.

    Returns:
        bool: True if QIS is running and returns a version string containing
            'v' within the timeout period; False otherwise.
        """
    qisRunning = isQisRunning(port=port)
    if not qisRunning:
        logger.debug("QIS is not running")
        return False

    logger.debug("Qis is running")
    myQis = QisInterface(connectionMessage=False, port=port)
    counter = 0
    maxCounter = 20
    while counter <= maxCounter:
        versionResponse: str = myQis.sendAndReceiveCmd(cmd="$version")
        if "v" in versionResponse.lower():
            qisResponding = True
            break
        else:
            logger.debug("Qis returned from $version: " + str(versionResponse) + "  Expected to contain ': v'")
            time.sleep(timeout / maxCounter)  # We attempt to get QIS
            counter += 1

    if not qisRunning:
        logger.debug("QIS is not running")
        return False
    else:
        logger.debug("QIS is running")
        return True


def startLocalQis(
        terminal: bool = False,
        headless: bool = False,
        args: Optional[List[str]] = None,
        timeout: int = 20,
        host: str = '127.0.0.1',
        **kwargs
) -> Optional['QisInterface']:
    """
    Executes QIS on the local system and returns a connected interface.

    Args:
        terminal (bool): True if QIS terminal should be shown on startup (-terminal).
        headless (bool): True if app should be run in headless mode.
        args (List[str], optional): List of additional raw parameters.
        timeout (int): Time in seconds to wait for launch.
        host (str): Host address (default localhost).
        **kwargs: Configuration for ports and QIS behavior.

            * **port** (int): The Telnet port to use. Defaults to 9722.
            * **rest_port** (int): The REST port to use. Defaults to 9780.
            * **loglevel** (str): Sets logging level [OFF, FATAL, ERROR, WARN, INFO, DEBUG, TRACE, ALL].
            * **logconsole** (str): If 'ON', logs to the console as well as to file.
            * **devdebug** (str): If 'ON', enables development debug output.
            * **devdebug2** (bool): If 'ON', enables extra costly debug output.

    Returns:
        Optional[QisInterface]: A connected interface object, or None if launch fails.
    """
    # 1. Extract values from kwargs with appropriate defaults
    port = kwargs.get('port', 9722)
    rest_port = kwargs.get('rest_port', 9780)

    # 2. Prepare Arguments
    launch_args = args.copy() if args else []

    # Map kwargs to their CLI flag equivalents
    kwarg_map = {
        'loglevel': '-loglevel=',
        'logconsole': '-logconsole',
        'devdebug': '-devdebug',
        'devdebug2': '-devdebug2',
        'port': '-port=',
        'rest_port': '-restport='
    }

    for key, flag in kwarg_map.items():
        if key in kwargs:
            val = kwargs[key]
            # Handle boolean flags (no value needed) vs value flags (suffix needed)
            if isinstance(val, bool):
                arg_str = flag if val else None
            else:
                arg_str = f"{flag}{val}"

            # Add to launch_args if flag generated and not already manually present
            if arg_str and not any(flag in a for a in launch_args):
                launch_args.append(arg_str)

    # 3. Check if already running on the specific target port
    if _check_port_open(host, port):
        logger.debug(f"QIS instance on port {port} is already running. Connecting...")
        return QisInterface(host=host, port=port)

    # 4. Check for installation
    if not find_qps():
        logger.error("Unable to find or install QPS... Aborting...")
        return None

    # 5. Prepare Command and Environment
    command, qis_dir = _prepare_qis_launch_env(terminal, headless, launch_args)
    if not command:
        return None

    # 6. Launch QIS Process
    current_dir = os.getcwd()
    try:
        os.chdir(qis_dir)
        process = _launch_qis_process(command, launch_args)
    finally:
        os.chdir(current_dir)

    # 7. Wait for QIS to be ready
    if not _wait_for_qis_service(host, port, timeout, process, launch_args):
        return None

    # 8. Return Connected Interface
    try:
        return QisInterface(host=host, port=port)
    except Exception as e:
        logger.error(f"QIS started, but failed to create interface object: {e}")
        return None


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


def _get_std_msg_and_err_from_QIS_process(process):
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
                logger.error(f"{source}: {line}")
            else:
                printText(f"{source}: {line}")
        except Empty:
            counter += 1
    stop_flag.set()  #Close the threads and return to the main loop where QPS is check to see if its started yet


def check_remote_qis(host='127.0.0.1', port=9722, timeout=0):
    """
        Checks if a local or specified instance of QIS is running and responding
        This continues to scan until qis is found or a timeout is hit.

        Returns
        -------
        is_running : bool
            True if QIS is running and responding

        """

    qisRunning = False
    myQis = None

    start = time.time()
    while True:
        # attempt to connect to Qis
        try:
            myQis = QisInterface(host=host, port=port, connectionMessage=False)
            if (myQis is not None):
                # if we can connect to qis, it's running
                qisRunning = True
                break
        except:
            # if there's no connection to qis, an exception will be caught
            pass
        if (time.time() - start) > timeout:
            break

    if (qisRunning is False):
        logger.debug("QIS is not running")
        return False
    else:
        logger.debug("QIS is running")
        return True


def checkAndCloseQis(host='127.0.0.1', port=9722):
    if isQisRunning() is True:
        closeQis()


def closeQis(host='127.0.0.1', port=9722):
    """
    Helper function to close an instance of QIS.  By default this is the local version, but
    an address can be specified for remote systems.
    
    Parameters
    ----------
    host : str, optional
        Host IP address if not localhost
    port : str, optional
        QIS connection port if set to a value other than the default
        
    """

    myQis = QisInterface(host, port)
    retVal = myQis.sendAndReceiveCmd(cmd="$shutdown")
    myQis.disconnect()
    time.sleep(1)
    return retVal


#DEPRICATED
def GetQisModuleSelection(QisConnection):
    """
    Prints a list of modules for user selection
    
    .. DEPRECATED -: 2.0.12
        Use the module selection functions of the QisInterface class instead
    """

    # Request a list of all USB and LAN accessible power modules
    devList = QisConnection.getDeviceList()
    # Removes rest devices
    devList = [x for x in devList if "rest" not in x]

    # Print the devices, so the user can choose one to connect to
    printText("\n ########## STEP 1 - Select a Quarch Module. ########## \n")
    printText(' --------------------------------------------')
    printText(' |  {:^5}  |  {:^30}|'.format("INDEX", "MODULE"))
    printText(' --------------------------------------------')

    try:
        for idx in xrange(len(devList)):
            printText(' |  {:^5}  |  {:^30}|'.format(str(idx + 1), devList[idx]))
            printText(' --------------------------------------------')
    except:
        for idx in range(len(devList)):
            printText(' |  {:^5}  |  {:^30}|'.format(str(idx + 1), devList[idx]))
            printText(' --------------------------------------------')

    # Get the user to select the device to control
    try:
        moduleId = int(raw_input("\n>>> Enter the index of the Quarch module: "))
    except NameError:
        moduleId = int(input("\n>>> Enter the index of the Quarch module: "))

    # Verify the selection
    if (moduleId > 0 and moduleId <= len(devList)):
        myDeviceID = devList[moduleId - 1]
    else:
        myDeviceID = None

    return myDeviceID


# ==========================================
#           HELPER FUNCTIONS
# ==========================================

def _parse_qis_port(args: List[str]) -> int:
    """Extracts the QIS port from arguments, defaulting to 9722."""
    port = 9722
    if args:
        for arg in args:
            if "-port=" in arg.lower():
                try:
                    port = int(arg.split('=')[1])
                except (IndexError, ValueError):
                    pass
    return port


def _prepare_qis_launch_env(terminal: bool, headless: bool, args: List[str]) -> Tuple[Optional[str], Optional[str]]:
    """Resolves paths, JVM flags, and builds the QIS command string."""

    # 1. OS Checks
    current_os = platform.system()
    current_arch = platform.machine().lower()

    # 2. Permissions
    _handle_java_permissions()

    # 3. Path Resolution
    if 'quarchpy_binaries' not in globals() and 'quarchpy_binaries' not in locals():
        logger.error("quarchpy_binaries module not found.")
        return None, None

    try:
        java_home = quarchpy_binaries.get_jre_home()
    except Exception as e:
        logger.error(f"Failed to get JRE home: {e}")
        return None, None

    # Locate QIS Jar
    # Assuming standard structure relative to this file
    base_path = os.path.dirname(os.path.abspath(__file__))
    # Go up one level from 'connection_specific' typically
    root_path = os.path.dirname(base_path)

    # Construct path: .../connection_specific/QPS/qis/qis.jar
    qis_jar_path = os.path.join(root_path, "connection_specific", "QPS", "qis", "qis.jar")
    qis_dir = os.path.dirname(qis_jar_path)

    # 4. Java Binary Selection
    java_bin_rel = "bin/java"
    if current_os == "Windows":
        java_bin_rel = r"bin\java"

    java_exe = os.path.join(java_home, java_bin_rel)
    java_exe_quoted = f'"{java_exe}"'

    # 5. Build JVM Arguments
    # Prefer IPv4
    cmd_prefix = "-Djava.net.preferIPv4Stack=true -Djava.net.preferIPv6Addresses=false"
    # Enable native access (required for newer Java versions)
    cmd_prefix += " --enable-native-access=ALL-UNNAMED"
    # Netty config
    cmd_prefix += " -Dio.netty.noUnsafe=true"

    # Headless logic
    is_headless = headless
    if args and "-headless" in args:
        is_headless = True

    if is_headless:
        cmd_prefix += " -Djava.awt.headless=true"

    # 6. Build Application Arguments
    cmd_suffix = ""
    if terminal:
        cmd_suffix += " -terminal"

    if args:
        for option in args:
            # Prevent double flags
            if option == "-terminal" and terminal:
                continue
            if option != "-headless":
                cmd_suffix += f" {option}"

    # 7. Final Command
    command = f'{java_exe_quoted} {cmd_prefix} -jar qis.jar{cmd_suffix}'

    return command, qis_dir


def _launch_qis_process(command: str, args: List[str]) -> Union[Popen, CompletedProcess]:
    """Launches QIS, checking for logging flags."""
    args_str = " ".join(args) if args else ""

    if "-logconsole=ON" in args_str:
        if platform.system() == "Windows":
            return subprocess.Popen(command, shell=True)
        else:
            return subprocess.run(command + "; exec bash", shell=True)
    else:
        text_mode = True if sys.version_info >= (3, 7) else False
        return subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=text_mode, shell=True)


def _wait_for_qis_service(host: str, port: int, timeout: int, process: Optional[subprocess.Popen], args: List[str]) -> bool:
    """Polls the specific QIS port until it opens."""
    start_time = time.time()
    args_str = " ".join(args) if args else ""
    logging_on = "-logconsole=ON" in args_str

    while True:
        # 1. Check TCP Connectivity
        if _check_port_open(host, port):
            # QIS accepts the connection
            logger.debug(f"QIS detected on port {port} after {time.time() - start_time:.2f}s")
            return True

        # 2. Monitor Process Health
        if not logging_on and process:
            # Drain pipes and check if process died
            if process.poll() is not None:
                logger.error("QIS process terminated unexpectedly.")
                return False
            try:
                _get_std_msg_and_err_from_QIS_process(process)
            except NameError:
                pass  # Function might not be available in this scope

        # 3. Timeout Check
        if time.time() - start_time > timeout:
            logger.error(f"QIS failed to launch on port {port} within {timeout}s.")
            return False

        time.sleep(0.2)

def _handle_java_permissions() -> None:
    """Checks and attempts to fix Java execution permissions."""
    permissions, message = find_java_permissions()
    if not permissions:
        logger.warning(message)
        printText("Not having correct permissions will prevent Quarch Java Programs from launching.")
        printText("Would you like quarchpy to attempt to fix the permissions now? (Y/N)")
        try:
            user_input = requestDialog(">>> ")
        except EOFError:
            user_input = "N"
        if user_input.strip().lower() in ['y', 'yes']:
            fix_permissions()

def _check_port_open(host: str, port: int) -> bool:
    """Simple TCP connect check."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(1)
    try:
        s.connect((host, int(port)))
        s.close()
        return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False
