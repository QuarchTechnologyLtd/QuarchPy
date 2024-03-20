import csv
import socket
import re
import time
import sys
import os
import datetime
import select
import threading
import math
import logging
import struct
from io import StringIO
from quarchpy.user_interface import *
import xml.etree.ElementTree as ET
from connection_specific.StreamChannels import StreamGroups


# QisInterface provides a way of connecting to a Quarch backend running at the specified ip address and port, defaults to localhost and 9722
class QisInterface:
    def __init__(self, host='127.0.0.1', port=9722, connectionMessage=True):
        self.host = host
        self.port = port
        self.maxRxBytes = 4096
        self.sock = None
        self.StreamRunSentSemaphore = threading.Semaphore()
        self.sockSemaphore = threading.Semaphore()
        self.stopFlagList = []
        self.listSemaphore = threading.Semaphore()
        self.deviceList = []
        self.deviceDict = {}
        self.dictSemaphore = threading.Semaphore()
        self.connect(connectionMessage = connectionMessage)
        self.stripesEvent = threading.Event()

        self.qps_stream_header = None
        self.qps_record_dir_path = None
        self.qps_record_start_time = None
        self.qps_stream_folder_name = None

        self.module_xml_header = None
        self.streamGroups = None
        self.has_digitals = False
        self.is_multirate = False

        self.streamSock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.streamSock.settimeout(5)
        self.streamSock.connect((self.host, self.port))
        self.pythonVersion = sys.version[0]
        self.cursor = '>'
        #clear packets
        welcomeString = self.streamSock.recv(self.maxRxBytes).rstrip()


    def connect(self, connectionMessage = True):
        '''
        Connect() tries to open a socket  on the host and port specified in the objects variables
        If successful it returns the backends welcome string. If it fails it returns a string saying unable to connect
        The backend should be running and host and port set before running this function. Normally it should be called at the beggining
        of talking to the backend and left open until finished talking when the disconnect() function should be ran

        Param:
        connectionMessage: boolean, optional
            Set to False if you don't want a warning message to appear when an instance is already running on that port. Useful when using isQisRunning() from qisFuncs
        '''
        try:
            self.deviceDictSetup('QIS')
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(5)
            self.sock.connect((self.host, self.port))

            #clear packets
            try:
                welcomeString = self.sock.recv(self.maxRxBytes).rstrip()
                welcomeString = 'Connected@' + str(self.host) + ':' + str(self.port) + ' ' + '\n    ' + str(welcomeString)
                self.deviceDict['QIS'][0:3] = [False, 'Connected', welcomeString]
                return welcomeString
            except Exception as e:
                logging.error('No welcome received. Unable to connect to Quarch backend on specified host and port (' + self.host + ':' + str(self.port) + ')')
                logging.error('Is backend running and host accessible?')
                self.deviceDict['QIS'][0:3] = [True, 'Disconnected', 'Unable to connect to QIS']
                raise e
        except Exception as e:
            self.deviceDictSetup('QIS')
            if connectionMessage:
                logging.error('Unable to connect to Quarch backend on specified host and port (' + self.host + ':' + str(self.port) + ').')
                logging.error('Is backend running and host accessible?')
            self.deviceDict['QIS'][0:3] = [True, 'Disconnected', 'Unable to connect to QIS']
            raise e
    
    # Tries to close the socket to specified host and port.
    def disconnect(self):
        res = 'Disconnecting from backend'
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
            self.sock.close()
            self.deviceDict['QIS'][0:3] = [False, "Disconnected", 'Successfully disconnected from QIS']
        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            message = 'Unable to end connection. ' + self.host + ':' + str(self.port) + ' \r\n' + str(exc_type) + ' ' + str(fname) + ' ' + str(exc_tb.tb_lineno)
            self.deviceDict['QIS'][0:3] = [True, "Connected", message]
            raise e
        return res

    def closeConnection(self, sock=None, conString=None):
        if sock == None:
            sock = self.sock
        if conString is None:
           cmd="close"
        else:
            cmd =conString+" close"

        response = self.sendAndReceiveText(sock, cmd)
        return response

    def startStream(self, module, fileName, fileMaxMB, streamName, streamAverage, releaseOnData, separator, streamDuration = None, inMemoryData = None):
        self.StreamRunSentSemaphore.acquire()
        self.deviceDictSetup('QIS')
        i = self.deviceMulti(module)
        self.stopFlagList[i] = True
        self.stripesEvent.set()
        self.module_xml_header = None

        # Create the thread
        t1 = threading.Thread(target=self.startStreamThread, name=module,
                              args=(module, fileName, fileMaxMB, streamName, streamAverage, releaseOnData, separator, streamDuration, inMemoryData))
        # Start the thread
        t1.start()

        # count = 0
        while (self.stripesEvent.is_set()):
            # count += 1                         --debugging to show delay
            pass
            # just wait until event is cleared

    def startStreamQPS(self, module, fileName, fileMaxMB, streamName, streamAverage, releaseOnData, separator):
        self.StreamRunSentSemaphore.acquire()
        self.deviceDictSetup('QIS')
        i = self.deviceMulti(module)
        self.stopFlagList[i] = True
        self.stripesEvent.set()
        self.module_xml_header = None

        # Create the thread
        t1 = threading.Thread(target=self.startStreamThreadQPS, name=module,
                              args=(module, fileName, fileMaxMB, streamName, streamAverage, releaseOnData, separator))
        # Start the thread
        t1.start()

        # count = 0
        while (self.stripesEvent.is_set()):
            # count += 1                         --debugging to show delay
            pass
            # just wait until event is cleared

    def stopStream(self, module, blocking = True):
        moduleName=module.ConString
        i = self.deviceMulti(moduleName)
        self.stopFlagList[i] = False
        # Wait until the stream thread is finished before returning to user.
        # This means this function will block until the QIS buffer is emptied by the second while
        # loop in startStreanThread. This may take some time, especially at low averaging but
        # should gurantee the data won't be lost and QIS buffer is emptied.
        if blocking:
            running = True
            while running:
                threadNameList = []
                for t1 in threading.enumerate():
                    threadNameList.append(t1.name)
                moduleStreaming= module.sendCommand("rec stream?").lower() #checking if module thinks its streaming.
                moduleStreaming2= module.sendCommand("stream?").lower() #checking if the module has told qis it has stopped streaming.

                if (moduleName in threadNameList or "running" in moduleStreaming or "running" in moduleStreaming2):
                    time.sleep(0.1)

                else:
                    running = False
        time.sleep(0.1)

    def startStreamThread(self, module, fileName, fileMaxMB, streamName, streamAverage, releaseOnData, separator, streamDuration = None, inMemoryData = None):
        # This is the function that is run when t1 is created. It is run in a seperate thread from
        # the main application so streaming can happen without blocking the main application from
        # doing other things. Within this function/thread you have to be very careful not to try
        # and 'communicate'  with anything from other threads. If you do, you MUST use a thread safe
        # way of communicating. The thread creates it's own socket and should use that, NOT the objects socket
        # (which some of the comms with module functions will use by default).

        f = None
        #Start module streaming and then read stream data
        if inMemoryData is not None:
            if not isinstance(inMemoryData, StringIO):
                raise Exception ("Error! The parameter 'inMemoryData' is NOT of type StringIO")
            f = inMemoryData
        else:
            f = open(fileName, 'w')

        stripes = ['Empty Header']
        #Send stream command so module starts streaming data into the backends buffer
        streamRes = self.sendAndReceiveCmd(self.streamSock, 'rec stream', device=module, betweenCommandDelay = 0)
        #printText(streamRes)
        if ('rec stream : OK' in streamRes):
            if (releaseOnData == False):
                self.StreamRunSentSemaphore.release()
                self.stripesEvent.clear()
            self.deviceDict[module][0:3] = [False, 'Running', 'Stream Running']
        else:
            self.StreamRunSentSemaphore.release()
            self.stripesEvent.clear()
            self.deviceDict[module][0:3] = [True, 'Stopped', module + " couldn't start because " + streamRes]
            return

        baseSamplePeriod = self.streamHeaderAverage(device=module, sock=self.streamSock)
        count=0
        maxTries=10
        while 'Header Not Available' in baseSamplePeriod:
            baseSamplePeriod = self.streamHeaderAverage(device=module, sock=self.streamSock)
            time.sleep(0.1)
            count += 1
            if count > maxTries:
                self.deviceDict[module][0:3] = [True, 'Stopped', 'Header not available']
                exit()
        version =  self.streamHeaderVersion(device=module, sock=self.streamSock)
        timeStampHeader = datetime.datetime.now().strftime("%H:%M:%S:%f %d/%m/%y")
        formatHeader = self.streamHeaderFormat(device=module, sock=self.streamSock)
        formatHeader = formatHeader.replace(", ", separator)
        f.write(formatHeader + '\n')

        numStripesPerRead = 4096
        maxFileExceeded = False
        openAttempts = 0
        leftover = 0
        remainingStripes = []
        streamOverrun = False
        streamComplete = False

        # baseSamplePeriod is a string in the form [int][unit]
        # where the unit can be S,mS,uS,nS
        # we need to convert it to a float number of seconds
        # and we also derive the baseSampleUnits in string and numeric form
        if 'ns' in baseSamplePeriod.lower():
            baseSampleUnitText = 'ns'
            baseSampleUnitExponent = -9
        elif 'us' in baseSamplePeriod.lower():
            baseSampleUnitText = 'us'
            baseSampleUnitExponent = -6
        elif 'ms' in baseSamplePeriod.lower():
            baseSampleUnitText = 'ms'
            baseSampleUnitExponent = -3
        elif 'S' in baseSamplePeriod.lower():
            baseSampleUnitText = 's'
            baseSampleUnitExponent = 0
        else:
            raise ValueError("couldn't decode samplePeriod")

        baseSamplePeriodS = int(re.search('^\d*\.?\d*', baseSamplePeriod).group())*(10**baseSampleUnitExponent)        

        # # TODO: MD Thinks this implements software averaging, is unused and now performed in QIS
        # if streamAverage != None:
        #     #Matt converting streamAveraging into number
        #     streamAverage = self.convertStreamAverage(streamAverage)
        #     stripesPerAverage = float(streamAverage) / (float(baseSamplePeriodS) * 4e-6)
        if inMemoryData is None:
            f = open(fileName, 'a', newline='') #changed from ab to a as all data should be in string format now regardless of py2 or py3
        isRun = True
        while isRun:
            try:
                # Until the event threadRunEvent is set externally to this thread,
                # loop and read from the stream
                i = self.deviceMulti(module)
                while self.stopFlagList[i] and (not streamOverrun) and (not streamComplete):
                    #now = time.time()
                    streamOverrun, removeChar, newStripes = self.streamGetStripesText(self.streamSock, module, numStripesPerRead)
                    newStripes = newStripes.replace(' ', separator)
                    if streamOverrun:
                        self.deviceDict[module][0:3] = [True, 'Stopped', 'Device buffer overrun']
                    # TODO: MD Why don't we return isEmpty in the tuple, instead of having this confusing test?
                    if (removeChar == -6 and len(newStripes) == 6):
                        isEmpty = True
                    else:
                        isEmpty = False
                    if isEmpty == False:
                        #Writes in file if not too big else stops streaming
                        if fileName is not None:
                            statInfo = os.stat(fileName)
                            fileMB = statInfo.st_size / 1048576
                        else:
                            fileMB = 1
                        try:
                            int(fileMaxMB)
                        except:
                            continue
                        if int(fileMB) < int(fileMaxMB):
                            if (releaseOnData == True):
                                self.StreamRunSentSemaphore.release()
                                self.stripesEvent.clear()
                                releaseOnData = False
                            # TODO: MD Thinks this implements software averaging, is unused and now performed in QIS where required
                            if(streamAverage != None):
                                leftover, remainingStripes = self.averageStripes(leftover, stripesPerAverage, newStripes[:removeChar], f, remainingStripes)
                            else:
                                # if we have a fixed streamDuration
                                if streamDuration != None:
                                    # Get the last data line in the file
                                    lastLine = newStripes.splitlines()[-3]    # the last data line is followed by 'eof' and '>'
                                    lastTime = lastLine.split(separator)[0] # get the first (time) entry

                                    # if the last entry is still within the required stream length, write the whole lot
                                    if int(lastTime) < int(streamDuration/(10**baseSampleUnitExponent)): # < rather than <= because we start at 0
                                        newStripes = newStripes.replace(' ', separator)
                                        f.write(newStripes[:removeChar])

                                    # else write each line individually until we have reached the desired endpoint
                                    else:
                                        for thisLine in newStripes.splitlines()[:-2]:
                                            lastTime = thisLine.split(separator)[0]
                                            if int(lastTime) < int(streamDuration/(10**baseSampleUnitExponent)):
                                                f.write(thisLine + '\r\n')  # Put the CR back on the end
                                            else:
                                                streamComplete = True
                                                break
                                else:
                                    newStripes = newStripes.replace(' ', separator)
                                    f.write(newStripes[:removeChar])

                        else:
                            maxFileExceeded = True
                            #printText('QisInterface file size exceeded  in loop 1- breaking')
                            maxFileStatus = self.streamBufferStatus(device=module, sock=self.streamSock)
                            f.write('Warning: Max file size exceeded before end of stream.\n')
                            f.write('Unrecorded stripes in buffer when file full: ' + maxFileStatus + '.')
                            self.deviceDict[module][0:3] = [True, 'Stopped', 'User defined max filesize reached']
                            break
                    else:
                        # there's no stripes in the buffer - it's not filling up fast -
                        # sleeps so we don't spam qis with requests (seems to make QIS crash)
                        # it might be clever to change the sleep time accoring to the situation
                        # e.g. wait longer with higher averaging or lots of no stripes in a row
                        time.sleep(0.1)
                        streamStatus = self.streamRunningStatus(device=module, sock=self.streamSock)
                        if streamOverrun:
                            #printText('QisInterface overrun - breaking')
                            break
                        elif "Stopped" in streamStatus:
                            self.deviceDict[module][0:3] = [True, 'Stopped', 'User halted stream']
                            break
                #printText('Left while 1')
                self.sendAndReceiveCmd(self.streamSock, 'rec stop', device=module, betweenCommandDelay = 0)
                streamState = self.sendAndReceiveCmd(self.streamSock, 'stream?', device=module, betweenCommandDelay=0)  # use "stream?" rather than "rec stream?" as it checks both QIS AND the device.
                while "stopped" not in streamState.lower():
                    logging.debug("waiting for stream? to return stopped")
                    time.sleep(0.1)
                    streamState = self.sendAndReceiveCmd(self.streamSock, 'stream?', device=module, betweenCommandDelay=0)  # use "stream?" rather than "rec stream?" as it checks both QIS AND the device.

                if (not streamOverrun) and (not maxFileExceeded):
                    self.deviceDict[module][0:3] = [False, 'Stopped', 'Stream stopped - emptying buffer']
                # print self.streamBufferStatus(device=module, sock=self.streamSock)
                if (not maxFileExceeded):
                    #If the backend buffer still has data then keep reading it out
                    #printText('Streaming stopped. Emptying data left in QIS buffer to file (' + self.streamBufferStatus(device=module, sock=self.streamSock) + ')')
                    streamOverrun, removeChar, newStripes = self.streamGetStripesText(self.streamSock, module, numStripesPerRead)
                    # TODO: Why don't we return isEmpty in the tuple, instead of having this confusing test?
                    if (removeChar == -6 and len(newStripes) == 6):
                        isEmpty = True
                    else:
                        isEmpty = False
                    while isEmpty == False: # if newStripes has length 6 then it only contains 'eof\r\n'
                        if inMemoryData is None:
                            statInfo = os.stat(fileName)
                            fileMB = statInfo.st_size / 1048576
                        else:
                            fileMB = 1
                        try:
                            int(fileMaxMB)
                        except:
                            continue
                        if int(fileMB) < int(fileMaxMB):
                            if streamComplete != True:
                                if(streamAverage != None):
                                    leftover, remainingStripes = self.averageStripes(leftover, stripesPerAverage, newStripes[:removeChar], f, remainingStripes)
                                else:
                                    newStripes = newStripes.replace(' ',separator)
                                    f.write(newStripes[:removeChar])
                        else:
                            if not maxFileExceeded:
                                maxFileStatus = self.streamBufferStatus(device=module,  sock=self.streamSock)
                                maxFileExceeded = True
                                self.deviceDict[module][0:3] = [True, 'Stopped', 'User defined max filesize reached']
                            break
                        #time.sleep(0.01) #reduce speed of loop to stop spamming qis
                        streamOverrun, removeChar, newStripes = self.streamGetStripesText(self.streamSock, module, numStripesPerRead, skipStatusCheck=True)
                        if removeChar == -6:
                            if len(newStripes) == 6:
                                isEmpty = True
                    if maxFileExceeded:
                        f.write(b'Warning: Max file size exceeded before end of stream.\n')
                        f.write(b'Unrecorded stripes in buffer when file full: ' + maxFileStatus + '.')
                        logging.warning('Max file size exceeded. Some data has not been saved to file: ' + maxFileStatus + '.')

                #printText('Stripes in buffer now: ' + self.streamBufferStatus(device=module, sock=self.streamSock))

                if streamOverrun:
                    self.deviceDict[module][0:3] = [True, 'Stopped', 'Device buffer overrun - QIS buffer empty']
                elif not maxFileExceeded:
                    self.deviceDict[module][0:3] = [False, 'Stopped', 'Stream stopped']
                time.sleep(0.2)
                isRun = False
            except IOError as err:
                #printText('\n\n!!!!!!!!!!!!!!!!!!!! IO Error in QisInterface !!!!!!!!!!!!!!!!!!!!\n\n')
                if inMemoryData is None:
                    f.close()
                time.sleep(0.5)
                openAttempts += 1
                if openAttempts > 4:
                    logging.error('\n\n!!!!!!!!!!!!!!!!!!!! Too many IO Errors in QisInterface !!!!!!!!!!!!!!!!!!!!\n\n')
                    raise err
            finally:
                if inMemoryData is None:
                    f.close()
                else:
                    inMemoryData = f

        # This is the function that is ran when t1 is created. It is ran in a seperate thread from
        # the main application so streaming can happen without blocking the main application from
        # doing other things. Within this function/thread you have to be very careful not to try
        # and 'communicate'  with anything from other threads. If you do, you MUST use a thread safe
        # way of communicating. The thread creates it's own socket and should use that NOT the objects socket
        # (which some of the comms with module functions will use by default).

    def startStreamThreadQPS(self, module, fileName, fileMaxMB, streamName, streamAverage, releaseOnData, separator):

        # Start module streaming and then read stream data
        # self.sendAndReceiveCmd(self.streamSock, 'stream mode resample 10mS', device=module, betweenCommandDelay=0)
        self.sendAndReceiveCmd(self.streamSock, 'stream mode header v3', device=module, betweenCommandDelay=0)
        self.sendAndReceiveCmd(self.streamSock, 'stream mode power enable', device=module, betweenCommandDelay=0)
        self.sendAndReceiveCmd(self.streamSock, 'stream mode power total enable', device=module, betweenCommandDelay=0)

        self.qps_record_start_time = time.time() * 1000

        stripes = ['Empty Header']
        # Send stream command so module starts streaming data into the backends buffer
        streamRes = self.sendAndReceiveCmd(self.streamSock, 'rec stream', device=module, betweenCommandDelay=0)
        # printText(streamRes)
        if ('rec stream : OK' in streamRes):
            if (releaseOnData == False):
                self.StreamRunSentSemaphore.release()
                self.stripesEvent.clear()
            self.deviceDict[module][0:3] = [False, 'Running', 'Stream Running']
        else:
            self.StreamRunSentSemaphore.release()
            self.stripesEvent.clear()
            self.deviceDict[module][0:3] = [True, 'Stopped', module + " couldn't start because " + streamRes]
            return

        # If recording to file then get header for file
        if (fileName is not None):

            baseSamplePeriod = self.streamHeaderAverage(device=module, sock=self.streamSock)
            count = 0
            maxTries = 10
            while 'Header Not Available' in baseSamplePeriod:
                baseSamplePeriod = self.streamHeaderAverage(device=module, sock=self.streamSock)
                time.sleep(0.1)
                count += 1
                if count > maxTries:
                    self.deviceDict[module][0:3] = [True, 'Stopped', 'Header not available']
                    exit()
            version = self.streamHeaderVersion(device=module, sock=self.streamSock)

        numStripesPerRead = 4096
        maxFileExceeded = False
        openAttempts = 0
        leftover = 0
        remainingStripes = []
        streamOverrun = False
        # if streamAverage != None:
        #     # Matt converting streamAveraging into number
        #     streamAverage = self.convertStreamAverage(streamAverage)
        #     stripesPerAverage = float(streamAverage) / (float(baseSamplePeriodS) * 4e-6)

        isRun = True

        self.create_dir_structure(module, fileName)

        while isRun:
            try:
                # with open(fileName, 'ab') as f:
                # Until the event threadRunEvent is set externally to this thread,
                # loop and read from the stream
                i = self.deviceMulti(module)
                while self.stopFlagList[i] and (not streamOverrun):
                    # now = time.time()
                    streamOverrun, removeChar, newStripes = self.streamGetStripesText(self.streamSock, module,
                                                                                      numStripesPerRead)
                    newStripes = newStripes.replace(' ',separator)

                    if streamOverrun:
                        self.deviceDict[module][0:3] = [True, 'Stopped', 'Device buffer overrun']
                    if (removeChar == -6 and len(newStripes) == 6):
                        isEmpty = True
                    else:
                        isEmpty = False
                    if isEmpty == False:
                        # Writes in file if not too big else stops streaming
                        # Writing multiple stripes
                        if "\r\n" in y:
                            y = y.split("\r\n")

                            if self.has_digitals:
                                # Write qps files for PAM
                                for stripes in y:
                                    if stripes:
                                        stripe = stripes.split(",")
                                        self.write_stripe_to_files_PAM(stripe)
                            else:
                                # Write qps files for PPM
                                for stripes in y:
                                    if stripes:
                                        stripe = stripes.split(",")
                                        self.write_stripe_to_files_HD(stripe)

                        else:
                            if self.has_digitals:
                                # Write qps files for PAM
                                for stripes in y:
                                    if stripes:
                                        stripe = stripes.split(",")
                                        self.write_stripe_to_files_PAM(stripe)
                            else:
                                # Write qps files for PPM
                                for stripes in y:
                                    if stripes:
                                        stripe = stripes.split(",")
                                        self.write_stripe_to_files_HD(stripe)


                    else:
                        # there's no stripes in the buffer - it's not filling up fast -
                        # sleeps so we don't spam qis with requests (seems to make QIS crash)
                        # it might be clever to change the sleep time accoring to the situation
                        # e.g. wait longer with higher averaging or lots of no stripes in a row
                        time.sleep(0.1)
                        streamStatus = self.streamRunningStatus(device=module, sock=self.streamSock)
                        if streamOverrun:
                            # printText('QisInterface overrun - breaking')
                            break
                        elif "Stopped" in streamStatus:
                            self.deviceDict[module][0:3] = [True, 'Stopped', 'User halted stream']
                            break

                # printText('Left while 1')
                self.sendAndReceiveCmd(self.streamSock, 'rec stop', device=module, betweenCommandDelay=0)
                # streamState = self.sendAndReceiveCmd(self.streamSock, 'stream?', device=module, betweenCommandDelay=0) # use "stream?" rather than "rec stream?" as it checks both QIS AND the device.
                # while "stopped" not in streamState.lower():
                #     logging.debug("waiting for stream? to contained stopped")
                #     time.sleep(0.1)
                #     streamState = self.sendAndReceiveCmd(self.streamSock, 'stream?', device=module,betweenCommandDelay=0)  # use "stream?" rather than "rec stream?" as it checks both QIS AND the device.

                isRun = False
            except IOError as err:
                # printText('\n\n!!!!!!!!!!!!!!!!!!!! IO Error in QisInterface !!!!!!!!!!!!!!!!!!!!\n\n')
                time.sleep(0.5)
                openAttempts += 1
                if openAttempts > 4:
                    logging.error(
                        '\n\n!!!!!!!!!!!!!!!!!!!! Too many IO Errors in QisInterface !!!!!!!!!!!!!!!!!!!!\n\n')
                    raise err

        self.create_index_file()
        if self.has_digitals:
            self.create_index_file_digitals()

        self.create_qps_file(module)

    def write_stripe_to_files_HD(self, stripe):
        # Cycle through items in stripe
        for index, item in enumerate(stripe):
            if index == 0:
                continue
            with open(os.path.join(self.qps_record_dir_path, "data000",
                                   "data000_00" + index - 1 + "_000000000"),
                      "a") as file1:#changed from ab to a as all data should be in string format now regardless of py2 or py3

                x = struct.pack(">d", int(item))
                # logging.debug(item, x)
                file1.write(x)

    def write_stripe_to_files_PAM(self, stripe):
        # Note to reader - List should be ordered 1>x on analogue and digitals
        counter = 0
        for group in self.streamGroups.groups:
            for i, channel in enumerate(group.channels):
                # incrementing here so we skip stripe[0] which is time
                counter += 1

                x = i
                while len(str(x)) < 3:
                    x = "0" + str(x)

                # Write all in group 0 to analogue
                if group.group_id == 0:

                    with open(os.path.join(self.qps_record_dir_path, "data000",
                                           "data000_"+x+"_000000000"),
                              "a") as file1:#changed from ab to a as all data should be in string format now regardless of py2 or py3
                        x = struct.pack(">d", int(stripe[counter]))
                        # logging.debug(item, x)
                        file1.write(x)
                else:
                    # Write all in group 1 to digital
                    with open(os.path.join(self.qps_record_dir_path, "data101",
                                           "data101_"+x+"_000000000"),
                              "a") as file1:#changed from ab to a as all data should be in string format now regardless of py2 or py3
                        x = struct.pack(">d", int(stripe[counter]))
                        # logging.debug(item, x)
                        file1.write(x)
    
    # Query the backend for a list of connected modules. A $scan command is sent to refresh the list of devices,
    # Then a wait occurs while the backend discovers devices (network ones can take a while) and then a list of device name strings is returned
    # The objects connection needs to be opened (connect()) before this is used
    def getDeviceList(self, sock=None):

        if sock == None:
            sock = self.sock
        devString = self.sendAndReceiveText(sock, '$list')
        devString = devString.replace('>', '')            
        devString = devString.replace(r'\d+\) ', '')
        devString = devString.split('\r\n')
        devString = filter(None, devString) #remove empty elements
        return devString

    def get_list_details(self, sock=None):
        if sock == None:
            sock = self.sock

        devString = self.sendAndReceiveText(sock, '$list details')
        devString = devString.replace('>', '')
        devString = devString.replace(r'\d+\) ', '')
        devString = devString.split('\r\n')
        devString = [x for x in devString if x]  # remove empty elements
        return devString

    def scanIP(QisConnection, ipAddress):
        """
        Triggers QIS to look at a specific IP address for a quarch module

        Parameters
        ----------
        QisConnection : QpsInterface
            The interface to the instance of QPS you would like to use for the scan.
        ipAddress : str
            The IP address of the module you are looking for eg '192.168.123.123'
        sleep : int, optional
            This optional variable sleeps to allow the network to scan for the module before allowing new commands to be sent to QIS.
        """

        logging.debug("Starting QIS IP Address Lookup at " + ipAddress)
        if not ipAddress.lower().__contains__("tcp::"):
            ipAddress = "TCP::" + ipAddress
        response = "No response from QIS Scan"
        try:
            response = QisConnection.sendCmd(cmd="$scan " + ipAddress, expectedResponse=True)
            # valid response is "Located device: 192.168.1.2"
            if "located" in response.lower():
                logging.debug(response)
                # return the valid response
                return response
            else:
                if "startup" not in response.lower():
                    logging.warning("No module found at " + ipAddress)
                    logging.warning(response)
                return response

        except Exception as e:
            logging.warning(e)
            if "startup" not in response.lower():
                logging.warning("No module found at " + ipAddress)

    def GetQisModuleSelection(self, favouriteOnly=True , additionalOptions=['rescan', 'all con types', 'ip scan'], scan=True):
        '''
        Fuction used to list the available deviced to QIS and present them to the user for selection.

        Returns myDeviceID - Str the connection string used to connect to the selected device.
        '''
        tableHeaders =["Modules"]
        ip_address = None
        favourite = favouriteOnly
        while True:
            printText("Scanning for modules...")
            if scan and ip_address is None:
                foundDevices = self.qis_scan_devices(scan=scan, favouriteOnly=favourite)
            elif scan and ip_address is not None:
                foundDevices = self.qis_scan_devices(scan=scan, favouriteOnly=favourite, ipAddress=ip_address)

            myDeviceID = listSelection(title="Select a module",message="Select a module",selectionList=foundDevices,
                                       additionalOptions= additionalOptions, nice=True, tableHeaders=tableHeaders,
                                       indexReq=True)
            if myDeviceID.lower() == 'rescan':
                favourite = True
                ip_address = None
                continue
            elif myDeviceID.lower() == 'all con types':
                favourite = False
                printText("Displaying all connection types...")
                continue
            elif myDeviceID.lower() == 'ip scan':
                ip_address = requestDialog(title="Please input the IP Address you would like to scan")
                favourite = False
                continue
            break

        return myDeviceID

    def qis_scan_devices(self, scan=True, favouriteOnly=True, ipAddress=None):
        deviceList = []
        foundDevices = "1"
        foundDevices2 = "2"  # this is used to check if new modules are being discovered or if all have been found.
        scanWait = 2  # The number of seconds waited between the two scans.

        if scan:
            if ipAddress == None:
                devString = self.sendAndReceiveText(self.sock, '$scan')
            else:
                devString = self.sendAndReceiveText(self.sock, '$scan TCP::' + ipAddress)
            time.sleep(scanWait)
            while foundDevices not in foundDevices2:
                foundDevices = self.sendAndReceiveText(self.sock, '$list')
                time.sleep(scanWait)
                foundDevices2 = self.sendAndReceiveText(self.sock, '$list')
        else:
            foundDevices = self.sendAndReceiveText(self.sock, '$list')

        if not "no devices found" in foundDevices.lower():
            foundDevices = foundDevices.replace('>', '')
            #foundDevices = foundDevices.replace(r'\d\) ', '')
            # printText('"' + devString + '"')
            foundDevices = foundDevices.split('\r\n')
            #Can't stream over REST! Removing all REST connections.
            tempList= list()
            for item in foundDevices:
                if item is None or "rest" in item.lower() or item == "":
                    pass
                else:
                    tempList.append(item.split(")")[1].strip())
            foundDevices = tempList

            #If favourite only is True then only show one connection type for each module connected.
            #First order the devices in preference type and then pick the first con type found for each module.
            if (favouriteOnly):
                foundDevices = self.sortFavourite(foundDevices)
        else:
            foundDevices = ["***No Devices Found***"]

        return foundDevices

    def sortFavourite(self, foundDevices):
        index = 0
        sortedFoundDevices = []
        conPref = ["USB", "TCP", "SERIAL", "REST", "TELNET"]
        while len(sortedFoundDevices) != len(foundDevices):
            for device in foundDevices:
                if conPref[index] in device.upper():
                    sortedFoundDevices.append(device)
            index += 1
        foundDevices = sortedFoundDevices
        # new dictionary only containing one favourite connection to each device.
        favConFoundDevices = []
        index = 0
        for device in sortedFoundDevices:
            if (favConFoundDevices == [] or not device.split("::")[1] in str(favConFoundDevices)):
                favConFoundDevices.append(device)
        foundDevices = favConFoundDevices
        return foundDevices

    # Query stream status for a device attached to backend
    # The objects connection needs to be opened (connect()) before this is used
    def streamRunningStatus(self, device, sock=None):
        if sock == None:
            sock = self.sock
        index = 0 # index of relevant line in split string
        streamStatus = self.sendAndReceiveText(sock, 'stream?', device)
        streamStatus = streamStatus.split('\r\n')
        streamStatus[index] = re.sub(r':', '', streamStatus[index]) #remove :
        return streamStatus[index]

    # Query stream buffer status for a device attached to backend
    # The objects connection needs to be opened (connect()) before this is used
    def streamBufferStatus(self, device, sock=None):
        if sock == None:
            sock = self.sock
        index = 1 # index of relevant line in split string
        streamStatus = self.sendAndReceiveText(sock, 'stream?', device)
        streamStatus = streamStatus.split('\r\n')
        streamStatus[index] = re.sub(r'^Stripes Buffered: ', '', streamStatus[index])
        return streamStatus[index]
    
    # TODO: MD - This function should be replaced with a more generic method of accessing the header
    # The return of a string with concatenated value and units should be replaced with something easier to parse
    #
    # Get the averaging used on the last/current stream
    # The objects connection needs to be opened (connect()) before this is used
    def streamHeaderAverage(self, device, sock=None):
        try:
            if sock == None:
                sock = self.sock
            index = 2 # index of relevant line in split string
            streamStatus = self.sendAndReceiveText(sock, sentText='stream text header', device=device)

            self.qps_stream_header = streamStatus

            # Check for the header format.  If XML, process here
            if (self.isXmlHeader(streamStatus)):
                # Get the basic averaging rate (V3 header)
                xml_root = self.getStreamXmlHeader(device=device, sock=sock)

                # For QPS streaming, stream header v3 command has already been issued before this
                self.module_xml_header = xml_root

                # Return the time based averaging string
                device_period = xml_root.find('.//devicePeriod')
                if device_period == None:
                    device_period = xml_root.find('.//devicePerioduS')
                    if device_period == None:
                        device_period = xml_root.find('.//mainPeriod')
                averageStr = device_period.text
                return averageStr
            # For legacy text headers, process here
            else:
                streamStatus = streamStatus.split('\r\n')
                if('Header Not Available' in streamStatus[0]):
                    dummy = streamStatus[0] + '. Check stream has been run on device.'
                    return dummy
                streamStatus[index] = re.sub(r'^Average: ', '', streamStatus[index])
                avg = streamStatus[index]
                avg = 2 ** int(avg)
                return '{}'.format(avg)
        except Exception as e:
            logging.error(device + ' Unable to get stream average.' + self.host + ':' + str(self.port))
            raise e
    
    # Get the version of the stream and convert to string for the specified device
    # The objects connection needs to be opened (connect()) before this is used
    def streamHeaderVersion(self, device, sock=None):
        try:
            if sock == None:
                sock = self.sock
            index = 0 # index of relevant line in split string
            streamStatus = self.sendAndReceiveText(sock,'stream text header', device)
            streamStatus = streamStatus.split('\r\n')
            if 'Header Not Available' in streamStatus[0]:
                str = streamStatus[0] + '. Check stream has been ran on device.'
                logging.error(str)
                return str
            version = re.sub(r'^Version: ', '', streamStatus[index])
            if version == '3':
                version = 'Original PPM'
            elif version == '4':
                version = 'XLC PPM'
            elif version == '5':
                version = 'HD PPM'
            else:
                version = 'Unknown stream version'
            return version
        except Exception as e:
            logging.error(device + ' Unable to get stream version.' + self.host + ':' + str(self.port))
            raise e
    
    # Get a header string giving which measurements are returned in the string for the specified device
    # The objects connection needs to be opened (connect()) before this is used
    def streamHeaderFormat(self, device, sock=None):
        try:
            if sock == None:
                sock = self.sock
            index = 1 # index of relevant line in split string STREAM MODE HEADER [?|V1,V2,V3]
            streamStatus = self.sendAndReceiveText(sock,'stream text header', device)
            # Check if this is a new XML form header
            if (self.isXmlHeader (streamStatus)):
               # Get the basic averaging rate (V3 header)
               xml_root = self.getStreamXmlHeader (device=device, sock=sock)
               # Return the time based averaging string               
               device_period = xml_root.find('.//devicePeriod')
               time_unit = 'uS'
               if device_period == None:
                   device_period = xml_root.find('.//devicePerioduS')
                   if device_period == None:
                       device_period = xml_root.find('.//mainPeriod')
                       if ('ns' in  device_period.text):
                        time_unit = 'nS'
               averageStr = device_period.text
               
               # Time column always first
               formatHeader = 'Time ' + time_unit + ','
               # Find the channels section of each group and iterate through it to add the channel columns
               for group in xml_root.iter():
                   if (group.tag == "channels"):
                       for chan in group:
                        # Avoid children that are not named channels
                        if (chan.find('.//name') is not None):
                            nameStr = chan.find('.//name').text
                            unitStr = chan.find('.//units').text
                            formatHeader = formatHeader +  nameStr + " " + unitStr + ","
               return formatHeader
            # Handle legacy text headers here
            else:
                streamStatus = streamStatus.split('\r\n')
                if 'Header Not Available' in streamStatus[0]:
                    str = streamStatus[0] + '. Check stream has been ran on device.'
                    logging.error(str)
                    return str
                outputMode = self.sendAndReceiveText(sock,'Config Output Mode?', device)
                powerMode = self.sendAndReceiveText(sock,'stream mode power?', device)
                format = int(re.sub(r'^Format: ', '', streamStatus[index]))
                b0 = 1              #12V_I
                b1 = 1 << 1         #12V_V
                b2 = 1 << 2         #5V_I
                b3 = 1 << 3         #5V_V
                formatHeader = 'StripeNum, Trig, '
                if format & b3:
                    if ('3V3' in outputMode):
                        formatHeader = formatHeader +  '3V3_V,'
                    else:
                        formatHeader = formatHeader +  '5V_V,'
                if format & b2:
                    if ('3V3' in outputMode):
                        formatHeader = formatHeader +  ' 3V3_I,'
                    else:
                        formatHeader = formatHeader +  ' 5V_I,'
                
                if format & b1:
                    formatHeader = formatHeader + ' 12V_V,'
                if format & b0:
                    formatHeader = formatHeader + ' 12V_I'
                if 'Enabled' in powerMode:
                    if ('3V3' in outputMode):
                        formatHeader = formatHeader + ' 3V3_P'
                    else:
                        formatHeader = formatHeader + ' 5V_P'
                    if ((format & b1) or (format & b0)):
                        formatHeader = formatHeader + ' 12V_P'
                return formatHeader
        except Exception as e:
            logging.error(device + ' Unable to get stream  format.' + self.host + ':' + '{}'.format(self.port))
            raise e

    # Get stripes out of the backends stream buffer for the specified device using text commands
    # The objects connection needs to be opened (connect()) before this is used
    def streamGetStripesText(self, sock, device, numStripes=4096, skipStatusCheck=False):

        bufferStatus = False
        # Allows the status check to be skipped when emptying the buffer after streaming has stopped (saving time)
        if (skipStatusCheck == False):
            streamStatus = self.sendAndReceiveText(sock, 'stream?', device)
            if ('Overrun' in streamStatus) or ('8388608 of 8388608' in streamStatus):
                bufferStatus = True
        stripes = self.sendAndReceiveText(sock, 'stream text all', device, readUntilCursor=True)
