"""

Contains general functions for starting and stopping QIS processes

"""

import os, sys
import time, platform
from threading import Thread, Lock, Event, active_count
from queue import Queue, Empty
from quarchpy.connection_specific.connection_QIS import QisInterface
from quarchpy.connection_specific.jdk_jres.fix_permissions import main as fix_permissions, find_java_permissions
from quarchpy.user_interface.user_interface import printText, logDebug
import subprocess
import logging


def isQisRunning():
    """
    Checks if a local instance of QIS is running and responding
    Returns
    -------
    is_running : bool
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
        logging.debug("QIS is not running")
        return False
    else:
        logging.debug("QIS is running")
        return True


def isQisRunningAndResponding(timeout=2):
    """
    checks if qis is running and responding to a $version
    """
    qisRunning = isQisRunning()
    if qisRunning == False:
        logging.debug("QIS is not running")
        return False

    logging.debug("Qis is running")
    myQis = QisInterface(connectionMessage=False)
    counter = 0
    maxCounter = 20
    while counter <= maxCounter:
        versionResponse = myQis.sendAndReceiveCmd(cmd="$version")
        if ": v" in versionResponse.lower():
            qisResponding = True
            break
        else:
            logging.debug("Qis returned from $version: " + str(versionResponse) + "  Expected to contain ': v'")
            time.sleep(timeout / maxCounter)  # We attempt to get QIS
            counter += 1

    if (qisRunning is False):
        logging.debug("QIS is not running")
        return False
    else:
        logging.debug("QIS is running")
        return True


def startLocalQis(terminal=False, headless=False, args=None, timeout=20):
    """
    Executes QIS on the local system, using the version contained within quarchpy
    
    Parameters
    ----------
    terminal : bool, optional
        True if QIS terminal should be shown on startup
    headless : bool, optional
        True if app should be run in headless mode for non graphical environments
    args : list[str], optional
        List of additional parameters to be supplied to QIS on the command line

    """

    # java path
    java_path = os.path.dirname(os.path.abspath(__file__))
    java_path, junk = os.path.split(java_path)
    java_path = os.path.join(java_path, "connection_specific", "jdk_jres")
    java_path = "\"" + java_path

    # change directory to /QPS/QIS
    qis_path = os.path.dirname(os.path.abspath(__file__))
    qis_path, junk = os.path.split(qis_path)

    # OS
    current_os = platform.system()
    current_arch = platform.machine()
    current_arch = current_arch.lower()  # ensure comparing same case

    # Currently officially unsupported
    if (current_os in "Linux" and current_arch == "aarch64") or (current_os in "Darwin" and current_arch == "arm64"):
        logging.warning("The system [" + current_os + ", " + current_arch + "] is not officially supported.")
        logging.warning("Please contact Quarch support for running QuarchPy on this system.")
        return

    # ensure the jres folder has the required permissions
    permissions, message = find_java_permissions()
    if permissions is False:
        logging.warning(message)
        logging.warning("Not having correct permissions will prevent Quarch Java Programs to launch")
        logging.warning("Run \"python -m quarchpy.run permission_fix\" to fix this.")
        user_input = input("Would you like to fix permissions now? (Y/N)")
        if user_input.lower() == "y":
            fix_permissions()
            permissions, message = find_java_permissions()
            time.sleep(0.5)
            if permissions is False:
                logging.warning("Attempt to fix permissions was unsuccessful. Please fix these manually.")
            else:
                logging.warning("Attempt to fix permissions was successful. Now continuing.")

    # if current_os != "Windows":
    #     subprocess.call(['chmod', '-R', '+rwx', java_path])

    # single or multiple QPS builds for each OS
    is_single_qps_build = True
    if is_single_qps_build:
        qis_path = os.path.join(qis_path, "connection_specific", "QPS", "win-amd64", "qis", "qis.jar")
    else:
        if current_os in "Windows":
            qis_path = os.path.join(qis_path, "connection_specific", "QPS", "win-amd64", "qis", "qis.jar")
        elif current_os in "Linux" and current_arch == "x86_64":
            qis_path = os.path.join(qis_path, "connection_specific", "QPS", "lin-amd64", "qis", "qis.jar")
        elif current_os in "Linux" and current_arch == "aarch64":
            qis_path = os.path.join(qis_path, "connection_specific", "QPS", "lin-arm64", "qis", "qis.jar")
        elif current_os in "Darwin" and current_arch == "x86_64":
            qis_path = os.path.join(qis_path, "connection_specific", "QPS", "mac-amd64", "qis", "qis.jar")
        elif current_os in "Darwin" and current_arch == "arm64":
            qis_path = os.path.join(qis_path, "connection_specific", "QPS", "mac-arm64", "qis", "qis.jar")
        else:  # default to windows
            qis_path = os.path.join(qis_path, "connection_specific", "QPS", "win-amd64", "qis", "qis.jar")

    # record current working directory
    current_dir = os.getcwd()
    os.chdir(os.path.dirname(qis_path))

    # Building the command

    # prefer IPV4 to IPV6
    ipv4v6_vm_args = "-Djava.net.preferIPv4Stack=true -Djava.net.preferIPv6Addresses=false"

    # Process command prefix. Needed for headless mode, to support OSs with no system tray.
    cmd_prefix = ipv4v6_vm_args
    if headless is True or (args is not None and "-headless" in args):
        cmd_prefix += " -Djava.awt.headless=true"

    # Process command suffix (additional standard options for QIS).
    if terminal is True:
        cmd_suffix = " -terminal"
    else:
        cmd_suffix = ""
    if args is not None:
        for option in args:
            # Avoid doubling the terminal option
            if option == "-terminal" and terminal is True:
                continue
            # Headless option is processed seperately as a java command
            if option != "-headless":
                cmd_suffix = cmd_suffix + " " + option


    command = "java\" " + cmd_prefix + " -jar qis.jar" + cmd_suffix

    # different start for different OS
    if current_os == "Windows":
        command = java_path + "\\win_amd64_jdk_jre\\bin\\" + command
    elif current_os == "Linux" and current_arch == "x86_64":
        command = java_path + "/lin_amd64_jdk_jre/bin/" + command
    elif current_os == "Linux" and current_arch == "aarch64":
        command = java_path + "/lin_arm64_jdk_jre/bin/" + command
    elif current_os == "Darwin" and current_arch == "x86_64":
        command = java_path + "/mac_amd64_jdk_jre/bin/" + command
    elif current_os == "Darwin" and current_arch == "arm64":
        command = java_path + "/mac_arm64_jdk_jre/bin/" + command
    else:  # default to windows
        command = java_path + "\\win_amd64_jdk_jre\\bin\\" + command

    # Use the command and check QIS has launched
    # If logging to a terminal window is on then os.system should be used to view logging.
    if "-logging=ON" in str(args):
        process = subprocess.Popen(command, shell=True)
        startTime = time.time()  # Checks for Popen launch only
        while not isQisRunning():
            if time.time() - startTime > timeout:
                raise TimeoutError("QIS failed to launch within timelimit of " + str(timeout) + " sec.")
            pass
    else:
        if sys.version_info[0] < 3:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        else:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, shell=True)

        startTime = time.time()  #Checks for Popen launch only
        while not isQisRunning():
            _get_std_msg_and_err_from_QIS_process(process)
            if time.time() - startTime > timeout:
                raise TimeoutError("QIS failed to launch within timelimit of " + str(timeout) + " sec.")
            pass

        if isQisRunningAndResponding(timeout=timeout):
            logDebug("QIS running and responding")
        else:
            logDebug("QIS running but not responding")

    # change directory back to start directory
    os.chdir(current_dir)


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
                logging.error(f"{source}: {line}")
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
        logging.debug("QIS is not running")
        return False
    else:
        logging.debug("QIS is running")
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
