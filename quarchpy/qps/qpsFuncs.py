import subprocess
import logging
import platform
import socket
from threading import Thread, Lock, Event
from queue import Queue, Empty
from typing import List, Optional, Tuple, Union, Any

from quarchpy.install_qps import find_qps
from quarchpy.qis import isQisRunning, startLocalQis
from quarchpy.connection_specific.connection_QPS import QpsInterface
from quarchpy.connection_specific.jdk_jres.fix_permissions import main as fix_permissions, find_java_permissions
from quarchpy.user_interface import *
logger = logging.getLogger(__name__)


def isQpsRunning(host='127.0.0.1', port=9822, timeout=0):
    '''
    This func will return true if QPS is running with a working QIS connection.
    '''
    myQps=None
    logger.debug("Checking if QPS is running")
    start = time.time()
    while True:
        try:
            myQps = QpsInterface(host, port)
            break
        except Exception as e:
            logger.debug("Error when making QPS interface. QPS may not be running.")
            logger.debug(e)
            if (time.time() - start) > timeout:
                break
    if myQps is None:
        logger.debug("QPS is not running")
        return False

    logger.debug("Checking if QPS reports a QIS connection") # "$qis status" returns connected if it has ever had a QIS connection.
    answer=0
    counter=0
    while True:
        answer = myQps.sendCmdVerbose(cmd="$qis status")
        if answer.lower()=="connected":
            logger.debug("QPS Running With QIS Connected")
            break
        else:
            logger.debug("QPS Running QIS NOT found. Waiting and retrying.")
            time.sleep(0.5)
            counter += 1
            if counter > 5:
                logger.debug("QPS Running QIS NOT found after "+str(counter)+" attempts.")
                return False

    logger.debug("Checking if QPS/QIS comms are running")
    start = time.time()
    while True:
        try:
            answer = myQps.sendCmdVerbose(cmd="$list")
            break
        except:
            pass
        if (time.time() - start) > timeout:
            break

    # check for a 1 showing the first module to be displayed, or a no module/device error message.
    if answer[0] == "1" or "no device" in str(answer).lower() or "no module" in str(answer).lower():
        logger.debug("QPS and QIS are running and responding with valid $list info")
        return True
    else:
        logger.debug("QPS did not return expected output from $list")
        logger.debug("$list: " + str(answer))
        return False

def startLocalQps(
    keepQisRunning: bool = False,
    args: List[str] = None,
    timeout: int = 30,
    startQPSMinimised: bool = True,
    host: str = '127.0.0.1'
) -> Optional['QpsInterface']:
    """
    Main entry point to start a local QPS instance.

    Args:
        keepQisRunning: If True, ensures QIS is also started/running.
        args: List of command line arguments for QPS (e.g. ['-port=9823']).
        timeout: Time in seconds to wait for QPS to become ready.
        startQPSMinimised: If True, adds the flag to start QPS minimized.
        host: The host address (default localhost).

    Returns:
        QpsInterface: Connected interface object if successful, None otherwise.
    """
    # 1. Parse ports from arguments
    qps_port, qis_port, qis_rest_port = _parse_ports(args)

    # 2. Check if already running
    if _check_port_open(host, qps_port):
        logger.debug(f"QPS instance on port {qps_port} is already running. Connecting...")
        # Assuming QpsInterface can be imported or is available in scope
        return QpsInterface(host=host, port=qps_port)

    # 3. Check for QPS installation
    if not find_qps():
        logger.error("Unable to find or install QPS... Aborting...")
        return None

    # 4. Handle QIS Backend (if required)
    if keepQisRunning:
        if not _ensure_qis_running(host, qis_port, qis_rest_port, timeout):
            return None

    # 5. Prepare Command and Environment
    command, qps_dir = _prepare_qps_launch_env(args, startQPSMinimised)
    if not command or not qps_dir:
        return None

    # 6. Launch QPS Process
    current_dir = os.getcwd()
    try:
        os.chdir(qps_dir) # Switch to QPS dir for launch dependencies
        process = _launch_process(command, args)
    finally:
        os.chdir(current_dir) # Always return to original dir

    # 7. Wait for QPS to be ready
    if not _wait_for_service(host, qps_port, timeout, process, args):
        return None

    # 8. Return Connected Interface
    try:
        return QpsInterface(host=host, port=qps_port)
    except Exception as e:
        logger.error(f"QPS started, but failed to create interface object: {e}")
        return None

