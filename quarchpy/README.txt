QuarchPy

Please refer to https://quarch.com/products/quarchpy-python-package to more details and support. 

INSTALLATION 

- MANUAL (.WHL FILE)
	1) Download the file from https://pypi.org/manage/project/quarchpy/releases/ 
	2) Open a terminal (linux/MacOS) or cmd prompt (Windows) and navigate to the file location.
	
	3) Run:

		pip install file_name.whl
	or
		python -m pip install file_name.whl


- AUTOMATIC (PIP) 
	- First time installs:
     		pip install quarchpy
     	or
     		python -m pip install quarchpy

  
	- Specific version:
		pip install quarchpy==version
	or
		python -m pip install quarchpy==version


	- Latest version
		pip install quarchpy --upgrade
	or
		python -m pip install quarchpy --upgrade

REQUIREMENTS
- QIS and QPS functions require Java 8.x

CONTENTS
- API for controlling Quarch modules via USB, Serial, Telnet and HTTP/ReST
- Automation controls for Quarch Power Modules via QIS and QPS (Requires Java)