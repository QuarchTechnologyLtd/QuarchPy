# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

QuarchPy is Quarch Technology's Python API for automating Quarch hardware modules (power modules, cable pull modules, switch modules, etc.) and Quarch's own software (QPS and QIS, see below). Distributed on PyPI as `quarchpy`.

## Commands

```bash
# Editable install for development
pip install -e .

# Install dev/test tools
pip install -r .github/workflows/requirements-dev.txt   # pytest, coverage, flake8 (+ prod requirements)

# Run the full test suite (mirrors CI)
coverage run -m pytest
coverage report

# Run a single test file / test
pytest tests/test_device/test_scanDevices.py
pytest tests/test_device/test_scanDevices.py::test_scan_devices

# Build check (matches CI "Verify Build" step)
python setup.py bdist_wheel --universal
```

There is no lint step enabled in CI currently (flake8 invocations in `.github/workflows/test.yml` are commented out). Tests are minimal (`tests/test_device/`) — most tests require physical Quarch hardware or a running QPS/QIS instance to be meaningful, so many are skip/pass-through when no device is present (see `test_scan_devices`, which passes if either a QTL device is found or none are found at all).

CI (`.github/workflows/test.yml`) runs the matrix across Python 3.7–3.13 on `ubuntu-22.04`. `Development` is the working branch; pushes to `DevRelease`/`Release` trigger PyPI/TestPyPI publishing.

## Architecture

### Import wiring is non-standard — read before adding new modules

`quarchpy/__init__.py` inserts several subpackage directories directly onto `sys.path` (`connection_specific`, `connection_specific/serial`, `connection_specific/QIS`, `connection_specific/usb_libs`, `config_files`, and the package root itself) before importing anything. Because of this, some internal modules import each other with bare top-level names (e.g. `from debug.versionCompare import ...`, `from device import quarchDevice`) rather than relative/`quarchpy.`-qualified imports, while others (newer code, e.g. `device/device.py`) use fully-qualified `from quarchpy.qis import ...` style. When adding new cross-module imports, check how the *specific file you're editing* already imports its neighbors and match that style rather than assuming one convention applies package-wide.

The public API surface is defined by what's re-exported in `quarchpy/__init__.py` and `quarchpy/device/__init__.py`. Per `CONTRIBUTING.md`, anything importable from `quarchpy/__init__.py` is treated as public API and is subject to the backwards-compatibility rules below.

### Connection layering

- **`quarchpy/connection.py`** — thin dispatcher that picks a low-level connection implementation based on a connection string prefix (`USB:`, `SERIAL:`, `TCP:`, `TELNET:`, `REST:`) and wraps it in `PYConnection`. Also defines `QISConnection`/`QPSConnection`, which wrap `QisInterface`/`QpsInterface` instead of talking to hardware directly.
- **`quarchpy/connection_specific/`** — one module per transport (`connection_USB.py`, `connection_Serial.py`, `connection_TCP.py`, `connection_Telnet.py`, `connection_ReST.py`), plus `connection_QIS.py` / `connection_QPS.py` (the protocol clients for Quarch's own server processes) and `mDNS.py` for LAN device discovery. `usb_libs/` and `serial/` hold vendored/platform-specific driver bits (32/64-bit USB libs); `jdk_jres/` bundles JDK/JRE handling used to launch QPS/QIS (Java-based).
- **`quarchpy/device/device.py`** — `quarchDevice` is the core class all device control goes through. It picks `ConType` ("PY", "QIS", or "QPS") and constructs the matching connection object from `connection.py`. `quarchPPM` (`device/quarchPPM.py`) and `quarchQPS` (`device/quarchQPS.py`) subclass `quarchDevice` for power-module- and QPS-streaming-specific behavior respectively; `quarchArray`/`subDevice` (`device/quarchArray.py`) model array controllers with attached sub-modules.
- **`quarchpy/device/scanDevices.py`** — device discovery across USB/LAN/serial, returns a dict of `{module_name: connection_string}`.

### QIS and QPS — Quarch's server processes

QIS and QPS are separate Java-based server applications Quarch ships as binaries (via the `quarchpy-binaries` PyPI package, fetched/managed by `quarchpy/install_qps.py`). QuarchPy can launch them locally and talk to them over a socket protocol:

- **`quarchpy/qis/qisFuncs.py`** — start/stop/check a local QIS instance (`startLocalQis`, `isQisRunning`, `closeQis`), plus module selection helpers. `connection_specific/connection_QIS.py` is the actual client protocol implementation.
- **`quarchpy/qps/qpsFuncs.py`** — same pattern for QPS (`startLocalQps`, `isQpsRunning`, `closeQps`). QPS is the higher-level streaming/measurement application; QIS is the lower-level instrument server.
- If QPS binaries are missing at launch time, QuarchPy auto-installs them (see README) via `install_qps.py`.

### Other notable areas

- **`quarchpy/disk_test/`**, **`quarchpy/fio/`**, **`quarchpy/iometer/`** — integrations for driving disk I/O benchmarking tools (fio, IOMeter) alongside Quarch power-cycling/fault-injection during tests.
- **`quarchpy/user_interface/`** — shared CLI/dialog helpers (`printText`, `requestDialog`, module-selection prompts) used across the scanning/QIS/QPS modules for interactive scripts.
- **`quarchpy/utilities/`** — standalone helpers: `BitManipulation.py`, `TimeValue.py`, `Version.py`, `TestCenter.py`.
- **`quarchpy/config_files/`** — `.qfg` device config files organized by module family (Cable_Modules, Switch_Modules, Power_Margining, Drive_Modules, Card_Modules), loaded at runtime by device code. Note: `config_files/Cable_Modules/.svn/` is a leftover Subversion working-copy directory, not part of the package — ignore it.
- **`quarchpy/debug/`** — diagnostic entry points (`SystemTest.py`, `module_debug.py`, `simple_terminal.py`, `upgrade_quarchpy.py`) and `versionCompare.py`, used both internally and as user-facing debug utilities (`python -m quarchpy.debug`).

### Logging

`quarchpy/__init__.py` sets up a package-wide `"quarchpy"` logger with a rotating file handler at `~/.quarchpy/quarchpy.log` (always DEBUG) and a console handler that dynamically mirrors the root logger's level via `SyncWithRootFilter`. Use `logging.getLogger(__name__)` in new modules rather than `print()` — `print()` is reserved for user-facing scripts, not library code (see `CONTRIBUTING.md` §8). Call `quarchpy.configure_logging(...)` to override console/file levels or the file path at runtime.

## Contribution conventions (from CONTRIBUTING.md)

- **Backwards compatibility is a priority.** Prefer additive changes (new optional params/functions) over modifying existing signatures/return types. If a public function must change, add a new one and deprecate the old one in its docstring (`Deprecated: use new_function(); will be removed in a future release.`) rather than removing it outright.
- **Docstrings are Google style** and required for public functions/classes — state purpose, args, returns, and any side effects/timing requirements.
- New device/QPS/QIS command wrappers must add real value (validation, convenience, safety) over the raw command — not be trivial renames — and should explain their purpose in the docstring and PR description.
- Commit style: `<type>(<area>): <description>`, e.g. `bug fix (stream processing): fix bug where stream would fail when xxx`, `feature(device discovery): add LAN retry logic`.
