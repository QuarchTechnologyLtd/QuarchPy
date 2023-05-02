# -*- coding: utf-8 -*-
"""
This module provides standard user interface elements to quarchpy functions, ensuring common style
and support for both terminal and TestCenter (quarch internal) execution
"""

# TODO: This class uses 'if' to switch between terminal and testcenter actions.  This is not good practice: The singleton factory should return an appropriate subclass which implements the testcenter OR terminal options 
# The entire module needs review and discussion

# Needed for python2 compatibility
# coding: utf-8
from __future__ import print_function

import traceback, sys, os, math, logging
from quarchpy.utilities import TestCenter
import time

class User_interface:
    """
    This class is a singleton pattern and provides common access to the user interace for user
    interaction.  The UI can be the terminal or TestCenter
    """

    instance = None

    class __user_interface:
        def __init__(self,ui):
            if ui in ["console","testcenter"]:
                self.selectedInterface = ui
            else:
                raise ValueError("requested ui type not valid")

    def __init__(self,ui):
        """
        """
    
        # if we haven't create a user_interface object before
        if not User_interface.instance:
            # create a user interface object with our selected interface type
            User_interface.instance = User_interface.__user_interface(ui)
        # otherwise change the existing user interface object to the new type
        else:
            User_interface.instance.selectedInterface = ui
