# QuarchPy

QuarchPy is a Python API for the automation of Quarch hardware modules and software. It enables robust, scriptable control over Quarch modules, making it straightforward to build reproducible test and automation workflows.

- Project repo: [QuarchTechnologyLtd/QuarchPy](https://github.com/QuarchTechnologyLtd/QuarchPy)
- License: See [LICENSE](./quarchpy/LICENSE.rst)

## Table of Contents

- [Features](#features)
- [Getting Started](#getting-started)
  - [Requirements](#requirements)
  - [Installation](#installation)
- [Application Notes](#application-notes)
- [Contributing](#contributing)
- [Support](#support)

## Features

- High-level Python interface to Quarch modules and software.
- Device discovery and connection via common transports (USB, TCP/IP/LAN, serial).
- Acquisition of measurements (voltage, current, power), streaming and logging.
- Scripting-friendly design.
- Structured error handling and timeouts for robust automation.
- Cross-platform support (Windows, Linux; macOS where supported by drivers).

## Getting Started

### Requirements

- Python 3.8+
- Access to Quarch modules
- Appropriate drivers or connectivity (USB, LAN, or serial) as required by your hardware
- Network or OS permissions to access the device

### Installation

Install the package from PyPI (if published):

```bash
pip install quarchpy
```

Or install from source:

```bash
git clone https://github.com/QuarchTechnologyLtd/QuarchPy.git
cd QuarchPy
pip install -e .
```

## Application Notes

For worked examples and detailed guides, check out our GitHub Application Notes repository:

- [Quarch Application Notes GitHub](https://github.com/QuarchTechnologyLtd/quarchpy-appnotes)

**Getting Started:**  
We recommend beginning with  
[AN-006 Python Control of Quarch Modules](https://github.com/QuarchTechnologyLtd/quarchpy-appnotes/tree/main/Application_Notes/AN-006_Python_Control_of_Quarch_Modules)  
which provides step-by-step instructions and sample Python code for controlling Quarch modules.

These resources will help you set up and script Quarch hardware with Python quickly and effectively.

## Contributing

Contributions are welcome! Please:
- Open an issue describing the problem or requested feature.
- Discuss design via issues or pull requests.
- Follow existing code style and add tests where applicable.
- Ensure changes are documented in this README or docstrings.
- See [CONTRIBUTING](./CONTRIBUTING.md)

## Support

- For hardware setup and official documentation, contact Quarch Technology or visit official product docs.
- For bugs or feature requests in this library, open an issue on the GitHub repository.
- For commercial support, reach out to Quarch via your support contract or sales contact.

---

© Quarch Technology Ltd. All rights reserved.
