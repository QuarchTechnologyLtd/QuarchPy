#!/usr/bin/env python
'''
This contains useful functions for Iometer automation with Quarch tools

########### VERSION HISTORY ###########

13/08/2018 - Andy Norrie    - First version, based on initial work from Pedro Leao
20/02/2023 - Matt Holsey    - Updating for App note overhaul, improving documentation
'''

'''
This function is normally called in a seperate thread and runs the Iometer process, using the given file name to
describe the tests to be carried out
'''

import time
import os
import subprocess
import threading
import multiprocessing as mp
from multiprocessing import Pipe
import csv
import datetime
import socket
import csv
import mmap
from quarchpy.iometer.gen_iometer_template import generate_iometer_template

try:
    # for Python 2.x
    from StringIO import StringIO
except ImportError:
    # for Python 3.x
    from io import StringIO

'''
Executes iometer within a seperate thread sub-process
'''
def runIOMeter(*fileName):

    time.sleep(1)

    filepassed = ""
    for value in fileName:
        filepassed = filepassed + value


    info = subprocess.STARTUPINFO()
    info.dwFlags = 1
    info.wShowWindow = 0

    runAsAdminCmd = "runas"
    
    proc = subprocess.Popen("IOmeter.exe /c "  + filepassed + " /r testfile.csv", stdout = subprocess.PIPE, stderr = subprocess.PIPE, startupinfo=info, shell=True)

    out, error = proc.communicate()

'''
Allows the given file to be iterated through, using a python 'generator' (allowing us to parse the IOmeter instant results file
'''
def followResultsFile (theFile):
    #thefile.seek(0,2)
    while True:
        line = theFile.readline()
        if not line:
            time.sleep(0.1)
            continue
        yield line


def processIometerInstResults(testName, myStream, userCallbacks):
    """
    This function follows the data accumulating from Iometer, in the instant results file, and
    processes it into QPS, adding annotationsa and custom channel data points as needed.

    This currently assumes that custom channels have been created for IOPS, Data and Response

    :param testName:
    :param myStream:
    :param userCallbacks:
    :return:
    """

    # Wait for the file to exist
    while(os.path.isfile("insttestfile.csv") == False):
        pass

    # Open the file for non-exclusive read
    resultsFile = open("insttestfile.csv", 'rb')
    
    # Attach the file iterator
    resultsIterator = followResultsFile (resultsFile)
    
    driveSpeed = ""
    fileSection = 0
    lineCount = 0
    lineCount2 = 0    
    sum_all_threads1 = 0
    sum_all_threads2 = 0
    sum_all_threads3 = 0
    testDescrip = "Undescribed Test"
    workerCount = 99999
    workerList = []
    resultsMap = {
        "IOPS": 0,
        "RATE": 0,
        "RESPONSE": 0,
    }

    # Loop through the lines generate from iometer output
    for dataLine in resultsIterator:
        f = StringIO (dataLine.decode ('utf-8'))
        lineCount = lineCount + 1           
        
        csvData = list(csv.reader (f))
        # Get the test description if there is one
        if (lineCount == 2):
           if (csvData[0][1] != ""):
               testDescrip = csvData[0][1]
        
        if (fileSection == 0 and csvData[0][0] != '\'Time Stamp'):            
            continue
        elif (fileSection == 0): 
            fileSection = 1
            continue

        if (fileSection == 1):            
            timeStamp =  csvData[0][0]

            # Call start of test callback
            if "TEST_START" in userCallbacks:
                userCallbacks["TEST_START"](myStream, timeStamp, testDescrip)
            
            fileSection = 2
            continue        

        if (fileSection == 2 and csvData[0][0] != 'TimeStamp'):            
            continue
        elif (fileSection == 2): 
            fileSection = 3
            continue

        if (fileSection == 3):
            lineCount2 += 1
            prevTimeStamp = timeStamp
            timeStamp =  csvData[0][0]
            if (timeStamp == '\'Time Stamp'):
                fileSection = 4
                continue

            # Track the workers we have seen (add up until we see the same worker again)
            if (workerCount == 99999):
                if (workerList.__contains__ (csvData[0][2]) == False):
                    workerList.append (csvData[0][2])
                else:
                    # Store worker count
                    workerCount = len(workerList)

                    # Get Data in correct units for QPS
                    sum_all_threads2 = sum_all_threads2*1000000
                    sum_all_threads3 = sum_all_threads3 / workerCount

                    # Process the current result
                    resultsMap["IOPS"] = sum_all_threads1
                    resultsMap["DATA_RATE"] = sum_all_threads2
                    resultsMap["RESPONSE_TIME"] = sum_all_threads3
                    # Call data callback
                    if "TEST_RESULT" in userCallbacks:
                        userCallbacks["TEST_RESULT"] (myStream, prevTimeStamp, resultsMap)                    
                
                    sum_all_threads1 = 0
                    sum_all_threads2 = 0
                    sum_all_threads3 = 0

            # Sum up the values from each worker
            dataValue1 = csvData[0][7]
            dataValue2 = csvData[0][13]
            dataValue3 = csvData[0][18]            
            sum_all_threads1 += float(dataValue1)
            sum_all_threads2 += float(dataValue2)
            sum_all_threads3 += float(dataValue3)
            
            if (lineCount2 % workerCount == 0):
                
                # Get Data in correct units for QPS
                sum_all_threads2 = sum_all_threads2*1000000
                sum_all_threads3 = sum_all_threads3 / workerCount

                resultsMap["IOPS"] = sum_all_threads1
                resultsMap["DATA_RATE"] = sum_all_threads2
                resultsMap["RESPONSE_TIME"] = sum_all_threads3
                if "TEST_RESULT" in userCallbacks:
                    userCallbacks["TEST_RESULT"] (myStream, prevTimeStamp, resultsMap)
                
                
                sum_all_threads1 = 0
                sum_all_threads2 = 0
                sum_all_threads3 = 0
                

        if (fileSection == 4):
            timeStamp =  csvData[0][0]
            # Call end of test callback
            if "TEST_END" in userCallbacks:
                userCallbacks["TEST_END"](myStream, timeStamp, testDescrip)
            
            #print ("TEST ENDED AT " + timeStamp)
            resultsFile.close ()               
            
            return

