# Contributing to QuarchPy 

Thanks for your interest in QuarchPy. This project provides a Python API for automating Quarch hardware and software. This guide gives you just enough direction to make helpful, focused contributions without unnecessary overhead.

---

## 1. Talk First (Issues)

Before starting anything non-trivial:
- Open an Issue describing the bug, improvement, or feature.
- Include: connection type (USB / LAN / Serial), OS, Python version, module type.
- For bugs: minimal script + actual vs expected behavior + relevant command responses.
- For potential public API changes: explain why existing APIs are insufficient.

Trivial edits (typos, very small doc tweaks) can go straight to a PR, but linking an Issue is still appreciated.

---

## 2. Getting Set Up

```bash
# 1. Download the source code from the repository
git clone https://github.com/QuarchTechnologyLtd/QuarchPy.git

# 2. Move into the project directory
cd QuarchPy

# 3. Create a fresh virtual environment to isolate dependencies
python -m venv .venv

# 4. Activate the virtual environment
source .venv/bin/activate        # Linux / macOS
# .venv\Scripts\activate         # Windows (Run this instead if on Windows)

# 5. Install the package in "Editable" mode
# This allows you to modify code and see changes immediately without reinstalling
pip install -e .

# 6. (Optional) Install the testing framework for future development
pip install pytest
```

Enable logging when investigating issues:

```python
import logging
logging.basicConfig(filename="quarch_debug.log", level=logging.DEBUG)
```

Attach the log file in bug reports if helpful.

---

## 3. Project Structure (Current vs Planned)

Current: the `quarchpy` package.

Planned (longer-term, subject to discussion):
```
quarchpy/        # Core library
tests/           # Pytest-based tests (not utilised yet)
docs/            # Additional markdown/app notes 
```

We are NOT using an `examples/` directory for now. If you have a helpful usage snippet, add it to:
- The relevant function/class docstring (Google style), or
- The Issue / PR description as a temporary reference.

---

## 4. Making Changes

1. Create a branch:
   ```
   git checkout -b feat/<short-description>
   # or fix/<short-description>, docs/<short-description>
   ```
2. Keep changes focused—avoid large refactors mixed with features.
3. Use clear names and f-strings (`f"Device {serial} failed"`).
4. Keep functions small and purposeful.

---

## 5. Public API Stability (Backwards Compatibility)

We aim to keep backwards compatibility.

Guidelines:
- Prefer additive changes (new optional params, helper functions).
- Avoid changing existing function signatures or return types.
- If change is unavoidable, add a new API alongside the old one and mark the old one deprecated in its docstring.
- Deprecation docstring suggestion:
  ```
  Deprecated: use new_function(); will be removed in a future release.
  ```
- Do not remove or rename public functions without:
  1. An Issue explaining the rationale.
  2. A deprecation period (at least one tagged release).
- Anything commonly imported in quarchpyt/init.py should be treated as public."

---

## 6. Testing (None Yet)

There is currently no test suite and no agreed strategy.

If you believe tests should accompany your change:
- Open an Issue first to discuss scope and approach.
- Keep any initial test additions minimal.
- Do not introduce large frameworks without agreement.

Until a direction is chosen, you are not required to add tests.

---

## 7. Commit Messages & Pull Requests

Commit style (concise and purposeful):
When making a commit, state the type of work done eg. bug fix, feature add, document improvement, etc...
State the area in which the work effects eg, streaming, device connection, QPS/QIS API, data processing, etc...
```
bug fix (stream processing): fix bug where stream would fail when xxx
feature(device discovery): add LAN retry logic
docs(contributing): clarify API cmd usage
```

Before opening a PR:
- Link the Issue (`Closes #<number>` if appropriate).
- Brief WHAT and WHY.
- Note any impact on public API (additive / deprecation / none).
- Avoid unrelated changes in the same PR.

Informal PR checklist:
- Code runs locally.
- No stray debug prints.
- Docs (README / docstrings) updated if behavior or API changed.
- Scope is clear.

---

## 8. Error Handling & Logging

- Use `logging` internally; reserve `print()` for User level scripts not API.
- Catch specific exceptions, not generic exceptions where feasible.
- Include command/context when raising or wrapping errors.

---

## 9. Style Touchpoints

- Follow PEP 8 generally; readability first.
- Docstrings MUST use Google style. Example:

  ```python
  def set_voltage(device, channel, millivolts):
      """Set the voltage of a channel.

      Args:
          device: Connected Quarch device instance.
          channel (str): Channel name (e.g. "12V", "3v3").
          millivolts (int): Target voltage in millivolts.

      Returns:
          str: Raw device response.

      Raises:
          ValueError: If millivolts is outside allowed range.
      """
      ...
  ```

- Keep docstrings explicit about intent and any side effects.
- Centralize repeated literal command strings if reused.
- Avoid large formatting-only PRs without discussion.

## 10. Adding Commands / Device Behaviors

If a wrapper function does not exist for a given QPS, QIS, or device command, contributors may add one. This enables immediate use of new features or commands added to the QPS CLI or device firmware.

When adding a wrapper, you **must provide**:

- **Purpose**: Explain what higher-level need the wrapper serves.
- **Documentation**: Include a clear docstring stating the wrapper’s intent, and mention relevant underlying commands or timing/sequencing requirements.
- **Justification**: In your pull request or issue description, state why the wrapper is needed, what problem it solves, and its added value (validation, convenience, safety, etc).

Wrappers should not be trivial renames—they should add convenience, validation, or clarity beyond the underlying command.

You may call device commands directly in user scripts if preferred, but wrappers are recommended for any reusable, higher-level functionality.

---

## 11. Documentation

If users need to know about a change:
- Update `README.md`.
- Add usage notes directly in docstrings (preferred over creating an examples directory).
- Mark deprecated APIs clearly in docstrings (and optionally in README if widely used).

---

## 12. Security / Sensitive Info

Do not commit:
- Credentials / tokens
- Proprietary hardware dumps
- Internal identifiers not meant for public distribution

Report possible security issues privately (not in a public Issue with details) please contact us at support@quarch.com.

---

## 13. Getting Help

- Open an Issue with `[question]` if unsure.
- Provide command sequences and responses for device errors.
- Include logging output when diagnosing connection problems.
- You can also drop us an email: support@quarch.com

---

## 14. Quick Flow

```
Issue → Branch → Change → Doc updates( If required) → Commit to branch → Pull Request → Quarch Code Review → Merge/Reject
```

Keep changes small, backward-compatible, and documented.

---

Thank you for contributing to QuarchPy!