#            time.sleep(0.001)
        if stripes[-1:] != self.cursor:
            return "Error no cursor returned."
        else:
            genEndOfFile = 'eof\r\n>'
            if stripes[-6:] == genEndOfFile:
                removeChar = -6
            else:
                removeChar = -1

        # stripes = stripes.split('\r\n')
        # stripes = filter(None, stripes) #remove empty sting elements
        #printText(stripes)
        return bufferStatus, removeChar, stripes

    def avgStringFromPwr(self, avgPwrTwo):
        if(avgPwrTwo==0):
            return '0'
        elif(avgPwrTwo==1):
            return '2'
        elif(avgPwrTwo > 1 and avgPwrTwo < 10 ):
            avg = 2 ** int(avgPwrTwo)
            return '{}'.format(avg)
        elif(avgPwrTwo==10):
            return '1k'
        elif(avgPwrTwo==11):
            return '2k'
        elif(avgPwrTwo==12):
            return '4k'
        elif(avgPwrTwo==13):
            return '8k'
        elif(avgPwrTwo==14):
            return '16k'
        elif(avgPwrTwo==15):
            return '32k'
        else:
            return 'Invalid Average Value'
    
    # TODO: MD Thinks this implements software averaging, is unused and now performed in QIS
    # Works out average values of timescales longer than max device averaging
    def averageStripes(self, leftover, streamAverage, newStripes, f, remainingStripes = []):
        newString = str(newStripes)
        newList = []
        if remainingStripes == []:
            newList = newString.split('\r\n')
        else:
            newList = remainingStripes
            newList.extend(newString.split('\r\n'))
        numElements = newList[0].count(' ') + 1
        streamTotalAverage = leftover + streamAverage
        splitList = [] * numElements
        if len(newList) < streamTotalAverage:
            remainingStripes = newList[:-1]
            return leftover, remainingStripes
        runningAverage = [0] * (len(newList[0].split(' ')) - 2)
        j = 0
        z = 1
        for i in newList[:-1]:
            splitList = i.split(' ')
            splitNumbers = [int(x) for x in splitList[2:]]
            runningAverage = [sum(x) for x in zip(runningAverage, splitNumbers)]
            if z == math.floor(streamTotalAverage):
                finalAverage = splitList[0:2] + [str(round(x / streamAverage)) for x in runningAverage]
                for counter in xrange(len(finalAverage)-1):
                    finalAverage[counter] = finalAverage[counter] + ' '
                for x in finalAverage:
                    f.write(x)
                f.write('\r\n')
                streamTotalAverage += streamAverage
                j += 1
            z += 1
        remainingStripes = newList[int(math.floor(j * streamAverage + leftover)):-1]
        leftover = (streamTotalAverage - streamAverage) % 1
        return leftover, remainingStripes

    def deviceMulti(self, device):
        if (device in self.deviceList):
            return self.deviceList.index(device)
        else:
            self.listSemaphore.acquire()
            self.deviceList.append(device)
            self.stopFlagList.append(True)
            self.listSemaphore.release()
            return self.deviceList.index(device)
    
    def deviceDictSetup(self, module):
        if module in self.deviceDict.keys():
            return
        elif module == 'QIS':
            self.dictSemaphore.acquire()
            self.deviceDict[module] = [False, 'Disconnected', "No attempt to connect to QIS yet"]
            self.dictSemaphore.release()
        else:
            self.dictSemaphore.acquire()
            self.deviceDict[module] = [False, 'Stopped', "User hasn't started stream"]
            self.dictSemaphore.release()
    
    def streamInterrupt(self):
        for key in self.deviceDict.keys():
            if self.deviceDict[key][0]:
                return True
        return False
    
    def interruptList(self):
        streamIssueList = []
        for key in self.deviceDict.keys():
            if self.deviceDict[key][0]:
                streamIssue = [key] 
                streamIssue.append(self.deviceDict[key][1])
                streamIssue.append(self.deviceDict[key][2])
                streamIssueList.append(streamIssue)
        return streamIssueList
    
    def waitStop(self):
        running = 1
        while running != 0:
            threadNameList = []
            for t1 in threading.enumerate():
                threadNameList.append(t1.name)
            running = 0
            for module in self.deviceList:
                if (module in threadNameList):
                    running += 1
                    time.sleep(0.5)
            time.sleep(1)

    def convertStreamAverage (self, streamAveraging):
        returnValue = 32000;
        if ("k" in streamAveraging):
            returnValue = streamAveraging.replace("k", "000")
        else:
            returnValue = streamAveraging

        return returnValue
        
    # Pass in a stream header and we check if it is XML or legacy format
    def isXmlHeader (self, headerText):
        if('?xml version=' not in headerText):
            return False;
        else:
            return True

    # Internal function.  Gets the stream header and parses it into useful information
    def getStreamXmlHeader (self, device, sock=None):
        try:
            if sock == None:
                sock = self.sock
            
            # Get the raw data
            headerData = self.sendAndReceiveText(sock, sentText='stream text header', device=device)

            # The XML can contain the cursor on the end!  Trap and remove it here TODO: Needs fixed in the command layer above
            if ('\r\n>' in headerData):
                headerData = headerData[:-1]
            
            # Check for no header (no stream started)
            if('Header Not Available' in headerData):
                logging.error(device + ' Stream header not available.' + self.host + ':' + str(self.port))
                return None;
                
            # Check for XML format
            if('?xml version=' not in headerData):
                logging.error(device + ' Header not in XML form.' + self.host + ':' + str(self.port))
                return None;
                
            # Parse XML into structured format
            xml_root = ET.fromstring(headerData)            
            
            # Check header format is supported by quarchpy
            versionStr = xml_root.find('.//version').text
            if ('V3' not in versionStr):
                logging.error(device + ' Stream header version not compatible: ' + xml_root['version'].text + '.' + self.host + ':' + str(self.port))
                raise Exception ("Stream header version not supported");
                
            # Return the XML structure for the code to use
            return xml_root
            
        except Exception as e:
            logging.error(device + ' Exception while parsing stream header XML.' + self.host + ':' + str(self.port))
            raise e

    def create_dir_structure(self, module, directory=None):
        """
        Creates the QPS directory structure and (empty) files to be written to

        I've put a bunch of try-except just to be sure the directory is correctly created.
        ( There's probably a better way of doing this than this )

        :param:    module: String  - Module string
        :param: directory: String  - Name of directory for QPS stream (defaults to default recording location if invalid)
        :return:  success: Boolean - Was the file structure created successfully?
        """

        directory = self.create_qps_directory(directory)

        digital_count = 0
        non_dig_counter = 0
        self.streamGroups = StreamGroups()
        for index, i in enumerate(self.module_xml_header.findall('.//channels')):
            self.streamGroups.add_group(index)
            for item in i.findall('.//channel'):
                self.streamGroups.groups[index].add_channel(item.find(".//name"), item.find(".//group"), item.find(".//dataPosition"))
                if item.find(".//group").text == "Digital":
                    digital_count += 1
                    self.has_digitals = True
                else:
                    non_dig_counter += 1

        # Inner folders for analogue and digital signals streaming
        in_folder_analogue = "data000"
        try:
            inner_path_analogues = os.path.join(directory, in_folder_analogue)
            os.mkdir(inner_path_analogues)
        except:
            logging.warning("Failed to make inner directory for analogue signals " + inner_path_analogues)
            return False

        in_folder_digitals = "data101"
        if self.has_digitals:
            try:
                inner_path_digitals = os.path.join(directory, in_folder_digitals)
                os.mkdir(inner_path_digitals)
            except:
                logging.warning("Failed to make inner directory for digital signals "+ inner_path_digitals)
                return False

        logging.debug("Steaming to : " + self.qps_record_dir_path)

        logging.debug("Creating qps data files")
        try:
            for i in range(non_dig_counter):
                file_name = "data000_00"+i+"_000000000"
                f = open(os.path.join(inner_path_analogues, file_name), "w")
                f.close()
            for i in range(digital_count):
                x = i
                while len(str(x)) < 3:
                    x = "0" + str(x)
                file_name = "data101_"+x+"_000000000"
                f = open(os.path.join(inner_path_digitals, file_name), "w")
                f.close()
        except:
            logging.warning("failed to create qps data files for analogue signals")
            return False

        logging.debug("Finished creating qps data files")

        logging.debug("Creating qps upper level files")
        try:
            file_names = ["annotations.xml", "notes.txt", "triggers.txt"]
            for file_nome in file_names:
                f = open(os.path.join(self.qps_record_dir_path, file_nome), "w")
                f.close()
        except Exception as err:
            logging.warning("failed to create qps upper level files, "+err)
            return False

        try:
            # Adding data000.idx separate as it's written in bytes not normal text
            f = open(os.path.join(self.qps_record_dir_path, "data000.idx"), "wb")
            f.close()
            if digital_count > 0:
                f = open(os.path.join(self.qps_record_dir_path, "data101.idx"), "wb")
                f.close()
        except Exception as err:
            logging.warning("failed to create data000.idx file, "+err)
            return False

        logging.debug("Finished creating QPS dir structure")

        return True

    def create_qps_directory(self, directory):
        folder_name = None
        # Checking if there was a directory passed; and if it's a valid directory
        if not directory:
            directory = os.path.join(os.path.expanduser("~"), "AppData", "Local", "Quarch", "QPS", "Recordings")
            logging.debug("No directory specified")
        elif not os.path.isdir(directory):
            new_dir = os.path.join(str(os.path.expanduser("~"), "AppData", "Local", "Quarch", "QPS", "Recordings"))
            logging.warning(directory+" was not a valid directory, streaming to default location: \n"+new_dir)
            directory = new_dir
        else:
            # Split the directory into a path of folders
            folder_name = str(directory).split(os.sep)
            # last folder name is the name we want
            folder_name = folder_name[-1]
            # Make it known to the entire class that the path we're streaming to is the one sent across by the user
            self.qps_record_dir_path = directory

        # If no folder name for the stream was passed, then default to 'quarchpy_recording' and a timestamp
        if not folder_name:
            folder_name = "quarchpy_recording"
            folder_name = folder_name + "-" + time.time()
            path = os.path.join(directory, self.qps_stream_folder_name)
            os.mkdir(path)
            self.qps_record_dir_path = path

        self.qps_stream_folder_name = folder_name

        return directory

    def create_index_file(self):
        """
        Create the necessary index file for QPS data000.idx

        For future revisions, this should be updated if there are file limits on each data file
        Current implementation assumes only 1 of each data file are made.

        No Return./
        """

        stream_header_size = -1

        my_byte_array = []

        # tree = ET.ElementTree(ET.fromstring(self.module_xml_header[:-1]))
        tree = self.module_xml_header

        return_b_array = []
        outBuffer = []
        x = 20
        stream_header_size = 20

        temp_dict = {"channels": 0}

        return_b_array, stream_header_size = self.add_header_to_byte_array(return_b_array, stream_header_size,
                                                                           temp_dict, tree, is_digital=False)

        self.add_header_to_buffer(outBuffer, return_b_array, stream_header_size, temp_dict)

        # Attempting to read the size of the first file in data files
        file = os.path.join(self.qps_record_dir_path, "data000", "data000_000_000000000")
        data = None
        with open(file, "rb") as f:
            data = f.read()  # if you only wanted to read 512 bytes, do .read(512)

        if not data:
            raise "No data written to file"

        num_records = len(data) / 8
        logging.debug("num_record = " + num_records)
        return_b_array.append(int(num_records).to_bytes(4, byteorder='big'))

        start_number = 0
        logging.debug("start_record = " + start_number)
        return_b_array.append(start_number.to_bytes(8, byteorder='big'))

        num_records = num_records - 1
        logging.debug("last_Record_number = "+num_records)
        return_b_array.append(int(num_records).to_bytes(8, byteorder='big'))

        # Add names of every file in data000 dir here.
        files = os.listdir(os.path.join(self.qps_record_dir_path, "data000"))
        for file3 in files:
            # print(file)
            item = strToBb(file3, False)
            # print(item)
            while len(item) < 32:
                item.append("\x00")
            # print(item)
            return_b_array.append(item)

        with open(os.path.join(self.qps_record_dir_path, "data000.idx"), "ab") as f:
            for item in outBuffer:
                # print(item)
                # print(type(item))
                f.write(bytes(item))
            # f.write(outBuffer)

        with open(os.path.join(self.qps_record_dir_path, "data000.idx"), "ab") as f:
            self.write_b_array_to_idx_file(f, return_b_array)

    def create_index_file_digitals(self):
        """
        Create the necessary index file for QPS data101.idx

        For future revisions, this should be updated if there are file limits on each data file
        Current implementation assumes only 1 of each data file are made.

        No Return.
        """

        stream_header_size = -1
        my_byte_array = []
        tree = self.module_xml_header
        return_b_array = []
        outBuffer = []
        temp_dict = {}

        return_b_array, stream_header_size = self.add_header_to_byte_array(return_b_array, stream_header_size,
                                                                           temp_dict, tree, is_digital=True)

        self.add_header_to_buffer(outBuffer, return_b_array, stream_header_size, temp_dict)

        # Attempting to read the size of the first file in data files
        file = os.path.join(self.qps_record_dir_path, "data101", "data101_000_000000000")
        data = None
        with open(file, "rb") as f:
            data = f.read()  # if you only wanted to read 512 bytes, do .read(512)

        if not data:
            raise "No data written to file"

        num_records = len(data) / 8
        logging.debug("num_record = "+ num_records)
        return_b_array.append(int(num_records).to_bytes(4, byteorder='big'))

        start_number = 0
        logging.debug("start_record = "+start_number)
        return_b_array.append(start_number.to_bytes(8, byteorder='big'))

        num_records = num_records - 1
        logging.debug("last_Record_number = "+ num_records)
        return_b_array.append(int(num_records).to_bytes(8, byteorder='big'))

        # Add names of every file in data000 dir here.
        files = os.listdir(os.path.join(self.qps_record_dir_path, "data101"))
        for file3 in files:
            # print(file)
            item = strToBb(file3, False)
            # print(item)
            while len(item) < 32:
                item.append("\x00")
            # print(item)
            return_b_array.append(item)

        with open(os.path.join(self.qps_record_dir_path, "data101.idx"), "ab") as f:
            for item in outBuffer:
                f.write(bytes(item))

        with open(os.path.join(self.qps_record_dir_path, "data101.idx"), "ab") as f:
            self.write_b_array_to_idx_file(f, return_b_array)

    def add_header_to_byte_array(self, return_b_array, stream_header_size, temp_dict, tree, is_digital=False):
        for element in tree:
            if "legacyVersion" in element.tag:
                intItem = element.text
                temp_dict[element.tag] = intItem
                # my_byte_array.append(int.to_bytes(intItem, 'big'))
            if "legacyAverage" in element.tag:
                intItem = element.text
                temp_dict[element.tag] = intItem
                # my_byte_array.append(int.to_bytes(intItem, 'big'))
            if "legacyFormat" in element.tag:
                intItem = element.text
                temp_dict[element.tag] = intItem
                # my_byte_array.append(int.to_bytes(intItem, 'big'))
            if "mainPeriod" in element.tag:
                intItem = element.text
                intItem = intItem[:-2]
                temp_dict[element.tag] = intItem
            if "channels" in element.tag:
                counter = 0
                for child in element:
                    for child2 in child:
                        if "group" in child2.tag:
                            if is_digital:
                                if str(child2.text).lower() == "digital":
                                    counter += 1
                            else:
                                if str(child2.text).lower() != "digital":
                                    counter += 1

                temp_dict[element.tag] = counter

                return_b_array = []

                stream_header_size = 20

                # Cycle through all the channels.
                for child in element:

                    if child.tag == "groupId":
                        continue

                    if is_digital:
                        # skip channel if we're only looking for digitals
                        if not str(child.find(".//group").text).lower() == "digital":
                            continue
                    else:
                        # skip if we're looking for analogues
                        if str(child.find(".//group").text).lower() == "digital":
                            continue

                    # my_byte_array.append(int.to_bytes(5, 'big'))
                    return_b_array.append(int(5).to_bytes(4, byteorder='big'))
                    stream_header_size += 4
                    name = None

                    for child2 in child:

                        if "group" in child2.tag:
                            my_byte_array = strToBb(str(child2.text))
                            return_b_array.append(my_byte_array)
                            # QPS index file requires name tag come after group tag.
                            return_b_array.append(name)
                            stream_header_size += len(my_byte_array)

                        if "name" in child2.tag:
                            my_byte_array = strToBb(str(child2.text))
                            name = my_byte_array
                            stream_header_size += len(my_byte_array)

                        if "units" in child2.tag:
                            my_byte_array = strToBb(str(child2.text))
                            return_b_array.append(my_byte_array)
                            stream_header_size += len(my_byte_array)

                            """
                            # Unclear if the only thing here is TRUE
                            bb = strToBB( Boolean.toString( cdr.isUsePrefixStr() ));
                            bbList.add(bb);
                            retVal += bb.capacity();
                            """
                            my_byte_array = strToBb(str("true"))
                            return_b_array.append(my_byte_array)
                            stream_header_size += len(my_byte_array)

                        if "maxTValue" in child2.tag:
                            my_byte_array = strToBb(str(child2.text))
                            return_b_array.append(my_byte_array)
                            stream_header_size += len(my_byte_array)

        return return_b_array, stream_header_size

    def add_header_to_buffer(self, outBuffer, return_b_array, stream_header_size, temp_dict):
        number = 2
        outBuffer.append(number.to_bytes(4, byteorder='big'))
        logging.debug("indexVersion : "+ number)

        number = 1 if self.has_digitals else 0
        outBuffer.append(number.to_bytes(4, byteorder='big'))
        logging.debug("value0 : "+ number)
        number = stream_header_size
        outBuffer.append(number.to_bytes(4, byteorder='big'))
        logging.debug("header_size : "+number)
        logging.debug("legacyVersion : "+ temp_dict['legacyVersion'])
        outBuffer.append(int(temp_dict["legacyVersion"]).to_bytes(4, byteorder='big'))
        logging.debug("legacyAverage : " + temp_dict['legacyAverage'])
        outBuffer.append(int(temp_dict["legacyAverage"]).to_bytes(4, byteorder='big'))
        logging.debug("legacyFormat : "+temp_dict['legacyFormat'])
        outBuffer.append(int(temp_dict["legacyFormat"]).to_bytes(4, byteorder='big'))
        logging.debug("mainPeriod : "+temp_dict['mainPeriod'])
        outBuffer.append(int(temp_dict["mainPeriod"]).to_bytes(4, byteorder='big'))
        logging.debug("channels : "+temp_dict['channels'])
        outBuffer.append(int(temp_dict["channels"]).to_bytes(4, byteorder='big'))
        return_b_array.append(int(self.qps_record_start_time).to_bytes(8, byteorder='big'))
        index_record_state = True
        logging.debug(int(1))
        return_b_array.append(int(1).to_bytes(1, byteorder='big'))
        record_type = 1
        logging.debug("record type : "+int(index_record_state))
        return_b_array.append(int(record_type).to_bytes(1, byteorder='big'))

    def write_b_array_to_idx_file(self, f, return_b_array):
        # print(return_b_array)
        for item in return_b_array:
            # print(item)
            if isinstance(item, int):
                # 'f.write(str(item).encode())
                # print(item)
                f.write(bytes([item]))
                continue
            if isinstance(item, bytes):
                # print(item)
                f.write(bytes(item))
                continue
            if isinstance(item, list):
                for character in item:
                    if isinstance(character, int):
                        f.write(bytes([character]))
                        continue
                    elif isinstance(item, bytes):
                        f.write(item)
                        continue
                    else:
                        f.write(str(character).encode())
                        continue

    def create_qps_file(self, module):
        """
        Creates the end QPS file that is used to open QPS

        :param module: Module QTL number that was used for the stream
        :return:
        """

        with open(os.path.join(self.qps_record_dir_path, self.qps_stream_folder_name + ".qps"), "w") as f:
            x = datetime.datetime.fromtimestamp(self.qps_record_start_time / 1000.0)
            x = str(x).split(".")
            x = x[0]
            x = x.replace("-", " ")
            f.write("Started: "+x+"\n")
            f.write("Device: " + module + "\n")
            f.write("Fixture: \n")

            x = datetime.datetime.now()
            x = str(x).split(".")
            x = x[0]
            x = x.replace("-", " ")
            f.write("Saved: "+x+ "\n")


    def sendCommand(self, cmd, device="", timeout=20,sock=None,readUntilCursor=True, betweenCommandDelay=0.0, expectedResponse=True):
        '''Send command is used to send a command to QIS and as far as I can see it has no difference than sendAndReceiveCmd'''
        if expectedResponse is True:
            if sock == None:
                sock = self.sock
            if not (device == ''):
                self.deviceDictSetup(device)
            res = self.sendAndReceiveText(sock, cmd, device, readUntilCursor)
            if (betweenCommandDelay > 0):
                time.sleep(betweenCommandDelay)
            # If ends with cursor get rid of it
            if res[-1:] == '>':
                res = res[:-3]  # remove last three chars - hopefully '\r\n>'
            return res

        else :
            self.sendText(sock, cmd, device)
            return

    # when sending commands to module (as opposed to back end)
    # If read until cursor is set to True (which is default) then keep reading response until a cursor is returned as the last character of result string
    # After command is sent wait for betweenCommandDelay which defaults to 0 but can be specified to add a delay between commands
    # The objects connection needs to be opened (connect()) before this is used
    def sendCmd(self, device='', cmd='$help', sock=None, readUntilCursor=True, betweenCommandDelay=0.0, expectedResponse = True):
        '''Send command is used to send a command to QIS and as far as I can see it has no difference than sendAndReceiveCmd'''
        if expectedResponse is True:
            res = self.sendAndReceiveCmd(device=device, cmd=cmd, sock=sock, readUntilCursor=readUntilCursor, betweenCommandDelay=betweenCommandDelay)
            #If ends with cursor get rid of it
            if res[-1:] == self.cursor:
                res = res[:-3] #remove last three chars - hopefully '\r\n>'
            return res
        else :
            self.sendText(sock, cmd, device)
            return

    def sendAndReceiveCmd(self, sock=None, cmd='$help', device='', readUntilCursor=True, betweenCommandDelay=0.0):
        if sock==None:
            sock = self.sock
        if not (device == ''):
            self.deviceDictSetup(device)
        res =  self.sendAndReceiveText(sock, cmd, device, readUntilCursor)
        if (betweenCommandDelay > 0):
            time.sleep(betweenCommandDelay)
        #If ends with cursor get rid of it
        if res[-1:] == '>':
            res = res[:-3] #remove last three chars - hopefully '\r\n>'
        return cmd + ' : ' + res

    def sendAndReceiveText(self, sock, sentText='$help', device='', readUntilCursor=True):
        # Send text to QIS
        # The objects connection needs to be opened (connect()) before this is used
        # If read until cursor is set to True (which is default) then keep reading response until a cursor is returned as the last character of result string

        # do sendText
        self.sockSemaphore.acquire()
        try:
            #Send Text
            self.sendText(sock, sentText, device)
            #Receive Response
            res = self.receiveText(sock)
            # Error Check / validate response
            if len(res) == 0:
                #logging.error("Empty response from QIS.")
                self.sendText(sock, "stream?", device)
                res = self.receiveText(sock)
                if len(res) != 0:
                    self.sendText(sock, sentText, device)
                    res = self.receiveText(sock)
                    if len(res) == 0:
                        raise (Exception("Empty response from QIS. Sent: " + sentText))
                else:
                    raise (Exception("Empty response from QIS. Sent: " + sentText))

            if res[0] == self.cursor:
                logging.warning('Only returned a cursor from QIS. Sent: ' + sentText)
            if 'Create Socket Fail' == res[0]: # If create socked fail (between QIS and tcp/ip module)
                logging.warning(res[0])
            if 'Connection Timeout' == res[0]:
                logging.warning(res[0])
            # If reading until a cursor comes back then keep reading until a cursor appears or max tries exceeded
            if readUntilCursor:
                maxReads = 1000
                count = 1
                # check for cursor at end of read and if not there read again
                while res[-1:] != self.cursor:
                    res+= self.receiveText(sock) #TODO Confirm this works with multi response CMD Like a $get stats on a large stream with many annos. test with py2 and py3
                    #res.extend(self.rxBytes(sock))
                    count += 1
                    if count >= maxReads:
                        raise Exception(' Count = Error: max reads exceeded before cursor returned')
            return res

        except Exception as e:
            #something went wrong during send qis cmd
            logging.error(e)
            raise e
        finally:
            self.sockSemaphore.release()


    def receiveText(self, sock):
        if self.pythonVersion == '3':
            res = bytearray()
            res.extend(self.rxBytes(sock))
            res = res.decode()
        else:
            res = self.rxBytes(sock)
        return res

    def sendText(self, sock, message='$help', device=''):
    # Send text to QIS, don't read it's response
    # The objects connection needs to be opened (connect()) before this is used
        if device != '':
            #specialTimeout =  '%500000'
            #message = device +  ' ' + specialTimeout +  ' ' + message
            message = device + ' ' + message
            #printText('Sending: "' + message + '" ' + self.host + ':' + str(self.port))

        if self.pythonVersion == 2:
            sock.sendall(message + '\r\n')
        else:
            convM = message + '\r\n'
            sock.sendall(convM.encode('utf-8'))
        return 'Sent:' + message

    def rxBytes(self,sock):
        #sock.setblocking(0) #make socket non-blocking
        #printText('rxBytes')
        maxExceptions=10
        exceptions=0
        maxReadRepeats=50
        readRepeats=0
        timeout_in_seconds = 10
        #Keep trying to read bytes until we get some, unless number of read repeads or exceptions is exceeded
        while True:
            try:
                #select.select returns a list of waitable objects which are ready. On windows it has to be sockets.
                #The first arguement is a list of objects to wait for reading, second writing, third 'exceptional condition'
                #We only use the read list and our socket to check if it is readable. if no timeout is specified then it blocks until it becomes readable.
                ready = select.select([sock], [], [], timeout_in_seconds)
                #time.sleep(0.1)
                #ready = [1,2]
                if ready[0]:
                    ret = sock.recv(self.maxRxBytes)
                    #time.sleep(0.1)
                    return ret
                else:
                    #printText('rxBytes - readRepeats + 1')

                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.connect((self.host, self.port))
                    sock.settimeout(5)

                    try:
                        welcomeString = self.sock.recv(self.maxRxBytes).rstrip()
                        welcomeString = 'Connected@' + self.host + ':' + str(self.port) + ' ' + '\n    ' + welcomeString
                        printText('New Welcome:' + welcomeString)
                    except Exception as e:
                        logging.error('tried and failed to get new welcome')
                        raise e

                    readRepeats=readRepeats+1
                    time.sleep(0.5)

            except Exception as e:
                #printText('rxBytes - exceptions + 1')
                exceptions=exceptions+1
                time.sleep(0.5)
                raise e

            #If read repeats has been exceeded we failed to get any data on this read.
            #   !!! This is likely to break whatever called us !!!
            if readRepeats >= maxReadRepeats:
                logging.error('Max read repeats exceeded - returning.')
                return 'No data received from QIS'
            #If number of exceptions exceeded then give up by exiting
            if exceptions >= maxExceptions:
                logging.error('Max exceptions exceeded - exiting') #exceptions are probably 10035 non-blocking socket could not complete immediatley
                exit()


def strToBb(string_in, add_length=True):
    length = len(str(string_in))
    b_array = []
    if add_length:
        b_array.append(length)
    for character in str(string_in):
        b_array.append(character)

    return b_array