import os, sys
import datetime
import time, platform
from quarchpy.qis import isQisRunning, startLocalQis
from quarchpy.connection_specific.connection_QIS import QisInterface
from quarchpy.connection_specific.connection_QPS import QpsInterface
from quarchpy.user_interface import *
import subprocess
import logging


def isQpsRunning(host='127.0.0.1', port=9822, timeout=0):
    '''
    This func will return true if QPS is running with a working QIS connection. This is becuase
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


def startLocalQps(keepQisRunning=False, args=[]):
    if keepQisRunning:
        if not isQisRunning():
            startLocalQis()
    temp =""
    args = temp.join(args)

    QpsPath = os.path.dirname(os.path.abspath(__file__))
    QpsPath, junk = os.path.split(QpsPath)
    QpsPath = os.path.join(QpsPath, "connection_specific", "QPS", "qps.jar")

    current_direc = os.getcwd()

    os.chdir(os.path.dirname(QpsPath))

    command = "-jar \"" + QpsPath + "\""

    currentOs = platform.system()

    if (currentOs in "Windows"):
        command = "start /high /b javaw -Djava.awt.headless=true " + command +" " + str(args)
        os.system(command)
    elif (currentOs in "Linux"):
        if sys.version_info[0] < 3:
            os.popen2("java " + command + " 2>&1")
        else:
            os.popen("java " + command + " 2>&1")
    else:
        command = "start /high /b javaw -Djava.awt.headless=true " + command + " " + str(args)
        os.system(command)

    while not isQpsRunning():
        time.sleep(0.3)
        pass

    os.chdir(current_direc)


def closeQps(host='127.0.0.1', port=9822):
    myQps = QpsInterface(host, port)
    myQps.sendCmdVerbose("$shutdown")
    del myQps
    time.sleep(1) #needed as calling "isQpsRunning()" will throw an error if it ties to connect while shutdown is in progress.

def GetQpsModuleSelection(QpsConnection, favouriteOnly=True, additionalOptions=[], scan=True):

    printText("QPS scanning for devices")
    tableHeaders = ["Module"]
    # Request a list of all USB and LAN accessible power modules
    devList = QpsConnection.getDeviceList(scan=scan)
    if "no device" in devList[0].lower() or "no module" in devList[0].lower():
        favouriteOnly = False  # If no device found conPref wont match and will bugout

    # Removes rest devices
    devList = [x for x in devList if "rest" not in x]
    message = "Select a quarch module"

    if (favouriteOnly):
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

    return myDeviceID


'''
Legacy function to handle old scripts which call an adjustTime function to get QPS format time.
This is now done in the QPS module level, so this function returns a integer linux millisecond value
as per the old one
'''


def legacyAdjustTime(timestamp):
    return timestamp


'''
Simple function to convert a timestamp or Python datetime object into QPS format time
QPS requires time in mS with no decimal point, so this is converted here
'''


def toQpsTimeStamp(timestamp):
    """

    Returns the parameter passed as a valid qps timestamp
    Assumes

    # 1620817118182 - ACCEPTED value for QPS    - Milliseconds, 13 chars

    # 1620817126    - time.time() Value         - Seconds

    :param int/float/datetime: Timestamp, mS
    :return: int             : QPS valid time, mS
    """

    # Python datetime object
    if (type(timestamp) is datetime):
        newTime = time.mktime(timestamp.timetuple())
        return int(newTime * 1000)
    # If numeric, assume standard unix time in milliseconds
    elif (type(timestamp) is float or type(timestamp) is int):
        return int(timestamp)
    else:
        # Try if its a numeric value string first (assumed to be milliseconds)
        try:
            timestamp = float(timestamp)
            return int(timestamp)
        # Fall back to assuming a standard format time string
        except:
            newTime = time.mktime(datetime.datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S:%f").timetuple())
            return int(newTime * 1000)
