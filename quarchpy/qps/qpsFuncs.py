from subprocess import CompletedProcess, Popen
from threading import Thread, Lock, Event
from queue import Queue, Empty
import platform
from typing import Optional, List, Tuple, Union

import quarchpy_binaries

from quarchpy.install_qps import find_qps
from quarchpy.qis import isQisRunning, startLocalQis
from quarchpy.connection_specific.connection_QPS import QpsInterface
from quarchpy.connection_specific.jdk_jres.fix_permissions import main as fix_permissions, find_java_permissions
from quarchpy.qis.qisFuncs import isQisRunningAndResponding
from quarchpy.user_interface import *
import subprocess
import logging

logger = logging.getLogger(__name__)


def isQpsRunning(host='127.0.0.1', port=9822, timeout=0):
    '''
    This func will return true if QPS is running with a working QIS connection.
    '''
    myQps = None
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

    logger.debug(
        "Checking if QPS reports a QIS connection")  # "$qis status" returns connected if it has ever had a QIS connection.
    answer = 0
    counter = 0
    while True:
        answer = myQps.sendCmdVerbose(cmd="$qis status")
        if answer.lower() == "connected":
            logger.debug("QPS Running With QIS Connected")
            break
        else:
            logger.debug("QPS Running QIS NOT found. Waiting and retrying.")
            time.sleep(0.5)
            counter += 1
            if counter > 5:
                logger.debug("QPS Running QIS NOT found after " + str(counter) + " attempts.")
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
        args: Optional[List[str]] = None,
        timeout: int = 30,
        startQPSMinimised: bool = True,
        host: str = '127.0.0.1',
        **kwargs
) -> Optional['QpsInterface']:
    """
    Main entry point to start a local QPS instance.

    Args:
        keepQisRunning (bool): If True, ensures QIS remains active after QPS closes.
        args (List[str], optional): Additional CLI arguments for QPS launch.
        timeout (int): Seconds to wait for services to initialize.
        startQPSMinimised (bool): If True, appends '-ccs=MIN' to launch arguments.
        host (str): The target host address. Defaults to '127.0.0.1'.
        **kwargs: Configuration for ports and QPS behavior.

            * **port** (int): Specify port for QPS to use. Defaults to 9822.
            * **qis_port** (int): Specify QIS port to use and listen to. Defaults to 9722.
            * **qis_rest_port** (int): Specify QIS rest port to use. Defaults to 9780.
            * **connect** (str): Connects to a device (e.g., 'USB::QTL1999-04-013').
            * **ccs** (str): Set to 'HIDE' to disable initial display of CCS.
            * **devdebug** (str): Set to 'ON' to enable development debug.
            * **logconsole** (str): If 'ON', logs to the console as well as to file.
            * **loglevel** (str): Logging level [OFF, FATAL, ERROR, WARN, INFO, DEBUG, TRACE, ALL].
            * **qissamelogging** (str): If 'ON', QIS inherits QPS logging levels.
            * **logviewer** (str): Specifies the log viewer file directory.
            * **open_file** (str): Opens an archived file.
            * **perfcontrols** (str): Set to 'ON' to enable performance controls.
            * **shownotifications** (str): Set to 'OFF' to disable notifications.

    Returns:
        Optional[QpsInterface]: A connected interface object, or None if launch fails.
        """
    # 1. Extract values from kwargs with appropriate defaults
    port = kwargs.get('port', 9822)
    qis_port = kwargs.get('qis_port', 9722)
    qis_rest_port = kwargs.get('qis_rest_port', 9780)

    # 2. Prepare Arguments
    launch_args = args.copy() if args else []

    # Map kwargs to their CLI flag equivalents
    # This automatically builds the command line based on your provided list
    kwarg_map = {
        'ccs': '-ccs=',
        'connect': '-connect=',
        'devdebug': '-devdebug=',
        'logconsole': '-logconsole',
        'loglevel': '-loglevel=',
        'qissamelogging': '-qissamelogging=',
        'logviewer': '-logviewer=',
        'open_file': '-open=',
        'perfcontrols': '-perfcontrols=',
        'shownotifications': '-shownotifications=',
        'port': '-port=',
        'qis_port': '-qisport=',
        'qis_rest_port': '-qisrestport='
    }

    for key, flag in kwarg_map.items():
        if key in kwargs:
            val = kwargs[key]
            # Handle boolean flags (like logconsole) vs value flags (like port)
            arg_str = flag if isinstance(val, bool) and val else f"{flag}{val}"

            # Add to launch_args if not already manually specified in the 'args' list
            if not any(flag in a for a in launch_args):
                launch_args.append(arg_str)

    # 3. Check if already running on the specific target port
    if isQpsRunning(host=host, port=port):
        logger.debug(f"QPS instance on port {port} is already running. Connecting...")
        return QpsInterface(host=host, port=port)

    # 4. Check QPS is installed in the expected location for QuarchPy
    if not find_qps():
        logger.error("Unable to find or install QPS... Aborting...")
        return None

    # 5. QIS Infrastructure Setup & Port Synchronization
    # Ensures QIS is running as a standalone process if keepQisRunning is True (so it survives QPS closing).
    # Also manually starts QIS if non-standard ports are requested, bypassing a known QPS bug where
    # it fails to propagate custom -qisport/-qisrestport flags to its own internal QIS launcher.
    if keepQisRunning:
        logger.debug("QIS is not running. Starting QIS...")
        if not _prepare_qis_backend(qis_port, qis_rest_port, timeout):
            return None

    # 6. Prepare Command and Environment
    command, qps_dir = _prepare_qps_launch_env(launch_args, startQPSMinimised)
    if not command:
        return None

    # 7. Launch QPS Process
    current_dir = os.getcwd()

    try:
        os.chdir(qps_dir)  # Switch to QPS dir for launch dependencies
        process = _launch_process(command, args)
    finally:
        os.chdir(current_dir)  # Always return to original dir

    # 8. Wait for QPS to be ready
    if not _wait_for_service(host, port, timeout, process, args):
        return None

    # 9. Return Connected Interface
    try:
        return QpsInterface(host=host, port=port)
    except Exception as e:
        logger.error(f"QPS started, but failed to create interface object: {e}")
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
                logger.error(f"{source}: {line}")
            else:
                printText(f"{source}: {line}")
        except Empty:
            counter += 1
    stop_flag.set()  #Close the threads and return to the main loop where QPS is check to see if its started yet


