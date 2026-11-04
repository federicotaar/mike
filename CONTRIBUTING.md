# Contributing

Mike is a personal project, but issues and well-scoped pull requests are
welcome.

## Ground rules

1. **Free only.** No paid APIs, no paid fallbacks. Usage limits are fine;
   moving the user's data to a paid provider is not.
2. **Honesty over polish.** If something does not work, the code and the
   README say so. Never fake a capability.
3. **Guardrails are untouchable by automation.** Changes to
   `agent/guardrails.py` get extra scrutiny and are never made by the
   agent itself.
4. **Tests are the contract.** `python -m pytest tests` must stay green;
   add coverage for behavior you change.

## Workflow

- Python: 4-space indent, type hints, `from __future__ import annotations`.
- Swift: SwiftUI, iOS 17+, 4-space indent.
- Commit messages: short imperative summary (`memory: add forget()`).
- Version bumps: edit `VERSION`; releases are tagged from it by CI and
  existing releases are never overwritten.
