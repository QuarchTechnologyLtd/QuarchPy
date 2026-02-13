import os
import sys
import inspect
from ._version import __version__
import logging
from pathlib import Path
from logging.handlers import RotatingFileHandler


# --- Dynamic Level Synchronization ---
class SyncWithRootFilter(logging.Filter):
    """
    A filter that dynamically checks the root logger's level.
    This allows the quarchpy console handler to 'point' to the
    global python log level even if it changes mid-script.
    """

    def filter(self, record):
        # Dynamically fetch the root logger's effective level
        root_level = logging.getLogger().getEffectiveLevel()
        # Only allow the log record if its level is >= the current root level
        return record.levelno >= root_level


logger = logging.getLogger("quarchpy")

# Master Valve: Must stay DEBUG so the File Handler captures everything.
logger.setLevel(logging.DEBUG)

# Propagate to root is False because we provide our own console handler.
# If True, you would see duplicate logs if the user also has a root handler.
logger.propagate = False

# Only add handlers once
if not logger.handlers:
    # 1. File handler (Always capture DEBUG for the 'permanent record')
    log_dir = Path.home() / ".quarchpy"
    log_dir.mkdir(exist_ok=True)
    logfile = log_dir / "quarchpy.log"

    file_handler = RotatingFileHandler(logfile, maxBytes=5_000_000, backupCount=5)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        "%Y-%m-%d %H:%M:%S"
    ))
    logger.addHandler(file_handler)

    # 2. Console: Dynamically mirrors the python root log level
    console_handler = logging.StreamHandler()

    # We set this to NOTSET (0) so the handler itself doesn't block anything...
    console_handler.setLevel(logging.NOTSET)

    # ...instead, we use the custom filter to do the dynamic level check.
    console_handler.addFilter(SyncWithRootFilter())

    console_handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        "%Y-%m-%d %H:%M:%S"
    ))
    logger.addHandler(console_handler)


# ---- Public API for users ----
def configure_logging(console_level=None, file_level=None, file_path=None):
    """Reconfigure quarchpy logging safely."""
    for handler in logger.handlers:
        # Change console level (Note: Setting this overrides the SyncWithRootFilter behavior)
        if isinstance(handler, logging.StreamHandler) and not isinstance(handler, RotatingFileHandler):
            if console_level is not None:
                # If the user explicitly sets a level, we remove the dynamic filter
                # so it behaves exactly as the user requested.
                for f in handler.filters:
                    if isinstance(f, SyncWithRootFilter):
                        handler.removeFilter(f)
                handler.setLevel(console_level)

        # Change file level and path
        if isinstance(handler, RotatingFileHandler):
            if file_level is not None:
                handler.setLevel(file_level)
            if file_path is not None:
                handler.baseFilename = str(file_path)

    logger.info(
        f"quarchpy logging reconfigured console_level:{console_level} file_level:{file_level} file_path:{file_path}")


# --- Path Management (Maintain existing legacy behavior) ---
base_path = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
folders = [
    "",
    "disk_test",
    "connection_specific",
    os.path.join("connection_specific", "serial"),
    os.path.join("connection_specific", "QIS"),
    os.path.join("connection_specific", "usb_libs"),
    "config_files"
]

for folder in folders:
    folder2add = os.path.realpath(os.path.join(base_path, folder))
    if folder2add not in sys.path:
        sys.path.insert(0, folder2add)

# --- Public API Imports ---
from debug.versionCompare import requiredQuarchpyVersion
from device import quarchDevice, getQuarchDevice, get_quarch_device
from connection_specific.connection_QIS import QisInterface, QisInterface as qisInterface
from connection_specific.connection_QPS import QpsInterface, QpsInterface as qpsInterface
from qis.qisFuncs import isQisRunning, startLocalQis, GetQisModuleSelection
from qis.qisFuncs import closeQis, closeQis as closeQIS
from device.quarchPPM import quarchPPM
from iometer.iometerFuncs import generateIcfFromCsvLineData, readIcfCsvLineData, generateIcfFromConf, runIOMeter, \
    processIometerInstResults
from device.quarchQPS import quarchQPS
from qps.qpsFuncs import isQpsRunning, startLocalQps, GetQpsModuleSelection
from qps.qpsFuncs import closeQps, closeQps as closeQPS
from disk_test.DiskTargetSelection import getDiskTargetSelection, getDiskTargetSelection as GetDiskTargetSelection
from fio.FIO_interface import runFIO
from device.scanDevices import scanDevices