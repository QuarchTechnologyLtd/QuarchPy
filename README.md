# QuarchPy

QuarchPy is a Python API for the automation of Quarch hardware modules and software. It enables robust, scriptable control over Quarch modules, making it straightforward to build reproducible test workflows, integrate with CI systems, and collect measurement data programmatically.

- Project repo: [QuarchTechnologyLtd/QuarchPy](https://github.com/QuarchTechnologyLtd/QuarchPy)
- License: See [LICENSE](./quarchpy/LICENSE.rst)

## Table of Contents

- [Features](#features)
- [Getting Started](#getting-started)
  - [Requirements](#requirements)
  - [Installation](#installation)
  - [Quick Start](#quick-start)
- [Usage](#usage)
  - [Device Discovery](#device-discovery)
  - [Connecting to a Module](#connecting-to-a-module)
  - [Basic Control](#basic-control)
  - [Measurements and Data Capture](#measurements-and-data-capture)
  - [Error Handling](#error-handling)
- [Configuration](#configuration)
- [Examples](#examples)
  - [Power Cycle a DUT and Measure Inrush](#power-cycle-a-dut-and-measure-inrush)
  - [Automate a Test Sequence](#automate-a-test-sequence)
- [CLI (if available)](#cli-if-available)
- [Best Practices](#best-practices)
- [Contributing](#contributing)
- [Support](#support)

## Features

- High-level Python interface to Quarch modules and software.
- Device discovery and connection via common transports (USB, TCP/IP/LAN, serial).
- Control of outputs and channels (enable/disable power rails, set profiles, triggers).
- Acquisition of measurements (voltage, current, power), streaming and logging.
- Scripting-friendly design to integrate with test frameworks (pytest, nose, CI).
- Structured error handling and timeouts for robust automation.
- Cross-platform support (Windows, Linux; macOS where supported by drivers).
- Extensible: add support for additional module types and commands.

## Getting Started

### Requirements

- Python 3.8+
- Access to Quarch modules or emulator
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
