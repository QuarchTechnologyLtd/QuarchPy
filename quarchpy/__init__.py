import os
import sys
import inspect
from ._version import __version__
import logging
from pathlib import Path
from logging.handlers import RotatingFileHandler

logger = logging.getLogger("quarchpy")
logger.setLevel(logging.DEBUG)

# Don't propagate to root unless you want duplicate output
logger.propagate = False

# Only add handlers once
if not logger.handlers:

    # File handler (always debug)
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

    # Console: default WARNING
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        "%Y-%m-%d %H:%M:%S"
    ))
    logger.addHandler(console_handler)


# ---- Public API for users ----
def configure_logging(console_level=None, file_level=None, file_path=None):
    """Reconfigure quarchpy logging safely."""
    for handler in logger.handlers:
        # Change console level
        if isinstance(handler, logging.StreamHandler):
            if console_level is not None:
                handler.setLevel(console_level)

        # Change file level and path
        if isinstance(handler, RotatingFileHandler):
            if file_level is not None:
                handler.setLevel(file_level)
            if file_path is not None:
                handler.baseFilename = str(file_path)

    logger.info("quarchpy logging reconfigured")


# Adds / to the path.
folder2add = os.path.realpath(os.path.abspath(os.path.split(inspect.getfile( inspect.currentframe() ))[0]) + "//")
if folder2add not in sys.path:
    sys.path.insert(0, folder2add)

# Adds /disk_test to the path.
folder2add = os.path.realpath(os.path.abspath(os.path.split(inspect.getfile( inspect.currentframe() ))[0]) + "//disk_test")
if folder2add not in sys.path:
    sys.path.insert(0, folder2add)

# Adds /connection_specific to the path.
folder2add = os.path.realpath(os.path.abspath(os.path.split(inspect.getfile( inspect.currentframe() ))[0]) + "//connection_specific")
if folder2add not in sys.path:
    sys.path.insert(0, folder2add)

# Adds /serial to the path.
folder2add = os.path.realpath(os.path.abspath(os.path.split(inspect.getfile( inspect.currentframe() ))[0]) + "//connection_specific//serial")
if folder2add not in sys.path:
    sys.path.insert(0, folder2add)

# Adds /QIS to the path.
folder2add = os.path.realpath(os.path.abspath(os.path.split(inspect.getfile( inspect.currentframe() ))[0]) + "//connection_specific//QIS")
if folder2add not in sys.path:
    sys.path.insert(0, folder2add)

# Adds /usb_libs to the path.
folder2add = os.path.realpath(os.path.abspath(os.path.split(inspect.getfile( inspect.currentframe() ))[0]) + "//connection_specific//usb_libs")
if folder2add not in sys.path:
    sys.path.insert(0, folder2add)

# Adds /usb_libs to the path.
folder2add = os.path.realpath(os.path.abspath(os.path.split(inspect.getfile( inspect.currentframe() ))[0]) + "//config_files")
if folder2add not in sys.path:
    sys.path.insert(0, folder2add)

# Basic functions imported up to the root module in the package
from debug.versionCompare import requiredQuarchpyVersion

#importing legacy API functions to the root module in the package.  This is to avoid
#breacking back-compatibility with old scripts.  Avoid using these direct imports
#and use the managed sub module format instead (from quarchpy.device import *)
from device import quarchDevice, getQuarchDevice, get_quarch_device
from connection_specific.connection_QIS import QisInterface, QisInterface as qisInterface
from connection_specific.connection_QPS import QpsInterface, QpsInterface as qpsInterface
from qis.qisFuncs import isQisRunning, startLocalQis, GetQisModuleSelection
from qis.qisFuncs import closeQis, closeQis as closeQIS
from device.quarchPPM import quarchPPM
from iometer.iometerFuncs import generateIcfFromCsvLineData, readIcfCsvLineData, generateIcfFromConf, runIOMeter, processIometerInstResults
from device.quarchQPS import quarchQPS
from qps.qpsFuncs import isQpsRunning, startLocalQps, GetQpsModuleSelection
from qps.qpsFuncs import closeQps, closeQps as closeQPS
from disk_test.DiskTargetSelection import getDiskTargetSelection, getDiskTargetSelection as GetDiskTargetSelection
from fio.FIO_interface import runFIO
from device.scanDevices import scanDevices