def generateIcfFromConf(confPath, driveInfo, managerName=socket.gethostname()):
    """
    Scans the given path for .conf files (ioMeter template files) and
    creates .icf files with the correct host and drive target information in place

    :param confPath: String         - Path to /conf
    :param driveInfo: Dictionary    - Dict with 3 keys: NAME, DRIVE, FW_REV
    :param managerName: String      - String of the current system name
    :return: N/A
    """

    configFiles = []
    fileCount = 0
    
    config_list = []
    
    # Scan through .conf files
    for file in os.listdir(confPath):
        if file.endswith(".conf"):
        
            confFilePath = os.path.join(confPath, file)
            icfFilePath = confFilePath.replace ('.conf', '.icf')

            # Delete any old icf file with the same name
            if os.path.exists(icfFilePath):
                os.remove(icfFilePath)        

            # Open the .conf file
            openFile = open (confFilePath)
            fileData = openFile.read ()
            openFile.close ()

            # Create the string modifications needed to set the correct target
            if driveInfo["FW_REV"]:
                newStr = str(driveInfo["DRIVE"]) +  ": \"" + str(driveInfo["NAME"]) + " " + str(driveInfo["FW_REV"]) + "\""
            else:
                newStr = str(driveInfo["DRIVE"]) +  ": \"" + str(driveInfo["NAME"]) + "\""

            oldStr = "[*TARGET*]"
            # Replace the string
            fileData = fileData.replace(str(oldStr),str(newStr))
            
            # Create the string modification to set the manager name
            newStr = managerName #+ "\n"
            oldStr = "[*MANAGER*]"
            fileData = fileData.replace(str(oldStr),str(newStr))

            # Write the text out to the final ICF file
            openFile = open (icfFilePath, 'a+')
            openFile.write (fileData)
            openFile.close ()
            
            # Increment file counter
            fileCount = fileCount + 1


