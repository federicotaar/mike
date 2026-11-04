# Safety model

Mike is an agent that can act, so the rules it cannot break live in code the
user owns - not in a prompt the model can talk its way around.

## Always ask first

`agent/guardrails.py` lists the actions that need an explicit yes through
the approvals inbox, every time:

- `send_message` - texting or emailing anyone as the user
- `spend` - any payment, purchase, booking, or credits
- `post_public` - posting anything publicly
- `grant_permission` - new accounts, scopes, or access
- `delete_data` - removing memories, files, or messages

There is no "remember my yes" for these. Each action asks again.

## The user can inspect and undo

- **Memory** is a plain SQLite database. The app shows what Mike knows, and
  the user can correct it (old entries stay in history, superseded) or
  delete it for good (`DELETE /memories/{id}`).
- **Activity log** records everything Mike does; it cannot erase it.
- **Stop button** pauses the agent immediately (`POST /stop`); chat then
  answers honestly that Mike is paused.

## Self-improvement is disabled until it is safe

`agent/selfedit.py` refuses to execute, unconditionally, until a real
isolated sandbox exists. Model-generated code never runs on the user's
machine with the server's network access and secrets. `guardrails.py` is on
the protected list: the self-edit loop may never change its own rules.

## Provider discipline

Mike uses exactly one inference provider, chosen and approved by the user.
When a free quota is spent, Mike says so and stops. It never moves the
user's data to another provider, never upgrades a plan, never falls back to
anything paid.

## Platform honesty

iOS does not allow an always-running agent. Mike's proactivity is scheduled
local notifications and speaking first on reopen - the app says this plainly
instead of pretending otherwise.
