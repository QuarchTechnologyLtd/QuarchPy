import socket
import re
import gzip
import datetime
from unittest.mock import open_spec

import select
import threading
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
        Connects to the backend QIS instance using a socket.  Host and port parameters
        were set during class init and are generally the localhost

        If successful, it retrieves and returns the backend's welcome string.
        In case of failure, an exception is raised and an appropriate error message is logged.
        The backend server must be running

        Parameters:
        connectionMessage: bool, optional
            Defaults to True. If set to False, suppresses the warning message about an
            instance already running on the specified port. This can be useful when
            using `isQisRunning()` from `qisFuncs`.

        Raises:
        Exception:
            If the connection fails or the welcome string is not received an exception is raised

        Returns:
        str:
            The welcome string received from the backend server upon a successful
            connection.  This will confirm the QIS version but is generally not used other than
            for debugging
        """

        try:
            self.deviceDictSetup('QIS')
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
            self.deviceDictSetup('QIS')
            if connection_message:
                logging.error('Unable to connect to Quarch backend on specified host and port (' + self.host + ':' + str(self.port) + ').')
                logging.error('Is backend running and host accessible?')
            self.deviceDict['QIS'][0:3] = [True, 'Disconnected', 'Unable to connect to QIS']
            raise e


    def disconnect(self):
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
        Instructs QIS to close the connection to physical device(s).  This will release the device such
        that it is accessible by other users.

        Parameters:
            sock: Optional; The socket object to close the connection to. Defaults to
                  the existing socket.
            con_string: Optional; Specify the device ID to close, otherwise all devices will be closed

        Returns:
            str: The response received after sending the close command. On success, this will be: 'OK'

        Raises:
            ConnectionResetError: Raised if the socket connection has already been
                                  reset.
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
        Initiates a data streaming process against a specified module. This is done by beginning a new thread

        Parameters:
        module : str
            The ID of the module for which the stream is being initiated.
        file_name : str
            The target file path+name for storing the  streamed data in CSV form.
        max_file_size : int
            The maximum size in megabytes allowed for the output file.
        release_on_data : bool
            If set, blocks further streams until this one has started fully
        separator : str
            The value separator used to format the streamed CSV data.
        stream_duration : float, optional
            The duration (in seconds) for which the streaming process should run. Unlimited if None.
        in_memory_data : object, optional
            An in memory CSV StringIO as an alternate to file output
        output_file_handle : object, optional
            A file handle to an output file where the stream data is written as an alternate to a file name
        use_gzip : bool, optional
            A flag indicating whether the output file should be compressed using gzip to reduce disk use

        Raises:
        None
        """
        self.StreamRunSentSemaphore.acquire()
        self.deviceDictSetup('QIS')
        i = self.deviceMulti(module)
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

    def start_stream_qps(self, module: str, file_name: str, max_file_size: float, release_on_data: bool):
        """
        Similar to start_stream, but the output is a QPS-compatible analysis file.

        Parameters:
        module: str
            The ID of the module for which to start the streaming operation.
        file_name: str
            The path of the file to which the streamed data will be saved.
        max_file_size: int
            Maximum total size of the streamed data in MB.
        release_on_data: Any
            Indicates whether to release a lock or semaphore after data streaming.
        """
        self.StreamRunSentSemaphore.acquire()
        self.deviceDictSetup('QIS')
        i = self.deviceMulti(module)
        self.stopFlagList[i] = True
        self.stripesEvent.set()
        self.module_xml_header = None

        # Create the thread
        t1 = threading.Thread(target=self.startStreamThreadQPS, name=module,
                              args=(module, file_name, max_file_size, release_on_data))
        # Start the thread
        t1.start()

        while self.stripesEvent.is_set():
            pass

    def stop_stream(self, module, blocking:bool = True):
        """
        Stops the data streaming process for a specified module ID. When blocking is requested, the function will
        not return until the data streaming process has stopped and all data has been written to the file.

        Parameters
        ----------
        module
            The quarchPPM module instance for which the streaming process is to be stopped.
        blocking : bool
            If set to True, the function will block and wait until the module has
            completely stopped streaming. Defaults to True.

        Raises
        ------
        None

        Returns
        -------
        None
        """

        module_name=module.ConString
        i = self.deviceMulti(module_name)
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
        Runs as a separate thread to collect data from a specified module and writes it to a CSV file, an
        in-memory buffer, or an existing file handle. Manages file opening and closing, as well as data
        streaming. All major data processing is done here.

        Arguments:
        module : str
            The name of the module from which data is to be streamed.
        file_name : str
            The path to the file where streamed data will be written. Mandatory if neither an in-memory
            buffer (in_memory_data) nor an external file handle (output_file_handle) is provided.
        max_file_size : float
            The maximum permissible file size in MB. After reaching this limit, streaming to the current
            file will stop
        release_on_data : bool
            True to prevent the stream lock from releasing until data has been received
        separator : str
            Custom separator used to CSV data
        stream_duration : int, optional
            Duration of streaming in seconds, relative to the sampling period. Defaults to streaming
            indefinitely.
        in_memory_data : StringIO, optional
            An in-memory buffer of type StringIO to hold streamed data. If set, data is written here
            instead of a file.
        output_file_handle : file-like object, optional
            A pre-opened file handle where data will be written. If set, file_name is ignored.
        use_gzip : bool, default False
            If True, writes streamed data to a gzip-compressed file.

        Raises:
        TypeError
            If in_memory_data is passed but is not of type StringIO.
        ValueError
            If file_name is not provided and neither in_memory_data nor output_file_handle is given.
            Also raised for invalid or undecodable sampling periods.
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
        stream_res = self.sendAndReceiveCmd(self.streamSock, 'rec stream', device=module, betweenCommandDelay=0)
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
                i = self.deviceMulti(module)
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
                self.sendAndReceiveCmd(self.streamSock, 'rec stop', device=module, betweenCommandDelay=0)
                stream_state = self.sendAndReceiveCmd(self.streamSock, 'stream?', device=module, betweenCommandDelay=0)
                while "stopped" not in stream_state.lower():
                    logging.debug("waiting for stream? to return stopped")
                    time.sleep(0.1)
                    stream_state = self.sendAndReceiveCmd(self.streamSock, 'stream?', device=module, betweenCommandDelay=0)

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

    def start_stream_thread_qps(self, module, file_name: str, release_on_data: bool):
        """
        Runs as a separate thread to collect data from a specified module and writes it to a QPS
        formal analysis file. Manages file opening and closing, as well as data streaming.
        All major data processing is done here.

        Arguments:
            module : str
                The name of the module from which data is to be streamed.
            file_name : str
                The path to the file where streamed data will be written.
            release_on_data : bool
                True to prevent the stream lock from releasing until data has been received

        Raises:
            IOError: If there are excessive IO errors while managing the stream.
        """

        separator = ','
        self.qps_record_start_time = time.time() * 1000

        # Send stream command so the module starts streaming data into the backends buffer
        stream_res = self.sendAndReceiveCmd(self.streamSock, 'rec stream', device=module, betweenCommandDelay=0)
        # Check the stream started
        if 'OK' in stream_res:
            if not release_on_data:
                self.StreamRunSentSemaphore.release()
                self.stripesEvent.clear()
            self.deviceDict[module][0:3] = [False, 'Running', 'Stream Running']
        else:
            self.StreamRunSentSemaphore.release()
            self.stripesEvent.clear()
            self.deviceDict[module][0:3] = [True, 'Stopped', module + " couldn't start because: " + stream_res]
            return

        # Ensure a file is specified
        if file_name is None:
            self.deviceDict[module][0:3] = [True, 'Stopped', module + " couldn't start - file path not specified"]
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
                return

        open_attempts = 0
        stream_overrun = False
        stream_complete = False
        is_run = True

        # Create the analysis file structure including subfolders
        self.create_dir_structure(module, file_name)

        # Now we loop to process the stripes of data as they are available
        while is_run:
            try:
                # Check for exit flags.  These can be from user request (stopFlagList) or from the stream
                # process ending
                i = self.deviceMulti(module)
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

                        # Write the stripes into the analysis file format
                        if "\r\n" in y:
                            y = y.split("\r\n")

                            if self.has_digitals:
                                # Write qps files for PAM
                                for stripes in y:
                                    if stripes:
                                        stripe = stripes.split(",")
                                        self.write_stripe_to_files_pam(stripe)
                            else:
                                # Write qps files for PPM
                                for stripes in y:
                                    if stripes:
                                        stripe = stripes.split(",")
                                        self.write_stripe_to_files_hd(stripe)

                        else:
                            if self.has_digitals:
                                # Write qps files for PAM
                                for stripes in y:
                                    if stripes:
                                        stripe = stripes.split(",")
                                        self.write_stripe_to_files_pam(stripe)
                            else:
                                # Write qps files for PPM
                                for stripes in y:
                                    if stripes:
                                        stripe = stripes.split(",")
                                        self.write_stripe_to_files_hd(stripe)


                    else:
                        if stream_overrun:
                            break  # Exit stream processing loop
                        elif "stopped" in stream_status_str:
                            self.deviceDict[module][0:3] = [True, 'Stopped', 'User halted stream']
                            break  # Exit stream processing loop
                # End of stream data processing loop

                # Ensure the stream is fully stopped, though standard exit cases should have ended it already
                self.sendAndReceiveCmd(self.streamSock, 'rec stop', device=module, betweenCommandDelay=0)
                stream_state = self.sendAndReceiveCmd(self.streamSock, 'stream?', device=module,
                                                      betweenCommandDelay=0)
                while "stopped" not in stream_state.lower():
                    logging.debug("waiting for stream? to return stopped")
                    time.sleep(0.1)
                    stream_state = self.sendAndReceiveCmd(self.streamSock, 'stream?', device=module,
                                                                      betweenCommandDelay=0)

                if stream_overrun:
                    self.deviceDict[module][0:3] = [True, 'Stopped', 'Device buffer overrun - QIS buffer empty']

                is_run = False  # Exit main while loop
            except IOError as err:
                logging.error(f"IOError in startStreamThread for module {module}: {err}")
                time.sleep(0.5)
                open_attempts += 1
                if open_attempts > 4:
                    logging.error(f"Too many IOErrors in QisInterface for module {module}. Raising error.")
                    # Set device status before raising, if possible
                    self.deviceDict[module][0:3] = [True, 'Stopped', f'IOError limit exceeded: {err}']
                    raise err

        # Finish up be creating the remaining items needed for the analysis file structure
        self.create_index_file()
        if self.has_digitals:
            self.create_index_file_digitals()
        self.create_qps_file(module)

    def write_stripe_to_files_hd(self, stripe):
        """
        Writes data from a given stripe in legacy HD format

        Arguments:
            stripe : str
                CSV form stripe from QIS
        """

        # Cycle through items in stripe
        for index, item in enumerate(stripe):
            if index == 0:
                continue
            with (open(os.path.join(self.qps_record_dir_path, "data000", "data000_00" + str(index - 1) + "_000000000"),
                       "a") as file1):

                x = struct.pack(">d", int(item))
                file1.write(x)

    def write_stripe_to_files_pam(self, stripe):
        """
        Writes data from a given stripe in PAM format

        Arguments:
            stripe : str
                CSV form stripe from QIS
        """

        # Note to reader - List should be ordered 1>x on analogue and digitals
        counter = 0
        for group in self.streamGroups.groups:
            for i, channel in enumerate(group.channels):
                # incrementing here, so we skip stripe[0] which is time
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

    def get_device_list(self, sock=None):
        """
        Retrieves the list of devices connected to QIS.  This does NOT re-scan, just returns the current list

        This method communicates with the server to retrieve information about
        the devices currently connected. The list of devices is processed and
        formatted into a clean list of device names or identifiers.

        Arguments:
        sock : Optional
            The network socket used for communication. If not provided, the
            class's default socket will be used.

        Returns:
        list
            A list of device identifiers retrieved from the QIS.
        """

        if sock is None:
            sock = self.sock

        dev_string = self.sendAndReceiveText(sock, '$list')
        dev_string = dev_string.replace('>', '')
        dev_string = dev_string.replace(r'\d+\) ', '')
        dev_string = dev_string.split('\r\n')
        dev_string = filter(None, dev_string) #remove empty elements

        return dev_string

    def get_list_details(self, sock=None):
        if sock is None:
            sock = self.sock

        dev_string = self.sendAndReceiveText(sock, '$list details')
        dev_string = dev_string.replace('>', '')
        dev_string = dev_string.replace(r'\d+\) ', '')
        dev_string = dev_string.split('\r\n')
        dev_string = [x for x in dev_string if x]  # remove empty elements
        return dev_string

    def scan_ip(self, qis_connection, ip_address):
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
            response = qis_connection.sendCmd(cmd="$scan " + ip_address, expectedResponse=True)
            # The valid response is "Located device: 192.168.1.2"
            if "located" in response.lower():
                logging.debug(response)
                # return the valid response
                return response
            else:
                if "startup" not in response.lower():
                    logging.warning("No module found at " + ip_address)
                    logging.warning(response)
                return response

        except Exception as e:
            logging.warning(e)
            if "startup" not in response.lower():
                logging.warning("No module found at " + ip_address)

    def get_qis_module_selection(self, preferred_connection_only=True , additional_options=['rescan', 'all con types', 'ip scan'], scan=True):
        """
        Scans for available modules and allows the user to select one through an interactive selection process.

        Arguments:
            preferred_connection_only : bool
                by default (True), returns only one preferred connection eg: USB for simplicity
            additional_options: list
                Additional operational options provided during module selection, such as rescan,
                all connection types, and IP scan. Defaults to ['rescan', 'all con types', 'ip scan']. These allow the
                additional options to be given to the user and handled in the top level script
            scan : bool
                Indicates whether to initiate a rescanning process for devices prior to listing. Defaults to True and
                will take longer to return

        Returns:
            str: The identifier of the selected module, or the action selected from the additional options.

        Raises:
            KeyError: Raised when unexpected keys are found in the scanned device data.
            ValueError: Raised if no valid selection is made or the provided IP address is invalid.
        """
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

    def qis_scan_devices(self, scan=True, preferred_connection_only=True, ip_address=None):
        """
        Begins a scan for new devices.  If you want a specific module by IP address instead of a general
        scan, you can supply it with the ip_address parameter.

        Arguments

        scan : bool
            Should a scan be initiated?  If False, the function will return immediately with the list
        preferred_connection_only : bool
            Tby default (True), returns only one preferred connection eg: USB for simplicity
        ip_address: str
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
                found_devices = self.sortFavourite(found_devices)
        else:
            found_devices = ["***No Devices Found***"]

        return found_devices

    def sort_favourite(self, found_devices):
        """
        Reduces the list of located devices by referencing to the preferred type of connection.  Only
        one connection type will be returned for each module for easier user selection. ie: A module connected
        on both USB and TCP will now only return with USB

        Arguments

        found_devices : list
            List of located devices from a scan operation

        Returns:
            list: Filtered list of modules with only one connection type.
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

    def stream_running_status(self, device, sock=None):
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
        stream_status = stream_status.split('\r\n')
        stream_status[index] = re.sub(r':', '', stream_status[index])
        return stream_status[index]

    def stream_buffer_status(self, device, sock=None):
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
        stream_status = stream_status.split('\r\n')
        stream_status[index] = re.sub(r'^Stripes Buffered: ', '', stream_status[index])
        return stream_status[index]

    # TODO: MD - This function should be replaced with a more generic method of accessing the header
    # The return of a string with concatenated value and units should be replaced with something easier to parse
    def stream_header_average(self, device, sock=None):
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
            stream_status = self.sendAndReceiveText(sock, sentText='stream text header', device=device)

            self.qps_stream_header = stream_status

            # Check for the header format.  If XML, process here
            if (self.is_xml_header(stream_status)):
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
                stream_status = stream_status.split('\r\n')
                if 'Header Not Available' in stream_status[0]:
                    dummy = stream_status[0] + '. Check stream has been run on device.'
                    return dummy
                stream_status[index] = re.sub(r'^Average: ', '', stream_status[index])
                avg = stream_status[index]
                avg = 2 ** int(avg)
                return '{}'.format(avg)
        except Exception as e:
            logging.error(device + ' Unable to get stream average.' + self.host + ':' + str(self.port))
            raise e

    def stream_header_format(self, device, sock=None):
        """
        Formats the stream header for use at the top of a CSV file.  This adds the appropriate time column and
        each of the channel data columns

        Arguments

        device : str
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
            # Check if this is a XML form header
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
                        if chan.find('.//name') is not None:
                            name_str = chan.find('.//name').text
                            unit_str = chan.find('.//units').text
                            format_header = format_header +  name_str + " " + unit_str + ","
               return format_header
            # Handle legacy HD text headers here.  This is only to support remaining users on very old versions
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

        Parameters:
        sock: Socket
            The socket instance used for communication with the device.
        device: str
            The device ID string

        Returns:
        tuple[str, str]
            A tuple containing:
            - The status of the data stream as a comma seperated list of status items
            - The retrieved text data from the stream.
        """

        stream_status = "running"
        is_end_of_block = False

        # Try and read the next blocks of stripes from QIS
        stripes = self.sendAndReceiveText(sock, 'stream text all', device, readUntilCursor=True)

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

    def deviceMulti(self, device):
        if device in self.deviceList:
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
    def is_xml_header (self, header_text):
        if '?xml version=' not in header_text:
            return False
        else:
            return True

    # Internal function.  Gets the stream header and parses it into useful information
    def get_stream_xml_header (self, device, sock=None):
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
                header_data = self.sendAndReceiveText(sock, sentText='stream text header', device=device)

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
                logging.error(device + ' Stream header version not compatible: ' + xml_root['version'].text + '.' + self.host + ':' + str(self.port))
                raise Exception ("Stream header version not supported");

            # Return the XML structure for the code to use
            return xml_root

        except Exception as e:
            logging.error(device + ' Exception while parsing stream header XML.' + self.host + ':' + str(self.port))
            raise e

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
            if res[-3:] == '\r\n>':
                res = res[:-3]  # remove last three chars - '\r\n>'
            elif res[-2:] == '\n>':
                    res = res[:-2]  # remove last 2 chars - '\n>'
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
                import xml.etree.ElementTree as ET

                maxReads = 1000
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
                    res += self.receiveText(sock)

                    # Increment count and check for max reads
                    count += 1
                    if count >= maxReads:
                        raise Exception('Count = Error: max reads exceeded before response was complete')

            return res

        except Exception as e:
            #something went wrong during send qis cmd
            logging.error("Error! Unable to retrieve response from QIS. Command: " + sentText)
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

    def closeConnection(self, sock=None, conString: str=None) -> str:
        """
        deprecated:: 2.2.13
        Use `close_connection` instead.
        """
        return self.close_connection (self, sock, conString)

    def startStream(self, module: str, fileName: str, fileMaxMB: int, releaseOnData: bool, separator: str,
                    streamDuration: int = None, inMemoryData=None, outputFileHandle=None, useGzip: bool = None):
        """
        deprecated:: 2.2.13
        Use `start_stream` instead.
        """
        return self.start_stream(module, fileName, fileMaxMB, releaseOnData, separator, streamDuration, inMemoryData, outputFileHandle, useGzip)

    def startStreamQPS(self, module, fileName, fileMaxMB, streamName, streamAverage, releaseOnData, separator):
        """
        deprecated:: 2.2.13
        Use `start_stream_qps` instead.
        """
        self.start_stream_qps (module, fileName, fileMaxMB, releaseOnData)

    def stopStream(self, module, blocking=True):
        """
        deprecated:: 2.2.13
        Use `stop_stream` instead.
        """
        self.stop_stream(module, blocking)

    def startStreamThreadQPS(self, module, fileName, releaseOnData, separator):
        """
        deprecated:: 2.2.13
        Use `start_stream_thread_qps` instead.
        """
        self.start_stream_thread_qps(module, fileName, releaseOnData)

    def getDeviceList(self, sock=None):
        """
        deprecated:: 2.2.13
        Use `start_stream_thread_qps` instead.
        """
        self.get_device_list(sock)

    def scanIP(self, QisConnection, ipAddress):
        """
        deprecated:: 2.2.13
        Use `scan_ip` instead.
        """
        self.scan_ip(QisConnection, ipAddress)

    def GetQisModuleSelection(self, favouriteOnly=True, additionalOptions=['rescan', 'all con types', 'ip scan'],
                          scan=True):
        """
        deprecated:: 2.2.13
        Use `get_qis_module_selection` instead.
        """
        self.get_qis_module_selection(favouriteOnly, additionalOptions, scan)
