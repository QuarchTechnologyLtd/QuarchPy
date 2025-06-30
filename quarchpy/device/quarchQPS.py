from __future__ import annotations
import logging
import time
from io import StringIO
from typing import Optional, Union, List, Any, Literal
import enum

# Third-party imports
try:
    import pandas as pd
except ImportError:
    pd = None  # type: ignore

# Local application imports
from quarchpy.device import quarchDevice
from quarchpy.user_interface.user_interface import requestDialog

def qpsNowStr() -> str:
    """
    Gets the current time as milliseconds since the Unix epoch.

    Returns:
        str: The current time as a string representing milliseconds
             since the epoch.
    """
    return str(current_milli_time())


# --- Main Classes ---

class quarchQPS(quarchDevice):
    """
    Represents a Quarch Power Supply (QPS) device, extending quarchDevice.

    Handles interaction specific to QPS modules, including stream management.
    """

    def __init__(self, quarchDevice: quarchDevice):
        """
        Initializes the quarchQPS wrapper using an existing quarchDevice object.

        Args:
            quarchDevice (quarchDevice): An initialized instance of
                the base quarchDevice class containing connection details.

        Raises:
            AttributeError: If the provided quarchDevice is not a valid QPS connection.
        """
        super().__init__(quarchDevice.ConString, ConType=quarchDevice.ConType)
        self.quarchDevice = quarchDevice
        self.connectionObj = quarchDevice.connectionObj

        if not hasattr(self.connectionObj, 'qps'):
            raise AttributeError("The provided quarchDevice is not a valid QPS connection.")
        self.IP_address = self.connectionObj.qps.host
        self.port_number = self.connectionObj.qps.port

    # --- Public API Methods ---

    def start_stream(self, directory: str, user_input: bool = True, stream_duration: str = "") -> 'quarchStream':
        """
        Initializes and starts a Quarch data stream.

        This method creates a quarchStream object, which handles the setup
        and management of the data stream for the QPS application.

        Args:
            directory (str): The target directory where stream data will be saved.
            user_input (bool, optional): Controls user interaction on failure.
                If True (default), prompts the user. If False, raises an
                Exception on failure.
            stream_duration (str, optional): Defines the requested duration for the
                stream. An empty string (default) signifies an indefinite stream.

        Returns:
            quarchStream: An instance of the quarchStream class representing and
            managing the active stream.
        """
        return quarchStream(self, directory, user_input, stream_duration)

    def startStream(self, directory: str, unserInput: bool = True, streamDuration: str = "") -> 'quarchStream':
        """
        DEPRECATED: Use start_stream instead.

        Args:
            directory (str): The target directory where stream data will be saved.
            unserInput (bool, optional): Controls user interaction on failure.
            streamDuration (str, optional): Defines the requested duration.

        Returns:
            quarchStream: An instance of the quarchStream class.
        """
        return self.start_stream(directory, unserInput, streamDuration)


