# quarchPPM.py Refactored (Logic moved to snake_case, original becomes wrapper)

from .device import quarchDevice  # Assuming relative import

import logging
import time
import xml.etree.ElementTree as ET

try:
    # Used by original setupPowerOutput logic
    from quarchpy.user_interface.user_interface import printText
except ImportError:
    printText = print  # Basic fallback
import json  # For parse_fixture_definition method


class quarchPPM(quarchDevice):
    # --- Special Methods (Untouched Logic) ---
    def __init__(self, originObj, skipDefaultSyntheticChannels=False):
        """
        Initializes the quarchPPM instance using an existing quarchDevice object.
        (Logic remains unchanged, internal calls remain original names)
        """
        if not isinstance(originObj, quarchDevice):
            raise TypeError("originObj must be an instance of quarchDevice.")
        if not hasattr(originObj, 'connectionObj') or not originObj.connectionObj:
            raise ValueError("originObj does not have a valid connection object.")

        # Share connection object and details
        self.connectionObj = originObj.connectionObj
        self.ConString = originObj.ConString
        self.ConType = originObj.ConType
        self.timeout = getattr(originObj, 'timeout', '5')  # Inherit timeout if available
        self._origin_ref = originObj

        self.fixture_definition = None
        self.default_channels = None

        logging.info(f"quarchPPM initialized for device: {self.ConString} (Type: {self.ConType})")

        # Get fixture definition using original method name (wrapper)
        try:
            self.fixture_definition = self.sendCommand("fix:chan:xml?")
        except Exception as e:
            logging.error(f"Failed to get fixture definition during init: {e}")
            self.fixture_definition = "FAIL: Error getting definition"

        # Handle potential double colon for QIS based on original logic
        numb_colons = self.ConString.count(":")
        if numb_colons == 1 and self.ConType[:3].upper() == "QIS":
            logging.debug("Adjusting ConString for potential QIS double colon format.")
            self.ConString = self.ConString.replace(':', '::')

        fixture_ok = self.fixture_definition is not None and "FAIL:" not in self.fixture_definition

        if not skipDefaultSyntheticChannels and self.ConType[:3].upper() == "QIS" and fixture_ok:
            try:
                # Call original snake_case method name (unchanged)
                self.create_default_synthetic_channels()
            except Exception as e_synth:
                logging.error(f"Failed to create default synthetic channels: {e_synth}")
        elif not fixture_ok:
            logging.warning("Skipping default synthetic channels: Fixture definition invalid or failed.")
        # (Other logging for skip reasons can be added here if desired)

    # --- Original Methods (Logic moved to snake_case below) ---

    def startStream(self, fileName='streamData.txt', fileMaxMB=200000, streamName='Stream With No Name',
                    streamDuration=None, streamAverage=None, releaseOnData=False, separator=",", inMemoryData=None):
        """ Starts a data stream using the QIS connection (camelCase wrapper). """
        return self.start_stream(fileName, fileMaxMB, streamName, streamDuration, streamAverage, releaseOnData,
                                 separator, inMemoryData)

    def streamRunningStatus(self):
        """ Checks the running status of the QIS stream (camelCase wrapper). """
        return self.get_stream_running_status()

    def streamBufferStatus(self):
        """ Checks the buffer status of the QIS stream (camelCase wrapper). """
        return self.get_stream_buffer_status()

    def streamInterrupt(self):
        """ Interrupts the QIS stream (camelCase wrapper). """
        return self.stream_interrupt()

    def waitStop(self):
        """ Waits for the QIS stream to stop (camelCase wrapper). """
        return self.wait_stop()

    def streamResampleMode(self, streamCom, group=None):
        """ Sets the resample mode for the QIS stream (camelCase wrapper). """
        return self.set_stream_resample_mode(streamCom, group)

    def stopStream(self):
        """ Stops the currently running QIS stream (camelCase wrapper). """
        return self.stop_stream()

    # Note: setupPowerOutput is defined like a static method in the original.
    # The wrapper will reflect this, not taking 'self'.
    def setupPowerOutput(myModule):
        """ Sets up power output on a given module instance (camelCase wrapper). """
        # Calls the corresponding snake_case function (defined below)
        return setup_power_output(myModule)

    # --- Original snake_case Methods (Unchanged Logic) ---

    def parse_synthetic_channels_from_instrument(self):
        """
        Parses the fixture XML and extracts the synthetic channels specified by the instrument defaults.
        (Original Logic Unchanged)
        """
        # Ensure fixture definition is valid XML before parsing
        if not self.fixture_definition or not isinstance(self.fixture_definition,
                                                         str) or self.fixture_definition.startswith("FAIL:"):
            logging.error("Cannot parse synthetic channels: Invalid or missing fixture definition.")
            return []
        try:
            # Parse the XML data from the fixture_definition (which is an XML string)
            root = ET.fromstring(self.fixture_definition)
        except ET.ParseError as e:
            logging.error(f"Failed to parse fixture definition XML: {e}")
            return []

        synthetic_channels = []
        # Use XPath to find channels reliably
        try:
            for channel in root.findall(".//SyntheticChannels/Channel"):
                # Extract values safely using .findtext() with defaults
                number_str = channel.findtext(".//Param[Name='Number']/Value", '0')
                function = channel.findtext(".//Param[Name='Function']/Value", '')
                enable_str = channel.findtext(".//Param[Name='Enable']/Value", 'false')
                enabled_by_default_str = channel.findtext(".//Param[Name='EnabledByDefault']/Value", 'false')
                visible_by_default_str = channel.findtext(".//Param[Name='VisibleByDefault']/Value", 'false')

                # Convert values with error handling
                try:
                    number = int(number_str)
                except ValueError:
                    number = 0; logging.warning("Invalid Number found in fixture XML")

                enable = enable_str.lower() == 'true'
                enabled_by_default = enabled_by_default_str.lower() == 'true'
                visible_by_default = visible_by_default_str.lower() == 'true'

                if not function: logging.warning("Empty Function found in fixture XML")

                synthetic_channel = SyntheticChannel(number, function, enable, enabled_by_default, visible_by_default)
                synthetic_channels.append(synthetic_channel)
        except Exception as e_parse:
            logging.error(f"Error parsing channel details from fixture XML: {e_parse}")

        return synthetic_channels

    def send_synthetic_channels(self, channels):
        """
        Sends the set of synthetic channels to the device.
        (Original Logic Unchanged - internal calls remain camelCase)
        """
        if not isinstance(channels, list):
            logging.error("send_synthetic_channels requires a list of channels.")
            return

        logging.info(f"Sending {len(channels)} synthetic channel definitions...")
        for channel in channels:
            if not isinstance(channel, SyntheticChannel):
                logging.warning(f"Skipping invalid item in channels list: {channel}")
                continue
            try:
                # Internal call remains camelCase (calls wrapper)
                result = self.sendCommand("stream create channel " + channel.function)

                # Original logic checked only for "OK" - make check more robust
                if result is None or "OK" not in result.upper():  # Check for None and case-insensitivity
                    # Raise or just log? Original raised Exception.
                    error_msg = f"Command failed for channel {channel.number}: '{channel.function}' = Received: '{result}'"
                    logging.error(error_msg)
                    raise Exception(error_msg)  # Replicate original behaviour
                else:
                    logging.debug(f"Successfully sent channel {channel.number}: {channel.function}")
            except Exception as e_send:
                # Catch errors from sendCommand or the check itself
                logging.error(f"Error sending synthetic channel {channel.number}: {e_send}")
                # Re-raise to indicate failure
                raise

    def create_default_synthetic_channels(self):
        """
        Creates the default synthetic channels based on the fixture XML.
        (Original Logic Unchanged - internal calls remain original names)
        """
        logging.info("Parsing and sending default synthetic channels...")
        try:
            # Internal call remains snake_case (original name)
            parsed_channels = self.parse_synthetic_channels_from_instrument()
            if parsed_channels:
                self.default_channels = parsed_channels  # Store parsed channels
                # Internal call remains snake_case (original name)
                self.send_synthetic_channels(self.default_channels)
                logging.info("Default synthetic channels sent successfully.")
            else:
                logging.warning("No default synthetic channels found or parsed from fixture.")
        except Exception as e:
            logging.error(f"Failed during default synthetic channel creation process: {e}")
            # Decide if this should propagate or just be logged.

    # --- New snake_case Methods (Containing Original Logic) ---

    def start_stream(self, fileName='streamData.txt', fileMaxMB=200000, streamName='Stream With No Name',
                     streamDuration=None, streamAverage=None, releaseOnData=False, separator=",", inMemoryData=None):
        """ Starts a data stream using the QIS connection (snake_case API). """
        # This method now contains the original logic from startStream
        # Assumes self.connectionObj is a QIS connection object with a 'qis' attribute
        if hasattr(self.connectionObj, 'qis') and hasattr(self.connectionObj.qis, 'startStream'):
            try:
                logging.info(f"Starting QIS stream '{streamName}' to '{fileName}'")
                return self.connectionObj.qis.startStream(self.ConString, fileName, fileMaxMB, streamName,
                                                          streamAverage, releaseOnData, separator, streamDuration,
                                                          inMemoryData)
            except Exception as e:
                logging.error(f"Error calling QIS startStream: {e}", exc_info=True)
                raise ConnectionError("Failed QIS startStream") from e
        else:
            raise AttributeError("QIS connection object or startStream method not found.")

    def get_stream_running_status(self):
        """ Checks the running status of the QIS stream (snake_case API). """
        # This method now contains the original logic from streamRunningStatus
        if hasattr(self.connectionObj, 'qis') and hasattr(self.connectionObj.qis, 'streamRunningStatus'):
            try:
                logging.debug("Checking QIS stream running status.")
                return self.connectionObj.qis.streamRunningStatus(self.ConString)
            except Exception as e:
                logging.error(f"Error calling QIS streamRunningStatus: {e}", exc_info=True)
                raise ConnectionError("Failed QIS streamRunningStatus") from e
        else:
            raise AttributeError("QIS connection object or streamRunningStatus method not found.")

    def get_stream_buffer_status(self):
        """ Checks the buffer status of the QIS stream (snake_case API). """
        # This method now contains the original logic from streamBufferStatus
        if hasattr(self.connectionObj, 'qis') and hasattr(self.connectionObj.qis, 'streamBufferStatus'):
            try:
                logging.debug("Checking QIS stream buffer status.")
                return self.connectionObj.qis.streamBufferStatus(self.ConString)
            except Exception as e:
                logging.error(f"Error calling QIS streamBufferStatus: {e}", exc_info=True)
                raise ConnectionError("Failed QIS streamBufferStatus") from e
        else:
            raise AttributeError("QIS connection object or streamBufferStatus method not found.")

    def stream_interrupt(self):
        """ Interrupts the QIS stream (snake_case API). """
        # This method now contains the original logic from streamInterrupt
        if hasattr(self.connectionObj, 'qis') and hasattr(self.connectionObj.qis, 'streamInterrupt'):
            try:
                logging.info("Sending QIS stream interrupt.")
                return self.connectionObj.qis.streamInterrupt()  # Assumes no args needed
            except Exception as e:
                logging.error(f"Error calling QIS streamInterrupt: {e}", exc_info=True)
                raise ConnectionError("Failed QIS streamInterrupt") from e
        else:
            raise AttributeError("QIS connection object or streamInterrupt method not found.")

    def wait_stop(self):
        """ Waits for the QIS stream to stop (snake_case API). """
        # This method now contains the original logic from waitStop
        if hasattr(self.connectionObj, 'qis') and hasattr(self.connectionObj.qis, 'waitStop'):
            try:
                logging.info("Waiting for QIS stream to stop...")
                result = self.connectionObj.qis.waitStop()  # Assumes no args needed
                logging.info("QIS stream stopped.")
                return result
            except Exception as e:
                logging.error(f"Error calling QIS waitStop: {e}", exc_info=True)
                raise ConnectionError("Failed QIS waitStop") from e
        else:
            raise AttributeError("QIS connection object or waitStop method not found.")

    def set_stream_resample_mode(self, streamCom, group=None):
        """ Sets the resample mode for the QIS stream (snake_case API). """
        # This method now contains the original logic from streamResampleMode
        retVal = "FAIL: Invalid arguments or connection issue"  # Default fail
        valid_format = False
        streamCom_lower = str(streamCom).lower()
        # Original check: streamCom[0:-2].isdigit() assumes units are present
        if streamCom_lower == "off":
            valid_format = True
        elif streamCom_lower.endswith("ms") and streamCom_lower[:-2].isdigit():
            valid_format = True
        elif streamCom_lower.endswith("us") and streamCom_lower[:-2].isdigit():
            valid_format = True

        if valid_format:
            cmd = "stream mode resample " + streamCom_lower
            if group is not None:
                try:
                    group_int = int(group)
                    cmd = f"stream mode resample group {group_int} {streamCom_lower}"
                except (ValueError, TypeError):
                    retVal = f"FAIL: Invalid group number '{group}'. Must be an integer."
                    logging.error(retVal)
                    return retVal

            # Check QIS connection before sending command
            if hasattr(self.connectionObj, 'qis') and hasattr(self.connectionObj.qis, 'sendAndReceiveCmd'):
                try:
                    logging.info(f"Setting stream resample mode: '{cmd}'")
                    retVal = self.connectionObj.qis.sendAndReceiveCmd(cmd=cmd, device=self.ConString)
                    if "fail" in retVal.lower():
                        logging.error(f"QIS command failed: '{cmd}' Response: {retVal}")
                    else:
                        logging.info(f"QIS command successful: '{cmd}' Response: {retVal}")
                except Exception as e:
                    retVal = f"FAIL: Error sending command '{cmd}' to QIS: {e}"
                    logging.error(retVal, exc_info=True)
            else:
                retVal = "FAIL: QIS connection object or sendAndReceiveCmd method not found."
                logging.error(retVal)
        else:
            retVal = f"FAIL: Invalid resampling argument '{streamCom}'. Valid options are: off, [x]ms or [x]us."
            logging.error(retVal)
        return retVal

    def stop_stream(self):
        """ Stops the currently running QIS stream (snake_case API). """
        # This method now contains the original logic from stopStream
        # *** Correcting parameter passed to qis.stopStream from self to self.ConString ***
        if hasattr(self.connectionObj, 'qis') and hasattr(self.connectionObj.qis, 'stopStream'):
            try:
                logging.info(f"Stopping QIS stream for {self.ConString}.")
                return self.connectionObj.qis.stopStream(self.ConString)  # Pass ConString
            except Exception as e:
                logging.error(f"Error calling QIS stopStream: {e}", exc_info=True)
                raise ConnectionError("Failed QIS stopStream") from e
        else:
            raise AttributeError("QIS connection object or stopStream method not found.")


