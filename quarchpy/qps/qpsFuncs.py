from threading import Thread, Lock, Event, active_count
from queue import Queue, Empty
import platform
from quarchpy.qis import isQisRunning, startLocalQis
from quarchpy.connection_specific.connection_QPS import QpsInterface
from quarchpy.connection_specific.jdk_jres.fix_permissions import main as fix_permissions, find_java_permissions
from quarchpy.user_interface import *
import subprocess
import logging


def isQpsRunning(host='127.0.0.1', port=9822, timeout=0):
    '''
    This func will return true if QPS is running with a working QIS connection.
    '''
    myQps=None
    logging.debug("Checking if QPS is running")
    start = time.time()
    while True:
        try:
            myQps = QpsInterface(host, port)
            break
        except Exception as e:
            logging.debug("Error when making QPS interface. QPS may not be running.")
            logging.debug(e)
            if (time.time() - start) > timeout:
                break
    if myQps is None:
        logging.debug("QPS is not running")
        return False

    logging.debug("Checking if QPS reports a QIS connection") # "$qis status" returns connected if it has ever had a QIS connection.
    answer=0
    counter=0
    while True:
        answer = myQps.sendCmdVerbose(cmd="$qis status")
        if answer.lower()=="connected":
            logging.debug("QPS Running With QIS Connected")
            break
        else:
            logging.debug("QPS Running QIS NOT found. Waiting and retrying.")
            time.sleep(0.5)
            counter += 1
            if counter > 5:
                logging.debug("QPS Running QIS NOT found after "+str(counter)+" attempts.")
                return False

    logging.debug("Checking if QPS/QIS comms are running")
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
        logging.debug("QPS and QIS are running and responding with valid $list info")
        return True
    else:
        logging.debug("QPS did not return expected output from $list")
        logging.debug("$list: " + str(answer))
        return False


def startLocalQps(keepQisRunning=False, args=[], timeout=30, startQPSMinimised=True):
    if keepQisRunning:
        if not isQisRunning():
            startLocalQis()
    temp =" "
    args = temp.join(args)
    if startQPSMinimised == True: #TODO add to release for QPS 1.38
        if "-ccs" not in args.lower():
            args +=" -ccs=MIN"

    # Record current working directory
    current_dir = os.getcwd()

    # JRE path
    java_path = os.path.dirname(os.path.abspath(__file__))
    java_path, junk = os.path.split(java_path)
    java_path = os.path.join(java_path, "connection_specific", "jdk_jres")
    java_path = "\"" + java_path
    # Start to build the path towards qps.jar
    qps_path = os.path.dirname(os.path.abspath(__file__))
    qps_path, junk = os.path.split(qps_path)

    # Check the current OS
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
        logging.warning("Not having correct permissions will prevent Quarch Java Programs from launching.")
        logging.warning("Run \"python -m quarchpy.run permission_fix\" to fix this.")
        user_input = input("Would you like to use auto run this now? (Y/N)")
        if user_input.lower() == "y":
            fix_permissions()
            permissions, message = find_java_permissions()
            time.sleep(0.5)
            if permissions is False:
                logging.warning("Attempt to fix permissions was unsuccessful. Please fix manually.")
            else:
                logging.warning("Attempt to fix permissions was successful. Now continuing.")

    # Single or multiple QPS builds for each OS
    is_single_qps_build = True
    if is_single_qps_build: # One QPS to rule them all.
        qps_path = os.path.join(qps_path, "connection_specific", "QPS", "win-amd64", "qps.jar")
    else: # Different QPS.jar for each OS
        if current_os in "Windows":
            qps_path = os.path.join(qps_path, "connection_specific", "QPS", "win-amd64", "qps.jar")
        elif current_os in "Linux" and current_arch == "x86_64":
            qps_path = os.path.join(qps_path, "connection_specific", "QPS", "lin-amd64", "qps.jar")
        elif current_os in "Linux" and current_arch == "aarch64":
            qps_path = os.path.join(qps_path, "connection_specific", "QPS", "lin-arm64", "qps.jar")
        elif current_os in "Darwin" and current_arch == "x86_64":
            qps_path = os.path.join(qps_path, "connection_specific", "QPS", "mac-amd64", "qps.jar")
        elif current_os in "Darwin" and current_arch == "arm64":
            qps_path = os.path.join(qps_path, "connection_specific", "QPS", "mac-arm64", "qps.jar")
        else:  # default to windows
            qps_path = os.path.join(qps_path, "connection_specific", "QPS", "win-amd64", "qps.jar")

    # Change the working directory to the directory containing qps.jar
    os.chdir(os.path.dirname(qps_path))


    # OS dependency
    if current_os in "Windows":
        command = java_path + "\\win_amd64_jdk_jre\\bin\\java\" -jar qps.jar " + str(args)
    elif current_os in "Linux" and current_arch == "x86_64":
        command = java_path + "/lin_amd64_jdk_jre/bin/java\" -jar qps.jar " + str(args)
    elif current_os in "Linux" and current_arch == "aarch64":
        command = java_path + "/lin_arm64_jdk_jre/bin/java\" -jar qps.jar " + str(args)
    elif current_os in "Darwin" and current_arch == "x86_64":
        command = java_path + "/mac_amd64_jdk_jre/bin/java\" -jar qps.jar " + str(args)
    elif current_os in "Darwin" and current_arch == "arm64":
        command = java_path + "/mac_arm64_jdk_jre/bin/java\" -jar qps.jar " + str(args)
    else:  # default to windows
        command = java_path + "\\win_amd64_jdk_jre\\bin\\java\" -jar qps.jar " + str(args)

    if "-logging=ON" in str(args): #If logging to a terminal window is on then os.system should be used to keep a window open to view logging.
        if current_os in "Windows":
            process = subprocess.Popen(command,shell=True)
        else:
            # Add a hold command to keep the terminal open (useful for bash)
            command_with_pause = command + "; exec bash"
            process = subprocess.run(command_with_pause, shell=True)
    else:
        if sys.version_info[0] < 3:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        else:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, shell=True)

        startTime = time.time()
        while not isQpsRunning():
            time.sleep(0.2)
            _get_std_msg_and_err_from_QPS_process(process)
            if time.time() - startTime > timeout:
                os.chdir(current_dir)
                raise TimeoutError("QPS failed to launch within timelimit of " + str(timeout) + " sec.")
        logging.debug("QPS detected after " + str(time.time() - startTime) + "s")

        while not isQisRunning():
            if time.time() - startTime > timeout:
                raise TimeoutError(
                    "QPS did launch but QIS did not respond during the timeout time of " + str(timeout) + " sec.")
            time.sleep(0.2)
        logging.debug("QIS detected after " + str(time.time() - startTime) + "s")

    # return current working directory
    os.chdir(current_dir)
    return


def reader(stream, q, source, lock,stop_flag):
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
    while counter <= 3: # If 3 empty reads from the queue then move on to see if QPS is running.
        try:
            source, line = q.get(timeout=1)  # Wait for 1 second for new lines
            counter = 0
            if source == "stderr":
                logging.error(f"{source}: {line}")
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
            while len(sortedDevList) != len(devList):
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

