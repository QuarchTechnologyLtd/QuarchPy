import logging
import sys
import time

from quarchpy.device import quarchDevice
from quarchpy.user_interface.user_interface import requestDialog
from quarchpy.utilities.Version import Version
from quarchpy.utilities.utils import (
    check_stream_stopped_status, check_export_status, current_second_time, current_milli_time
)

if sys.version_info[0] < 3:
    from StringIO import StringIO
else:
    from io import StringIO


# Using standard Unix time, milliseconds since the epoch (midnight 1 January 1970 UTC)
# Should avoid issues with time zones and summer time correction but the local and host
# clocks should still be synchronised
def qpsNowStr():
    """Gets the current time as milliseconds since the Unix epoch.

    Uses the utility function `current_milli_time` which aims to provide
    a timestamp suitable for Quarch systems, avoiding timezone/DST issues
    if clocks are synchronized.

    Returns:
        str: The current time as a string representing milliseconds
             since the epoch (e.g., "1678886400123").
    """
    return current_milli_time()  # datetime supports microseconds


class quarchQPS(quarchDevice):
    """
    Represents a Quarch Power Supply (QPS) device, extending quarchDevice.

    Handles interaction specific to QPS modules, including stream management.
    """

    def __init__(self, quarchDevice):
        """
        Initializes the quarchQPS wrapper using an existing quarchDevice object.

        Args:
            quarchDevice (quarchDevice): An initialized instance of
                the base quarchDevice class containing connection details.
        """
        super().__init__(quarchDevice.ConString)
        self.quarchDevice = quarchDevice
        self.ConType = quarchDevice.ConType
        self.ConString = quarchDevice.ConString

        self.connectionObj = quarchDevice.connectionObj
        self.IP_address = quarchDevice.connectionObj.qps.host
        self.port_number = quarchDevice.connectionObj.qps.port

    def startStream(self, directory, unserInput=True, streamDuration=""):
        """DEPRECATED or ALIAS: Use start_stream instead.

        Starts a stream by calling the start_stream method.

        Args:
            directory (str): The desired directory for the stream output.
            unserInput (bool, optional): If True (default), allows user interaction
                to rectify issues if a failure occurs. Set to False if user
                interaction is unavailable (e.g., automation). Defaults to True.
            streamDuration (str, optional): Specifies the duration of the stream.
                An empty string (default) signifies an indefinite stream.

        Returns:
            quarchStream: An instance of the quarchStream class which manages
            the newly initiated stream.
        """
        return self.start_stream(directory, unserInput, streamDuration)

    def start_stream(self, directory, unserInput=True, streamDuration=""):
        """
        Initializes and starts a Quarch data stream.

        This method creates a quarchStream object, which handles the setup
        and management of the data stream from the QPS device to the specified
        directory.

        Args:
            directory (str): The target directory where stream data will be saved.
            unserInput (bool, optional): Controls user interaction on failure
                during stream initiation. If True (default), prompts the user.
                If False, suppresses interaction and raises an Exception on failure.
                Defaults to True.
            streamDuration (str, optional): Defines the requested duration for the
                stream. An empty string (default) signifies an indefinite stream.

        Returns:
            quarchStream: An instance of the quarchStream class representing and
            managing the active stream.
        """
        return quarchStream(self, directory, unserInput, streamDuration)


