"""

Contains general functions for starting and stopping QIS processes

"""

import os, sys
import socket
import time, platform
from subprocess import CompletedProcess, Popen
from threading import Thread, Lock, Event, active_count
from queue import Queue, Empty
from typing import Optional, List, Any, Tuple, Union

import quarchpy_binaries

from quarchpy.connection_specific.connection_QIS import QisInterface
from quarchpy.connection_specific.jdk_jres.fix_permissions import main as fix_permissions, find_java_permissions
from quarchpy.install_qps import find_qps
from quarchpy.user_interface.user_interface import printText, logDebug
import subprocess
import logging
logger = logging.getLogger(__name__)


def isQisRunning():
    """
    Checks if a local instance of QIS is running and responding
    Returns
    -------
    is_running : bool\
        True if QIS is running and responding
    """

    qisRunning = False
    myQis = None
    #attempt to connect to Qis
    try:
        myQis = QisInterface(connectionMessage=False)
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


def isQisRunningAndResponding(timeout=2):
    """
    checks if qis is running and responding to a $version
    """
    qisRunning = isQisRunning()
    if qisRunning == False:
        logger.debug("QIS is not running")
        return False

    logger.debug("Qis is running")
    myQis = QisInterface(connectionMessage=False)
    counter = 0
    maxCounter = 20
    while counter <= maxCounter:
        versionResponse = myQis.sendAndReceiveCmd(cmd="$version")
        if "v" in versionResponse.lower():
            qisResponding = True
            break
        else:
            logger.debug("Qis returned from $version: " + str(versionResponse) + "  Expected to contain ': v'")
            time.sleep(timeout / maxCounter)  # We attempt to get QIS
            counter += 1

    if (qisRunning is False):
        logger.debug("QIS is not running")
        return False
    else:
        logger.debug("QIS is running")
        return True


def startLocalQis(
    terminal: bool = False,
    headless: bool = False,
    args: List[str] = [],
    timeout: int = 20,
    host: str = '127.0.0.1'
) -> Optional['QisInterface']:
    """
    Executes QIS on the local system and returns a connected interface.

    Args:
        terminal: True if QIS terminal should be shown on startup.
        headless: True if app should be run in headless mode.
        args: List of additional parameters (e.g. ['-port=9723']).
        timeout: Time in seconds to wait for launch.
        host: Host address (default localhost).

    Returns:
        QisInterface: Connected interface object if successful, None otherwise.
    """
    # 1. Parse port from arguments (Default QIS port is 9722)
    qis_port = _parse_qis_port(args)

    # 2. Check if already running on the target port
    if _check_port_open(host, qis_port):
        logger.debug(f"QIS instance on port {qis_port} is already running. Connecting...")
        return QisInterface(host=host, port=qis_port)

    # 3. Check for installation
    if not find_qps():
        logger.error("Unable to find QPS/QIS directory... Aborting...")
        return None

    # 4. Prepare Command and Environment
    command, qis_dir = _prepare_qis_launch_env(terminal, headless, args)
    if not command:
        return None

    # 5. Launch QIS Process
    current_dir = os.getcwd()
    try:
        os.chdir(qis_dir)
        process = _launch_qis_process(command, args)
    finally:
        os.chdir(current_dir)

    # 6. Wait for QIS to be ready
    if not _wait_for_qis_service(host, qis_port, timeout, process, args):
        return None

    # 7. Return Connected Interface
    try:
        return QisInterface(host=host, port=qis_port)
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

    if (current_os == "Linux" and current_arch == "aarch64") or \
            (current_os == "Darwin" and current_arch == "arm64"):
        logger.warning(f"The system [{current_os}, {current_arch}] is not officially supported.")
        return None, None

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

    if "-logging=ON" in args_str:
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
    logging_on = "-logging=ON" in args_str

    while True:
        # 1. Check TCP Connectivity
        if _check_port_open(host, port):
            # QIS accepts the connection
            logger.debug(f"QIS detected on port {port} after {time.time() - start_time:.2f}s")

            # Optional: Extra check to ensure it's actually responding to commands
            # (Replaces old 'isQisRunningAndResponding' logic efficiently)
            # You could do a quick handshake here if strict validation is required,
            # but usually TCP open is sufficient for startup success.
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
        logger.warning("Not having correct permissions will prevent Quarch Java Programs from launching.")
        logger.warning('Run "python -m quarchpy.run permission_fix" to fix this.')

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
