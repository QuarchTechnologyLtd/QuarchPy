====================
Changelog (Quarchpy)
====================
Quarchpy
--------
*QuarchPy is a python package designed to provide an easy-to-use API which will work seamlessly over any connection option: USB, Serial and LAN. With it, you can create your own scripts for controlling Quarch devices - without having to worry about the low-level code involved with communication.*

*The package contains all prerequisites needed as a single PyPI project, which can be installed from the python online repository using PIP. This makes it easy to install and update, while also providing you with full access to the source code if you want to make changes or additions.*

*QuarchPy can also communicate to the device via QIS (Quarch Instrument Server), QPS (Quarch Power Studio), or simply using Python scripts.  Both QIS and QPS are included with the QuarchPy Package - they are ready to use (Java and drivers may also be needed).*


Change Log
----------


2.1.7
-----
- New QPS v1.27
- New QIS v1.32

2.1.6
-----
- New QPS v1.26
- New QIS v1.31

2.1.5
-----
- New QPS v1.24

2.1.4
-----
- New QPS v1.23
- New QIS v1.29

2.1.3
-----
- New QPS v1.22
- modules on the network can now be connected to using conType:QTLNumber eg. TCP:QTL1999-02-001. 
- fixed QIS not closing with QPS when launch with by QPS
- closeConnection added to QIS api
- display table formats multiline items and handles empty cells

2.1.2
-----
- QPS v1.20
- QIS v1.19

2.1.1
-----
- Seperation of QIS module scan and QIS select device
- Added getQuarchDevice which is a wrapper around quarchDevice that allows connections to sub-devices in array controllers over all connection types
- Version compare updated to use __version__ rather than pkg_resources
- Seperated the SystenTest (debug_info) into seperate parts with flags to allow the user to skip certain parts. This allows the test to be run without user interaction of selecting a module.


2.1.0
-----
- logging improvements
- usb locked devices fix for CentOS, Ubuntu, and Fedora

2.0.22
------
- Calibration and QCS removed from quarchpy and are not in their own packages
- New command "python -m quarchpy.run debug -usbfix" sets USB rules to fix quarch modules appearing as locked devices on Linux OS

2.0.21
------
- new QIS v1.23

2.0.20
------
- New modules added to calibration, wiring prompt added, logging improvements
- Fixes for PAM streaming using QIS
- Added Quarchpy.run list_drives 
- Improved communication for connection_QPS
- Improved QCS debugging
- Reworked QCS drive detection for upcoming custom drive detection
- "quarchpy.run list_drives" command added


2.0.19
------
- QPS v1.17
- Quarchpy run terminal runs the simple python terminal to talk to modules
- Scan Specific IP address for Quarch module via QIS/QPS added
- Updated performance class for new QCS tests
- Fixed Centos QCS drive selection bug
- Improved QCS connection classes
- Improved features for QCS 
- Minor bug fixes

2.0.18
------
- QPS 1.13
- Iomenter drive location bugfix
- Units added to stats export from QPS
- Changed QCS tests to work off of a python format
- Updated drive detection in QCS
- Updated communication to TLS 

2.0.16
------
- QPS 1.11

2.0.15
------
- QIS v1.19.03 and QPS 1.10.12
- Updated debug info test
- Snapshots and stats from QPS functions added
- Calibration updates

2.0.14
------
- QPS annotations through quarchpy improvements

2.0.13
------
- Python2 bug fixes 
- UI tidy up
- New custom annotations and comments QPS API

2.0.12
------
- Fixed issue with array module scan over UDP outside of subnet
- Bug fix for HD connection via USB in linux
- Added headless launch of QIS
- Added Shinx auto documentation
- Fixed issue with USB command response timeout in longer QCS tests
- Fixed issue where UDP locate parser was using the legacy header, not the quarch fields
- Improved qurchpy.run oarsing and help generation
- Fixed syntax warnings for string literal comparisons
- Calibration wait for specific module uptime and report file updates

2.0.11
------
- Improved list selection for devices
- Fixed bug when scanning for devices within an Array
- Module detection fixes for QCS and PAM/Rev-B HD
- Clean up of calibration switchbox code and user logging

2.0.10
------
- QCS server logging cleaned up
- Additional platform tests added to debug_info test
- Cleaned up print() statements and replaced with logging calls
- Help message added to quarchpy.run command
- Module detection fixes for QCS
- Improved calibration prompts
- Added initial calibration stubs for the PAM
- QCS improvements to linux drive enumeration tests

2.0.9
-----
- Significant QCS additions including power testing
- Added remote switchbox to calibration utility
- Various minor bug fixes and improvements to calibration utility

2.0.8
-----
- Added readme.md for PyPi description
- Fixed bug in QIS when checking if QIS is running
- Various minor additions for QCS

2.0.7
-----
- Changes since 2.0.2
- Minor bug fixes
- Calibration Changes
- QIS folder gone, QIS now in QPS only
- Run package added
- Update quarchpy added
- SystemTest improvements
- UI changes, input validation, smart port select

2.0.2 
-----
- UI Package added 
- Connection over TCP for python added
- Logging on devices
- Drive test core added

2.0.0
-----
- Major folder restructure
- Added test center support
- Detected streaming devices
- Added latest qps1.09 and qis
- Minor bug fixes

1.8.0
-----

- Tab to white space convert
- Updated __init__ file to co-allign with python practices
- Updated project structure 
- Added documents for changes and Script Locations
- Disk selection update
- Compatibility with Python 3 and Linux Improved!

1.7.6
-----

- Fixes bug with usb connection

1.7.5
-----
- Fixed USB DLL Compatibility 
- Fixed potential path issues with Qis and Qps open

1.7.4
-----

- Updated to QPS 1.08

1.7.3
-----

- Additional Bug Fixes

1.7.2
-----

- Bug fixing timings for QIS (LINUX + WINDOWS)

1.7.1
-----

- Updated FIO for use with Linux and to allow arguments without values 
- Fixes path problem on Linux
- Fixes FIO on Linux

1.7.0
-----

- Improved compatability with Windows and Ubuntu 

1.6.1
------

- Updating USB Scan
- Adding functionality to specify OS bit architecture (windows)

1.6.0
-----
- custom $scan IP
- fixes QIS detection
- implements custom separator for stream files
- Bug fix - QIS Load

1.5.4
-----

- Updating README and LICENSE

1.5.2
-----

- Bug Fix - Case sensitivity issue with devices 

1.5.1
-----

- Additional Bug Fixes

1.5.0
-----

- Integration with FIO 
- Additional QPS functionality
- Added device search timeout

1.4.1
-----

- Fixed the wmi error when importing quarchpy.

1.4.0
---

- Integration with QPS
- supports Iometer testing
- Additional fixes for wait times

1.3.4
-----

- Implemented resampling and a better way to launch QIS from the script.

1.3.3
-----

- Implements isQisRunning
- Implements qisInterface
- Changes startLocalQIS to startLocalQis
- Fixes a bug in QIS interface listDevices that didn't allow it to work with Python 3

1.3.2
-----

- Bug Fix running QIS locally

1.3.1
-----

- Implements startLocalQIS
- Packs QIS v1.6 - fixes the bugs with QIS >v1.6 and multiple modules
- Updates quarchPPM (connection_specific)
- Compatible with x6 PPM QIS stream.

1.2.0
-----

- Changes to object model