def reader(stream, q, source, lock,stop_flag):
    """
    Used to read output and place it in a queue for multithreaded reading
    :param stream:
    :param q:
    :param source:
    :param lock: The lock for the queue
    :param stop_flag: Flag to exit the loop and close the thread
    :return: None
    """
    while not stop_flag.is_set():
        line = stream.readline()
        if not line:
            break
        with lock:
            q.put((source, line.strip()))

def _get_std_msg_and_err_from_QPS_process(process):
    """
    Uses multithreading to check for stderr and stdmsg passed by the process that launches QPS
    This allows the user to understand why QPS might not have appeared.
    :param process: The Process Used to launch QPS
    :return: None
    """
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
    while counter <= 3: # If 3 empty reads from the queue then move on to see if QPS is running.
        try:
            source, line = q.get(timeout=1)  # Wait for 1 second for new lines
            counter = 0
            if source == "stderr":
                logger.error(f"{source}: {line}")
            else:
                printText(f"{source}: {line}")
        except Empty:
            counter += 1
    stop_flag.set() #Close the threads and return to the main loop where QPS is check to see if its started yet


def closeQps(host='127.0.0.1', port=9822):
    myQps = QpsInterface(host, port)
    myQps.sendCmdVerbose("$shutdown")
    del myQps
    time.sleep(1) #needed as calling "isQpsRunning()" will throw an error if it ties to connect while shutdown is in progress.

def GetQpsModuleSelection(QpsConnection, favouriteOnly=True, additionalOptions=['rescan', 'all con types', 'ip scan'], scan=True):
    favourite = favouriteOnly
    ip_address = None
    while True:
        printText("QPS scanning for devices")
        tableHeaders = ["Module"]
        # Request a list of all USB and LAN accessible power modules
        if ip_address == None:
            devList = QpsConnection.getDeviceList(scan=scan)
        else:
            devList = QpsConnection.getDeviceList(scan=scan, ipAddress=ip_address)
        if "no device" in devList[0].lower() or "no module" in devList[0].lower():
            favourite = False  # If no device found conPref wont match and will bugout

        # Removes rest devices
        devList = [x for x in devList if "rest" not in x]
        message = "Select a quarch module"

        if (favourite):
            index = 0
            sortedDevList = []
            conPref = ["USB", "TCP", "SERIAL", "REST", "TELNET"]
            while len(sortedDevList) < len(devList):
                for device in devList:
                    if conPref[index] in device.upper():
                        sortedDevList.append(device)
                index += 1
            devList = sortedDevList

            # new dictionary only containing one favourite connection to each device.
            favConDevList = []
            index = 0
            for device in sortedDevList:
                if (favConDevList == [] or not device.split("::")[1] in str(favConDevList)):
                    favConDevList.append(device)
            devList = favConDevList

        if User_interface.instance != None and User_interface.instance.selectedInterface == "testcenter":
            tempString = ""
            for module in devList:
                tempString+=module+"="+module+","
            devList = tempString[0:-1]


        myDeviceID = listSelection(title=message, message=message, selectionList=devList,
                                   additionalOptions=additionalOptions, nice=True, tableHeaders=tableHeaders, indexReq=True)

        if myDeviceID in 'rescan':
            ip_address = None
            favourite = True
            continue
        elif myDeviceID in 'all con types':
            printText('Displaying all conection types...')
            favourite = False
            continue
        elif myDeviceID in 'ip scan':
            ip_address = requestDialog("Please input IP Address of the module you would like to connect to: ")
            favourite = False
            continue
        else:
            return myDeviceID

# ==========================================
#           HELPER FUNCTIONS
# ==========================================

def _parse_ports(args: List[str]) -> Tuple[int, int, int]:
    """Extracts QPS and QIS ports from the argument list."""
    qps_port = 9822
    qis_port = 9722
    qis_rest_port = 9780

    for arg in args:
        arg_lower = arg.lower()
        if "-port=" in arg_lower:
            qps_port = int(arg.split('=')[1])
        elif "-qisport=" in arg_lower:
            qis_port = int(arg.split('=')[1])
        elif "-qisrestport=" in arg_lower:
            qis_rest_port = int(arg.split('=')[1])

    return qps_port, qis_port, qis_rest_port


