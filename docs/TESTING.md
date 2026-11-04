# Testing

## Python core

```bash
pip install -r requirements-dev.txt
python -m pytest tests -q
```

The suite covers the app's contract with the core:

- `test_api.py` - endpoint shapes, approval lifecycle, token auth, pause
  behavior, honest failure replies, input validation
- `test_memory.py` - remember/recall/correct/forget, approvals, activity,
  pruning, kind validation
- `test_brain.py` - fail-closed provider behavior
- `test_config.py` - defensive env parsing
- `test_notify.py` - push no-op without a topic
- `test_guardrails.py` - sensitive actions always ask first
- `test_selfedit.py` - self-edit execution refuses in every environment
- `test_dbpath.py` - regression: repo-local default DB path

`python-tests.yml` runs this suite in CI on every backend change.

## iOS app

- `ios/SelfTest/main.swift` + `runtime-smoke.yml` - headless runtime smoke
  checks on a simulator
- `ios/UITest/*.yaml` - maestro flows (keyboard, notifications, proactive
  greeting) run by `keyboard-uitest.yml`, `notif-smoke.yml`
- `sim-screenshots.yml` - automated UI captures used as visual evidence
- `build-ipa.yml` - produces the signed `Mike-iPhone.ipa` release artifact

Known unverified area: on-device model memory/performance on a physical
iPhone 13 (simulator runs pass; device testing is tracked in the README).
