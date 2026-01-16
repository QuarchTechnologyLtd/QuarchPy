import sys
import socket
import logging
import time
import re
from typing import Union, List, Optional, Any

from quarchpy.user_interface import user_interface, User_interface, printText, listSelection, requestDialog

logger = logging.getLogger(__name__)

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
        logger.debug("Sending cmd to QPS: " + str(cmd))
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
                    logger.warning("Command : " + str(cmd) + " Hit timeout during QPS read. timeout = " + str(timeout))
                    break

        pos = response.rfind('\r\n>')
        if pos == -1:
            logger.warning("Did not retrieve trailing '\\r\\n>' from QPS read, returned full response so far")
            logger.warning("command : " + cmd.replace('\r\n', '\\r\\n'))
            logger.warning("returned : " + response.replace('\r\n', '\\r\\n'))
            pos = len(str(response))
        return response[:pos]

    def sendCmdVerbose(self, cmd, timeout=20):
        cmd = cmd + "\r\n"
        logger.debug("Sending cmd to QPS: "+str(cmd))
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
                    logger.warning("Command : "+str(cmd)+ " Hit timeout during QPS read. timeout = " +str(timeout))
                    break

        pos = response.rfind('\r\n>')
        if pos == -1:
            logger.warning("Did not retrieve trailing '\\r\\n>' from QPS read, returned full response so far")
            logger.warning("command : " + cmd.replace('\r\n','\\r\\n'))
            logger.warning("returned : " + response.replace('\r\n','\\r\\n'))
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
        # logger.debug("Starting QPS IP Address Lookup")
        time.sleep(
            sleep)  # Time must be allowed for QPS to Scan. If another scan request is sent it will time out and throw an error.

    def get_list_details(self, sock=None):
        # if sock == None:
        #     sock = self.sock
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

    def get_qps_module_selection(
            self,
            preferred_connection_only: bool = True,
            additional_options: Optional[List[str]] = None,
            scan: bool = True
    ) -> Any | None:
        """
        Scans for QPS devices and prompts the user to select one.
        """
        if additional_options is None:
            additional_options = ['rescan', 'all con types', 'ip scan']

        # State variables
        favourite = preferred_connection_only
        ip_address = None

        while True:
            printText("QPS scanning for devices")

            # 1. Fetch raw list from QPS
            dev_list = self._fetch_device_list(scan, ip_address)

            # 2. Check for empty results and sanitize
            # If no devices found, force favorite mode off to prevent sorting bugs
            if self._is_list_empty_or_error(dev_list):
                favourite = False

            # Remove REST devices (unsupported here)
            dev_list = [x for x in dev_list if "rest" not in x]

            # 3. Apply 'Favourite' Logic (Sort by type & Deduplicate)
            if preferred_connection_only:
                dev_list = self._apply_favourite_sorting(dev_list)

            # 4. Apply TestCenter formatting (if applicable)
            display_list = self._format_for_testcenter(dev_list)

            # 5. Show UI
            selection = listSelection(
                title="Select a Quarch module",
                message="Select a Quarch module",
                selectionList=display_list,
                additionalOptions=additional_options,
                nice=True,
                tableHeaders=["Module"],
                indexReq=True
            )

            # 6. Handle User Response
            # If the user picked a device, return it. If they picked an option, loop again.
            action = self._parse_selection_action(selection)

            if action == "RETURN_DEVICE":
                return selection
            elif action == "RESCAN":
                ip_address = None
                favourite = True
                continue
            elif action == "SHOW_ALL":
                printText('Displaying all connection types...')
                favourite = False
                continue
            elif action == "IP_SCAN":
                ip_address = requestDialog("Please input IP Address of the module you would like to connect to: ")
                favourite = False
                continue

    def select_device(self, preferred_connection_only=True):
        """
        Opens a UI prompt for the user to select a device available on this QPS instance.
        """
        return self.get_qps_module_selection(preferred_connection_only=preferred_connection_only)

    def open_recording(self, file_path, cmdTimeout=5, pollInterval=3, startOpenTimout=5):
        """

        """
        #print("Open recording at file : \""+str(file_path)+"\"")
        notLoadingMessageStartTime=None
        loadingStarted=False
        message=""

        openResponse = self.sendCmdVerbose("$open recording qpsFile=\""+str(file_path)+"\"",timeout=cmdTimeout)
        #print(openResponse)
        while(1):
            update=self.sendCmdVerbose("$progress check task=\"open recording\"",timeout=cmdTimeout)
            #print(update)
            m = re.search(r'\d+(\.\d+)?%', update)
            if m: # A percentage was found
                loadingStarted=True
                found = float(m.group(0)[:-1])
                user_interface.progressBar(found,100)
                if found > 99.9: # This will catch the case we have 99.9999% or 100% loaded. recording with less that 1mill records auto return 100%
                    message = "Passed, Recording opened, loading detected and complete."
                    break
            elif "Initialising main chart" in update:
                loadingStarted = True
                user_interface.progressBar(found, 100)
            elif "Chart window is open but no loading is in progress." in update:
                if loadingStarted == True:
                    # Loading started and has now ended, so we can exit the loop.
                    message="Passed, Recording opened, loading detected and complete."
                    break
                else: # QPS has not started loading a recording.
                    if notLoadingMessageStartTime == None:
                        # Start a timer from now so that if loading doesn't take place between now and a timeout value,
                        # we exit, stating that no loading started within the desired time.
                        notLoadingMessageStartTime = time.time()
                    elif time.time() - notLoadingMessageStartTime> startOpenTimout:
                        message = "No detection that QPS started loading the recording within " + str(startOpenTimout) + "s."
                        break

            time.sleep(pollInterval) # Sleep pollInterval time, so we are not hammering QPS for updates while its busy loading.
        time.sleep(1) # sleep outside the loop as there is a
        return message

    def _fetch_device_list(self, scan: bool, ip_address: Optional[str]) -> List[str]:
        """Retrieves the device list from QPS, handling IP scan logic."""
        if ip_address is None:
            return self.getDeviceList(scan=scan)
        else:
            return self.getDeviceList(scan=scan, ipAddress=ip_address)

    def _is_list_empty_or_error(self, dev_list: List[str]) -> bool:
        """Checks if the returned list is empty or contains error messages."""
        if not dev_list:
            return True
        first_item = dev_list[0].lower()
        return "no device" in first_item or "no module" in first_item

    def _apply_favourite_sorting(self, dev_list: List[str]) -> List[str]:
        """
        Sorts devices by connection preference and removes duplicates.
        Preference Order: USB > TCP > SERIAL > REST > TELNET
        """
        sorted_list = self._sort_by_connection_type(dev_list)
        deduped_list = self._deduplicate_physical_devices(sorted_list)
        return deduped_list

    def _sort_by_connection_type(self, dev_list: List[str]) -> List[str]:
        """Reorders the list based on specific connection type priority."""
        sorted_list = []
        con_pref = ["USB", "TCP", "SERIAL", "REST", "TELNET"]

        for pref in con_pref:
            for device in dev_list:
                if pref in device.upper():
                    if device not in sorted_list:
                        sorted_list.append(device)
        return sorted_list

    def _deduplicate_physical_devices(self, dev_list: List[str]) -> List[str]:
        """
        Filters the list to keep only the highest priority connection for each unique device ID.
        (e.g., if both USB::QTL1 and TCP::QTL1 exist, keep only USB because it appeared first).
        """
        unique_list = []
        seen_ids = set()

        for device in dev_list:
            try:
                # Extract the unique serial (e.g., 'QTL1234' from 'USB::QTL1234')
                if "::" in device:
                    device_id = device.split("::")[1]
                    if device_id not in seen_ids:
                        unique_list.append(device)
                        seen_ids.add(device_id)
                else:
                    # Fallback for non-standard formats
                    if device not in unique_list:
                        unique_list.append(device)
            except IndexError:
                if device not in unique_list:
                    unique_list.append(device)

        return unique_list

    def _format_for_testcenter(self, dev_list: List[str]) -> Union[List[str], str]:
        """
        Formats the list specifically for the TestCenter interface if active.
        TestCenter requires a comma-separated string format: "Item1=Item1,Item2=Item2"
        """
        if User_interface.instance is not None and getattr(User_interface.instance, 'selectedInterface',
                                                           '') == "testcenter":
            # Convert list to TestCenter-style string
            formatted_str = ",".join([f"{module}={module}" for module in dev_list])
            return formatted_str

        return dev_list

    def _parse_selection_action(self, selection: str) -> str:
        """Determines if the selection is a device ID or a menu action."""
        # Using 'in' allows for loose matching if the UI returns slightly different strings
        if selection in 'rescan':
            return "RESCAN"
        elif selection in 'all con types':
            return "SHOW_ALL"
        elif selection in 'ip scan':
            return "IP_SCAN"
        else:
            return "RETURN_DEVICE"

    
