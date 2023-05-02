"""
Contains general functions for starting and stopping QIS processes
"""

import os, sys 
import time, platform 
from quarchpy.connection_specific.connection_QIS import QisInterface 
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
 
def startLocalQis(terminal=False, headless=False, args=None):
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

    QisPath =os.path.dirname(os.path.abspath(__file__))
    QisPath,junk = os.path.split (QisPath)
    QisPath = os.path.join(QisPath, "connection_specific","QPS", "qis", "qis.jar")
    
    # Process command prefix (needed for headless mode)
    if (headless == True or (args is not None and "-headless" in args)):
        cmdPrefix = " -Djava.awt.headless=true "
    else:
        cmdPrefix = ""
        
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
    command = cmdPrefix + "-jar qis.jar"+cmdSuffix
    
    #different start for different OS 
    currentOs = platform.system()
    if (currentOs == "Windows"): 
        if(cmdSuffix == " -logging=ON"):
            command = "java " + command
        else: 
            command = "start /high /b javaw " + command      
        os.system(command)
    elif (currentOs == "Linux"):
        if sys.version_info[0] < 3:
            os.popen2("java " + command)
        else:
            os.popen("java " + command)
    else: 
        command = "start /high /b javaw " + command 
        os.system(command)

    #Qis needs a small time for startup
    time.sleep(2)

    #see if new instance of qis has started
    startTime = time.time()
    currentTime = time.time()
    timeout = 10
    while not isQisRunning():
        time.sleep(0.1)
        currentTime = time.time()
        if currentTime - startTime > timeout:
            raise TimeoutError("QIS failed to launch within timelimit of " +str(timeout) +" sec." )
            break
        pass
    
    #change directory back to start directory 
    os.chdir(current_direc) 

    #This prevents QIS being lanuched more that once by the same instance of quarchpy
    # try:
    #     startLocalQis.func_code = (lambda:None).func_code
    # except:
    #     startLocalQis.__code__ = (lambda:None).__code__

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
    print ("\n ########## STEP 1 - Select a Quarch Module. ########## \n")
    print (' --------------------------------------------')
    print (' |  {:^5}  |  {:^30}|'.format("INDEX", "MODULE"))
    print (' --------------------------------------------')
        
    try:
        for idx in xrange(len(devList)):
            print (' |  {:^5}  |  {:^30}|'.format(str(idx+1), devList[idx]))
            print(' --------------------------------------------')
    except:
        for idx in range(len(devList)):
            print (' |  {:^5}  |  {:^30}|'.format(str(idx+1), devList[idx]))
            print(' --------------------------------------------')

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
 
 
