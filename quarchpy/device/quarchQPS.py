from quarchpy.device import quarchDevice
from quarchpy.qps import toQpsTimeStamp
from quarchpy.utilities.Version import Version
from quarchpy.user_interface.user_interface import requestDialog
import os, time, datetime, sys, logging

if sys.version_info[0] < 3:
    from StringIO import StringIO
else:
    from io import StringIO

current_milli_time = lambda: int(round(time.time() * 1000))
current_second_time = lambda: int(round(time.time()))


# Using standard Unix time,  milliseconds since the epoch (midnight 1 January 1970 UTC)
# Should avoid issues with time zones and summer time correction but the local and host
# clocks should still be synchronised
def qpsNowStr():
    return current_milli_time()  # datetime supports microseconds


class quarchQPS(quarchDevice):
    def __init__(self, quarchDevice):
        self.quarchDevice = quarchDevice
        self.ConType = quarchDevice.ConType
        self.ConString = quarchDevice.ConString

        self.connectionObj = quarchDevice.connectionObj
        self.IP_address = quarchDevice.connectionObj.qps.host
        self.port_number = quarchDevice.connectionObj.qps.port

    def startStream(self, directory, unserInput=True):
        """
        directory - str - desired stream dir
        unserInput=True - if a failure occurs userInput=True allows user to rectify problem with user input. set to False if user interaction is not available (automating).
        """
        time.sleep(1)  # TODO remove this sleep once script->QPS timeing issue resolved. This works fine in the meantime
        return quarchStream(self.quarchDevice, directory, unserInput)


