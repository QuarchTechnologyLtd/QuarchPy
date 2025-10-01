import gzip
import re
import socket
import threading
import xml.etree.ElementTree as ET
from io import StringIO

import select
from connection_specific.StreamChannels import StreamGroups

from quarchpy.user_interface import *


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
        self.connect(connection_message = connectionMessage)
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
        welcome_string = self.streamSock.recv(self.maxRxBytes).rstrip()


    def connect(self, connection_message: bool = True) -> str:
        """
        Opens the connection to the QIS backend

        Args:
            connection_message:
                Defaults to True. If set to False, suppresses the warning message about an
                instance already running on the specified port. This can be useful when
                using `isQisRunning()` from `qisFuncs`.

        Raises:
        Exception:
            If the connection fails or the welcome string is not received an exception is raised

        Returns:
            The welcome string received from the backend server upon a successful
            connection.  This will confirm the QIS version but is generally not used other than
            for debugging
        """

        try:
            self.device_dict_setup('QIS')
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(5)
            self.sock.connect((self.host, self.port))

            #clear packets
            try:
                welcome_string = self.sock.recv(self.maxRxBytes).rstrip()
                welcome_string = 'Connected@' + str(self.host) + ':' + str(self.port) + ' ' + '\n    ' + str(welcome_string)
                self.deviceDict['QIS'][0:3] = [False, 'Connected', welcome_string]
                return welcome_string
            except Exception as e:
                logging.error('No welcome received. Unable to connect to Quarch backend on specified host and port (' + self.host + ':' + str(self.port) + ')')
                logging.error('Is backend running and host accessible?')
                self.deviceDict['QIS'][0:3] = [True, 'Disconnected', 'Unable to connect to QIS']
                raise e
        except Exception as e:
            self.device_dict_setup('QIS')
            if connection_message:
                logging.error('Unable to connect to Quarch backend on specified host and port (' + self.host + ':' + str(self.port) + ').')
                logging.error('Is backend running and host accessible?')
            self.deviceDict['QIS'][0:3] = [True, 'Disconnected', 'Unable to connect to QIS']
            raise e


    def disconnect(self) -> str:
        """
        Disconnects the current connection to the QIS backend.

        This method attempts to gracefully disconnect from the backend server and updates
        the connection state in the device dictionary. If an error occurs during the
        disconnection process, the state is updated to indicate the failure, and the
        exception is re-raised

        Returns:
            str: A message indicating that the disconnection process has started.

        Raises:
            Exception: Propagates any exception that occurs during the disconnection process.
        """
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

    def close_connection(self, sock=None, con_string: str=None) -> str:
        """
        Orders QIS to release a given device (or all devices if no connection string is specified)
        This is more important for TCP connected devices as the socket is held open until
        specifically released.

        Args:
            sock:
                The socket object to close the connection to. Defaults to the existing socket.
            con_string:
                Specify the device ID to close, otherwise all devices will be closed

        Raises:
            ConnectionResetError: Raised if the socket connection has already been reset.

        Returns:
            The response received after sending the close command. On success, this will be: 'OK'

        """
        if sock is None:
            sock = self.sock
        if con_string is None:
            cmd = "close"
        else:
            cmd = con_string + " close"
        try:
            response = self.sendAndReceiveText(sock, cmd)
            return response
        except ConnectionResetError:
            logging.error('Unable to close connection to device(s), QIS may be already closed')
            return "FAIL: Unable to close connection to device(s), QIS may be already closed"

    def start_stream(self, module: str, file_name: str, max_file_size: int, release_on_data: bool, separator: str, stream_duration: float=None, in_memory_data: StringIO=None, output_file_handle=None, use_gzip: bool=None):
        """
        Begins a stream process which will record data from the module to a CSV file or in memory CSV equivalent

        Args:
            module:
                The ID of the module for which the stream is being initiated.
            file_name:
                The target file path+name for storing the  streamed data in CSV form.
            max_file_size:
                The maximum size in megabytes allowed for the output file.
            release_on_data:
                If set, blocks further streams until this one has started
            separator:
                The value separator used to format the streamed CSV data.
            stream_duration:
                The duration (in seconds) for which the streaming process should run. Unlimited if None.
            in_memory_data:
                An in memory CSV StringIO as an alternate to file output
            output_file_handle:
                A file handle to an output file where the stream data is written as an alternate to a file name
            use_gzip:
                A flag indicating whether the output file should be compressed using gzip to reduce disk use

        Returns:
            None
        """
        self.StreamRunSentSemaphore.acquire()
        self.device_dict_setup('QIS')
        i = self.device_control_index(module)
        self.stopFlagList[i] = True
        self.stripesEvent.set()
        self.module_xml_header = None

        # Create the worker thread to handle stream processing
        t1 = threading.Thread(target=self.start_stream_thread, name=module,
                              args=(module, file_name, max_file_size, release_on_data, separator, stream_duration, in_memory_data, output_file_handle, use_gzip))
        # Start the thread
        t1.start()

        while self.stripesEvent.is_set():
            pass

    def stop_stream(self, module, blocking:bool = True):
        """

        Args:
            module:
                The quarchPPM module instance for which the streaming process is to be stopped.
            blocking:
                If set to True, the function will block and wait until the module has
                completely stopped streaming. Defaults to True.

        Returns:
            None

        """

        module_name=module.ConString
        i = self.device_control_index(module_name)
        self.stopFlagList[i] = False

        # Wait until the stream thread is finished before returning to the user.
        # This means this function will block until the QIS buffer is emptied by the second while
        # loop in startStreamThread. This may take some time, especially at low averaging,
        # but should guarantee the data won't be lost and QIS buffer is emptied.
        if blocking:
            running = True
            while running:
                thread_name_list = []
                for t1 in threading.enumerate():
                    thread_name_list.append(t1.name)
                module_streaming= module.sendCommand("rec stream?").lower() #checking if module thinks its streaming.
                module_streaming2= module.sendCommand("stream?").lower() #checking if the module has told qis it has stopped streaming.

                if module_name in thread_name_list or "running" in module_streaming or "running" in module_streaming2:
                    time.sleep(0.1)
                else:
                    running = False

    def start_stream_thread(self, module: str, file_name: str, max_file_size: float, release_on_data: bool, separator: str,
                          stream_duration: int=None, in_memory_data=None, output_file_handle=None, use_gzip: bool=False):
        """

        Args:
            module:
                The name of the module from which data is to be streamed.
            file_name:
                The path to the file where streamed data will be written. Mandatory if neither an in-memory
                buffer (in_memory_data) nor an external file handle (output_file_handle) is provided.
            max_file_size:
                The maximum permissible file size in MB. After reaching this limit, streaming to the current
                file will stop
            release_on_data:
                True to prevent the stream lock from releasing until data has been received
            separator:
                Custom separator used to CSV data
            stream_duration:
                Duration of streaming in seconds, relative to the sampling period. Defaults to streaming
                indefinitely.
            in_memory_data:
                An in-memory buffer of type StringIO to hold streamed data. If set, data is written here
                instead of a file.
            output_file_handle:
                A pre-opened file handle where data will be written. If set, file_name is ignored.
            use_gzip:
                If True, writes streamed data to a gzip-compressed file.

        Raises:
        TypeError
            If in_memory_data is passed but is not of type StringIO.
        ValueError
            If file_name is not provided and neither in_memory_data nor output_file_handle is given.
            Also raised for invalid or undecodable sampling periods.

        Returns:
            None
        """

        f = None
        max_mb_val = 0
        file_opened_by_function = False  # True if this function opens the file
        is_in_memory_stream = False  # True if using inMemoryData (StringIO)

        # Output priority: 1. output_file_handle, 2. inMemoryData, 3. A new a file
        if output_file_handle is not None:
            f = output_file_handle
            # Caller is responsible for the handle's mode (e.g., text/binary) and type.
        elif in_memory_data is not None:
            if not isinstance(in_memory_data, StringIO):
                raise TypeError("Error! The parameter 'inMemoryData' must be of type StringIO.")
            f = in_memory_data
            is_in_memory_stream = True
        else:
            # No external handle or in-memory buffer, so open a file.
            if not file_name:  # fileName is mandatory if we are to open a file.
                raise ValueError("fie_name must be provided if output_file_handle and in_memory_data are None.")
            file_opened_by_function = True
            if use_gzip:
                # Open in text mode ('wt'). Encoding 'utf-8' is a good default.
                # gzip.open in text mode handles newline conversions.
                f = gzip.open(file_name, 'wt', encoding='utf-8')
            else:
                # Open in text mode ('w').
                # newline='' ensures that '\n' is written as '\n' on all platforms.
                f = open(file_name, 'w', encoding='utf-8', newline='')

        # Check for a valid max file size limit
        if max_file_size is not None:
            try:
                max_mb_val = int(max_file_size)
            except (ValueError, TypeError):
                logging.warning(f"Invalid max_file_size parameter: {max_file_size}. No limit will be applied")
                max_file_size = None

        # Send stream command so the module starts streaming data into the backends buffer
        stream_res = self.send_command('rec stream', device=module, qis_socket=self.streamSock)
        # Check the stream started
        if 'OK' in stream_res:
            if not release_on_data:
                self.StreamRunSentSemaphore.release()
                self.stripesEvent.clear()
            self.deviceDict[module][0:3] = [False, 'Running', 'Stream Running']
        else:
            self.StreamRunSentSemaphore.release()
            self.stripesEvent.clear()
            self.deviceDict[module][0:3] = [True, 'Stopped', module + " couldn't start because " + stream_res]
            if file_opened_by_function and f:
                try:
                    f.close()
                except Exception as e_close:
                    logging.error(f"Error closing file {file_name} on stream start failure: {e_close}")
            return

        # Poll for the stream header to become available. This is needed to configure the output file
        base_sample_period = self.stream_header_average(device=module, sock=self.streamSock)
        count = 0
        max_tries = 10
        while 'Header Not Available' in base_sample_period:
            base_sample_period = self.stream_header_average(device=module, sock=self.streamSock)
            time.sleep(0.1)
            count += 1
            if count > max_tries:
                self.deviceDict[module][0:3] = [True, 'Stopped', 'Header not available']
                if file_opened_by_function and f:
                    try:
                        f.close()
                    except Exception as e_close:
                        logging.error(f"Error closing file {file_name} on header failure: {e_close}")
                return  # Changed from exit() for cleaner thread termination

        # Format the header and write it to the output file
        format_header = self.stream_header_format(device=module, sock=self.streamSock)
        format_header = format_header.replace(", ", separator)
        f.write(format_header + '\n')

        # Initialize stream variables
        max_file_exceeded = False
        open_attempts = 0
        leftover = 0
        remaining_stripes = []
        stream_overrun = False
        stream_complete = False
        stream_status_str = ""

        # Calculate and verify stripe rate information
        if 'ns' in base_sample_period.lower():
            base_sample_unit_exponent = -9
        elif 'us' in base_sample_period.lower():
            base_sample_unit_exponent = -6
        elif 'ms' in base_sample_period.lower():
            base_sample_unit_exponent = -3
        elif 'S' in base_sample_period.lower():  # Original was 'S', assuming it means 's'
            base_sample_unit_exponent = 0
        else:
            # Clean up and raise error if baseSamplePeriod is undecodable
            if file_opened_by_function and f:
                try:
                    f.close()
                except Exception as e_close:
                    logging.error(f"Error closing file {file_name} due to ValueError: {e_close}")
            raise ValueError(f"couldn't decode samplePeriod: {base_sample_period}")

        base_sample_period_period_s = int(re.search(r'^\d*\.?\d*', base_sample_period).group()) * (10 ** base_sample_unit_exponent)

        # Now we loop to process the stripes of data as they are available
        is_run = True
        while is_run:
            try:
                # Check for exit flags.  These can be from user request (stopFlagList) or from the stream
                # process ending
                i = self.device_control_index(module)
                while self.stopFlagList[i] and (not stream_overrun) and (not stream_complete):

                    # Read a block of stripes from QIS
                    stream_status_str, new_stripes = self.stream_get_stripes_text(self.streamSock, module)

                    # Overrun is a termination event where the stream stopped earlier than desired and must
                    # be flagged to the user
                    if "overrun" in stream_status_str:
                        stream_overrun = True
                        self.deviceDict[module][0:3] = [True, 'Stopped', 'Device buffer overrun']
                    if "eof" in stream_status_str:
                        stream_complete = True

                    # Continue here if there are stripes to process
                    if len(new_stripes) > 0:
                        # switch in the correct value seperator
                        new_stripes = new_stripes.replace(' ', separator)

                        # Track the total size of the file here if needed
                        if max_file_size is not None:
                            current_file_mb = 0.0
                            if is_in_memory_stream:
                                current_file_mb = f.tell() / 1048576.0
                            elif file_name:
                                try:
                                    # os.stat reflects the size on disk. For buffered writes (incl. gzip),
                                    # this might not be the exact current unwritten buffer size + disk size
                                    # without a flush, but it's an decent estimate.
                                    stat_info = os.stat(file_name)
                                    current_file_mb = stat_info.st_size / 1048576.0
                                except FileNotFoundError:
                                    current_file_mb = 0.0  # File might not exist yet or fileName is not locatable
                                except Exception as e_stat:
                                    logging.warning(f"Could not get file size for {file_name}: {e_stat}")
                                    current_file_mb = 0.0  # Default to small size on error
                            else:
                                # output_file_handle was given, but fileName was None. Cannot check disk size.
                                # Assume it's okay or managed by the caller. fileMaxMB check effectively bypassed.
                                current_file_mb = 0.0

                            # Flag the limit has been exceeded
                            if current_file_mb > max_mb_val:
                                max_file_exceeded = True
                                max_file_status = self.stream_buffer_status(device=module, sock=self.streamSock)
                                f.write('Warning: Max file size exceeded before end of stream.\n')
                                f.write('Unrecorded stripes in buffer when file full: ' + max_file_status + '.\n')
                                self.deviceDict[module][0:3] = [True, 'Stopped', 'User defined max filesize reached']
                                break  # Exit stream processing loop

                        # Release the stream semaphore now we have data
                        if release_on_data:
                            self.StreamRunSentSemaphore.release()
                            self.stripesEvent.clear()
                            release_on_data = False

                        # If a duration has been set, track it based on the time of the last stripe
                        if stream_duration is not None:
                            last_line = new_stripes.splitlines()[-1]
                            last_time = last_line.split(separator)[0]

                            # Write all the stripes if we can
                            if int(last_time) < int(stream_duration / (10 ** base_sample_unit_exponent)):
                                f.write(new_stripes)
                            # Otherwise only write stripes within the duration limit
                            else:
                                for this_line in new_stripes.splitlines():
                                    this_time_str = this_line.split(separator)[0]
                                    if int(this_time_str) < int(stream_duration / (10 ** base_sample_unit_exponent)):
                                        f.write(this_line + '\r\n')  # Put the CR back on the end
                                    else:
                                        stream_complete = True
                                        break
                        # Default to writing all stripes
                        else:
                            f.write(new_stripes)
                    # If we have no data
                    else:
                        if stream_overrun:
                            break  # Exit stream processing loop
                        elif "stopped" in stream_status_str:
                            self.deviceDict[module][0:3] = [True, 'Stopped', 'User halted stream']
                            break  # Exit stream processing loop
                # End of stream data processing loop

                # Ensure the stream is fully stopped, though standard exit cases should have ended it already
                self.send_command('rec stop', device=module, qis_socket=self.streamSock)
                stream_state = self.send_command('stream?', device=module, qis_socket=self.streamSock)
                while "stopped" not in stream_state.lower():
                    logging.debug("waiting for stream? to return stopped")
                    time.sleep(0.1)
                    stream_state = self.send_command('stream?', device=module, qis_socket=self.streamSock)

                if stream_overrun:
                    self.deviceDict[module][0:3] = [True, 'Stopped', 'Device buffer overrun - QIS buffer empty']
                elif not max_file_exceeded:
                    self.deviceDict[module][0:3] = [False, 'Stopped', 'Stream stopped']

                is_run = False  # Exit main while loop
            except IOError as err:
                logging.error(f"IOError in startStreamThread for module {module}: {err}")
                # f might have been closed by the system if it's a pipe and the other end closed or other severe errors.
                # Attempt to close only if this function opened it, and it seems like it might be openable/closable.
                if file_opened_by_function and f is not None:
                    try:
                        if not f.closed:
                            f.close()
                    except Exception as e_close:
                        logging.error(f"Error closing file {file_name} during IOError handling: {e_close}")
                    f = None  # Avoid trying to close again in finally if error persists

                time.sleep(0.5)
                open_attempts += 1
                if open_attempts > 4:
                    logging.error(f"Too many IOErrors in QisInterface for module {module}. Raising error.")
                    # Set device status before raising, if possible
                    self.deviceDict[module][0:3] = [True, 'Stopped', f'IOError limit exceeded: {err}']
                    raise  # Re-raise the last IOError
            finally:
                if file_opened_by_function and f is not None:
                    try:
                        if not f.closed:  # Check if not already closed (e.g. in IOError block)
                            f.close()
                    except Exception as e_close:
                        logging.error(f"Error closing file {file_name} in finally block: {e_close}")
                # If output_file_handle was passed, the caller is responsible for closing.
                # If inMemoryData was passed, it's managed by the caller.

    def get_device_list(self, sock=None) -> filter:
        """
        returns a list of device IDs that are available for connection

        Args:
            sock:
                Optional connection socket

        Returns:
            A filtered iterable list of devices

        """

        if sock is None:
            sock = self.sock

        dev_string = self.sendAndReceiveText(sock, '$list')
        dev_string = dev_string.replace('>', '')
        dev_string = dev_string.replace(r'\d+\) ', '')
        dev_string = dev_string.split('\r\n')
        dev_string = filter(None, dev_string) #remove empty elements

        return dev_string

    def get_list_details(self, sock=None) -> list:
        """
        Extended version of get_device_list which also returns the additional details
        fields for each module

        Args:
            sock:
                Optional connection socket
        Returns:
                Iterable list of strings containing the details of each device available for connection.

        """
        if sock is None:
            sock = self.sock

        dev_string = self.sendAndReceiveText(sock, '$list details')
        dev_string = dev_string.replace('>', '')
        dev_string = dev_string.replace(r'\d+\) ', '')
        dev_string = dev_string.split('\r\n')
        dev_string = [x for x in dev_string if x]  # remove empty elements
        return dev_string

    def scan_ip(self, qis_connection, ip_address) -> bool:
        """
        Triggers QIS to look at a specific IP address for a module

        Arguments

        QisConnection : QpsInterface
            The interface to the instance of QIS you would like to use for the scan.
        ipAddress : str
            The IP address of the module you are looking for eg '192.168.123.123'
        """

        logging.debug("Starting QIS IP Address Lookup at " + ip_address)
        if not ip_address.lower().__contains__("tcp::"):
            ip_address = "TCP::" + ip_address
        response = "No response from QIS Scan"
        try:
            response = qis_connection.send_command("$scan " + ip_address)
            # The valid response is "Located device: 192.168.1.2"
            if "located" in response.lower():
                logging.debug(response)
                # return the valid response
                return True
            else:
                logging.warning("No module found at " + ip_address)
                logging.warning(response)
                return False

        except Exception as e:
            logging.warning("No module found at " + ip_address)
            logging.warning(e)
            return False


    def get_qis_module_selection(self, preferred_connection_only=True, additional_options="DEF_ARGS", scan=True) -> str:
        """
        Scans for available modules and allows the user to select one through an interactive selection process.
        Can also handle additional custom options and some built-in ones such as rescanning

        Arguments:
            preferred_connection_only : bool
                by default (True), returns only one preferred connection eg: USB for simplicity
            additional_options: list
                Additional operational options provided during module selection, such as rescan,
                all connection types, and IP scan. Defaults to ['rescan', 'all con types', 'ip scan']. These allow the
                additional options to be given to the user and handled in the top level script
            scan : bool
                Indicates whether to initiate a rescanning process for devices before listing. Defaults to True and
                will take longer to return

        Returns:
            str: The identifier of the selected module, or the action selected from the additional options.

        Raises:
            KeyError: Raised when unexpected keys are found in the scanned device data.
            ValueError: Raised if no valid selection is made or the provided IP address is invalid.
        """

        # Avoid mutable warning by adding the argument list in the function rather than the header
        if additional_options == "DEF_ARGS":
            additional_options = ['rescan', 'all con types', 'ip scan']

        table_headers = ["Modules"]
        ip_address = None
        favourite = preferred_connection_only
        while True:
            printText("Scanning for modules...")
            found_devices = None
            if scan and ip_address is None:
                found_devices = self.qis_scan_devices(scan=scan, preferred_connection_only=favourite)
            elif scan and ip_address is not None:
                found_devices = self.qis_scan_devices(scan=scan, preferred_connection_only=favourite, ip_address=ip_address)

            my_device_id = listSelection(title="Select a module",message="Select a module",
                                          selectionList=found_devices, additionalOptions= additional_options,
                                          nice=True, tableHeaders=table_headers, indexReq=True)

            if my_device_id.lower() == 'rescan':
                favourite = True
                ip_address = None
                continue
            elif my_device_id.lower() == 'all con types':
                favourite = False
                printText("Displaying all connection types...")
                continue
            elif my_device_id.lower() == 'ip scan':
                ip_address = requestDialog(title="Please input the IP Address you would like to scan")
                favourite = False
                continue
            break

        return my_device_id

    def qis_scan_devices(self, scan=True, preferred_connection_only=True, ip_address=None) -> list:
        """
        Begins a scan for devices and returns a simple list of devices

        Args:
            scan:
                Should a scan be initiated?  If False, the function will return immediately with the list
            preferred_connection_only:
                The default (True), returns only one preferred connection eg: USB for simplicity
            ip_address:
                IP address of the module you are looking for eg '192.168.123.123'

        Returns:
            list: List of module strings found during scan
        """

        device_list = []
        found_devices = "1"
        found_devices2 = "2"  # this is used to check if new modules are being discovered or if all have been found.
        scan_wait = 2  # The number of seconds waited between the scan and the initial list
        list_wait = 1  # The time between checks for new devices in the list

        if scan:
            # Perform the initial scan attempt
            if ip_address is None:
                dev_string = self.sendAndReceiveText(self.sock, '$scan')
            else:
                dev_string = self.sendAndReceiveText(self.sock, '$scan TCP::' + ip_address)
            # Wait for devices to enumerate
            time.sleep(scan_wait)
            # While new devices are being found, extend the wait time
            while found_devices not in found_devices2:
                found_devices = self.sendAndReceiveText(self.sock, '$list')
                time.sleep(list_wait)
                found_devices2 = self.sendAndReceiveText(self.sock, '$list')
        else:
            found_devices = self.sendAndReceiveText(self.sock, '$list')

        # If we found devices, process them into a list to return
        if not "no devices found" in found_devices.lower():
            found_devices = found_devices.replace('>', '')
            found_devices = found_devices.split('\r\n')
            # Can't stream over REST. Removing all REST connections.
            temp_list= list()
            for item in found_devices:
                if item is None or "rest" in item.lower() or item == "":
                    pass
                else:
                    temp_list.append(item.split(")")[1].strip())
            found_devices = temp_list

            # If the preferred connection only flag is True, then only show one connection type for each module connected.
            # First, order the devices by their preference type and then pick the first con type found for each module.
            if preferred_connection_only:
                found_devices = self.sort_favourite(found_devices)
        else:
            found_devices = ["***No Devices Found***"]

        return found_devices

    def sort_favourite(self, found_devices) -> list:
        """
        Reduces the list of located devices by referencing to the preferred type of connection.  Only
        one connection type will be returned for each module for easier user selection. ie: A module connected
        on both USB and TCP will now only return with USB

        Args:
            found_devices:
                List of located devices from a scan operation

        Returns:
            List of devices filtered/sorted devices
        """

        index = 0
        sorted_found_devices = []
        con_pref = ["USB", "TCP", "SERIAL", "REST", "TELNET"]
        while len(sorted_found_devices) != len(found_devices):
            for device in found_devices:
                if con_pref[index] in device.upper():
                    sorted_found_devices.append(device)
            index += 1
        found_devices = sorted_found_devices

        # new dictionary only containing one favourite connection to each device.
        fav_con_found_devices = []
        index = 0
        for device in sorted_found_devices:
            if fav_con_found_devices == [] or not device.split("::")[1] in str(fav_con_found_devices):
                fav_con_found_devices.append(device)
        found_devices = fav_con_found_devices
        return found_devices

    def stream_running_status(self, device, sock=None) -> str:
        """
        returns a single word status string for a given device.  Generally this will be running, overrun, or stopped

        Arguments

        device : str
            The device ID to target
        sock:
            The socket to communicate over, or None to use the default.

        Returns:
            str: Single word status string to show the operation of streaming
        """
        if sock is None:
            sock = self.sock

        index = 0
        stream_status = self.sendAndReceiveText(sock, 'stream?', device)

        # Split the response, select the first time and trim the colon
        status_parts = stream_status.split('\r\n')
        stream_status = re.sub(r':', '', status_parts[index])
        return stream_status

    def stream_buffer_status(self, device, sock=None) -> str:
        """
        returns the info on the stripes buffered during the stream

        Arguments

        device : str
            The device ID to target
        sock:
            The socket to communicate over, or None to use the default.

        Returns:
            str: String with the numbers of stripes buffered
        """
        if sock is None:
            sock = self.sock

        index = 1
        stream_status = self.sendAndReceiveText(sock, 'stream?', device)

        # Split the response, select the second the info on the stripes buffered
        status_lines = stream_status.split('\r\n')
        stream_status = re.sub(r'^Stripes Buffered: ', '', status_lines[index])
        return stream_status

    # TODO: MD - This function should be replaced with a more generic method of accessing the header
    # The return of a string with concatenated value and units should be replaced with something easier to parse
    def stream_header_average(self, device, sock=None) -> str:
        """
        Gets the averaging used on the current stream, required for processing the stripe data returned from QIS

        Arguments

        device : str
            The device ID to target
        sock:
            The socket to communicate over, or None to use the default.

        Returns:
            str: String with the rate and unit
        """
        try:
            if sock is None:
                sock = self.sock

            index = 2 # index of relevant line in split string
            stream_status = self.send_and_receive_text(sock, send_text='stream text header', device=device)

            self.qps_stream_header = stream_status

            # Check for the header format.  If XML, process here
            if self.is_xml_header(stream_status):
                # Get the basic averaging rate (V3 header)
                xml_root = self.get_stream_xml_header(device=device, sock=sock)
                self.module_xml_header = xml_root

                # Return the time-based averaging string
                device_period = xml_root.find('.//devicePeriod')
                if device_period is None:
                    device_period = xml_root.find('.//devicePerioduS')
                    if device_period is None:
                        device_period = xml_root.find('.//mainPeriod')
                average_str = device_period.text
                return average_str
            # For legacy text headers, process here
            else:
                status_lines = stream_status.split('\r\n')
                if 'Header Not Available' in status_lines[0]:
                    dummy = status_lines[0] + '. Check stream has been run on device.'
                    return dummy
                average_str = re.sub(r'^Average: ', '', status_lines[index])
                avg = average_str
                avg = 2 ** int(avg)
                return '{}'.format(avg)
        except Exception as e:
            logging.error(device + ' Unable to get stream average.' + self.host + ':' + str(self.port))
            raise e

    def stream_header_format(self, device, sock=None) -> str:
        """
        Formats the stream header for use at the top of a CSV file.  This adds the appropriate time column and
        each of the channel data columns

        Arguments

        device:
            The device ID to target
        sock:
            The socket to communicate over, or None to use the default.

        Returns:
            str: Get the CSV formatted header string for the current stream
        """
        try:
            if sock is None:
                sock = self.sock

            index = 1
            stream_status = self.sendAndReceiveText(sock,'stream text header', device)
            # Check if this is an XML form header
            if self.is_xml_header (stream_status):
               # Get the basic averaging rate (V3 header)
               xml_root = self.get_stream_xml_header (device=device, sock=sock)
               # Return the time-based averaging string
               device_period = xml_root.find('.//devicePeriod')
               time_unit = 'uS'
               if device_period is None:
                   device_period = xml_root.find('.//devicePerioduS')
                   if device_period is None:
                       device_period = xml_root.find('.//mainPeriod')
                       if 'ns' in  device_period.text:
                        time_unit = 'nS'

               # The time column always first
               format_header = 'Time ' + time_unit + ','
               # Find the channels section of each group and iterate through it to add the channel columns
               for group in xml_root.iter():
                   if group.tag == "channels":
                       for chan in group:
                        # Avoid children that are not named channels
                            if (chan.find('.//name') is not None):
                                name_str = chan.find('.//name').text
                                group_str = chan.find('.//group').text
                                unit_str = chan.find('.//units').text
                                format_header = format_header +  name_str + " " + group_str + " " + unit_str + ","
               format_header = format_header.rstrip(",")
               return format_header
            else:
                stream_status = stream_status.split('\r\n')
                if 'Header Not Available' in stream_status[0]:
                    err_str = stream_status[0] + '. Check stream has been ran on device.'
                    logging.error(err_str)
                    return err_str
                output_mode = self.sendAndReceiveText(sock,'Config Output Mode?', device)
                power_mode = self.sendAndReceiveText(sock,'stream mode power?', device)
                data_format = int(re.sub(r'^Format: ', '', stream_status[index]))
                b0 = 1              #12V_I
                b1 = 1 << 1         #12V_V
                b2 = 1 << 2         #5V_I
                b3 = 1 << 3         #5V_V
                format_header = 'StripeNum, Trig, '
                if data_format & b3:
                    if '3V3' in output_mode:
                        format_header = format_header +  '3V3_V,'
                    else:
                        format_header = format_header +  '5V_V,'
                if data_format & b2:
                    if '3V3' in output_mode:
                        format_header = format_header +  ' 3V3_I,'
                    else:
                        format_header = format_header +  ' 5V_I,'

                if data_format & b1:
                    format_header = format_header + ' 12V_V,'
                if data_format & b0:
                    format_header = format_header + ' 12V_I'
                if 'Enabled' in power_mode:
                    if '3V3' in output_mode:
                        format_header = format_header + ' 3V3_P'
                    else:
                        format_header = format_header + ' 5V_P'
                    if (data_format & b1) or (data_format & b0):
                        format_header = format_header + ' 12V_P'
                return format_header
        except Exception as e:
            logging.error(device + ' Unable to get stream  format.' + self.host + ':' + '{}'.format(self.port))
            raise e

    def stream_get_stripes_text(self, sock, device: str) -> tuple[str, str]:
        """
        Retrieve and process text data from a QIS stream.
        We try to ready a block of data and also check for end of data and error cases

        Args:
            sock:
                The socket instance used for communication with the device.
            device:
                The device ID string

        Returns:
            A tuple containing:
            - The status of the data stream as a comma seperated list of status items
            - The retrieved text data from the stream.
        """

        stream_status = "running"
        is_end_of_block = False

        # Try and read the next blocks of stripes from QIS
        stripes = self.sendAndReceiveText(sock, 'stream text all', device)

        # The 'eof' marker ONLY indicates that the full number of requested stripes was not available.
        # More may be found later.
        if stripes.endswith("eof\r\n>"):
            is_end_of_block = True
            stripes = stripes.rstrip("eof\r\n>")
        # The current reader seems to lose the final line feeds, so check for this
        if len(stripes) > 0:
            if not stripes.endswith("\r\n"):
                stripes += "\r\n"

        # If there is an unusually small data set, check the stream status to make sure data is coming
        # 7 is a little arbitrary, but smaller than any possible stripe size.  Over calling will not matter anyway
        if len(stripes) < 7 or is_end_of_block:
            current_status = self.sendAndReceiveText(sock, 'stream?', device).lower()
            if "running" in current_status:
                stream_status = "running"
            elif "overrun" in current_status or "out of buffer" in current_status:
                stream_status = "overrun"
            elif "stopped" in current_status:
                stream_status = "stopped"
                # If the stream is stopped and at end of block, we have read all the data
                if is_end_of_block:
                    stream_status = stream_status + "eof"

        return stream_status, stripes

    def device_control_index(self, device) -> int:
        """
        Returns the index of the device in the control lists.  If the device is not
        registered, then it is added first.  This is a key part of allowing us to
        track the status of multiple streaming devices and manage them from outside
        their streaming thread

        Args:
            device:
                Device ID string
        Returns:
            Index of the device in the various control lists

        """
        if device in self.deviceList:
            return self.deviceList.index(device)
        else:
            self.listSemaphore.acquire()
            self.deviceList.append(device)
            self.stopFlagList.append(True)
            self.listSemaphore.release()
            return self.deviceList.index(device)

    def device_dict_setup(self, module) -> None:
        """
        Adds a dictionary entry for a new module we are connecting to (including the base QIS connection)
        This is used for tracking the status of modules throughout the streaming process

        Args:
            module:

        Returns:
            None
        """
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

    # Pass in a stream header and we check if it is XML or legacy format
    def is_xml_header (self, header_text) -> bool:
        """
        Checks if the given header string is in XML format (as apposed to legacy text format) or an invalid string

        Args:
            header_text:
                The header string to evaluate
        Returns:
            True if the header is in XML form

        """
        if '?xml version=' not in header_text:
            return False
        else:
            return True

    # Internal function.  Gets the stream header and parses it into useful information
    def get_stream_xml_header (self, device, sock=None) -> ET.Element:
        """
        Gets the XML format header from an attached device (which must have run or be running a stream)
        Parses the string into XML and returns the root element

        Args:
            device:
                Device ID to return from
            sock:
                Optional QIS socket to use for communication.

        Returns:

        """
        header_data = None

        try:
            if sock is None:
                sock = self.sock
            count = 0
            while True:
                if count > 5:
                    break
                count += 1
                # Get the raw data
                header_data = self.send_and_receive_text(sock, send_text='stream text header', device=device)

                # Check for no header (no stream started)
                if 'Header Not Available' in header_data:
                    logging.error(device + ' Stream header not available.' + self.host + ':' + str(self.port))
                    continue

                # Check for XML format
                if '?xml version=' not in header_data:
                    logging.error(device + ' Header not in XML form.' + self.host + ':' + str(self.port))
                    continue

                break
            # Parse XML into a structured format
            xml_root = ET.fromstring(header_data)

            # Check header format is supported by quarchpy
            version_str = xml_root.find('.//version').text
            if 'V3' not in version_str:
                logging.error(device + ' Stream header version not compatible: ' + xml_root.find('version').text + '.' + self.host + ':' + str(self.port))
                raise Exception ("Stream header version not supported")

            # Return the XML structure for the code to use
            return xml_root

        except Exception as e:
            logging.error(device + ' Exception while parsing stream header XML.' + self.host + ':' + str(self.port))
            raise e

    def send_command (self, command: str, device: str = '', qis_socket: socket.socket=None, no_cursor_expected: bool=False, no_response_expected: bool=False, command_delay: float=0.0) -> str:
        """
        Sends a command and returns the response as a string.  Multiple lines are escaped with CRLF.
        The command is sent to the QIS socket, and depending on the command will be replied by either QIS
        or the hardware module.

        Args:
            command:
                Command string
            device:
                Optional Device ID string to send the command to. Use default/blank for QIS direct commands
            qis_socket:
                Optional Socket to use for the command, if the default is not wanted
            no_cursor_expected:
                Optional Flag true if the command does not return a cursor, so we should not wait for it
            no_response_expected:
                Optional Flag true if the command does not return a response, so we should not wait for it.
            command_delay:
                Optional delay to prevent commands running in close succession.  Timed in seconds.
        Returns:
            Command response string or None if no response expected
        """
        if no_response_expected:
            self.send_text(qis_socket, command, device)
            return ""
        else:
            if qis_socket is None:
                qis_socket = self.sock
            if not (device == ''):
                self.device_dict_setup(device)
            res = self.send_and_receive_text(qis_socket, command, device, not no_cursor_expected)

            # This is a poor sleep mechanism!  Better would be to track time since the last command
            if command_delay > 0:
                time.sleep(command_delay)

            # Trim the expected cursor at the end of the response
            if res[-3:] == '\r\n>':
                res = res[:-3]  # remove last three chars - '\r\n>'
            elif res[-2:] == '\n>':
                    res = res[:-2]  # remove last 2 chars - '\n>'
            return res

    def send_and_receive_text(self, sock, send_text='$help', device='', read_until_cursor=True) -> str:
        """
        Internal function for command handling.  This handles complex cases such as timeouts and XML
        response formatting, which conflicts with the default cursor

        Args:
            sock:
                The socket to communicate over
            send_text:
                The command text to send
            device:
                Optional device ID to send the command to
            read_until_cursor:
                Flag to indicate if we should read until the cursor is returned

        Returns:
            Response string from the module
        """

        # Avoid multiple threads trying to send at once. QIS only has a single socket for all devices
        self.sockSemaphore.acquire()
        try:
            # Send the command
            self.send_text(sock, send_text, device)
            # Receive Response
            res = self.receive_text(sock)
            # If we get no response, log an error and try to flush using a simple stream query command
            # If that works, we retry our command.  In fail cases we raise an exception and abort as
            # the connection is bad
            if len(res) == 0:
                logging.error("Empty response from QIS for cmd: " + send_text + ". To device: " + device)
                self.send_text(sock, "stream?", device)
                res = self.receive_text(sock)
                if len(res) != 0:
                    self.send_text(sock, send_text, device)
                    res = self.receive_text(sock)
                    if len(res) == 0:
                        raise (Exception("Empty response from QIS. Sent: " + send_text))
                else:
                    raise (Exception("Empty response from QIS. Sent: " + send_text))

            if res[0] == self.cursor:
                logging.error('Only returned a cursor from QIS. Sent: ' + send_text)
                raise (Exception("Only returned a cursor from QIS. Sent: " + send_text))
            if 'Create Socket Fail' == res[0]: # If create socked fail (between QIS and tcp/ip module)
                logging.error(res[0])
                raise (Exception("Failed to open QIS to module socked. Sent: " + send_text))
            if 'Connection Timeout' == res[0]:
                logging.error(res[0])
                raise (Exception("Connection timeout from QIS. Sent: " + send_text))

            # If reading until a cursor comes back, then keep reading until a cursor appears or max tries exceeded
            # Because large XML responses are possible, we need to validate them as complete before looking
            # for a final cursor
            if read_until_cursor:

                max_reads = 1000
                count = 1
                is_xml = False

                while True:

                    # Determine if the response is XML based on its start
                    if count == 1:  # Only check this on the first read
                        if res.startswith("<?xml"):  # Likely XML if it starts with '<'
                            is_xml = True
                        elif res.startswith("<XmlResponse"):
                            is_xml = True


                    if is_xml:
                        # Try to parse the XML to check if it's complete
                        try:
                            ET.fromstring(res[:-1])  # If it parses, the response is complete
                            return res[:-1]  # Exit the loop, valid XML received
                        except ET.ParseError:
                            pass  # Keep reading until XML is complete
                    else:
                        # Handle normal strings
                        if res[-1:] == self.cursor:  # If the last character is '>', stop reading
                            break

                    # Receive more data
                    res += self.receive_text(sock)

                    # Increment count and check for max reads
                    count += 1
                    if count >= max_reads:
                        raise Exception('Count = Error: max reads exceeded before response was complete')

            return res

        except Exception as e:
            # Something went wrong during send qis cmd
            logging.error("Error! Unable to retrieve response from QIS. Command: " + send_text)
            logging.error(e)
            raise e
        finally:
            self.sockSemaphore.release()

    def receive_text(self, sock) -> str:
        """
        Received bytes from the socket and converts to a test string
        Args:
            sock:
                Socket to communicate over

        Returns:

        """
        res = bytearray()
        res.extend(self.rx_bytes(sock))
        res = res.decode()

        return res

    def send_text(self, sock, message='$help', device='') -> bool:
        """

        Args:
            sock:
                Socket to communicate over
            message:
                text command to send
            device:
                Optional device ID to target with the command

        Returns:

        """
        # Send text to QIS, don't read its response
        if device != '':
            message = device + ' ' + message

        conv_mess = message + '\r\n'
        sock.sendall(conv_mess.encode('utf-8'))
        return True

    def rx_bytes(self,sock) -> bytes:
        """
        Reads an array of bytes from the socket as part of handling a command response

        Args:
            sock:
                Socket to communicate over
        Returns:
            Bytes read

        """

        max_exceptions=10
        exceptions=0
        max_read_repeats=50
        read_repeats=0
        timeout_in_seconds = 10

        #Keep trying to read bytes until we get some, unless the number of read repeats or exceptions is exceeded
        while True:
            try:
                # Select.select returns a list of waitable objects which are ready. On Windows, it has to be sockets.
                # The first argument is a list of objects to wait for reading, second writing, third 'exceptional condition'
                # We only use the read list and our socket to check if it is readable. if no timeout is specified,
                # then it blocks until it becomes readable.
                # TODO: AN: It is very unclear why we try to open a new socket if data is not ready.
                #   This would seem like a hard failure case!
                ready = select.select([sock], [], [], timeout_in_seconds)
                if ready[0]:
                    ret = sock.recv(self.maxRxBytes)
                    return ret
                # If the socket is not ready for read, open a new one
                else:
                    logging.error("Timeout: No bytes were available to read from QIS")
                    logging.debug("Opening new QIS socket")
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.connect((self.host, self.port))
                    sock.settimeout(5)

                    try:
                        welcome_string = self.sock.recv(self.maxRxBytes).rstrip()
                        welcome_string = 'Connected@' + self.host + ':' + str(self.port) + ' ' + '\n    ' + welcome_string
                        logging.debug("Socket opened: " + welcome_string)
                    except Exception as e:
                        logging.error('Timeout: Failed to open new QIS socket and get the welcome message')
                        raise e

                    read_repeats=read_repeats+1
                    time.sleep(0.5)

            except Exception as e:
                raise e

            # If we read no data, its probably an error, but there may be cases where an empty response is valid
            if read_repeats >= max_read_repeats:
                logging.error('Max read repeats exceeded')
                return b''

    def closeConnection(self, sock=None, conString: str=None) -> str:
        """
        deprecated:: 2.2.13
        Use `close_connection` instead.
        """
        return self.close_connection (sock=sock, con_string=conString)

    def startStream(self, module: str, fileName: str, fileMaxMB: int, releaseOnData: bool, separator: str,
                    streamDuration: int = None, inMemoryData=None, outputFileHandle=None, useGzip: bool = None):
        """
        deprecated:: 2.2.13
        Use `start_stream` instead.
        """
        return self.start_stream(module, fileName, fileMaxMB, releaseOnData, separator, streamDuration, inMemoryData, outputFileHandle, useGzip)

    def stopStream(self, module, blocking=True):
        """
        deprecated:: 2.2.13
        Use `stop_stream` instead.
        """
        return self.stop_stream(module, blocking)

    def getDeviceList(self, sock=None):
        """
        deprecated:: 2.2.13
        Use `start_stream_thread_qps` instead.
        """
        return self.get_device_list(sock)

    def scanIP(self, QisConnection, ipAddress):
        """
        deprecated:: 2.2.13
        Use `scan_ip` instead.
        """
        return self.scan_ip(QisConnection, ipAddress)

    def GetQisModuleSelection(self, favouriteOnly=True, additionalOptions=['rescan', 'all con types', 'ip scan'],
                          scan=True):
        """
        deprecated:: 2.2.13
        Use `get_qis_module_selection` instead.
        """
        return self.get_qis_module_selection(favouriteOnly, additionalOptions, scan)

    def sendCommand(self, cmd, device="", timeout=20,sock=None,readUntilCursor=True, betweenCommandDelay=0.0, expectedResponse=True) -> str:
        """
        deprecated:: 2.2.13
        Use `send_command` instead.
        """
        return self.send_command(cmd, device, sock, False, not expectedResponse, betweenCommandDelay)

    def sendCmd(self, device='', cmd='$help', sock=None, readUntilCursor=True, betweenCommandDelay=0.0, expectedResponse = True) -> str:
        """
        deprecated:: 2.2.13
        Use `send_command` instead.
        """
        return self.send_command(cmd, device, sock, not readUntilCursor, not expectedResponse, betweenCommandDelay)

    def sendAndReceiveCmd(self, sock=None, cmd='$help', device='', readUntilCursor=True, betweenCommandDelay=0.0) -> str:
        """
        deprecated:: 2.2.13
        Use `send_command` instead.
        """
        return self.send_command(cmd, device, sock, not readUntilCursor, no_response_expected=False, command_delay=betweenCommandDelay)

    def streamRunningStatus(self, device: str) -> str:
        """
        deprecated:: 2.2.13
        Use `stream_running_status` instead.
        """
        return self.stream_running_status(device)

    def streamHeaderFormat(self, device, sock=None) -> str:
        """
        deprecated:: 2.2.13
        Use `stream_header_format` instead.
        """
        return self.stream_header_format(device, sock)

    def streamInterrupt(self) -> bool:
        """
        deprecated:: 2.2.13
        No indication this is used anywhere
        """
        for key in self.deviceDict.keys():
            if self.deviceDict[key][0]:
                return True
        return False

    def interruptList(self):
        """
        deprecated:: 2.2.13
        No indication this is used anywhere
        """
        streamIssueList = []
        for key in self.deviceDict.keys():
            if self.deviceDict[key][0]:
                streamIssue = [key]
                streamIssue.append(self.deviceDict[key][1])
                streamIssue.append(self.deviceDict[key][2])
                streamIssueList.append(streamIssue)
        return streamIssueList

    def waitStop(self):
        """
        deprecated:: 2.2.13
        No indication this is used anywhere
        """
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
        """
        deprecated:: 2.2.13
        No indication this is used anywhere
        """
        returnValue = 32000
        if ("k" in streamAveraging):
            returnValue = streamAveraging.replace("k", "000")
        else:
            returnValue = streamAveraging

        return returnValue

    def sendAndReceiveText(self, sock, sendText='$help', device='', readUntilCursor=True) -> str:
        """
        deprecated:: 2.2.13
        Use `send_and_receive_text` instead.
        """
        return self.send_and_receive_text(sock, send_text=sendText, device=device, read_until_cursor=readUntilCursor)