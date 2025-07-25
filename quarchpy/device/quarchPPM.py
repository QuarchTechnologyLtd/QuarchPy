# -*- coding: utf-8 -*-
"""
Library for Quarch Power Modules (PPM).

This module provides the quarchPPM class for interacting with Quarch Power
Modules, building upon the base quarchDevice. It includes methods for controlling
power, streaming data, and managing synthetic channels.
"""

import logging
import xml.etree.ElementTree as ET
from io import StringIO
from typing import IO, List, Optional

from quarchpy.user_interface.user_interface import printText

from .device import quarchDevice


class quarchPPM(quarchDevice):
    """
    A class to represent a Quarch Power Module (PPM).

    This class provides an interface for controlling Quarch PPM devices,
    including streaming, power control, and configuration.
    """

    def __init__(self, originObj: quarchDevice, skipDefaultSyntheticChannels: bool = False):
        """
        Initialises the quarchPPM object.

        Args:
            originObj (quarchDevice): The original device object.
            skipDefaultSyntheticChannels (bool): If True, skips the creation
                of default synthetic channels on QIS-based devices.
        """
        super().__init__(originObj.ConString)
        self.connectionObj = originObj.connectionObj
        self.ConString = originObj.ConString
        self.ConType = originObj.ConType
        self.fixture_definition = self.send_command("fix:chan:xml?")
        self.default_channels: Optional[List['SyntheticChannel']] = None

        # Standardise a connection string format
        if self.ConString.count(":") == 1:
            self.ConString = self.ConString.replace(':', '::')

        # Create default synthetic channels if applicable
        if not skipDefaultSyntheticChannels and self.ConType[:3].upper() == "QIS" and "FAIL:" not in self.fixture_definition:
            self.create_default_synthetic_channels()

    # --------------------------------------------------------------------------
    # New snake_case API
    # --------------------------------------------------------------------------

    def start_stream(
        self,
        file_name: str = 'streamData.txt',
        file_max_mb: int = 200000,
        stream_name: str = 'Stream With No Name',
        stream_duration: Optional[float] = None,
        stream_average: Optional[int] = None,
        release_on_data: bool = False,
        separator: str = ",",
        in_memory_data: Optional[StringIO] = None,
        output_file_handle: Optional[IO] = None,
        use_gzip: Optional[bool] = None
    ) -> str:
        """
        Starts a data stream from the device.

        Args:
            file_name (str): The name of the file to stream data to.
            file_max_mb (int): The maximum size of the output file in megabytes.
            stream_name (str): A descriptive name for the stream.
            stream_duration (Optional[float]): The duration for the stream to run
                in seconds. Defaults to None (continuous).
            stream_average (Optional[int]): The number of samples to average.
                Defaults to None.
            release_on_data (bool): If True, releases the connection on data
                reception.
            separator (str): The separator character to use in the output file.
            in_memory_data (Optional[StringIO]): A StringIO object to store
                streamed data in memory. Defaults to None.
            output_file_handle (Optional[IO]): An open file handle to write
                stream data to. Defaults to None.
            use_gzip (Optional[bool]): If True, compresses the output file using
                gzip. Defaults to None.

        Returns:
            str: The response from the device after starting the stream.
        """
        return self.connectionObj.qis.startStream(
            self.ConString, file_name, file_max_mb, stream_name,
            stream_average, release_on_data, separator, stream_duration,
            in_memory_data, output_file_handle, use_gzip
        )

    def stream_running_status(self) -> str:
        """
        Checks if a stream is currently running.

        Returns:
            str: The running status of the stream.
        """
        return self.connectionObj.qis.streamRunningStatus(self.ConString)

    def stream_buffer_status(self) -> str:
        """
        Gets the status of the stream buffer.

        Returns:
            str: The status of the stream buffer, typically indicating fullness.
        """
        return self.connectionObj.qis.streamBufferStatus(self.ConString)

    def stream_interrupt(self) -> str:
        """
        Interrupts the current stream.

        Returns:
            str: The response from the device after interrupting the stream.
        """
        return self.connectionObj.qis.streamInterrupt()

    def wait_stop(self) -> str:
        """
        Waits for the current operation to stop.

        Returns:
            str: The response from the device.
        """
        return self.connectionObj.qis.waitStop()

    def stream_resample_mode(self, stream_com: str, group: Optional[int] = None) -> str:
        """
        Sets the resample mode for the stream.

        Args:
            stream_com (str): The resampling command. Valid options are "off",
                or a time value like "10ms" or "500us".
            group (Optional[int]): The specific group to apply the resampling
                mode to. If None, applies to the main stream.

        Returns:
            str: The device's response, or an error message if the command is
                 invalid.
        """
        if stream_com.lower() == "off" or stream_com[0:-2].isdigit():
            if group is not None:
                cmd = f"stream mode resample group {group} {stream_com.lower()}"
            else:
                cmd = f"stream mode resample {stream_com.lower()}"

            retVal = self.connectionObj.qis.sendAndReceiveCmd(cmd=cmd, device=self.ConString)
            if "fail" in retVal.lower():
                logging.error(retVal)
        else:
            retVal = "Invalid resampling argument. Valid options are: off, [x]ms or [x]us."
            logging.error(retVal)
        return retVal

    def stop_stream(self) -> str:
        """
        Stops the current data stream.

        Returns:
            str: The response from the device after stopping the stream.
        """
        return self.connectionObj.qis.stopStream(self)

    def setup_power_output(self) -> None:
        """
        Configures and enables the module's power output.

        Checks the output mode, sets a default voltage if required (e.g., for
        XLC modules), and then enables the power output if it's off.

        Raises:
            ValueError: If an invalid voltage is entered by the user.
        """
        out_mode_str = self.send_command("config:output Mode?")
        if "DISABLED" in out_mode_str:
            try:
                drive_voltage = input(
                    "\nModule requires manual voltage selection."
                    "\n>>> Please select a voltage [3V3, 5V]: "
                ) or "3V3"
                if drive_voltage.upper() not in ["3V3", "5V"]:
                    raise ValueError("Invalid voltage selected.")
                self.send_command(f"config:output:mode:{drive_voltage}")
            except ValueError as e:
                logging.error(e)

        power_state = self.send_command("run power?")
        if "OFF" in power_state or "PULLED" in power_state:
            printText("\nTurning the outputs on...")
            self.send_command("run:power up")
            printText("Done!")

    def parse_synthetic_channels_from_instrument(self) -> List['SyntheticChannel']:
        """
        Parses synthetic channel definitions from the device's fixture XML.

        This function reads the fixture XML structure and looks for channels
        under the SyntheticChannels node, extracting their properties.

        Returns:
            List[SyntheticChannel]: A list of SyntheticChannel objects parsed
                from the XML.
        """
        root = ET.fromstring(self.fixture_definition)
        synthetic_channels = []

        for channel in root.findall(".//SyntheticChannels/Channel"):
            number_elem = channel.find(".//Param[Name='Number']/Value")
            function_elem = channel.find(".//Param[Name='Function']/Value")
            enable_elem = channel.find(".//Param[Name='Enable']/Value")
            enabled_by_default_elem = channel.find(".//Param[Name='EnabledByDefault']/Value")
            visible_by_default_elem = channel.find(".//Param[Name='VisibleByDefault']/Value")

            number = int(number_elem.text) if number_elem is not None else 0
            function = function_elem.text if function_elem is not None else ""
            enable = enable_elem.text.lower() == 'true' if enable_elem is not None else False
            enabled_by_default = enabled_by_default_elem.text.lower() == 'true' if enabled_by_default_elem is not None else False
            visible_by_default = visible_by_default_elem.text.lower() == 'true' if visible_by_default_elem is not None else False

            synthetic_channel = SyntheticChannel(
                number, function, enable, enabled_by_default, visible_by_default
            )
            synthetic_channels.append(synthetic_channel)

        return synthetic_channels

    def send_synthetic_channels(self, channels: List['SyntheticChannel']) -> None:
        """
        Sends commands to the device to create a set of synthetic channels.

        Args:
            channels (List[SyntheticChannel]): A list of SyntheticChannel objects
                to create on the device.

        Raises:
            Exception: If the command to create a channel fails.
        """
        for channel in channels:
            result = self.send_command(f"stream create channel {channel.function}")
            if result != "OK":
                raise Exception(
                    f"Command failed for channel {channel.number}: "
                    f"{channel.function} = {result}"
                )

    def create_default_synthetic_channels(self) -> None:
        """
        Creates default synthetic channels based on the fixture XML.

        This method parses the channels from the instrument's fixture definition
        and sends the necessary commands to create them. This is typically run
        once during initialization.
        """
        self.default_channels = self.parse_synthetic_channels_from_instrument()
        self.send_synthetic_channels(self.default_channels)

    # --------------------------------------------------------------------------
    # Deprecated camelCase API (for backward compatibility)
    # --------------------------------------------------------------------------

    def startStream(self, fileName: str = 'streamData.txt', fileMaxMB: int = 200000,
                    streamName: str = 'Stream With No Name', streamDuration: Optional[float] = None,
                    streamAverage: Optional[int] = None, releaseOnData: bool = False, separator: str = ",",
                    inMemoryData: Optional[StringIO] = None, outputFileHandle: Optional[IO] = None,
                    useGzip: Optional[bool] = None) -> str:
        """
        DEPRECATED: Use start_stream instead.

        Starts a data stream from the device.

        Args:
            fileName (str): The name of the file to stream data to.
            fileMaxMB (int): The maximum size of the output file in megabytes.
            streamName (str): A descriptive name for the stream.
            streamDuration (Optional[float]): The duration for the stream to run
                in seconds. Defaults to None (continuous).
            streamAverage (Optional[int]): The number of samples to average.
                Defaults to None.
            releaseOnData (bool): If True, releases the connection on data
                reception.
            separator (str): The separator character to use in the output file.
            inMemoryData (Optional[StringIO]): A StringIO object to store
                streamed data in memory. Defaults to None.
            outputFileHandle (Optional[IO]): An open file handle to write
                stream data to. Defaults to None.
            useGzip (Optional[bool]): If True, compresses the output file using
                gzip. Defaults to None.

        Returns:
            str: The response from the device after starting the stream.
        """
        return self.start_stream(
            file_name=fileName, file_max_mb=fileMaxMB, stream_name=streamName,
            stream_duration=streamDuration, stream_average=streamAverage,
            release_on_data=releaseOnData, separator=separator,
            in_memory_data=inMemoryData, output_file_handle=outputFileHandle,
            use_gzip=useGzip
        )

    def streamRunningStatus(self) -> str:
        """
        DEPRECATED: Use stream_running_status instead.

        Checks if a stream is currently running.

        Returns:
            str: The running status of the stream.
        """
        return self.stream_running_status()

    def streamBufferStatus(self) -> str:
        """
        DEPRECATED: Use stream_buffer_status instead.

        Gets the status of the stream buffer.

        Returns:
            str: The status of the stream buffer, typically indicating fullness.
        """
        return self.stream_buffer_status()

    def streamInterrupt(self) -> str:
        """
        DEPRECATED: Use stream_interrupt instead.

        Interrupts the current stream.

        Returns:
            str: The response from the device after interrupting the stream.
        """
        return self.stream_interrupt()

    def waitStop(self) -> str:
        """
        DEPRECATED: Use wait_stop instead.

        Waits for the current operation to stop.

        Returns:
            str: The response from the device.
        """
        return self.wait_stop()

    def streamResampleMode(self, streamCom: str, group: Optional[int] = None) -> str:
        """
        DEPRECATED: Use stream_resample_mode instead.

        Sets the resample mode for the stream.

        Args:
            streamCom (str): The resampling command. Valid options are "off",
                or a time value like "10ms" or "500us".
            group (Optional[int]): The specific group to apply the resampling
                mode to. If None, applies to the main stream.

        Returns:
            str: The device's response, or an error message if the command is
                 invalid.
        """
        return self.stream_resample_mode(stream_com=streamCom, group=group)

    def stopStream(self) -> str:
        """
        DEPRECATED: Use stop_stream instead.

        Stops the current data stream.

        Returns:
            str: The response from the device after stopping the stream.
        """
        return self.stop_stream()

    def setupPowerOutput(self) -> None:
        """
        DEPRECATED: Use setup_power_output instead.

        Configures and enables the module's power output.

        Checks the output mode, sets a default voltage if required (e.g., for
        XLC modules), and then enables the power output if it's off.

        Raises:
            ValueError: If an invalid voltage is entered by the user.
        """
        return self.setup_power_output()


class SyntheticChannel:
    """
    A data class representing a synthetic channel.

    Attributes:
        number (int): The unique identifier for the synthetic channel.
        function (str): The function/command defining the channel's behavior.
        enable (bool): Whether the channel is currently enabled.
        enabled_by_default (bool): Whether the channel is enabled by default.
        visible_by_default (bool): Whether the channel is visible by default.
    """

    def __init__(
        self,
        number: int,
        function: str,
        enable: bool,
        enabled_by_default: bool,
        visible_by_default: bool
    ):
        """Initializes the SyntheticChannel object."""
        self.number = number
        self.function = function
        self.enable = enable
        self.enabled_by_default = enabled_by_default
        self.visible_by_default = visible_by_default

    def __repr__(self) -> str:
        """Provides a readable string representation of the object."""
        return (f"SyntheticChannel(Number={self.number}, Function='{self.function}', "
                f"Enable={self.enable}, EnabledByDefault={self.enabled_by_default}, "
                f"VisibleByDefault={self.visible_by_default})")
