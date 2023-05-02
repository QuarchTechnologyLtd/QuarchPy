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


    def sendCmdVerbose(self, cmd, timeout=300):
        cmd = cmd + "\r\n"

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
        #print(cmd+" : "+retVal)
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

    def getDeviceList(self, scan = True):
        deviceList = []
        scanWait = 2
        foundDevices = "1"
        foundDevices2 = "2"
        if scan:
            devString = self.sendCmdVerbose('$scan')
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

    
