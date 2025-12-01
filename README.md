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

### Quickstart

- Quickstart: See [QUICKSTART](./QUICK_START.md)

## Usage

Below are common workflows. API names may differ slightly depending on your installed version.

### Device Discovery

```python
from quarchpy.device import scanDevices

# Scan for quarch devices over all connection types (USB, Serial and LAN)
print("Scanning for devices...\n")
deviceList = scanDevices('all', favouriteOnly=False)
```

Supported connection types:
- USB
- LAN (TCP | REST)
- Serial

### Connecting to a Module

```python

```