def closeQps(host='127.0.0.1', port=9822):
    myQps = QpsInterface(host, port)
    myQps.sendCmdVerbose("$shutdown")
    del myQps
    time.sleep(
        1)  #needed as calling "isQpsRunning()" will throw an error if it ties to connect while shutdown is in progress.


def GetQpsModuleSelection(QpsConnection: 'QpsInterface', favouriteOnly=True,
                          additionalOptions=['rescan', 'all con types', 'ip scan'], scan=True):
    """
    Deprecated: use QpsInterface.get_module_selection instead.
    This function will return a module selection list from QPS.

    """
    return (
        QpsConnection.get_qps_module_selection(preferred_connection_only=favouriteOnly,
                                               additional_options=additionalOptions, scan=scan)
    )


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
            try:
                qps_port = int(arg.split('=')[1])
            except (IndexError, ValueError):
                pass
        elif "-qisport=" in arg_lower:
            try:
                qis_port = int(arg.split('=')[1])
            except (IndexError, ValueError):
                pass
        elif "-qisrestport=" in arg_lower:
            try:
                qis_rest_port = int(arg.split('=')[1])
            except (IndexError, ValueError):
                pass

    return qps_port, qis_port, qis_rest_port


def _prepare_qis_backend(qis_port: int, qis_rest_port: int, timeout: int) -> bool:
    """Checks if QIS is running on the target port, starts it if not."""
    if isQisRunning(qis_port):
        return True

    logger.debug(f"Starting QIS on ports {qis_port}/{qis_rest_port}...")
    startLocalQis(port=qis_port, rest_port=qis_rest_port)

    # Wait for QIS
    start_time = time.time()
    while not isQisRunning(qis_port):
        if time.time() - start_time > timeout:
            logger.error(f"QIS failed to start on port {qis_port} within {timeout} seconds.")
            return False
        time.sleep(0.5)

    while not isQisRunningAndResponding(port=qis_port):
        if time.time() - start_time > timeout:
            logger.error(f"QIS failed to respond on port {qis_port} within {timeout} seconds.")
            return False
        time.sleep(0.5)

    return True


