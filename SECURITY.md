# Security Policy

## Reporting a vulnerability

Do not post secrets, private user data, or exploit details in a public issue.
If the Security tab offers "Report a vulnerability", use that private route.
Otherwise, open an issue containing only a request for a private reporting
channel, with no vulnerability details. Private reporting availability and
response timing are not guaranteed.

## Scope that matters most

- The core's bearer-token auth (`MIKE_TOKEN`) and loopback-only default
- Keychain storage of the Groq key and backend token in the iOS app
- The approvals/guardrails flow (`agent/guardrails.py`)
- The disabled self-edit loop (`agent/selfedit.py`) - if you find a path
  that executes model-generated code, that is a critical report

## Supported versions

Only the latest release (see `VERSION`) receives fixes.
