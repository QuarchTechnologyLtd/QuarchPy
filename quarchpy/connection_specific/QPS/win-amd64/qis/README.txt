qis 1.47

Copyright Quarch Technology Limited 2025.

Warning and Disclaimer
======================

qis:

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.


Overview
========

	qis greatly simplifies the task of interfacing user scripts to the PPM. All time dependent code and 
	data decoding is hidden behind a TCP/IP server interface supporting both REST and raw TCP protocols.
	In addition, the live stream data passes through an internal intermediary buffer further simplifying
	the timing requirements of any interfacing scripts.
	
	See help.txt for more information.
	
Dependencies
============

qis uses:

usb4java v1.3 for USB communication with Quarch PPMs, usb4java 1.3 is licensed under LGPL V3.0
Netty for Ethernet services, Netty v4.1.43 distributed under Apache License 2.0

See directory License for additional information.

Installation
============

Unpack qis to a local directory.

Start qis by running "qis.bat" on Windows or "./qis.sh" on Linux (check execute permissions if it doesn't run), or simply by running "java -jar qis.jar"