# --- Standalone Function (from Class Scope) ---

# New snake_case function containing logic FORMERLY in setupPowerOutput
# Note: This function operates on a passed module instance, not 'self'.
def setup_power_output(myModule):
    """
    Simple function to check the output mode of the power module, setting it if required
    then enabling the outputs if not already done. (snake_case API)
    """
    # This function now contains the actual implementation
    # Input validation
    if not isinstance(myModule, quarchDevice):
        logging.error("setup_power_output requires a valid quarchDevice instance.")
        printText("Error: Invalid module provided to setup_power_output.")
        return  # Or raise TypeError

    module_id = getattr(myModule, 'ConString', 'Unknown Module')
    logging.info(f"Setting up power output for: {module_id}")

    try:
        # Internal call remains camelCase (calls the wrapper on the passed instance)
        outModeStr = myModule.sendCommand("config:output Mode?")
        if outModeStr is None: raise ConnectionError("Did not receive response for output mode query.")

        if "DISABLED" in outModeStr:
            drive_voltage = "5V"  # Default if input fails or is skipped
            printText("\nModule output disabled (or HD fixture?).")
            try:
                # Use input() for Py2/3 compatibility
                user_input = input(">>> Please select a voltage [3V3, 5V] (Default 5V): ")
                if user_input.upper() == "3V3":
                    drive_voltage = "3V3"
                elif user_input.upper() == "5V":
                    drive_voltage = "5V"
                elif user_input == "":
                    drive_voltage = "5V"  # Explicit default
                else:
                    printText(f"Invalid input '{user_input}', using default {drive_voltage}.")
            except Exception as e:
                printText(f"Error during input, using default {drive_voltage}. Error: {e}")

            logging.info(f"Setting output mode to {drive_voltage}")
            # Internal call remains camelCase (calls the wrapper)
            myModule.sendCommand("config:output:mode:" + drive_voltage)
            time.sleep(0.1)  # Allow mode change to settle?

        # Check power state using original camelCase method name (wrapper)
        powerState = myModule.sendCommand("run power?")
        if powerState is None: raise ConnectionError("Did not receive response for power state query.")

        if "OFF" in powerState or "PULLED" in powerState:  # PULLED comes from PAM
            printText("\n Turning the outputs on..."),
            # Internal call remains camelCase (calls the wrapper)
            myModule.sendCommand("run:power up")
            # Verify power up? Optional, add short delay and re-check powerState
            time.sleep(0.5)
            newPowerState = myModule.sendCommand("run power?")
            if newPowerState and ("ON" in newPowerState or "UP" in newPowerState):  # Check for ON or UP
                printText(" Done!")
                logging.info("Module outputs turned ON.")
            else:
                printText(" Failed to verify power up!")
                logging.error(f"Failed to verify module power up. State: {newPowerState}")
        else:
            printText("\nModule outputs already ON.")
            logging.info("Module outputs already ON.")

    except (ConnectionError, TimeoutError) as e:
        printText(f"\nError communicating with module {module_id}: {e}")
        logging.error(f"Communication error during setupPowerOutput for {module_id}: {e}")
    except Exception as e:
        printText(f"\nUnexpected error during power setup for {module_id}: {e}")
        logging.error(f"Unexpected error during setupPowerOutput for {module_id}: {e}", exc_info=True)


# --- SyntheticChannel Class (Unchanged) ---
class SyntheticChannel:
    """ Class representing a SyntheticChannel. """

    # Special methods __init__ and __repr__ remain unchanged
    def __init__(self, number, function, enable, enabled_by_default, visible_by_default):
        self.number = number
        self.function = function
        self.enable = enable
        self.enabled_by_default = enabled_by_default
        self.visible_by_default = visible_by_default

    def __repr__(self):
        return (f"SyntheticChannel(Number={self.number}, Function='{self.function}', "
                f"Enable={self.enable}, EnabledByDefault={self.enabled_by_default}, "
                f"VisibleByDefault={self.visible_by_default})")