class quarchStream:
    """
    Manages an active data stream from a Quarch QPS device.

    Instantiation automatically attempts to start the stream. Provides methods to control and monitor the stream.
    """

    def __init__(self, quarchQPS, directory, unserInput=True, streamDuration=""):
        """
        Initializes and attempts to start a data stream from the QPS device.

        Copies necessary connection details from the quarchQPS object and
        calls the internal startQPSStream method. Handles initial failure
        based on the unserInput flag.

        Args:
            quarchQPS (quarchQPS): The quarchQPS object representing the
                device to stream from.
            directory (str): The target directory for the stream data.
            unserInput (bool, optional): Controls user interaction if the initial
                stream start command fails. If False, raises Exception on failure.
                Defaults to True.
            streamDuration (str, optional): Requested stream duration. Defaults to "".

        Raises:
            Exception: If starting the stream fails (`startQPSStream` returns a
                failure message) and `unserInput` is False.
        """
        self.connectionObj = quarchQPS.connectionObj
        self.IP_address = quarchQPS.connectionObj.qps.host
        self.port_number = quarchQPS.connectionObj.qps.port
        self.ConString = quarchQPS.ConString
        self.ConType = quarchQPS.ConType

        response = self.start_qps_stream(directory, streamDuration)
        if "fail:" not in response.lower():
            return
        else:
            if unserInput is False:
                raise Exception(response)
            else:
                self.failCheck(response, streamDuration)

    def startQPSStream(self, newDirectory, streamDuration=""):
        """DEPRECATED or ALIAS: use start_qps_stream instead
        Starts the QPS stream and directs the output to a specified directory.

        Args:
            newDirectory (str): The path to the directory where the stream data should be saved.
            streamDuration (str, optional): The duration for which the stream should run.

        Returns:
            str: The response message received from the QPS system after attempting
                 to start the stream. This could be a success confirmation or an error message.
        """

        # Return the final response obtained (either from the first or second attempt).
        return self.start_qps_stream(newDirectory, streamDuration)

    def start_qps_stream(self, newDirectory, streamDuration=""):
        """
        Starts the QPS stream and directs the output to a specified directory.

        Args:
            newDirectory (str): The path to the directory where the stream data should be saved.
            streamDuration (str, optional): The duration for which the stream should run.

        Returns:
            str: The response message received from the QPS system after attempting
                 to start the stream. This could be a success confirmation or an error message.
        """
        # Construct the command string to start the QPS stream.
        # Ensures the directory path is enclosed in quotes and appends the duration.
        command = f'$start stream "{str(newDirectory)}" {str(streamDuration)}'

        # Send the command to the QPS system using the verbose send command method.
        response = self.connectionObj.qps.sendCmdVerbose(command)

        # Check if the initial response indicates an error.
        if "Error" in response:
            # If an error occurred on the first attempt, retry sending the exact same command.
            # NOTE: This is a simple retry mechanism. Consider adding delays or more robust error handling if needed.
            response = self.connectionObj.qps.sendCmdVerbose(command)

        # Return the final response obtained (either from the first or second attempt).
        return response

    def failCheck(self, response, streamDuration):
        """
        DEPRECATED: Use fail_check instead.

        Handles potential failures when starting a stream by delegating to fail_check.
        This acts as a wrapper or entry point for the main failure handling logic
        implemented in the fail_check method.

        Args:
            response (str): The initial response received after attempting to start the stream.
            streamDuration (str): The duration intended for the stream (passed along for retries).

        Returns:
            str: The final response after handling any recoverable failures. This will be
                 a success message, or this function will propagate an exception if
                 an unhandled failure occurred in fail_check.
        """
        # Call the primary failure handling logic (fail_check).
        return self.fail_check(response, streamDuration)

    def fail_check(self, response, streamDuration):
        """
        Handles specific failures encountered during stream start-up, prompting the user if necessary.

        It iteratively checks the response for known, recoverable "fail:" conditions.
        Currently, it handles the "Directory already exists" failure by prompting the
        user for a new directory name and retrying the stream start command.
        Other failures will result in an exception.

        Args:
            response (str): The response message received from a stream start attempt.
            streamDuration (str): The duration for the stream, needed for retry attempts.

        Returns:
            str: The successful response message after a retry.

        Raises:
            Exception: If the response contains "fail:" but is not a known, handled
                       failure type (e.g., not "Directory already exists").
        """
        # Loop as long as the response (converted to lowercase) contains "fail:".
        while "fail:" in response.lower():
            # Check if the specific failure is due to the directory already existing.
            if "Fail: Directory already exists" in response:
                # Prompt the user for a new directory name using an external dialog function.
                # Assumes requestDialog(message) returns the user's input string.
                newDir = requestDialog(message=response + "  Please enter a new file name:")
                # Attempt to start the stream again with the new directory name.
                # The result updates the 'response' variable for the next loop iteration or exit.
                response = self.startQPSStream(newDir, streamDuration)
            else:
                # If the failure message is not recognized or handled specifically...
                # Raise a general exception, passing the original failure response message.
                # This halts execution for unhandled failure types.
                raise Exception(response)
        # If the loop finishes (i.e., "fail:" is no longer in the response),
        # return the last received response, which should indicate success.
        return response

    def get_stats(self, format="df"):
        """
        Retrieves statistics from the QPS device.

        Args:
            format (str): The desired output format ("df" for pandas DataFrame, "list" for list of lists). Defaults to "df".

        Returns:
            pandas.DataFrame or list: Statistics data in the specified format.
            Raises Exception if the QPS command fails.
        """
        # Send the '$get stats' command to the QPS device via the connection object, wait up to 60s, remove whitespace.
        command_response = self.connectionObj.qps.sendCmdVerbose("$get stats", timeout=60).strip()
        # Check if the response indicates a failure.
        if command_response.startswith("Fail"):
            # Raise an exception if the command failed.
            raise Exception(command_response)

        # Check if the requested format is a pandas DataFrame.
        if format == "df":
            # Try importing pandas and suppressing FutureWarnings.
            try:
                import warnings
                import pandas as pd
                warnings.simplefilter(action='ignore', category=FutureWarning)
            # Handle cases where pandas cannot be imported.
            except Exception as e:
                logging.error(e)  # Log the specific import error.
                logging.warning("pandas not imported correctly. Continuing")  # Log a warning.
                # If pandas is not available, maybe return the raw string or raise another error?
                # Current behavior: continues, but pd below will fail. Consider adding return None or raising here.

            # Set pandas display options for better console output (show all columns, wider display).
            pd.set_option('display.max_columns', None)
            pd.set_option('display.width', 1024)
            # Treat the command response string as an in-memory text file.
            test_data = StringIO(command_response)

            # Read the CSV data from the string into a DataFrame.
            # Handle different argument names for bad line handling based on pandas version.
            # `header=[0, 1]` indicates a MultiIndex header (two rows).
            if Version.is_v1_ge_v2(pd.__version__, "1.3.0"):  # Check if pandas version is 1.3.0 or greater.
                # Use 'on_bad_lines' argument for newer pandas versions.
                retVal = pd.read_csv(test_data, sep=",", header=[0, 1], on_bad_lines="skip")
            else:
                # Use 'error_bad_lines' argument for older pandas versions.
                retVal = pd.read_csv(test_data, sep=",", header=[0, 1], error_bad_lines=False)  # False skips bad lines silently.
        # Check if the requested format is a list.
        elif format == "list":
            # Initialize an empty list to store the rows.
            retVal = []
            # Normalize line endings and split the response string into lines.
            for line in command_response.replace("\r\n", "\n").split("\n"):
                # Initialize an empty list for the current row's elements.
                row = []
                # Split the line into elements using the comma delimiter.
                for element in line.split(","):
                    # Add each element to the current row list.
                    row.append(element)
                # Add the completed row list to the main list.
                retVal.append(row)
        # It might be good to add an 'else' here to handle invalid format arguments.

        # Return the processed statistics data (either DataFrame or list).
        return retVal

    def stats_to_CSV(self, file_name="", poll_till_complete=False, check_interval=0.5):
        """
        Commands the QPS device to save its current statistics grid to a CSV file.

        Sends the '$stats to csv' command to the device. Optionally, it can wait
        until the export process on the device is complete before returning.

        Args:
            file_name (str, optional):
                The absolute path and filename for the CSV file on the QPS device's
                filesystem. If empty, the QPS device typically assigns a default name
                and location. Defaults to "".
            poll_till_complete (bool, optional):
                If True, the method will repeatedly query the device's export status
                and only return after the export is finished. Defaults to False.
            check_interval (float, optional):
                The time in seconds to wait between status checks when
                `poll_till_complete` is True. Defaults to 0.5.

        Returns:
            str: The initial response message from the QPS device after sending the
                 '$stats to csv' command.

        Raises:
            Exception: If the initial '$stats to csv' command response from the
                       QPS device starts with "Fail".
        """
        # Send the command to the QPS device to export stats to the specified CSV file.
        # Enclose the filename in quotes to handle spaces. Wait up to 60 seconds for the initial response.
        command_response = self.connectionObj.qps.sendCmdVerbose(f'$stats to csv "{file_name}"', timeout=60)

        # Check if the initial command failed immediately.
        if command_response.startswith("Fail"):
            raise Exception(command_response)

        # If requested, wait until the device reports that the CSV export is finished.
        if poll_till_complete:
            # Check the current export status.
            is_exporting = check_export_status(self.get_stats_export_status())
            # Loop as long as the device indicates it is still exporting.
            while is_exporting:
                # Re-check the status.
                is_exporting = check_export_status(self.get_stats_export_status())
                # Pause execution briefly before the next check.
                time.sleep(check_interval)

        # Return the initial response received from the QPS device (not the final status).
        return command_response

    def get_custom_stats_range(self, start_time, end_time):
        """
        Retrieves statistics from the QPS device for a specified time range.

        This method queries the QPS device for statistics calculated between the
        provided start and end times, ignoring any previously set annotations
        that might define other calculation intervals. It returns the result
        as a pandas DataFrame.

        Args:
            start_time (str or int):
                The start time for the statistics calculation. Can be provided as:
                - An integer/string representing seconds since the stream start.
                - A string in the format "daysDhours:minutes:seconds.milliseconds"
                  (e.g., "0D00:01:30.500" for 1 minute, 30.5 seconds).
            end_time (str or int):
                The end time for the statistics calculation, using the same formats
                as `start_time`.

        Returns:
            pandas.DataFrame: A DataFrame containing the calculated statistics for
                              the specified time range. The structure typically includes
                              multi-level columns for different metrics (e.g., Min, Max, Avg)
                              across various channels.

        Raises:
            ImportError: If the pandas library is not installed.
            Exception: If the QPS command '$get custom stats range' fails (response
                       starts with "Fail").
            Exception: If pandas fails to parse the response data into a DataFrame.
        """
        # Attempt to import pandas and related modules.
        try:
            import warnings
            import pandas as pd
            warnings.simplefilter(action='ignore',
                                  category=FutureWarning)  # Suppress potential future warnings from pandas.
        except ImportError:
            # Log a warning if pandas cannot be imported and re-raise the error.
            logging.warning("pandas not imported correctly. Required for get_custom_stats_range.")
            # Re-raising ensures the function cannot proceed without pandas.
            raise ImportError("pandas library is required for get_custom_stats_range")

        # Construct and send the command to the QPS device, including start and end times.
        # Wait up to 60 seconds for the response.
        command_response = self.connectionObj.qps.sendCmdVerbose(
            f"$get custom stats range {start_time} {end_time}", timeout=60)

        # Check if the QPS device reported a failure for the command.
        if command_response.startswith("Fail"):
            raise Exception(command_response)

        # Treat the raw string response from the QPS as an in-memory text file (CSV format).
        test_data = StringIO(command_response)

        # Attempt to parse the CSV data from the response into a pandas DataFrame.
        try:
            # Configure pandas display options (optional, affects console printing of the df).
            pd.set_option('display.max_columns', None)
            pd.set_option('display.width', 1024)

            # Read the CSV data, handling version differences in pandas arguments.
            # header=[0, 1] specifies that the first two rows form a MultiIndex header.
            if Version.is_v1_ge_v2(pd.__version__, "1.3.0"):  # Check pandas version >= 1.3.0
                # Use 'on_bad_lines' argument for newer pandas. 'skip' ignores problematic lines.
                df = pd.read_csv(test_data, sep=",", header=[0, 1], on_bad_lines="skip")
            else:
                # Use 'error_bad_lines' argument for older pandas. False skips bad lines.
                df = pd.read_csv(test_data, sep=",", header=[0, 1], error_bad_lines=False)
        except Exception as e:
            # Log an error if DataFrame creation fails and re-raise the exception.
            logging.error(f"Unable to create pandas data frame from command response: {command_response}")
            raise e  # Propagate the exception (e.g., parsing error).

        # Return the successfully created DataFrame.
        return df

    # Deprecated alias for take_snapshot
    def takeSnapshot(self):
        """
        DEPRECATED: Use take_snapshot() instead.

        Triggers the QPS device to take an immediate snapshot of the current stream data.

        Returns:
            str: The response message from the QPS device.
        Raises:
            Exception: If the QPS command fails.
        """
        # Calls the actual implementation method.
        return self.take_snapshot()

    def take_snapshot(self):
        """
        Triggers the QPS device to capture an immediate snapshot.

        Sends the '$take snapshot' command. The snapshot is typically saved
        within the currently configured stream directory on the QPS device itself.

        Returns:
            str: The response message from the QPS device after sending the command.
                 Usually "OK" on success.
        Raises:
            Exception: If the QPS command response starts with "Fail".
        """
        # Send the command to trigger the snapshot.
        command_response = self.connectionObj.qps.sendCmdVerbose("$take snapshot")
        # Check for an immediate failure response.
        if command_response.startswith("Fail"):
            raise Exception(command_response)
        # Return the success or failure message from the device.
        return command_response

    # Deprecated alias for get_stream_state
    def getStreamState(self):
        """
        DEPRECATED: Use get_stream_state() instead.

        Queries the QPS application for the current state of the data stream processing.

        Returns:
            str: The stream state reported by the QPS application.
        Raises:
            Exception: If the QPS command fails.
        """
        # Calls the actual implementation method.
        return self.get_stream_state()

    def get_stream_state(self):
        """
        Queries the QPS application for its current stream processing state.

        Sends the '$stream state' command. Note that the QPS application state
        may differ from the physical module's streaming state. For example, QPS
        might report "Running" or "Stopping" while it processes data buffered
        from a module that has already finished sending data.

        Returns:
            str: The stream state as reported by the QPS application.
        Raises:
            Exception: If the QPS command response starts with "Fail".
        """
        # Send the command to query the stream state.
        command_response = self.connectionObj.qps.sendCmdVerbose("$stream state")
        # Check for an immediate failure response.
        if command_response.startswith("Fail"):
            raise Exception(command_response)
        # Return the state string provided by the QPS.
        return command_response

    # Deprecated alias for add_annotation
    def addAnnotation(self, title, annotationTime=0, extraText="", yPos="", titleColor="", annotationColor="",
                      annotationType="", annotationGroup="", timeFormat="unix"):
        """
        DEPRECATED: Use add_annotation() instead.

        Adds a custom annotation or comment marker to the QPS stream data.
        """
        # Calls the actual implementation method, passing all arguments through.
        return self.add_annotation(title, annotationTime, extraText, yPos, titleColor, annotationColor, annotationType,
                                   annotationGroup, timeFormat)

    def add_annotation(self, title, annotationTime=0, extraText="", yPos="", titleColor="", annotationColor="",
                       annotationType="", annotationGroup="", timeFormat="unix"):
        """
        Adds a custom annotation marker to the active QPS stream.

        Constructs and sends a '$stream annotation add' command to the QPS device
        with various customization options for appearance, timing, and type.

        Args:
            title (str):
                The primary text label displayed next to the annotation marker.
            annotationTime (str or int, optional):
                Specifies when the annotation should appear.
                - 0 (default): Places the annotation at the current time ("live").
                - Integer/String number: Interpreted as milliseconds (if timeFormat='unix')
                  or seconds (if timeFormat='elapsed') from the start of the stream.
                - String starting with 'e' (e.g., "e10"): Interpreted as elapsed time in seconds
                  (legacy format, converted to "10s").
                - Other strings containing letters: Assumed to be elapsed time format (e.g. "10s", "1m30s").
                Defaults to 0.
            extraText (str, optional):
                Additional text visible when inspecting the annotation in the QPS interface. Defaults to "".
            yPos (str or int, optional):
                Vertical position on the graph (percentage, 0=bottom, 100=top). Defaults to "".
            titleColor (str, optional):
                Hex color code (e.g., "FF0000") for the title text. Defaults to "".
            annotationColor (str, optional):
                Hex color code (e.g., "00FF00") for the annotation marker itself. Defaults to "".
            annotationType (str, optional):
                Determines the type, often influencing statistics ("annotate" vs. "comment").
                Defaults to "annotate". Can be set to "comment".
            annotationGroup (str, optional):
                Assigns the annotation to a specific group (functionality depends on QPS version/usage).
                Defaults to "". (Note: This parameter isn't used in the current command construction).
            timeFormat (str, optional):
                Specifies the interpretation of `annotationTime` if it's numeric.
                "unix" (milliseconds since epoch) or "elapsed" (time since stream start).
                Automatically adjusted based on `annotationTime` format if not explicitly "unix".
                Defaults to "unix".

        Returns:
            str: The response message from the QPS device after sending the command ("OK").
        """
        # Normalize annotation type for easier comparison.
        annotationType = annotationType.lower()
        # Ensure annotationTime is a string for parsing checks.
        annotationTime = str(annotationTime)

        # --- Time Format and Value Handling ---
        # Check if annotationTime uses an elapsed time format (contains letters or starts with 'e').
        if any(c.isalpha() for c in annotationTime):  # Check if any character is alphabetic.
            timeFormat = "elapsed"  # Assume elapsed format if letters are present.
            # Handle legacy 'e' prefix for elapsed seconds (e.g., "e5" -> "5s").
            if annotationTime.startswith("e"):
                annotationTime = annotationTime[1:] + "s"  # Remove 'e', add 's'.
        # Handle the special case where annotationTime is 0, meaning "now".
        elif annotationTime == "0":
            annotationTime = current_milli_time()  # Get current time in Unix milliseconds.
            timeFormat = "unix"  # Set format explicitly to Unix time.

        # --- Annotation Type Handling ---
        # Default to 'annotate' type if empty or explicitly 'annotation'.
        if annotationType == "" or annotationType == "annotation":
            annotationType = "annotate"
        # Allow 'comment' type to pass through.
        elif annotationType == "comment":
            pass  # No change needed for 'comment'.
        # Note: Other potential annotation types might exist but are not explicitly handled here.

        # --- Command Construction ---
        # Escape newline characters in text fields for safe command transmission.
        title = title.replace("\n", "\\n")
        extraText = extraText.replace("\n", "\\n")

        # Start building the QPS command string.
        cmd = f'$stream annotation add time={annotationTime} text="{title}"'

        # Append optional parameters to the command string if they are provided.
        if extraText:  # Check if extraText is not empty.
            cmd += f' extraText="{extraText}"'
        if yPos != "":  # Check if yPos is explicitly provided (not just default empty string).
            cmd += f' yPos={yPos}'
        # Check if annotationType is explicitly provided (important: `type` is a Python built-in, compare `annotationType`).
        if annotationType:  # Check if annotationType is not empty.
            # Potential Bug: Original code used `if type != ""`. This likely intended `if annotationType != ""`.
            # Using `if annotationType:` which correctly checks if the string is non-empty.
            cmd += f' type={annotationType}'
        if annotationColor:  # Check if annotationColor is not empty.
            cmd += f' colour={annotationColor}'  # QPS uses 'colour'.
        if titleColor:  # Check if titleColor is not empty.
            cmd += f' textColour={titleColor}'  # QPS uses 'textColour'.
        if timeFormat:  # Check if timeFormat is not empty.
            cmd += f' timeFormat={timeFormat}'
        # Note: annotationGroup is not currently added to the command.

        # Send the fully constructed command to the QPS device.
        return self.connectionObj.qps.sendCmdVerbose(cmd)

    def addComment(self, title, commentTime=0, extraText="", yPos="", titleColor="", commentColor="", annotationType="",
                   annotationGroup="", timeFormat="unix"):
        # Comments are just annotations that do not affect the statistics grid.
        # This function was kept to be backwards compatible and is a simple pass through to add annotation.
        if annotationType == "":
            annotationType = "comment"
        return self.addAnnotation(title=title, annotationTime=commentTime, extraText=extraText, yPos=yPos,
                                  titleColor=titleColor, annotationColor=commentColor, annotationType=annotationType,
                                  annotationGroup=annotationGroup, timeFormat=timeFormat)

    def add_comment(self, title, commentTime=0, extraText="", yPos="", titleColor="", commentColor="",
                    annotationType="",
                    annotationGroup="", timeFormat="unix"):

        # Comments are just annotations that do not affect the statistics grid.
        # This function was kept to be backwards compatible and is a simple pass through to add annotation.
        if annotationType == "":
            annotationType = "comment"
        return self.addAnnotation(title=title, annotationTime=commentTime, extraText=extraText, yPos=yPos,
                                  titleColor=titleColor, annotationColor=commentColor, annotationType=annotationType,
                                  annotationGroup=annotationGroup, timeFormat=timeFormat)

    # Alias for save_csv
    def saveCSV(self, filePath, linesPerFile=None, cr=None, delimiter=None, timeout=60, pollTillComplete=False,
                checkInterval=0.5):
        """DEPRECATED: Use save_csv instead."""
        return self.save_csv(filePath, linesPerFile, cr, delimiter, timeout, pollTillComplete, checkInterval)

    def save_csv(self, file_path, lines_per_file=None, use_cr=None, delimiter=None, timeout=60,
                 poll_till_complete=False,
                 check_interval=0.5):
        """
        Commands the QPS device to save the currently streamed data to a CSV file(s).

        Constructs and sends the '$save csv' command with optional arguments for
        splitting files, line endings, and delimiters. Can optionally poll the
        device until the export process is complete.

        Args:
            file_path (str):
                The target file path on the QPS device's filesystem where the CSV
                should be saved.
            lines_per_file (int or str, optional):
                Specifies the maximum number of lines per CSV file. Use an integer
                or "all" to save to a single file. Defaults to None (device default).
            use_cr (bool, optional):
                Specifies the line ending. True for CRLF, False for LF.
                Defaults to None (device default).
            delimiter (str, optional):
                The character to use as a field delimiter in the CSV file.
                Defaults to None (device default, usually ',').
            timeout (int, optional):
                Maximum time in seconds to wait for the initial command response from QPS.
                Defaults to 60.
            poll_till_complete (bool, optional):
                If True, continuously checks the stream export status after sending
                the command and only returns once the export is finished. Defaults to False.
            check_interval (float, optional):
                Time in seconds to wait between status checks when poll_till_complete is True.
                Defaults to 0.5.

        Returns:
            str: The initial response message from the QPS device after sending the
                 '$save csv' command.
        """
        args = ""  # Initialize string for optional command arguments.

        # Build optional arguments for the QPS command.
        if lines_per_file is not None:
            args += f" -l{lines_per_file}"  # -l flag for lines per file.
        if use_cr is not None:
            # -c flag for carriage return ('yes' or 'no').
            args += " -cyes" if use_cr else " -cno"
        if delimiter is not None:
            args += f" -s{delimiter}"  # -s flag for separator/delimiter.

        # Send the command to QPS to save the stream data.
        # Enclose file path in quotes; append optional arguments.
        command_response = self.connectionObj.qps.sendCmdVerbose(f'$save csv "{file_path}" {args}'.strip(),
                                                                 timeout=timeout)

        # --- Polling Logic ---
        # Check export status *after* sending the save command if polling is enabled.
        # This ensures we wait for the current export to finish first.
        if poll_till_complete:
            is_exporting = check_export_status(self.get_stream_export_status())
            while is_exporting:
                logging.debug("Waiting for current stream export to complete...")
                is_exporting = check_export_status(self.get_stream_export_status())
                time.sleep(check_interval)

        # Return the initial response from the '$save csv' command.
        return command_response

    # Alias for create_channel
    def createChannel(self, channelName, channelGroup, baseUnits, usePrefix):
        """DEPRECATED: Use create_channel instead."""
        return self.create_channel(channelName, channelGroup, baseUnits, usePrefix)

    def create_channel(self, channel_name, channel_group, base_units, use_prefix):
        """
        Creates a new custom data channel on the QPS device for the current stream.

        Args:
            channel_name (str): The name for the new channel.
            channel_group (str): The group to associate the channel with (e.g., "Voltage").
            base_units (str): The fundamental unit for the channel (e.g., "V", "A", "W", "count").
            use_prefix (bool): If True, allows automatic SI prefixes (k, M, m, u, etc.)
                               based on magnitude. If False, uses only the base unit.

        Returns:
            str: The response message from the QPS device.
        """
        # Convert the boolean 'use_prefix' argument to the string "yes" or "no" expected by QPS.
        prefix_str = "yes" if use_prefix else "no"

        # Construct and send the '$create channel' command.
        return self.connectionObj.qps.sendCmdVerbose(
            f"$create channel {channel_name} {channel_group} {base_units} {prefix_str}"
        )

    # Alias for hide_channel
    def hideChannel(self, channelSpecifier):
        """DEPRECATED: Use hide_channel instead."""
        return self.hide_channel(channelSpecifier)

    def hide_channel(self, channel_specifier):
        """
        Hides a specified channel from the QPS stream view.

        Args:
            channel_specifier (str): The identifier of the channel to hide.

        Returns:
            str: The response message from the QPS device.
        """
        # Construct and send the '$hide channel' command.
        return self.connectionObj.qps.sendCmdVerbose(f"$hide channel {channel_specifier}")

    # Alias for show_channel
    def showChannel(self, channelSpecifier):
        """DEPRECATED: Use show_channel instead."""
        return self.show_channel(channelSpecifier)

    def show_channel(self, channel_specifier):
        """
        Shows (un-hides) a specified channel in the QPS stream view.

        Args:
            channel_specifier (str): The identifier of the channel to show
                                     (e.g., "5v:voltage", "MyCustomChannel").

        Returns:
            str: The response message from the QPS device.
        """
        # Construct and send the '$show channel' command.
        return self.connectionObj.qps.sendCmdVerbose(f"$show channel {channel_specifier}")

    # Alias for my_channels
    def myChannels(self):
        """DEPRECATED: Use my_channels or channels instead."""
        return self.my_channels()

    def my_channels(self):
        """
        Retrieves the list of available channels from QPS as a single raw string.

        Returns:
            str: The raw response string from the QPS '$channels' command, typically
                 containing newline-separated channel identifiers.
        """
        # Send the '$channels' command and return the raw response.
        return self.connectionObj.qps.sendCmdVerbose("$channels")

    def channels(self):
        """
        Retrieves the list of available channels from QPS, split into a list of strings.

        Returns:
            list[str]: A list where each element is a channel identifier string.
        """
        # Send the '$channels' command, get the raw response, and split it into lines.
        return self.connectionObj.qps.sendCmdVerbose("$channels").splitlines()

    # Alias for stop_stream
    def stopStream(self, pollTillComplete=False, checkInterval=0.1):
        """DEPRECATED: Use stop_stream instead."""
        return self.stop_stream(pollTillComplete, checkInterval)

    def stop_stream(self, poll_till_complete=False, check_interval=0.1):
        """
        Sends the command to stop the QPS data stream.

        Optionally polls the QPS stream state until it is no longer "running",
        ensuring buffered data has been processed.

        Args:
            poll_till_complete (bool, optional): If True, waits until the QPS stream
                                               state is no longer "running". Defaults to False.
            check_interval (float, optional): Time in seconds between status checks
                                             when polling. Defaults to 0.1.

        Returns:
            str: The final checked stream status string ("stopped", "fail", "error") if polling,
                 otherwise the initial response from the '$stop stream' command.
        """
        # Send the command to stop the stream.
        response = self.connectionObj.qps.sendCmdVerbose("$stop stream")
        # Check for immediate failure of the stop command itself.
        if response.startswith("Fail"):
            raise Exception(response)

        # Poll until the stream has fully stopped processing if required.
        if poll_till_complete:
            # Get the initial stream state (after sending stop).
            # Uses the alias getStreamState internally, assumes it calls get_stream_state
            stream_state = self.getStreamState().lower()
            # Check the status using the utility function.
            response = check_stream_stopped_status(stream_state)  # Initial status check
            # Loop while QPS still reports it's running (processing buffer).
            while "running" in stream_state:
                logging.debug(f"Stream buffer still emptying: {stream_state}")
                # Wait before checking again.
                time.sleep(check_interval)
                # Get updated stream state.
                stream_state = self.getStreamState().lower()
                # Check the status again using the utility function.
                response = check_stream_stopped_status(stream_state)  # Update response based on latest state

        # Return the initial command response (if not polling) or the final checked status (if polling).
        return response

    # Alias for hide_all_default_channels
    def hideAllDefaultChannels(self):
        """DEPRECATED: Use hide_all_default_channels instead."""
        self.hide_all_default_channels()

    def hide_all_default_channels(self):
        """
        Hides a predefined list of common default QPS/PAM channels.

        This method contains a hardcoded list of channel specifiers typically
        present on Quarch systems and calls hide_channel for each one.

        Note:
            This list might not be exhaustive or accurate for all hardware/firmware
            versions. A TODO exists to query the device for channels dynamically.
        """
        # TODO: Query QPS / Device for all channel names and hide them dynamically
        #       instead of using a hardcoded list.

        # List of common default channels to hide
        default_channels = [
            # Standard voltage channels
            "3.3v:voltage", "3v3:voltage", "5v:voltage", "12v:voltage",
            # Standard current channels
            "3.3v:current", "3v3:current", "5v:current", "12v:current",
            # Standard power channels
            "3.3v:power", "3v3:power", "5v:power", "12v:power", "tot:power",
            # Default PAM digital channels
            "perst#:digital", "wake#:digital", "clkreq#:digital",
            # Corrected 'lkreq#' to 'clkreq#' based on typical usage
            "smclk:digital", "smdat:digital"
        ]

        # Iterate through the list and hide each channel.
        for channel in default_channels:
            try:
                self.hide_channel(channel)
            except Exception as e:
                # Log a warning if hiding a specific channel fails (e.g., it doesn't exist)
                logging.warning(f"Failed to hide channel '{channel}': {e}")

    # Alias for add_data_point
    def addDataPoint(self, channelName, groupName, dataValue, dataPointTime=0, timeFormat="unix"):
        """DEPRECATED: Use add_data_point instead."""
        self.add_data_point(channelName, groupName, dataValue, dataPointTime, timeFormat)

    def add_data_point(self, channel_name, group_name, data_value, data_point_time=0, time_format="unix"):
        """
        Adds a single data point to a specified custom channel in the QPS stream.

        Args:
            channel_name (str): The name of the custom channel to add data to.
                                (This channel should typically be created first using `create_channel`).
            group_name (str): The group associated with the channel (must match creation).
            data_value (int or float): The numeric value of the data point.
            data_point_time (int or str, optional):
                The timestamp for the data point.
                - 0 (default) or None: Uses the current time (Unix milliseconds).
                - Integer/String number: Interpreted according to `time_format`.
                Defaults to 0.
            time_format (str, optional):
                Specifies how `data_point_time` is interpreted.
                "unix" (milliseconds since epoch) or "elapsed" (time since stream start).
                Defaults to "unix".
        """
        # Determine the timestamp: use current time if 0 or None is provided.
        if data_point_time is None or data_point_time == 0:
            timestamp = qpsNowStr()  # Get current time in Unix milliseconds.
            time_format = "unix"  # Ensure time format matches the timestamp generated.
        else:
            # Ensure timestamp is a string for the command. (Original code converted to int first, which might lose precision if time was float/str)
            timestamp = str(data_point_time)

        # Construct the command string.
        command = (f"$stream data add {channel_name} {group_name} "
                   f"{timestamp} {data_value} {time_format}")

        # Log the command being sent (consider changing level from warning if this is normal operation).
        logging.warning(command)  # Original code used warning level.

        # Send the command to add the data point.
        self.connectionObj.qps.sendCmdVerbose(command)

    def get_stream_export_status(self):
        """
        Queries the QPS device for the status of the main stream data export process.

        Returns:
            str: The response string from QPS indicating the stream export status
                 (e.g., "Idle", "Exporting", "Complete", "Fail:<reason>").
        """
        # Send the command to get the status of stream CSV export.
        return self.connectionObj.qps.sendCmdVerbose("$stream export status")

    def get_stats_export_status(self):
        """
        Queries the QPS device for the status of the statistics data export process.

        Returns:
            str: The response string from QPS indicating the stats export status
                 (e.g., "Idle", "Exporting", "Complete", "Fail:<reason>").
        """
        # Send the command to get the status of statistics CSV export.
        return self.connectionObj.qps.sendCmdVerbose("$stream stats export status")