class quarchStream:
    """
    Manages an active data stream from a Quarch QPS device.

    Instantiation automatically attempts to start the stream. Provides methods to
    control and monitor the stream.
    """

    def __init__(self, quarchQPS: quarchQPS, directory: str, unserInput: bool = True, streamDuration: str = ""):
        """
        Initializes and attempts to start a data stream from the connected device.

        Args:
            quarchQPS (quarchQPS): The quarchQPS object to stream from.
            directory (str): The target directory for the stream data.
            unserInput (bool, optional): Controls user interaction if the initial
                stream start command fails. Defaults to True.
            streamDuration (str, optional): Requested stream duration. Defaults to "".

        Raises:
            Exception: If starting the stream fails and `unserInput` is False.
        """
        self.connectionObj = quarchQPS.connectionObj
        self.IP_address = quarchQPS.IP_address
        self.port_number = quarchQPS.port_number
        self.ConString = quarchQPS.ConString
        self.ConType = quarchQPS.ConType

        response = self.startQPSStream(directory, streamDuration)
        if "fail:" in response.lower():
            if unserInput is False:
                raise Exception(response)
            else:
                self.failCheck(response, streamDuration)

    # --- Public API Methods ---

    def start_qps_stream(self, new_directory: str, stream_duration: str = "") -> str:
        """
        Sends the command to start the QPS stream.

        Args:
            new_directory (str): The path for the stream data.
            stream_duration (str, optional): The duration for the stream. Defaults to "".

        Returns:
            str: The response from the QPS system.
        """
        command = f'$start stream "{new_directory}" {stream_duration}'.strip()
        response = self.connectionObj.qps.sendCmdVerbose(command)
        if "Error" in response:
            logging.debug("Initial start stream command failed with 'Error', retrying once.")
            response = self.connectionObj.qps.sendCmdVerbose(command)
        return response

    def startQPSStream(self, newDirectory: str, streamDuration: str = "") -> str:
        """
        DEPRECATED: Use start_qps_stream instead.

        Args:
            newDirectory (str): The path to the directory where the stream data should be saved.
            streamDuration (str, optional): The duration for which the stream should run.

        Returns:
            str: The response message from the QPS system.
        """
        return self.start_qps_stream(newDirectory, streamDuration)

    def fail_check(self, response: str, stream_duration: str) -> str:
        """
        Handles recoverable failures during stream startup.

        Currently handles "Directory already exists" by prompting for a new name.

        Args:
            response (str): The failure response message from the server.
            stream_duration (str): The stream duration, for retrying.

        Returns:
            str: The successful response after a retry.

        Raises:
            Exception: If the failure is not a known, handled type.
        """
        while "fail:" in response.lower():
            if "Fail: Directory already exists" in response:
                new_dir = requestDialog(message=f"{response}\nPlease enter a new file name:")
                response = self.start_qps_stream(new_dir, stream_duration)
            else:
                raise Exception(f"Unhandled QPS stream start failure: {response}")
        return response

    def failCheck(self, response: str, streamDuration: str) -> str:
        """
        DEPRECATED: Use fail_check instead.

        Args:
            response (str): The response message from a stream start attempt.
            streamDuration (str): The duration for the stream, needed for retry attempts.

        Returns:
            str: The successful response message after a retry.

        Raises:
            Exception: If the response contains an unhandled failure.
        """
        return self.fail_check(response, streamDuration)

    def get_stats(self, format: str = "df") -> Union[pd.DataFrame, List[List[str]], None]:
        """
        Retrieves statistics from the QPS device.

        Args:
            format (str, optional): The desired output format ("df" for pandas
                DataFrame, "list" for list of lists). Defaults to "df".

        Returns:
            Union[pd.DataFrame, List[List[str]], None]: Statistics data in the
            specified format, or None if pandas is required but not found.

        Raises:
            Exception: If the QPS command fails.
        """
        command_response = self.connectionObj.qps.sendCmdVerbose("$get stats", timeout=60).strip()
        if command_response.startswith("Fail"):
            raise Exception(command_response)

        if format == "df":
            if pd is None:
                logging.error("Pandas is not installed, cannot return DataFrame.")
                return None

            test_data = StringIO(command_response)

            df = pd.read_csv(test_data, sep=",", header=[0, 1], on_bad_lines="skip")

            return df

        elif format == "list":
            ret_val = []
            for line in command_response.replace("\r\n", "\n").split("\n"):
                row = [element for element in line.split(",")]
                ret_val.append(row)
            return ret_val

        return None

    def stats_to_csv(self, file_name: str = "", poll_till_complete: bool = False,
                     check_interval: float = 0.5, timeout: int = 60) -> str:
        """
        Commands the QPS device to save its current statistics to a CSV file.

        Args:
            file_name (str, optional): Absolute path for the CSV file on the QPS
                device's filesystem. Defaults to "".
            poll_till_complete (bool, optional): If True, waits for the export
                to finish. Defaults to False.
            check_interval (float, optional): Seconds between status checks when
                polling. Defaults to 0.5.
            timeout (int, optional): Max seconds to wait for polling to complete.
                Defaults to 60.

        Returns:
            str: The initial response from the QPS device.

        Raises:
            Exception: If the initial QPS command fails.
            TimeoutError: If polling is enabled and times out.
        """
        cmd = f'$stats to csv "{file_name}"'
        command_response = self.connectionObj.qps.sendCmdVerbose(cmd, timeout=60)

        if command_response.startswith("Fail"):
            raise Exception(command_response)

        if poll_till_complete:
            start_time = time.monotonic()
            while check_export_status(self.get_stats_export_status()):
                if (time.monotonic() - start_time) > timeout:
                    raise TimeoutError(f"QPS CSV Export of stats timed out after {timeout} seconds")
                time.sleep(check_interval)

        return command_response

    def stats_to_CSV(self, file_name: str = "", poll_till_complete: bool = False,
                     check_interval: float = 0.5, timeout: int = 60) -> str:
        """
        DEPRECATED: Use stats_to_csv instead.

        Args:
            file_name (str, optional): The absolute path for the CSV file. Defaults to "".
            poll_till_complete (bool, optional): If True, polls until the export is
                finished. Defaults to False.
            check_interval (float, optional): Time in seconds between status checks
                when polling. Defaults to 0.5.
            timeout (int, optional): Max time in seconds to wait for polling. Defaults to 60.

        Returns:
            str: The initial response message from the QPS device.
        """
        return self.stats_to_csv(file_name, poll_till_complete, check_interval, timeout)

    def get_custom_stats_range(self, start_time: Union[int, str], end_time: Union[int, str]) -> Optional[pd.DataFrame]:
        """
        Retrieves statistics from the QPS device for a specified time range.

        Args:
            start_time (Union[int, str]): The start time for stats calculation.
            end_time (Union[int, str]): The end time for stats calculation.

        Returns:
            Optional[pd.DataFrame]: A DataFrame containing the stats.

        Raises:
            ImportError: If the pandas library is not installed.
            Exception: If the QPS command fails or data parsing fails.
        """
        if pd is None:
            logging.warning("pandas not imported correctly. Required for get_custom_stats_range.")
            raise ImportError("pandas library is required for get_custom_stats_range")

        command_response = self.connectionObj.qps.sendCmdVerbose(
            f"$get custom stats range {start_time} {end_time}", timeout=60)

        if command_response.startswith("Fail"):
            raise Exception(command_response)

        test_data = StringIO(command_response)
        try:
            df = pd.read_csv(test_data, sep=",", header=[0, 1], on_bad_lines="skip")
        except Exception as e:
            logging.error(f"Unable to create pandas data frame from command response: {command_response}")
            raise e
        return df

    def take_snapshot(self) -> str:
        """
        Triggers the QPS device to capture an immediate snapshot.

        Returns:
            str: The response from the QPS device.

        Raises:
            Exception: If the command fails.
        """
        command_response = self.connectionObj.qps.sendCmdVerbose("$take snapshot")
        if command_response.startswith("Fail"):
            raise Exception(command_response)
        return command_response

    def takeSnapshot(self) -> str:
        """
        DEPRECATED: Use take_snapshot instead.

        Returns:
            str: The response message from the QPS device.
        """
        return self.take_snapshot()

    def get_stream_state(self) -> str:
        """
        Queries the QPS application for its current stream processing state.

        Returns:
            str: The stream state as reported by the QPS application.

        Raises:
            Exception: If the command fails.
        """
        command_response = self.connectionObj.qps.sendCmdVerbose("$stream state")
        if command_response.startswith("Fail"):
            raise Exception(command_response)
        return command_response

    def getStreamState(self) -> str:
        """
        DEPRECATED: Use get_stream_state instead.

        Returns:
            str: The stream state reported by the QPS application.
        """
        return self.get_stream_state()

    def add_annotation(self, title: str, annotation_time: Union[int, str] = 0, extra_text: str = "",
                       y_pos: Union[int, str] = "",
                       title_color: str = "", annotation_color: str = "", annotation_type: str = "annotate",
                       time_format: str = "unix") -> str:
        """
        Adds a custom annotation marker to the active QPS stream.

        Args:
            title (str): The primary text label for the annotation.
            annotation_time (Union[int, str], optional): When the annotation appears. Defaults to 0 ("now").
            extra_text (str, optional): Additional text for the annotation. Defaults to "".
            y_pos (Union[int, str], optional): Vertical position (0-100). Defaults to "".
            title_color (str, optional): Hex color for the title. Defaults to "".
            annotation_color (str, optional): Hex color for the marker. Defaults to "".
            annotation_type (str, optional): "annotate" or "comment". Defaults to "annotate".
            time_format (str, optional): "unix" or "elapsed". Defaults to "unix".

        Returns:
            str: The response message from the QPS device.
        """
        time_val = str(annotation_time)
        if any(c.isalpha() for c in time_val):
            time_format = "elapsed"
            if time_val.startswith("e"):
                time_val = time_val[1:] + "s"
        elif time_val == "0":
            time_val = qpsNowStr()
            time_format = "unix"

        title = title.replace("\n", "\\n")
        extra_text = extra_text.replace("\n", "\\n")

        cmd = f'$stream annotation add time={time_val} text="{title}"'
        if extra_text:
            cmd += f' extraText="{extra_text}"'
        if y_pos != "":
            cmd += f' yPos={y_pos}'
        if annotation_type:
            cmd += f' type={annotation_type}'
        if annotation_color:
            cmd += f' colour={annotation_color}'
        if title_color:
            cmd += f' textColour={title_color}'
        if time_format:
            cmd += f' timeFormat={time_format}'

        return self.connectionObj.qps.sendCmdVerbose(cmd)

    def addAnnotation(self, title: str, annotationTime: Union[int, str] = 0, extraText: str = "",
                      yPos: Union[int, str] = "",
                      titleColor: str = "", annotationColor: str = "", annotationType: str = "",
                      annotationGroup: str = "", timeFormat: str = "unix") -> str:
        """
        DEPRECATED: Use add_annotation instead.

        Args:
            title (str): The primary text label for the annotation.
            annotationTime (Union[int, str], optional): Timestamp. Defaults to 0 ("now").
            extraText (str, optional): Additional text. Defaults to "".
            yPos (Union[int, str], optional): Vertical position (0-100). Defaults to "".
            titleColor (str, optional): Hex color for the title. Defaults to "".
            annotationColor (str, optional): Hex color for the marker. Defaults to "".
            annotationType (str, optional): "annotate" or "comment". Defaults to "".
            annotationGroup (str, optional): Not used. Defaults to "".
            timeFormat (str, optional): "unix" or "elapsed". Defaults to "unix".

        Returns:
            str: The response message from the QPS device.
        """
        current_type = annotationType.lower()
        if current_type == "" or current_type == "annotation":
            current_type = "annotate"

        return self.add_annotation(title, annotation_time=annotationTime, extra_text=extraText, y_pos=yPos,
                                   title_color=titleColor, annotation_color=annotationColor,
                                   annotation_type=current_type, time_format=timeFormat)

    def add_comment(self, title: str, comment_time: Union[int, str] = 0, **kwargs: Any) -> str:
        """
        Adds a 'comment' type annotation to the QPS stream.

        This is a convenience wrapper for `add_annotation` that sets the type to 'comment'.

        Args:
            title (str): The text label for the comment.
            comment_time (Union[int, str], optional): The timestamp. Defaults to 0.
            **kwargs: Other arguments accepted by `add_annotation`.

        Returns:
            str: The response message from the QPS device.
        """
        kwargs['annotation_type'] = 'comment'
        return self.add_annotation(title, annotation_time=comment_time, **kwargs)

    def addComment(self, title: str, commentTime: Union[int, str] = 0, extraText: str = "", yPos: Union[int, str] = "",
                   titleColor: str = "", commentColor: str = "", annotationType: str = "",
                   annotationGroup: str = "", timeFormat: str = "unix") -> str:
        """
        DEPRECATED: Use add_comment instead.

        Args:
            title (str): The text label for the comment.
            commentTime (Union[int, str], optional): The timestamp. Defaults to 0.
            extraText (str, optional): Additional text. Defaults to "".
            yPos (Union[int, str], optional): Vertical position (0-100). Defaults to "".
            titleColor (str, optional): Hex color for the title. Defaults to "".
            commentColor (str, optional): Hex color for the comment marker. Defaults to "".
            annotationType (str, optional): Overridden to 'comment'. Defaults to "".
            annotationGroup (str, optional): Not used. Defaults to "".
            timeFormat (str, optional): "unix" or "elapsed". Defaults to "unix".

        Returns:
            str: The response message from the QPS device.
        """
        return self.add_comment(title, comment_time=commentTime, extraText=extraText, yPos=yPos,
                                titleColor=titleColor, commentColor=commentColor,
                                timeFormat=timeFormat)

    def save_csv(self, file_path: str, lines_per_file: Optional[Union[int, str]] = None, use_cr: Optional[bool] = None,
                 delimiter: Optional[str] = None, timeout: int = 180, poll_till_complete: bool = False,
                 check_interval: float = 0.5) -> str:
        """
        Commands the QPS device to save the stream data to a CSV file.

        Args:
            file_path (str): Target file path on the QPS device's filesystem.
            lines_per_file (Optional[Union[int, str]], optional): Max lines per file. Defaults to None.
            use_cr (Optional[bool], optional): True for CRLF, False for LF. Defaults to None.
            delimiter (Optional[str], optional): Field delimiter for the CSV. Defaults to None.
            timeout (int, optional): Timeout in seconds. Defaults to 180.
            poll_till_complete (bool, optional): If True, waits for export to finish. Defaults to False.
            check_interval (float, optional): Seconds between status checks when polling. Defaults to 0.5.

        Returns:
            str: The initial response from the QPS device.

        Raises:
            TimeoutError: If polling is enabled and the export does not complete in time.
        """
        args = ""
        if lines_per_file is not None:
            args += f" -l{lines_per_file}"
        if use_cr is not None:
            args += " -cyes" if use_cr else " -cno"
        if delimiter is not None:
            args += f" -s{delimiter}"

        command = f'$save csv "{file_path}" {args}'.strip()
        command_response = self.connectionObj.qps.sendCmdVerbose(command, timeout=timeout)

        if poll_till_complete:
            start_time = time.monotonic()
            while check_export_status(self.get_stream_export_status()):
                if (time.monotonic() - start_time) > timeout:
                    raise TimeoutError(f"Stream export to CSV timed out after {timeout} seconds")
                logging.debug("Waiting for stream export to complete...")
                time.sleep(check_interval)

        return command_response

    def saveCSV(self, filePath: str, linesPerFile: Optional[Union[int, str]] = None, cr: Optional[bool] = None,
                delimiter: Optional[str] = None, timeout: int = 180, pollTillComplete: bool = False,
                checkInterval: float = 0.5) -> str:
        """
        DEPRECATED: Use save_csv instead.

        Args:
            filePath (str): The target file path on the QPS device's filesystem.
            linesPerFile (Optional[Union[int, str]], optional): Max lines per file. Defaults to None.
            cr (Optional[bool], optional): True for CRLF, False for LF line endings. Defaults to None.
            delimiter (Optional[str], optional): Field delimiter for the CSV. Defaults to None.
            timeout (int, optional): Timeout in seconds. Defaults to 180.
            pollTillComplete (bool, optional): If True, waits for export to finish. Defaults to False.
            checkInterval (float, optional): Seconds between status checks when polling. Defaults to 0.5.

        Returns:
            str: The initial response from the QPS device.
        """
        return self.save_csv(filePath, linesPerFile, cr, delimiter, timeout, pollTillComplete, checkInterval)

    def create_channel(self, channel_name: str, channel_group: str, base_units: str, use_prefix: bool) -> str:
        """
        Creates a new custom data channel on the QPS device.

        Args:
            channel_name (str): The name for the new channel.
            channel_group (str): The group to associate the channel with (e.g., "Voltage").
            base_units (str): The fundamental unit for the channel (e.g., "V", "A").
            use_prefix (bool): If True, allows channel prefixes (e.g., 'm' for milli).

        Returns:
            str: The response from the QPS device.
        """
        prefix_str = "yes" if use_prefix else "no"
        command = f"$create channel {channel_name} {channel_group} {base_units} {prefix_str}"
        return self.connectionObj.qps.sendCmdVerbose(command)

    def createChannel(self, channelName: str, channelGroup: str, baseUnits: str, usePrefix: bool) -> str:
        """
        DEPRECATED: Use create_channel instead.

        Args:
            channelName (str): The name for the new channel.
            channelGroup (str): The group to associate the channel with.
            baseUnits (str): The fundamental unit for the channel.
            usePrefix (bool): If True, allows channel prefixes.

        Returns:
            str: The response message from the QPS device.
        """
        return self.create_channel(channelName, channelGroup, baseUnits, usePrefix)

    def hide_channel(self, channel_specifier: str) -> str:
        """
        Hides a specified channel from the QPS stream view.

        Args:
            channel_specifier (str): The identifier of the channel to hide (e.g., "5v:voltage").

        Returns:
            str: The response from the QPS device.
        """
        return self.connectionObj.qps.sendCmdVerbose(f"$hide channel {channel_specifier}")

    def hideChannel(self, channelSpecifier: str) -> str:
        """
        DEPRECATED: Use hide_channel instead.

        Args:
            channelSpecifier (str): The identifier of the channel to hide.

        Returns:
            str: The response message from the QPS device.
        """
        return self.hide_channel(channelSpecifier)

    def show_channel(self, channel_specifier: str) -> str:
        """
        Shows (un-hides) a specified channel in the QPS stream view.

        Args:
            channel_specifier (str): The identifier of the channel to show.

        Returns:
            str: The response from the QPS device.
        """
        return self.connectionObj.qps.sendCmdVerbose(f"$show channel {channel_specifier}")

    def showChannel(self, channelSpecifier: str) -> str:
        """
        DEPRECATED: Use show_channel instead.

        Args:
            channelSpecifier (str): The identifier of the channel to show.

        Returns:
            str: The response message from the QPS device.
        """
        return self.show_channel(channelSpecifier)

    def channels(self) -> List[str]:
        """
        Retrieves the list of available channels from QPS, split into a list of strings.

        Returns:
            list[str]: A list where each element is a channel identifier string.
        """
        return self.connectionObj.qps.sendCmdVerbose("$channels").splitlines()

    def myChannels(self) -> str:
        """
        DEPRECATED: Use channels instead.

        Retrieves the list of available channels from QPS as a single raw string.

        Returns:
            str: The raw response string from the QPS '$channels' command.
        """
        return self.connectionObj.qps.sendCmdVerbose("$channels")

    def hide_all_default_channels(self) -> None:
        """
        Hides a predefined list of common default QPS/PAM channels.

        Note:
            This list is hardcoded and might not be exhaustive for all hardware.
        """
        default_channels = [
            "3.3v:voltage", "3v3:voltage", "5v:voltage", "12v:voltage",
            "3.3v:current", "3v3:current", "5v:current", "12v:current",
            "3.3v:power", "3v3:power", "5v:power", "12v:power", "tot:power",
            "perst#:digital", "wake#:digital", "clkreq#:digital",
            "smclk:digital", "smdat:digital"
        ]
        for channel in default_channels:
            try:
                self.hide_channel(channel)
            except Exception as e:
                logging.warning(f"Failed to hide default channel '{channel}': {e}")

    def hideAllDefaultChannels(self) -> None:
        """
        DEPRECATED: Use hide_all_default_channels instead.

        Hides a predefined list of common default QPS/PAM channels.
        """
        self.hide_all_default_channels()

    def add_data_point(self, channel_name: str, group_name: str, data_value: Union[int, float],
                       data_point_time: Union[int, str] = 0, time_format: str = "unix") -> None:
        """
        Adds a single data point to a specified custom channel.

        Args:
            channel_name (str): The name of the custom channel.
            group_name (str): The group associated with the channel.
            data_value (Union[int, float]): The numeric value of the data point.
            data_point_time (Union[int, str], optional): Timestamp for the data point.
                Defaults to 0 (current time).
            time_format (str, optional): "unix" or "elapsed". Defaults to "unix".
        """
        if data_point_time == 0:
            timestamp = qpsNowStr()
            time_format = "unix"
        else:
            timestamp = str(data_point_time)

        command = (f"$stream data add {channel_name} {group_name} "
                   f"{timestamp} {data_value} {time_format}")

        self.connectionObj.qps.sendCmdVerbose(command)

    def addDataPoint(self, channelName: str, groupName: str, dataValue: Union[int, float],
                     dataPointTime: Union[int, str] = 0, timeFormat: str = "unix") -> None:
        """
        DEPRECATED: Use add_data_point instead.

        Adds a single data point to a specified custom channel in the QPS stream.

        Args:
            channelName (str): The name of the custom channel to add data to.
            groupName (str): The group associated with the channel (must match creation).
            dataValue (int or float): The numeric value of the data point.
            dataPointTime (int or str, optional): The timestamp for the data point.
            timeFormat (str, optional): The format of the given time ["elapsed"|"unix"].
        """
        self.add_data_point(channelName, groupName, dataValue, dataPointTime, timeFormat)

    def get_stream_export_status(self) -> str:
        """
        Queries the QPS device for the status of the main stream data export process.

        Returns:
            str: The response string from QPS indicating the stream export status
        """
        return self.connectionObj.qps.sendCmdVerbose("$stream export status")

    def get_stats_export_status(self) -> str:
        """
        Queries the QPS device for the status of the statistics data export process.

        Returns:
            str: The response string from QPS indicating the stats export status
        """
        return self.connectionObj.qps.sendCmdVerbose("$stream stats export status")

    def stop_stream(self, poll_till_complete: bool = False, check_interval: float = 0.1, timeout: int = 60) -> Literal[Status.OVERRUN, Status.STOPPED] | Any:
        """
        Sends the command to stop the QPS data stream.

        Args:
            poll_till_complete (bool, optional): If True, waits for the stream to fully stop. Defaults to False.
            check_interval (float, optional): Seconds between status checks when polling. Defaults to 0.1.
            timeout (int, optional): Max seconds to wait for polling to complete. Defaults to 60.

        Returns:
            str: The final stream status if polling, otherwise the initial command response.

        Raises:
            Exception: If the stop command itself fails.
            TimeoutError: If polling is enabled and times out.
        """
        response = self.connectionObj.qps.sendCmdVerbose("$stop stream")
        if response.startswith("Fail"):
            raise Exception(response)

        if poll_till_complete:
            start_time = time.monotonic()
            while True:
                stream_state = self.get_stream_state().lower()
                is_stopped = check_stream_stopped_status(stream_state)
                if is_stopped:
                    return is_stopped

                if (time.monotonic() - start_time) > timeout:
                    raise TimeoutError(f"Timeout ({timeout}s) waiting for stream to stop. Last state: {stream_state}")

                logging.debug(f"Stream buffer still emptying: {stream_state}")
                time.sleep(check_interval)

        return response

    def stopStream(self, pollTillComplete: bool = False, checkInterval: float = 0.1, timeout: int = 60) -> str:
        """
        DEPRECATED: Use stop_stream instead.

        Args:
            pollTillComplete (bool, optional): If True, waits until the QPS stream
                                               state is no longer "running". Defaults to False.
            checkInterval (float, optional): Time in seconds between status checks
                                             when polling. Defaults to 0.1.
            timeout (int, optional): Maximum time in seconds to wait. Defaults to 60.

        Returns:
            str: The final checked stream status string ("STOPPED", "OVERRUN") if polling,
                 otherwise the initial response from the '$stop stream' command.
        """
        return self.stop_stream(pollTillComplete, checkInterval, timeout)


