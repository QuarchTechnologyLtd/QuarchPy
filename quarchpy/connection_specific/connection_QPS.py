import sys
import socket
import time
import datetime
import subprocess
import os
import random
import logging
import time


class QpsInterface:
    def __init__(self, host='127.0.0.1', port=9822):
        self.host = host
        self.port = port
        
        self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client.settimeout(5)
        self.client.connect((host, port))

        self.client.settimeout(None)
        time.sleep(1)
        self.recv()
        time.sleep(1)

        # Not blocking qps socket so scripts can continue if no read - 22/06
        self.client.setblocking(False)


    def recv(self):
        try:
            if sys.hexversion >= 0x03000000:
                response = self.client.recv(4096)
                i = 0
                for b in response:                                          # end buffer on first \0 character/value
                    if b > 0:
                        i += 1
                    else:
                        break;

                return response[:i].decode('utf-8', "ignore")
            else:
                return self.client.recv(4096)
        except Exception as e:
            # Catching socket timeout caused from non blocking socket
            return ""


    def send(self, data):
        if sys.hexversion >= 0x03000000:
            self.client.send( data.encode() )
        else:
            self.client.send( data )

    def sendCommand(self, cmd, timeout=20, expectedResponse=True ):
        cmd = cmd + "\r\n"
        logging.debug("Sending cmd to QPS: " + str(cmd))
        self.send(cmd)

        start = time.time()
        response = self.recv().strip()
        while response.rfind('\r\n>') == -1:  # If true then the resposnse is large and multi packeted
            time.sleep(0.1)
            t_response = self.recv().strip()
            # Add current response to new response
            response += t_response
            # Keep reading from the socket if there's stuff that was retreived
            if len(str(t_response)) == 0:
                if time.time() - start > timeout:
                    logging.warning("Command : " + str(cmd) + " Hit timeout during QPS read. timeout = " + str(timeout))
                    break

        pos = response.rfind('\r\n>')
        if pos == -1:
            logging.warning("Did not retrieve trailing '\\r\\n>' from QPS read, returned full response so far")
            logging.warning("command : " + cmd.replace('\r\n', '\\r\\n'))
            logging.warning("returned : " + response.replace('\r\n', '\\r\\n'))
            pos = len(str(response))
        return response[:pos]

    def sendCmdVerbose(self, cmd, timeout=20):
        cmd = cmd + "\r\n"
        logging.debug("Sending cmd to QPS: "+str(cmd))
        self.send(cmd)

        start = time.time()
        response = self.recv().strip()
        while response.rfind('\r\n>') == -1: #If true then the resposnse is large and multi packeted
            time.sleep(0.1)
            t_response = self.recv().strip()
            # Add current response to new response
            response += t_response
            # Keep reading from the socket if there's stuff that was retreived
            if len(str(t_response)) == 0:
                if time.time() - start > timeout:
                    logging.warning("Command : "+str(cmd)+ " Hit timeout during QPS read. timeout = " +str(timeout))
                    break

        pos = response.rfind('\r\n>')
        if pos == -1:
            logging.warning("Did not retrieve trailing '\\r\\n>' from QPS read, returned full response so far")
            logging.warning("command : " + cmd.replace('\r\n','\\r\\n'))
            logging.warning("returned : " + response.replace('\r\n','\\r\\n'))
            pos = len(str(response))
        return response[:pos]


    def connect(self, targetDevice):
        cmd="$connect " + targetDevice
        retVal = self.sendCmdVerbose(cmd)
        time.sleep(0.3)
        return retVal


    def disconnect(self, targetDevice):
        self.sendCmdVerbose("$disconnect")

    def closeConnection(self, conString=None):
        if conString is None:
           return self.sendCmdVerbose("close")
        else:
            return self.sendCmdVerbose(conString+" close")
    def scanIP(self, ipAddress, sleep=10):
        """
        Triggers QPS to look at a specific IP address for a quarch module

        Parameters
        ----------
        QpsConnection : QpsInterface
            The interface to the instance of QPS you would like to use for the scan.
        ipAddress : str
            The IP address of the module you are looking for eg '192.168.123.123'
        sleep : int, optional
            This optional variable sleeps to allow the network to scan for the module before allowing new commands to be sent to QPS.
        """
        ipAddress = "TCP::" + ipAddress

        self.send("$scan " + ipAddress)
        # logging.debug("Starting QPS IP Address Lookup")
        time.sleep(
            sleep)  # Time must be allowed for QPS to Scan. If another scan request is sent it will time out and throw an error.

    def get_list_details(self, sock=None):
        if sock == None:
            sock = self.sock
        devString = self.sendCmdVerbose("$module list details")
        #devString = self.sendAndReceiveText(sock, '$list details')
        devString = devString.replace('>', '')
        devString = devString.replace(r'\d+\) ', '')
        devString = devString.split('\r\n')
        devString = [x for x in devString if x]  # remove empty elements
        return devString

    def getDeviceList(self, scan = True, ipAddress = None):
        deviceList = []
        scanWait = 2
        foundDevices = "1"
        foundDevices2 = "2"
        if scan:
            if ipAddress == None:
                devString = self.sendCmdVerbose('$scan')
            else:
                devString = self.sendCmdVerbose('$module scan tcp::' + ipAddress)
            time.sleep(scanWait)
            while foundDevices not in foundDevices2:
                foundDevices = self.sendCmdVerbose('$list')
                time.sleep(scanWait)
                foundDevices2 = self.sendCmdVerbose('$list')
        else:
            foundDevices = self.sendCmdVerbose('$list')

        response = self.sendCmdVerbose( "$list" )

        time.sleep(2)

        response2 = self.sendCmdVerbose( "$list" )

        while (response != response2):
            response = response2
            response2 = self.sendCmdVerbose( "$list" )
            time.sleep(1)
        if "no device" in response.lower() or "no module" in response.lower():
            return [response.strip()]
        #check if a response was received and the first char was a digit
        if( len(response) > 0 and response[0].isdigit ):
            sa = response.split()
            for s in sa:
                #checks for invalid chars
                if( ")" not in s and ">" not in s ):
                    #append to list if conditions met
                    deviceList.append( s )

        #return list of devices
        return deviceList


    def open_recording(self, file_path, cmdTimeout=5, pollInterval=3, startOpenTimout=5):
        """

        """
        #print("Open recording at file : \""+str(file_path)+"\"")
        self.sendCmdVerbose("$open recording qpsFile=\""+str(file_path)+"\"",timeout=cmdTimeout)
        loadingStarted=False
        message=""
        startTime=time.time()
        notLoadingMessageStartTime=None
        while(1):
            update=self.sendCmdVerbose("$progress check \"open recording\"",timeout=cmdTimeout)
            #print(update)
            m = re.search('\d+(\.\d+)?%', update)
            if m: # A percentage was found
                loadingStarted=True
                found = float(m.group(0)[:-1])
                user_interface.progressBar(found,100)
                if found > 99.9: # This will catch the case we have 99.9999% or 100% loaded. recording with less that 1mill records auto return 100%
                    message = "Passed, Recording opened, loading detected and complete."
                    break
            elif("Chart window is open but no loading is in progress." in update):
                if loadingStarted ==True:
                    # Loading started and has now ended, so we can exit the loop.
                    message="Passed, Recording opened, loading detected and complete."
                    break
                else: # QPS has not started loading a recording.
                    if notLoadingMessageStartTime == None:
                        # Start a timer from now so that if loading doesn't take place between now and a timeout value,
                        # we exit, stating that no loading started within the desired time.
                        notLoadingMessageStartTime = time.time()
                    elif time.time() - notLoadingMessageStartTime> startOpenTimout:
                        message = "No detection that QPS started loading the recording within "+str(startOpenTimout)+"s."
                        break

            time.sleep(pollInterval) #Sleep pollInterval time, so we are not hammering QPS for updates while its busy loading.
        time.sleep(1) #sleep outside the loop as there is a
        return message


    
