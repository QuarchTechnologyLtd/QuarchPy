"""
Contains general functions for starting and stopping QIS processes
"""

import os, sys 
import time, platform
from threading import Thread, Lock, Event, active_count
from queue import Queue, Empty
from quarchpy.connection_specific.connection_QIS import QisInterface
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
    if qisRunning ==False:
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
    # Gathering Vars needed to build the command
    QisPath =os.path.dirname(os.path.abspath(__file__))
    QisPath,junk = os.path.split (QisPath)
    QisPath = os.path.join(QisPath, "connection_specific","QPS", "qis", "qis.jar")

    # Building the command
    # Process command prefix. Needed for headless mode, to support OSs with no system tray.
    if (headless == True or (args is not None and "-headless" in args)):
        cmdPrefix = "java -Djava.awt.headless=true"
    else:
        cmdPrefix = "java"
    # Process command suffix (additional standard options for QIS).
    if (terminal == True):
        cmdSuffix = " -terminal"
    else:
        cmdSuffix = ""
    if args is not None:
        for option in args:
            # Avoid doubling the terminal option
            if (option == "-terminal" and terminal == True):
                continue
            # Headless option is processed seperately as a java command
            if (option != "-headless"):
                cmdSuffix = cmdSuffix + " " + option
    # Find file path and change directory to Qis Location
    current_direc = os.getcwd() 
    os.chdir(os.path.dirname(QisPath))
    command = cmdPrefix+" -jar qis.jar"+cmdSuffix

    # Use the command and check QIS has launched
    if "-logging=ON" in str(args): #If logging to a terminal window is on then os.system should be used to view logging.
        os.system(command)
    else:
        if sys.version_info[0] < 3:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        else:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, shell=True)

        startTime = time.time() #Checks for Popen launch only
        while not isQisRunning():
            _get_std_msg_and_err_from_QIS_process(process)
            if time.time() - startTime > timeout:
                raise TimeoutError("QIS failed to launch within timelimit of " + str(timeout) + " sec.")
            pass


        if isQisRunningAndResponding(timeout=timeout):
            logDebug("QPS running and responding")
        else:
            logDebug("QIS running but not responding")

    #change directory back to start directory 
    os.chdir(current_direc)


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
    retVal=myQis.sendAndReceiveCmd(cmd = "$shutdown")
    myQis.disconnect()
    time.sleep(1)
    return retVal

#DEPRICATED
def GetQisModuleSelection (QisConnection):
    """
    Prints a list of modules for user selection
    
    .. deprecated:: 2.0.12
        Use the module selection functions of the QisInterface class instead
    """
    
    # Request a list of all USB and LAN accessible power modules
    devList = QisConnection.getDeviceList()
    # Removes rest devices
    devList = [ x for x in devList if "rest" not in x ]

    # Print the devices, so the user can choose one to connect to
    printText ("\n ########## STEP 1 - Select a Quarch Module. ########## \n")
    printText (' --------------------------------------------')
    printText (' |  {:^5}  |  {:^30}|'.format("INDEX", "MODULE"))
    printText (' --------------------------------------------')
        
    try:
        for idx in xrange(len(devList)):
            printText (' |  {:^5}  |  {:^30}|'.format(str(idx+1), devList[idx]))
            printText(' --------------------------------------------')
    except:
        for idx in range(len(devList)):
            printText (' |  {:^5}  |  {:^30}|'.format(str(idx+1), devList[idx]))
            printText(' --------------------------------------------')

    # Get the user to select the device to control
    try:
        moduleId = int(raw_input ("\n>>> Enter the index of the Quarch module: "))
    except NameError:
        moduleId = int(input ("\n>>> Enter the index of the Quarch module: "))

    # Verify the selection
    if (moduleId > 0 and moduleId <= len(devList)):
        myDeviceID = devList[moduleId-1]
    else:
        myDeviceID = None

    return myDeviceID

