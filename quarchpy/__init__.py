import os
import sys
#import re
import inspect
from ._version import __version__

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
from device import quarchDevice, getQuarchDevice
from connection_specific.connection_QIS import QisInterface as qisInterface
from connection_specific.connection_QPS import QpsInterface as qpsInterface
from qis.qisFuncs import isQisRunning, startLocalQis, GetQisModuleSelection
from qis.qisFuncs import closeQis as closeQIS
from device.quarchPPM import quarchPPM
from iometer.iometerFuncs import generateIcfFromCsvLineData, readIcfCsvLineData, generateIcfFromConf, runIOMeter, processIometerInstResults
from device.quarchQPS import quarchQPS
from qps.qpsFuncs import isQpsRunning, startLocalQps, GetQpsModuleSelection
from qps.qpsFuncs import closeQps as closeQPS
from disk_test.DiskTargetSelection import getDiskTargetSelection as GetDiskTargetSelection
from qps.qpsFuncs import toQpsTimeStamp as adjustTime
from fio.FIO_interface import runFIO
from device.scanDevices import scanDevices

