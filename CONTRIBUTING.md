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
- QUICK_START.md (if it improves onboarding), or
- The relevant function/class docstring (Google style), or
- The Issue / PR description as a temporary reference.

Do not create an `examples/` folder unless there is a future consensus to introduce it.

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
- Anything commonly imported from `quarchpy.*` by users should be treated as public.

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
```
fix(power): correct margining voltage selection
feat(discovery): add LAN retry logic
docs(contributing): clarify API stability
```

Before opening a PR:
- Link the Issue (`Closes #<number>` if appropriate).
- Brief WHAT and WHY.
- Note any impact on public API (additive / deprecation / none).
- Avoid unrelated changes in the same PR.

Informal PR checklist:
- Code runs locally.
- No stray debug prints.
- Docs (README / QUICK_START.md / docstrings) updated if behavior or API changed.
- Scope is clear.

---

## 8. Error Handling & Logging

- Use `logging` internally; reserve `print()` for QUICK_START or manual scripts.
- Catch specific exceptions where feasible.
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

---

## 10. Adding Commands / Device Behaviors

Wrapper functions around `sendCommand()` should not be added without clear justification.

Required justification (via Issue or PR description):
- What problem does the wrapper solve?
- Why can’t users directly call `sendCommand()`?
- Does it add validation, safety, or multi-step convenience?
- Any timing or sequencing guarantees?

In the wrapper’s docstring:
- State the higher-level intent (e.g. “Convenience method to margin voltage safely.”)
- Mention underlying device commands if helpful (`Sig:<rail>:Volt`, etc.).
- Do not hide critical timing requirements—document them.

Avoid:
- Wrappers that only rename a single `sendCommand()` call.
- Abstractions that obscure error conditions or device states.

---

## 11. Documentation

If users need to know about a change:
- Update `README.md`.
- Update QUICK_START.md for improved onboarding.
- Add usage notes directly in docstrings (preferred over creating an examples directory).
- Mark deprecated APIs clearly in docstrings (and optionally in README if widely used).

---

## 12. Release & Versioning (Lightweight)

No formal changelog yet.
- Avoid breaking changes.
- Use deprecation rather than removal.
- Group related changes logically.

---

## 13. Security / Sensitive Info

Do not commit:
- Credentials / tokens
- Proprietary hardware dumps
- Internal identifiers not meant for public distribution

Report possible security issues privately (not in a public Issue with details).

---

## 14. Getting Help

- Open an Issue with `[question]` if unsure.
- Provide command sequences and responses for device errors.
- Include logging output when diagnosing connection problems.
- You can also drop us an email: support@quarch.com

---

## 15. Quick Flow

```
Issue → Branch → Change → (Optional doc updates) → Commit → PR → Review → Merge
```

Keep changes small, backward-compatible, and documented.

---

Thank you for contributing to QuarchPy!