def _ensure_qis_running(host: str, qis_port: int, qis_rest_port: int, timeout: int) -> bool:
    """Checks if QIS is running on the target port, starts it if not."""
    if _check_port_open(host, qis_port):
        return True

    logger.debug(f"Starting QIS on ports {qis_port}/{qis_rest_port}...")
    qis_args = [f'-port={qis_port}', f'-restport={qis_rest_port}']
    startLocalQis(args=qis_args)

    # Wait for QIS
    start_time = time.time()
    while not _check_port_open(host, qis_port):
        if time.time() - start_time > timeout:
            logger.error(f"QIS failed to start on port {qis_port} within timeout.")
            return False
        time.sleep(0.5)

    return True


def _prepare_qps_launch_env(args: List[str], startQPSMinimised: bool) -> Tuple[Optional[str], Optional[str]]:
    """Resolves paths, checks OS support/permissions, and builds the java command."""

    # Check OS Support
    current_os = platform.system()
    current_arch = platform.machine().lower()

    if (current_os == "Linux" and current_arch == "aarch64") or (current_os == "Darwin" and current_arch == "arm64"):
        logger.warning(f"System [{current_os}, {current_arch}] is not officially supported.")
        return None, None

    # Handle Permissions
    _handle_java_permissions()

    # Resolve Paths
    base_path = os.path.dirname(os.path.abspath(__file__))
    base_path, junk = os.path.split(base_path)
    java_root = os.path.join(base_path, "connection_specific", "jdk_jres")
    qps_jar_path = os.path.join(base_path, "connection_specific", "QPS", "qps.jar")
    qps_dir = os.path.dirname(qps_jar_path)

    # Select Java Binary
    java_bin = _get_java_binary_path(java_root, current_os, current_arch)

    # Build Command String
    args_str = " ".join(args) if args else " "
    if startQPSMinimised and "-ccs" not in args_str.lower():
        args_str += " -ccs=MIN"

    # Quote paths
    command = f'"{java_bin}" -jar qps.jar {args_str}'

    return command, qps_dir


def _get_java_binary_path(java_root: str, current_os: str, current_arch: str) -> str:
    """Selects the correct Java binary for the architecture."""
    if current_os == "Windows":
        return os.path.join(java_root, "win_amd64_jdk_jre", "bin", "java")
    elif current_os == "Linux":
        folder = "lin_arm64_jdk_jre" if current_arch == "aarch64" else "lin_amd64_jdk_jre"
        return os.path.join(java_root, folder, "bin", "java")
    elif current_os == "Darwin":
        folder = "mac_arm64_jdk_jre" if current_arch == "arm64" else "mac_amd64_jdk_jre"
        return os.path.join(java_root, folder, "bin", "java")

    # Fallback
    return os.path.join(java_root, "win_amd64_jdk_jre", "bin", "java")


def _handle_java_permissions() -> None:
    """Checks and attempts to fix Java execution permissions."""
    permissions, message = find_java_permissions()
    if not permissions:
        logger.warning(message)
        try:
            fix_permissions()
            permissions, _ = find_java_permissions()
            if not permissions:
                logger.warning("Auto-fix for permissions failed. Please fix manually.")
            else:
                logger.warning("Permissions fixed successfully.")
        except Exception as e:
            logger.warning(f"Permission fix error: {e}")


def _launch_process(command: str, args: List[str]) -> subprocess.Popen:
    """Launches the subprocess, handling logging flags."""
    args_str = " ".join(args) if args else ""

    if "-logging=ON" in args_str:
        if platform.system() == "Windows":
            return subprocess.Popen(command, shell=True)
        else:
            return subprocess.run(command + "; exec bash", shell=True)
    else:
        # NOTE: 'text=True' was added in Python 3.7.
        # For older compatibility (3.6) 'universal_newlines=True' is used, but 3.7+ supports both.
        # We assume 3.7+ here as requested.
        return subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, shell=True)


def _wait_for_service(host: str, port: int, timeout: int, process: Optional[subprocess.Popen], args: List[str]) -> bool:
    """Polls the port until open, checking process output for errors."""
    start_time = time.time()
    args_str = " ".join(args) if args else ""
    logging_on = "-logging=ON" in args_str

    while True:
        if _check_port_open(host, port):
            logger.debug(f"Service detected on port {port} after {time.time() - start_time:.2f}s")
            return True

        # If hidden, drain pipes to prevent deadlock and check for crashes
        if not logging_on and process:
            # Assuming _get_std_msg_and_err_from_QPS_process is defined in your module
            _get_std_msg_and_err_from_QPS_process(process)

        if time.time() - start_time > timeout:
            logger.error(f"Service failed to launch on port {port} within {timeout}s.")
            return False

        time.sleep(0.2)


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