'''Setup Logging'''
def setup_logging(logLevel):
    # check log file is present or writeable
    numeric_level = getattr(logging, logLevel.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError('Invalid log level: %s' % logLevel)
    logging.basicConfig(format='%(asctime)s.%(msecs)03d %(levelname)s {%(module)s} [%(funcName)s] %(message)s', datefmt='%Y-%m-%d,%H:%M:%S', level=numeric_level)

'''
def listSelection(title,message,selectionList)

    prompts the user to return a selection from the list
    if nice = False:
        selectionList format is a comma delimited string (key1=value1,key2=value2...)
        the function will return the selected key
    if nice = True:
        selectionList format is a list of lists containing each column value [["NAME1","DESCRIPTION1"],[["NAME2","DESCRIPTION2"]]]
        the function will return the selected list with the index in position 0 ["1","NAME1","DESCRIPTION1"]
    

    THIS IS MORE LIKE A DICTIONARY SELECTION FUNC THAT RETURNS THE KEY

'''
def listSelection(title="",message="",selectionList=[], additionalOptions = [], nice = False, tableHeaders=[], indexReq=True, align="l"):

    if User_interface.instance != None and User_interface.instance.selectedInterface == "testcenter":

        converted = False
        if type(selectionList) is list:
            converted = True
            tempSelectionListStringDict = ""
            for row in selectionList:
                tempSelectionListStringDict += str(row[0])+"="+str(row[1])+","
            selectionList = tempSelectionListStringDict[0:-1]

        retVal = TestCenter.testPoint("Quarch_Host.ShowGenericDialog", "Title=" + __formatForTestcenter(title),
                                "Message=" + __formatForTestcenter(message),
                                "ItemListString=" + __formatForTestcenter(selectionList),
                                "OptionListString=" + __formatForTestcenter(str(additionalOptions)));
        if converted:
            i=0
            for row in selectionList:
                i+=1
                if retVal == row[0] or retVal == row[1]:
                    retVal = [str(i)] + row

        return retVal

    else: #default mode console output

        #print message
        if message not in "":
            print(message)
        if nice is True:
            retVal = niceListSelection(selectionList, tableHeaders=tableHeaders, indexReq=indexReq, additionalOptions=additionalOptions, align=align)
            return retVal


        #split selection list into key=value pairs and print each value
        # first split on ','s into list of key=value pairs
        selectionList = selectionList.split(',')
        # then split each list item on '=' into a [key,value] list
        selectionList = [str(x).split("=") for x in selectionList]

        count=1
        for item in selectionList:
            # if list item has index and value print them
            if len(item)>1:
                print(str(count) + " - " + item[1])
            else:
                print(item[0])
            count += 1

        print("")
        # Request user selection
        while (True):
            if sys.version_info.major >= 3:
                userStr = input("Please select an option:\n>")
            else:
                userStr = raw_input("Please select an option:\n>")

            # Validate the response
            try:
                userNumber = int(userStr)
                if (userNumber <= len(selectionList) and userNumber >= 1):
                    break
            except:
                print ("INVALID SELECTION!")

        # return the key associated with this entry
        return selectionList[userNumber-1][0]

'''
niceListSelection
Takes in a 2D List and displays a table. Returns one list (row) 
Will take 2DList, 2DTuple, Dictionary and return a list element
'''
def niceListSelection(selectionList,title="",message="", tableHeaders=None, indexReq=True, additionalOptions = None, align="l"):
    # takes in a 2d list and display it with an index column for selection
    # get user input of selection
    # return 2d[selection]
    try:
        selectionList = selectionList.copy()
        additionalOptions =additionalOptions.copy()
        tableHeaders = tableHeaders.copy()
    except:
        pass

    if additionalOptions is not None and additionalOptions.__len__() > 0:
        if isinstance(additionalOptions, str):
            additionalOptions = additionalOptions.split(',')
        selectionList += additionalOptions


    if isinstance(selectionList,str):
        selectionList = selectionList.split(',')
    elif isinstance(selectionList, dict):
        selectionList = dictToList(selectionList)

    displayTable(selectionList, indexReq=indexReq, tableHeaders=tableHeaders, align=align)
    print("")
    # Request user selection
    while (True):
        if sys.version_info.major >= 3:
            userStr = input("Please select an option:\n>")
        else:
            userStr = raw_input("Please select an option:\n>")

        # Validate the response
        try:
            userNumber = int(userStr)
            if (userNumber <= len(selectionList) and userNumber >= 1):
                break
        except:
            print("INVALID SELECTION!")

    # return the key associated with this entry
    return selectionList[userNumber - 1]


'''
printText(text)

    prints out the specified text via the currently selected user interface

    arguments:
        text - a string of text, or a list of strings
        fillLine - If true print will cover the width of the screen (useful when using "\r" to write on the same line)
        terminalWidth - Width of terminal writing to
        fill - The character that will be used to fill the remaining space 
    

'''
def printText(text, fillLine=False, terminalWidth=100, fill=" ",**kwargs):

        if User_interface.instance != None and User_interface.instance.selectedInterface == "testcenter":
            # if line is not empty
            if text.strip()!="":
                TestCenter.testPoint ("Quarch_Host.LogComment","Message=" + __formatForTestcenter(text))

        else:
            if fillLine:
                text +=fill*(terminalWidth-len(text)) #TODO Split string at \n or \r\n make a list, add the line fill for each item,then add back the \n and \r\n and combine together again.
            if kwargs!= {}:
                print(text,**kwargs)
            else:
                print(text)
        return

'''
showDialog(title,message)
prints a message to the user and waits for acknowledgement
'''
def showDialog(message="",title=""):


        if User_interface.instance != None and User_interface.instance.selectedInterface == "testcenter":
            TestCenter.testPoint ("Quarch_Host.ShowDialog","Title=" + __formatForTestcenter(title),"Message=" + __formatForTestcenter(message))

        else:
            print(message)
            if sys.version_info.major >= 3:
                userStr = input("Press enter to continue\n>")
            else:
                userStr = raw_input("Press enter to continue\n>")


def showImage(title="", message="", imagePath=""):
    if User_interface.instance != None and User_interface.instance.selectedInterface == "testcenter":
        TestCenter.testPoint("Quarch_Host.ShowImageDialog", "Title=" + __formatForTestcenter(title),
                             "Message=" + __formatForTestcenter(message),
                             "ImagePath=" + __formatForTestcenter(imagePath))

    else:
        print("show image at " + str(imagePath))


'''
printProgressBar (iteration,total,prefix='',suffix='',decimals=1,length=100,fill='█')

    prints a text based progress bar

        iteration   - Required  : current iteration (Int)
        total       - Required  : total iterations (Int)
        prefix      - Optional  : prefix string (Str)
        suffix      - Optional  : suffix string (Str)
        decimals    - Optional  : positive number of decimals in percent complete (Int)
        length      - Optional  : character length of bar (Int)
        fill        - Optional  : bar fill character (Str)

'''
def progressBar (iteration, total,prefix = '', suffix = '', decimals = 1, fill = '█', fullWidth = 100):
    if iteration >=0 and total >0:

        if User_interface.instance != None and User_interface.instance.selectedInterface == "testcenter":
            TestCenter.testPoint ("Quarch_Host.ShowTaskProgress","Title=Task Progress", "Iteration="+str(int(iteration)), "Total="+str(int(total)));

        else:
            percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total)))
            length = fullWidth - (len(prefix)+len(suffix)+len(percent) +4) #the length of the bar must scale acording to anything else on the line

            filledLength = int(length * iteration // total)
            bar = fill * filledLength + '-' * (length - filledLength)
            print('%s|%s|%s%%%s' % (prefix, bar, percent, suffix), end = '\r')

            # Print New Line on Complete
            if iteration >= total:
                print()


'''
startTestBlock(text)
    prints out the specified text via the currently selected user interface
    arguments:
        text - a string of text, or a list of strings
'''
def startTestBlock(text):

        if User_interface.instance != None and User_interface.instance.selectedInterface == "testcenter":
            return TestCenter.beginTestBlock(__formatForTestcenter(text))

        else:
            print("")
            print("*** "+text+" ***")
            return True

'''
endTestBlock()
    finishes the current test block in testcenter, no action in console
'''
def endTestBlock(message="End test block"):

        if User_interface.instance != None and User_interface.instance.selectedInterface == "testcenter":
            return TestCenter.endTestBlock()
        else:            
            print("*** "+message+" *** \r\n")
            return

'''
logCalibrationResult(title,result)
This was a little naughty as its callibration specific. If you are looking for something without the report obj look at logSimpleResult() func.
'''
def logCalibrationResult(title,report):

    if User_interface.instance != None and User_interface.instance.selectedInterface == "testcenter":
        if report["result"]:
            TestCenter.testPoint("Quarch_Host.LogTestPoint", "Test=" + __formatForTestcenter(title), "Result=True",
                                 "Message=" + __formatForTestcenter(
                                     title) + " Passed, worst case: " + __formatForTestcenter(report["worst case"]))
            # add the report as comments
            for line in report["report"].splitlines():
                TestCenter.testPoint("Quarch_Host.LogComment", "Message=" + __formatForTestcenter(line))
            TestCenter.endTestBlock()
        else:

            TestCenter.testPoint("Quarch_Host.LogTestPoint", "Test=" + __formatForTestcenter(title), "Result=False",
                                 "Message=" + __formatForTestcenter(
                                     title) + " Failed, worst case: " + __formatForTestcenter(report["worst case"]))
            # add the report as comments
            for line in report["report"].splitlines():
                TestCenter.testPoint("Quarch_Host.LogComment", "Message=" + __formatForTestcenter(line))
            TestCenter.endTestBlock()

    else:
        if report["result"]:
            print("\t" + title + " Passed")
            print("\tworst case: " + report["worst case"])
        else:
            print("\t" + title + " Failed")
            print("")
            data =report["report"]
            print(data)

'''
storeResult(string)
'''
def storeResult(message):
    if User_interface.instance != None and User_interface.instance.selectedInterface == "testcenter":
        TestCenter.testPoint("Quarch_Internal.storeMessage", "Message=" + message)
    else:
        print(message)

'''
logsSimpleCalibrationResult(title,result)
PASS/FAIL ONLY
'''
def logSimpleResult(title,result):
    #printText("Result = "+str(result))
    if type(result)==str:
        if result.lower() in ['true', '1', 't', 'y', 'yes', 'pass']:
            result=True
        elif result.lower() in ['false','0','f','n','no','fail']:
            result=False
        else:
            raise ValueError("Result = "+result+" is not valid.")
    if User_interface.instance != None and User_interface.instance.selectedInterface == "testcenter":
        if result==True:
            TestCenter.testPoint("Quarch_Host.LogTestPoint", "Test=" + __formatForTestcenter(title), "Result=True",
                                 "Message=" + __formatForTestcenter(title))
        elif result==False:

            TestCenter.testPoint("Quarch_Host.LogTestPoint", "Test=" + __formatForTestcenter(title), "Result=False",
                                 "Message=" + __formatForTestcenter(title))
        else:
            title = "Result is bad format!  Title:" + str(title)+ " result: " +str(result)
            TestCenter.testPoint("Quarch_Host.LogTestPoint", "Test=" + __formatForTestcenter(title), "Result=False",
                                 "Message=" + __formatForTestcenter(title))
    else:

        if result==True:
            print("\t" + title + " Passed")
        elif result == False:
            print("\t" + title + " Failed")
        else:
            title = "Result is bad format!  Title:" + str(title)+ " result: " +str(result)
            print("\t" + title)

'''
logResults(test,notes)
'''
def logResults(test,notes):

        if User_interface.instance != None and User_interface.instance.selectedInterface == "testcenter":
            TestCenter.testPoint ("Quarch_Internal.ResultDialog","Test="+ __formatForTestcenter(test),"Notes=" + __formatForTestcenter(notes))

        else:
            print("\t" +test+": "+notes)

        return


'''
requestDialog(title, message)
'''
def requestDialog( title="", message = "", desiredType = None, minRange=None, maxRange=None, defaultUserInput=""):
    validValue = False
    if desiredType != None and desiredType.lower() == "string": #If "string" or None do the same thing. Default is string type.
        desiredType = None
    while validValue == False:
        if User_interface.instance != None and User_interface.instance.selectedInterface == "testcenter":

            userStr = TestCenter.testPoint("Quarch_Host.ShowRequestDialog","Title= " + __formatForTestcenter(title), "Message=" + __formatForTestcenter(message));

        else:  # default mode console output
            # Request user selection
            if message =="" and title!="":
                message=title
            if sys.version_info.major >= 3:
                userStr = input(message+"\n>")
            else:
                userStr = raw_input(message+"\n>")
        if userStr == "":
            userStr = defaultUserInput
        validValue = validateUserInput(userStr, desiredType, minRange, maxRange)

    return userStr
'''
Takes string checks if can cast to desired type and returns it as that type, can check if within range for ints and floats.
'''
def validateUserInput ( userStr, desiredType, minRange, maxRange):
    validValue = False
    if desiredType == None:
        validValue = True
    if desiredType == "float":
        try:
            userStr = float(userStr)
            if ((minRange != None and maxRange != None) and (userStr < minRange or userStr > maxRange)):
                validValue = False
            else:
                validValue = True
        except:
            pass

    elif desiredType == "int":
        try:
            userStr = int(userStr)
            if ((minRange != None and maxRange != None) and (userStr< minRange or userStr > maxRange)):
                validValue = False
            else:
                validValue = True
        except:
            pass
    elif desiredType == "path":
        if (os.path.isdir(userStr) == False):
            validValue = False
        else:
            validValue = True
    if validValue == False:
            printText ( str(userStr)+ " is not a valid " + str(desiredType))
            if minRange != None and maxRange != None:
                printText("Please enter a " + str(desiredType) + " between " + str(minRange) + " and " + str(maxRange))
            else:
                printText("Please enter a valid " + str(desiredType))
    return validValue

'''
Takes a string input of comma seperated ints or range of ints and converts it to an array of strings with padding if requested eg:
 2-5, 9,11,31-35  ->  002,003,004,005,009,011,031,032,033,034,035
intLength tells the function to zeo pad the int before returning it.
'''
def userRangeIntSelection(inputString, intLength=3 ):
    inputList = inputString.split(",")
    returnList=[]
    for item in inputList:
        if "-" in item:
            myRange = item.split("-")
            myRange = range(int(myRange[0]),int(myRange[1])+1)
            returnList.extend(myRange)
        else:
            if validateUserInput(item,"int",0,999):
                returnList.append(item)

    for i, item in enumerate(returnList):
        returnList[i] = str(item)
        if intLength != None:
            returnList[i] = returnList[i].zfill(intLength)
    return returnList


'''
Takes in a 2D List and displays a table.
Will take 2DList/Tuple. Will Process a Dictionary, 1DList/Tuple, CSV String
'''
def displayTable(tableData=[[""]], message="", tableHeaders=None, indexReq=False, printToConsole = True, align = "l"):
    retVal =""
    try:
        tableData=tableData.copy()
        if tableHeaders is not None: tableHeaders=tableHeaders.copy()
    except:
        pass
    if tableHeaders ==[]:
        tableHeaders =None
    if isinstance(tableData, str):
        tableData = tableData.split(',')
    elif isinstance(tableData, dict):
        tableData = dictToList(tableData)
    #Process list to make it into 2d list to display.
    try:
        if not isinstance(tableData[0], tuple) and not isinstance(tableData[0], list) and not isinstance(tableData[0], dict):
            tempList=list()
            for item in tableData:
                tempList.append(list([item]))
            tableData = tempList
    except:
        pass
    # print message
    if message != "":
        print(message)

    if indexReq:
        if tableHeaders is not None:
            tableHeaders.insert(0,"#")
        counter =1
        for rows in tableData:
            rows.insert(0,counter)
            counter+=1

    #calculate required column width for each column
    columnWidths = []
    itemLegnth = 0
    for row in range(len(tableData)):
        for column in range(len(tableData[row])):
            item = str(tableData[row][column])
            if item == None:
                item="NoneType"
                tableData[row][column] = item
            if item.__contains__("\r") or item.__contains__("\n"):
                item = item.replace("\r", "\\r").replace("\n","\\n")
                tableData[row][column] = item
            itemLegnth = len(str(item))
            try:
                if columnWidths[column] < itemLegnth:
                    columnWidths[column] = itemLegnth
            except:  # if null pointer
                columnWidths.append(itemLegnth)
    if tableHeaders is not None:
        index = 0
        for item in tableHeaders:
            itemLegnth = len(str(item))
            try:
                if columnWidths[index] < itemLegnth:
                    columnWidths[index] = itemLegnth
            except:  # if null pointer
                columnWidths.append(itemLegnth)
            index += 1

    #Calculate the edge to be displayed at the top and bottom
    topEdge = "+"
    middleEdge = "+"
    bottomEdge = "+"

    firstLoop = True
    for columnWidth in columnWidths:
        if firstLoop is False:
            topEdge += "+"
            middleEdge += "+"
            bottomEdge += "+"
        topEdge += "-" * (columnWidth + 2)
        middleEdge += "-" * (columnWidth + 2)
        bottomEdge += "-" * (columnWidth + 2)
        firstLoop = False

    topEdge = topEdge + "+"
    middleEdge = middleEdge + "+"
    bottomEdge = bottomEdge + "+"

    #Always add the top reguardless of table headers or not.
    retVal += topEdge + "\n"
    #Add table headers section
    if tableHeaders is not None:
        rowString = "|"
        index = 0
        for item in tableHeaders:
            spaces = (columnWidths[index] - len(str(item)) + 2)
            if align.lower() in "l":
                rowString += str(item) + " " * spaces + "|"
            elif align.lower() in "c":
                prefix =  " " * math.floor(spaces/2)
                suffix =  " " * math.ceil(spaces/2)
                rowString += prefix + str(item) + suffix + "|"
            elif align.lower() in "r":
                rowString += " " * spaces + str(item) + "|"
            index += 1
        retVal += rowString + "\n"
        retVal += middleEdge + "\n"
    #Add table data section
    for rowData in tableData:
        index = 0
        rowString = "|"
        for item in rowData:
            spaces = (columnWidths[index] - len(str(item)) + 2)
            if align.lower() in "l":
                rowString += str(item) + " " * spaces + "|"
            elif align.lower() in "c":
                prefix =  " " * math.floor(spaces/2)
                suffix =  " " * math.ceil(spaces/2)
                rowString += prefix + str(item) + suffix + "|"
            elif align.lower() in "r":
                rowString += " " * spaces + str(item) +  "|"

            index += 1
        retVal += rowString + "\n"
    retVal += bottomEdge
    if printToConsole: printText(retVal)
    return retVal

'''Converts dictionary to list'''
def dictToList(tableData):
    tempList = []
    tempEl = []
    for k, v in tableData.items():
        tempEl = []
        tempEl.append(v)
        tempEl.append(k)
        tempList.append(tempEl)
    tableData = tempList
    return tableData


def is_user_admin():
    if os.name == 'nt':
        import ctypes
        # WARNING: requires Windows XP SP2 or higher!
        try:
            # If == 1, user is running from elevated cmd prompt
            # printText(ctypes.windll.shell32.IsUserAnAdmin() == 1)
            return ctypes.windll.shell32.IsUserAnAdmin() == 1
        except:
            traceback.print_exc()
            return False
    elif os.name == 'posix':
        # Check for root on Posix
        return os.getuid() == 0
    else:
        raise RuntimeError("Unsupported operating system for this module: %s" % (os.name,))


'''
'''
def __formatForTestcenter(text):
    # escape special characters
    # turn \' to \\'s
    text = text.replace('\\','\\\\')
    #get rid of any alarms that may be included in console mode
    text = text.replace('\a', '')
    # replace line endings
    text = '|'.join(text.splitlines())
    return text
    
def get_check_valid_calPath(calPath, message="Enter the desired save path for the calibration report."):
    inputOK = False
    while inputOK is False:
        if (calPath is None):
            calPath = os.path.expanduser("~")
            calPath = requestDialog("Enter Report Path",
                                    message+" Leave blank to default to [" + calPath + "] :",
                                    desiredType="path", defaultUserInput=os.path.expanduser("~"))

        if (os.path.isdir(calPath) == False):
            printText("Supplied calibration path is invalid: " + calPath)
            inputOK = False
            calPath = None
        else:
            inputOK = True
    return calPath
    
def check_path_write_permissions(path, message="Please enter a valid path with write permissions: "):
    import tempfile, errno
    valid_path=False
    while valid_path==False:
        try:
            if path==None:
                path=""
            f = open(path+"\\tempFile.txt", "w")
            f.write("some text")
            f.flush()
            f.close()
            os.remove(path+"\\tempFile.txt")
            valid_path=True
        except OSError as e:
            if e.errno == errno.EACCES or e.errno == errno.EEXIST:  # 13 or 17
                path= requestDialog("No write permissions at path: \""+path+"\".   ",
                                    message,desiredType="path")
            else:
                e.filename = path
                raise e
    return path


# Deprecated version of the function, here for compatability only
# calls into the visual_sleep() function
def quarchSleep (sleepLength,updatePeriod=1,title=""):
    visual_sleep (sleepLength, updatePeriod, title)

def visual_sleep (sleepLength,updatePeriod=1,title=""):
    """
    Wrapper for sleep function that gives a visual indicator of the sleep time
    """
    if title !="":
        printText(title)
    startTime = time.time()
    currentTime = time.time()
    while(currentTime-startTime<sleepLength):
        progressBar(iteration=currentTime-startTime,total=sleepLength)
        time.sleep(updatePeriod)
        currentTime = time.time()
    progressBar(iteration=1,total=1) #show 100%