def generateIcfFromCsvLineData(csvData, icfFilePath, driveInfo, managerName=socket.gethostname()):
    """
    Takes a CSV data dictionary and creates an .icf file at the given path. DriveInfo and optional manager name are
    used to specify the target and host within the file

    :param csvData: Dictionary      - Row read from CSV
    :param icfFilePath: String      - File path for the new file
    :param driveInfo: Dictionary    - Dict with 3 keys: NAME, DRIVE, FW_REV
    :param managerName: String      - Name of System
    """

    # Creating a temporary file
    templateFilePath = os.path.dirname(os.path.abspath(__file__)) + "\\IometerTemplate.dat"
    csvTestName = None
    csvWorkers = None
    csvRequestSize = None
    csvReadPer = None
    csvRandomPer = None
    csvRunTime = None
    accessSpecName = "quarch-autogenerated-spec"
    accessSpecString = ""
        
    # Get the required data from the CSV dictionary
    csvTestName = csvData["TEST_NAME"]
    csvWorkers =  csvData["WORKER_COUNT"]
    csvRequestSize = csvData["REQUEST_SIZE"]
    csvReadPer = csvData["READ_PER"]
    csvRandomPer = csvData["RANDOM_PER"]
    csvRunTime = csvData["RUN_TIME"]
    # Build the access spec string
    accessSpecString = "\t" + csvRequestSize + ",100," + csvReadPer + "," + csvRandomPer + ",0,1,0,0" 


    # Delete any old icf file with the same name
    if os.path.exists(icfFilePath):
        os.remove(icfFilePath)

    # If the iometer template is missing, generate a new one
    if not os.path.exists(templateFilePath):
        generate_iometer_template()

    # Open the template file and read the data
    openFile = open (templateFilePath)
    fileData = openFile.readlines ()
    openFile.close ()

    # Grabbing segments from template file
    workerData = fileData[51:72]
    workerData = "".join(workerData)
    fileData = fileData[:51]
    fileData = "".join(fileData)
    
    # Create the string modification to set the manager name
    newStr = managerName
    oldStr = "[*MANAGER*]"
    fileData = fileData.replace(str(oldStr),str(newStr))
        
    # Create the string modification to set access specification define
    newStr = "'Access specification name,default assignment\n\t" + accessSpecName + ",NONE\n'size,% of size,% reads,% random,delay,burst,align,reply\n" + accessSpecString
    oldStr = "[*ACCESS_SPEC_DEFINE*]"
    fileData = fileData.replace(str(oldStr),str(newStr))
        
    # Create the string modification to set the test name
    newStr = csvTestName
    oldStr = "[*TEST_NAME*]"
    fileData = fileData.replace(str(oldStr),str(newStr))
        
    # Create the string modification to set the run time
    newStr = csvRunTime
    oldStr = "[*TIME_SECS*]"
    fileData = fileData.replace(str(oldStr),str(newStr))
        
    # Create the string modification to set the test name
    newStr = csvRunTime
    oldStr = "[*TIME_SECS*]"
    fileData = fileData.replace(str(oldStr),str(newStr))

    
    # Create the string modifications needed to set the correct target
    if driveInfo["FW_REV"]:
        newStr = str(driveInfo["DRIVE"]) +  ": \"" + str(driveInfo["NAME"]) + " " + str(driveInfo["FW_REV"]) + "\""
    else:
        newStr = str(driveInfo["DRIVE"]) +  ": \"" + str(driveInfo["NAME"]) + "\""

    oldStr = "[*TARGET_1*]"
    # Replace the string
    workerData = workerData.replace(str(oldStr),str(newStr))

    oldStr = "[*SPEC_1*]"
    # Replace the string
    workerData = workerData.replace(str(oldStr),str(accessSpecName))

    for x in range(int(csvWorkers)):
        workerData0 = workerData

        oldStr = "[*WORKER_#*]"
        # Replace the string
        fileData = fileData + workerData0.replace(str(oldStr),str(x+1)) 
    
    finalString = "'End manager\n'END manager list\nVersion 1.1.0"

    # Write the text out to the final ICF file
    openFile = open (icfFilePath, 'a+')
    openFile.write (fileData + finalString)
    openFile.close ()



def readIcfCsvLineData(csvFileName, csvFileLine):
    """
    Reads the given CSV file which must be formatter for Iometer .icf data (One header, no blank rows).
    Reads the data into a dictionary
    """
    csvFilePath = os.getcwd() + "\\" + csvFileName
    # Open the file
    with open(csvFilePath, 'rt') as csvFile:
        # Use a CSV reader
        csvReader = csv.reader (csvFile, delimiter='\t')
        #Convert it to an iterable list
        csvReader = list(csvReader)
        # Get the header and data rows
        headerRow = csvReader[0]
        try:
            dataRow = csvReader[csvFileLine]
        except:
            return None, False

        
    # Init the data dictionary
    csvDataLine = {
        "TEST_NAME": None,
        "WORKER_COUNT": None,
        "REQUEST_SIZE": None,
        "READ_PER": None,
        "RANDOM_PER": None,
        "RUN_TIME": None,
    }
    
    # Fill dictionary in with the available columns
    csvDataLine.update(dict(zip(["TEST_NAME", "WORKER_COUNT", "REQUEST_SIZE", "READ_PER", "RANDOM_PER", "RUN_TIME"], dataRow)))

    return csvDataLine, True    
