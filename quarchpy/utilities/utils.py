# utils.py
from enum import Enum
# -------------------------------------
#  Constants/Enums
# -------------------------------------
class Status(Enum):
    IN_PROGRESS = "IN PROGRESS"
    COMPLETE = "COMPLETE"

# -------------------------------------
#  API Utility Functions
# -------------------------------------

import time
import logging

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

def check_stream_stopped_status(stream_status):
    # Check the stream status, so we know if anything went wrong during the capture period
    if "stopped" in stream_status:
        if "overrun" in stream_status:
            return 'Stream interrupted due to internal device buffer has filled up'
        else:
            return 'OK'

# -------------------------------------
#  QPS API Utility Functions
# -------------------------------------
def check_export_status(export_status):
    if export_status == Status.COMPLETE:
        return True
    elif export_status == Status.IN_PROGRESS:
        return False


# -------------------------------------
#  QIS API Utility Functions
# -------------------------------------


# -------------------------------------
#  Logging Utilities
# -------------------------------------
def setup_logger(name, log_file, level=logging.INFO):
    """Set up a logger for different modules."""
    logger = logging.getLogger(name)
    handler = logging.FileHandler(log_file)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(level)
    return logger