def _prepare_qps_launch_env(args: List[str], startQPSMinimised: bool) -> Tuple[Optional[str], Optional[str]]:
    """Resolves paths using quarchpy_binaries, checks permissions, and builds command."""

    # 1. Check OS Support
    current_os = platform.system()
    current_arch = platform.machine().lower()

    # 2. Handle Permissions
    _handle_java_permissions()

    # 3. Resolve Paths using quarchpy_binaries
    if 'quarchpy_binaries' not in globals() and 'quarchpy_binaries' not in locals():
        # Fallback if module isn't imported or available
        logger.error("quarchpy_binaries module not found. Cannot locate JRE.")
        return None, None

    try:
        java_home = quarchpy_binaries.get_jre_home()
    except Exception as e:
        logger.error(f"Failed to get JRE home: {e}")
        return None, None

    # Resolve QPS Jar Path
    qps_root = os.path.dirname(os.path.abspath(__file__))
    qps_root, _ = os.path.split(qps_root)  # Up one level
    qps_jar_path = os.path.join(qps_root, "connection_specific", "QPS", "qps.jar")
    qps_dir = os.path.dirname(qps_jar_path)

    # 4. Construct Command
    # Determine separator based on OS (Windows uses \, Linux/Mac use /)

    java_bin = "bin/java"
    if current_os == "Windows":
        java_bin = r"bin\java"

    # Full path to java executable
    java_exe = os.path.join(java_home, java_bin)

    # Wrap java path in quotes for safety
    java_exe_quoted = f'"{java_exe}"'

    # Prepare Args String
    args_str = " ".join(args) if args else " "
    if startQPSMinimised and "-ccs" not in args_str.lower():
        args_str += " -ccs=MIN"

    # Build Final Command
    command = f'{java_exe_quoted} -jar qps.jar {args_str}'

    return command, qps_dir


def _handle_java_permissions() -> None:
    """Checks and attempts to fix Java execution permissions."""
    permissions, message = find_java_permissions()
    if not permissions:
        logger.warning(message)
        printText("Not having correct permissions will prevent Quarch Java Programs from launching.")
        printText('Run "python -m quarchpy.run permission_fix" to fix this.')
        printText("Would you like quarchpy to attempt to fix the permissions now? (Y/N)")
        try:
            user_input = requestDialog(">>> ")
        except EOFError:
            user_input = "N"
        if user_input.strip().lower() in ['y', 'yes']:
            fix_permissions()


def _launch_process(command: str, args: List[str]) -> Union[Popen, CompletedProcess]:
    """Launches the subprocess, handling logging flags."""
    args_str = " ".join(args) if args else ""

    if "-logconsole=ON" in args_str:
        if platform.system() == "Windows":
            return subprocess.Popen(command, shell=True)
        else:
            return subprocess.run(command + "; exec bash", shell=True)
    else:
        # Use text=True for Python 3.7+
        text_mode = True if sys.version_info >= (3, 7) else False
        # Fallback for 3.6 if needed (universal_newlines=True)
        return subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=text_mode, shell=True)


def _wait_for_service(host: str, port: int, timeout: int, process: Optional[subprocess.Popen], args: List[str]) -> bool:
    """Polls the port until open, checking process output for errors."""
    start_time = time.time()
    args_str = " ".join(args) if args else ""
    logging_on = "-logconsole=ON" in args_str

    while True:
        if isQpsRunning(host, port):
            logger.debug(f"QPS detected on port {port} after {time.time() - start_time:.2f}s")
            return True

        # If hidden, drain pipes to prevent deadlock and check for crashes
        if not logging_on and process:
            _get_std_msg_and_err_from_QPS_process(process)

        if time.time() - start_time > timeout:
            logger.error(f"QPS failed to launch on port {port} within timelimit of {timeout} sec.")
            return False

        time.sleep(0.2)