# -------------------------------------
#  Constants/Enums
# -------------------------------------
class Status(enum.Enum):
    IN_PROGRESS = "IN PROGRESS"
    COMPLETE = "COMPLETE"
    STOPPED = "STOPPED"
    OVERRUN = "OVERRUN"
    OK = "OK"


# -------------------------------------
#  API Utility Functions
# -------------------------------------
def current_milli_time():
    return int(round(time.time() * 1000))


def current_second_time():
    return int(round(time.time()))


# -------------------------------------
#  Stream API Utility Functions
# -------------------------------------
def check_stream_status(stream_status):
    # Check the stream status, so we know if anything went wrong during the capture period
    if "stopped" in stream_status:
        if "overrun" in stream_status:
            return '\tStream interrupted due to internal device buffer has filled up'
        elif "user" in stream_status:
            return '\tStream interrupted due to max file size has being exceeded'
        else:
            return "\tStopped for unknown reason"
    return "\t Stream running"


def check_stream_stopped_status(stream_status):
    # Check the stream status, so we know if anything went wrong during the capture period
    if "stopped" in stream_status:
        if "overrun" in stream_status:
            logging.warning('Stream interrupted due to internal device buffer has filled up')
            return Status.OVERRUN
        else:
            return Status.STOPPED
    return Status.IN_PROGRESS


# -------------------------------------
#  QPS API Utility Functions
# -------------------------------------
def check_export_status(export_status):
    if export_status == Status.COMPLETE:
        return True
    elif export_status == Status.IN_PROGRESS:
        return False
    return False