class quarchStream:
    def __init__(self, quarchQPS, directory, unserInput=True):
        self.connectionObj = quarchQPS.connectionObj
        self.IP_address = quarchQPS.connectionObj.qps.host
        self.port_number = quarchQPS.connectionObj.qps.port
        self.ConString = quarchQPS.ConString
        self.ConType = quarchQPS.ConType
        time.sleep(1)
        response = self.startQPSStream(directory)
        if not "fail:" in response.lower():
            return
        else:
            if unserInput is False:
                raise Exception(response)
            else:
                self.failCheck(response)

    def startQPSStream(self, newDirectory):
        '''STARTS the stream '''
        response = self.connectionObj.qps.sendCmdVerbose("$start stream \"" + str(newDirectory) + "\"")
        if "Error" in response:
            response = self.connectionObj.qps.sendCmdVerbose("$start stream " + str(newDirectory))
        return response

    def failCheck(self, response):
        ''' handles failed starting of stream that requires input from user to fix.'''
        while "fail:" in response.lower():
            if "Fail: Directory already exists" in response:
                newDir = requestDialog(message=response+"  Please enter a new file name:")
                response = self.startQPSStream(newDir)
            else:  # If its a failure we don't know how to handle.
                raise Exception(response)
        return response

    def get_stats(self, format="df"):
        """
                      Returns the QPS annotation statistics grid information as a pandas dataframe object

                                  Returns
                                  -------
                                  df = : dataframe
                                      The response text from QPS. If successful "ok. Saving stats to : file_name" otherwise returns the exception thrown
        """
        command_response = self.connectionObj.qps.sendCmdVerbose("$get stats", timeout=60).strip()
        if command_response.startswith("Fail"):
            raise Exception(command_response)

        if format == "df":
            try:
                import warnings
                import pandas as pd
                warnings.simplefilter(action='ignore', category=FutureWarning)
            except Exception as e:
                logging.error(e)
                logging.warning("pandas not imported correctly. Continuing")
            pd.set_option('display.max_columns', None)
            pd.set_option('display.width', 1024)
            test_data = StringIO(command_response)

            # pandas.read_csv() replaced error_bad_lines with on_bad_lines from v1.3.0
            if Version.is_v1_ge_v2(pd.__version__, "1.3.0"):
                retVal = pd.read_csv(test_data, sep=",", header=[0, 1], on_bad_lines="skip")
            else:
                retVal = pd.read_csv(test_data, sep=",", header=[0, 1], error_bad_lines=False)
        elif format == "list":
            retVal = []
            for line in command_response.replace("\r\n", "\n").split("\n"):
                row = []
                for element in line.split(","):
                    row.append(element)
                retVal.append(row)

        return retVal

    def stats_to_CSV(self, file_name=""):
        """
        Saves the statistics grid to a csv file

                    Parameters
                    ----------
                    file-name= : str, optional
                        The absolute path of the file you would like to save the csv to. If left empty then a filename will be give.
                        Default location is the path of the executable.
                    Returns
                    -------
                    command_response : str or None

                        The response text from QPS. If successful "ok. Saving stats to : file_name" otherwise returns the exception thrown
        """
        command_response = self.connectionObj.qps.sendCmdVerbose("$stats to csv \"" + file_name + "\"", timeout=60)
        if command_response.startswith("Fail"):
            raise Exception(command_response)
        return command_response

    def get_custom_stats_range(self, start_time, end_time):
        """
                      Returns the QPS statistics information over a specific time ignoring any set annotations.

                                Parameters
                                ----------
                                start_time = : str
                                    The time in seconds you would like the stats to start this can be in integer or string format.
                                    or using the following format to specify daysDhours:minutes:seconds.milliseconds
                                    xxxDxx:xx:xx.xxxx
                                end_time = : str
                                    The time in seconds you would like the stats to stop this can be in integer or string format
                                    or using the following format to specify daysDhours:minutes:seconds.milliseconds
                                    xxxDxx:xx:xx.xxxx
                                Returns
                                -------
                                df = : dataframe
                                    The response text from QPS. If successful "ok. Saving stats to : file_name" otherwise returns the exception thrown
        """
        try:
            import warnings
            import pandas as pd
            warnings.simplefilter(action='ignore', category=FutureWarning)
        except:
            logging.warning("pandas not imported correctly")
        command_response = self.connectionObj.qps.sendCmdVerbose(
            "$get custom stats range " + str(start_time) + " " + str(end_time), timeout=60)
        if command_response.startswith("Fail"):
            raise Exception(command_response)
        test_data = StringIO(command_response)
        try:
            pd.set_option('display.max_columns', None)
            pd.set_option('display.width', 1024)
            # df = pd.read_csv(test_data, sep=",", header=[0,1])
            # pandas.read_csv() replaced error_bad_lines with on_bad_lines from v1.3.0
            if Version.is_v1_ge_v2(pd.__version__, "1.3.0"):
                df = pd.read_csv(test_data, sep=",", header=[0, 1], on_bad_lines="skip")
            else:
                df = pd.read_csv(test_data, sep=",", header=[0, 1], error_bad_lines=False)
        except Exception as e:
            logging.error("Unable to create pandas data frame from command response :" + str(command_response))
            raise e
        return df

    def takeSnapshot(self):
        """
                      Triggers QPS take snapshot function and saves it in the streams directory.
        """
        command_response = self.connectionObj.qps.sendCmdVerbose("$take snapshot")
        if command_response.startswith("Fail"):
            raise Exception(command_response)
        return (command_response)

    def getStreamState(self):
        """
                      Askes QPS for the stream status.
                      QPS stream state != Module stream state.
                      This is different from "rec stream?" cmd to the module as it will return "streaming" when the module is nolonger streaming but QPS is still receiveing stream data from the module.
                      ei the module has stopped streaming but is emptying the stream buffer.
        """
        command_response = self.connectionObj.qps.sendCmdVerbose("$stream state")
        if command_response.startswith("Fail"):
            raise Exception(command_response)
        return (command_response)

    def addAnnotation(self, title, annotationTime=0, extraText="", yPos="", titleColor="", annotationColor="",
                      annotationType="", annotationGroup=""):
        """
                    Adds a custom annotation to stream with given parameters.

                    Parameters
                    ----------
                    title= : str
                        The title appears next to the annotation in the stream
                    extraText= : str, optional
                        The additional text that can be viewed when selecting the annotation
                    yPos : str, optional
                        The percetange of how high up the screen the annotation should appear 0 is the bottom and 100 the top
                    titleColor : str, optional
                        The color of the text next to the annotation in hex format 000000 to FFFFFF
                    annotationColor : str, optional
                        The color of the annotation marker in hex format 000000 to FFFFFF
                    annotationGroup : str, optional
                        The group the annotation belongs to
                    annotationTime : int, optional
                        The time in milliseconds after the start of the stream at which the annotation should be placed. 0 will plot the annotation live at the most recent sample

                    Returns
                    -------
                    command_response : str or None

                        The response text from QPS. "ok" if annotation successfully added
            """
        annotationTime = str(annotationTime)
        annotationType = annotationType.lower()
        if annotationType == "" or annotationType == "annotation":
            annotationType = "annotate"
        elif annotationType == "comment":
            pass  # already in the correct format for command
        else:
            retString = "Fail annotationType must be 'annotation' or 'comment'"
            logging.warning(retString)
            return retString

        # If the function has already been passed the XML string to give to QPS
        if ("<<" in title.replace(" ", "")):
            annotationString = str(title)
        else:
            annotationString = "<"

            if annotationTime == "0":
                # Use current time
                annotationTime = qpsNowStr()
            elif (annotationTime.startswith("e")):
                pass
            else:
                # Convert timestamp to QPS format
                # annotationTime = toQpsTimeStamp(annotationTime)
                annotationTime = str(annotationTime)

            if title != "":
                annotationString += "<text>" + str(title) + "</text>"
            if extraText != "":
                annotationString += "<extraText>" + str(extraText) + "</extraText>"
            if yPos != "":
                annotationString += "<yPos>" + str(yPos) + "</yPos>"
            if titleColor != "":
                annotationString += "<textColor>" + str(titleColor) + "</textColor>"
            if annotationColor != "":
                annotationString += "<color>" + str(annotationColor) + "</color>"
            if annotationGroup != "":
                annotationString += "<userType>" + str(annotationGroup) + "</userType>"
            annotationString += ">"

        # command is sent on newline so \n needs to be chnaged to \\n which is changed back just before printing in qps.
        annotationString = annotationString.replace("\n", "\\n")
        logging.debug("Time sending to QPS:" + str(annotationTime))
        return self.connectionObj.qps.sendCmdVerbose(
            "$" + annotationType + " " + str(annotationTime) + " " + annotationString)

    def addComment(self, title, commentTime=0, extraText="", yPos="", titleColor="", commentColor="", annotationType="",
                   annotationGroup=""):
        # Comments are just annotations that do not affect the statistics grid.
        # This function was kept to be backwards compatible and is a simple pass through to add annotation.
        if annotationType == "":
            annotationType = "comment"
        return self.addAnnotation(title=title, annotationTime=commentTime, extraText=extraText, yPos=yPos,
                                  titleColor=titleColor, annotationColor=commentColor, annotationType=annotationType,
                                  annotationGroup=annotationGroup)

    def saveCSV(self, filePath, linesPerFile=None, cr=None, delimiter=None, timeout=60):
        """
            Saves the stream to csv file at specified location

            Parameters
            ----------
            filePath= : str
                The file path that ou would like the CSV file saved to.
            linesPerFile= : str, optional
                    The number of lines per CSV file. Can be any int number or "all"
            cr : bool, optional
                Whether the end of line terminator should include a carriage return.
            delimiter : str, optional
                The delimiter to be used by the csv file.
            timeout : str, otptional
                The timeout to wait for a response from QPS

            Returns
            -------
            command_response : str or None
                The response text from QPS. "ok" if command is successful or the stack trace if exception thrown
        """
        args = ""

        if linesPerFile != None:
            args += " -l" + str(linesPerFile)
        if cr != None:
            if cr is True:
                args += " -cyes"
            elif cr is False:
                args += " -cno"
        if delimiter != None:
            args += " -s" + delimiter

        # , filePath, linesPerFile, cr, delimiter
        return self.connectionObj.qps.sendCmdVerbose("$save csv \"" + filePath + "\" " + args, timeout=timeout)

    def createChannel(self, channelName, channelGroup, baseUnits, usePrefix):
        # Conditions to convert false / true inputs to specification input
        if usePrefix == False:
            usePrefix = "no"
        if usePrefix == True:
            usePrefix = "yes"

        return self.connectionObj.qps.sendCmdVerbose(
            "$create channel " + channelName + " " + channelGroup + " " + baseUnits + " " + usePrefix)

    def hideChannel(self, channelSpecifier):
        return self.connectionObj.qps.sendCmdVerbose("$hide channel " + channelSpecifier)

    def showChannel(self, channelSpecifier):
        return self.connectionObj.qps.sendCmdVerbose("$show channel " + channelSpecifier)

    def myChannels(self):
        return self.connectionObj.qps.sendCmdVerbose("$channels")

    def channels(self):
        return self.connectionObj.qps.sendCmdVerbose("$channels").splitlines()

    def stopStream(self):
        return self.connectionObj.qps.sendCmdVerbose("$stop stream")

    def stopStreamAndAllowBufferToEmpty(self, checkInterval=0.5):
        self.stopStream()
        streamState = self.getStreamState().lower()
        while "running" in streamState:
            logging.debug("Stream buffer still emptying: " + streamState)
            time.sleep(checkInterval)
            streamState = self.getStreamState().lower()
        logging.debug("QPS no longer Streaming: " + streamState)

    def hideAllDefaultChannels(self):

        # TODO query QPS / Device for all channel names and hide all of them
        # All Default Channels
        self.hideChannel("3.3v:voltage")
        self.hideChannel("3v3:voltage")
        self.hideChannel("5v:voltage")
        self.hideChannel("12v:voltage")
        self.hideChannel("3v3:current")
        self.hideChannel("3.3v:current")
        self.hideChannel("5v:current")
        self.hideChannel("12v:current")
        self.hideChannel("3v3:power")
        self.hideChannel("3.3v:power")
        self.hideChannel("5v:power")
        self.hideChannel("12v:power")
        self.hideChannel("tot:power")
        # Default PAM channels
        self.hideChannel("perst#:digital")
        self.hideChannel("wake#:digital")
        self.hideChannel("lkreq#:digital")
        self.hideChannel("smclk:digital")
        self.hideChannel("smdat:digital")

    # function to add a data point the the stream
    # time value will default to current time if none passed
    def addDataPoint(self, channelName, groupName, dataValue, dataPointTime=0, timeFormat="unix"):
        '''
        channelName - str
        groupName - str
        dataValue - int/float value of the data point
        dataPointTime=0 - time of the data point
        timeFormat="unix" - the format of the given time
        '''
        if dataPointTime == None or dataPointTime == 0:
            dataPointTime = qpsNowStr()
        else:
            dataPointTime = toQpsTimeStamp(dataPointTime)

        self.connectionObj.qps.sendCmdVerbose(
            "$stream data add " + channelName + " " + groupName + " " + str(dataPointTime) + " " + str(
                dataValue) + " " + timeFormat)
