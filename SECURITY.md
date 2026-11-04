# Security Policy

## Reporting a vulnerability

Do not open a public issue for security problems. Use GitHub's private
vulnerability reporting on this repository ("Security" tab, "Report a
vulnerability"). You will get a response as soon as possible; this is a
solo-maintainer project.

## Scope that matters most

- The core's bearer-token auth (`MIKE_TOKEN`) and loopback-only default
- Keychain storage of the Groq key and backend token in the iOS app
- The approvals/guardrails flow (`agent/guardrails.py`)
- The disabled self-edit loop (`agent/selfedit.py`) - if you find a path
  that executes model-generated code, that is a critical report

## Supported versions

Only the latest release (see `VERSION`) receives fixes.
