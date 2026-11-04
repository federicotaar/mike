# Safety and current limits

## Implemented boundaries

- Groq-mode phone tools allow time and memory lookup without approval.
  Saving a memory or scheduling a reminder queues a local approval first.
- The Python core has a separate approval queue. Approving an entry records
  a decision; it does not execute a message, purchase, or public post.
- Money, messages, public posts and new account permissions are not tools
  currently available to Mike. `guardrails.py` lists sensitive action names,
  but that list is not a complete enforcement layer for future tools.
- Self-edit execution unconditionally refuses to run. No model-generated
  code is executed by the core. Isolation and user-reviewed merging are planned.
- Keys and backend tokens use the iPhone Keychain. Backend connections
  require HTTPS and refuse cross-host redirects.

## Data ownership

The phone keeps its own JSON memory and activity files. The optional core
uses a separate SQLite database. They are not synced. The core provides a
memory deletion endpoint; an in-app memory editor is not implemented.
Activity is an ordinary local record, not a tamper-proof audit log.

The backend stop endpoint pauses backend chat. It does not cancel phone
notifications or stop the phone's direct Groq/on-device provider. iOS local
notifications and speaking on reopen are limited proactivity, not an
always-running agent. Physical iPhone model performance is still unverified.

## Provider and cost limits

No provider fallback or plan upgrade is performed. Use only the free-tier
account you choose. Availability and quota are controlled by the provider;
Mike cannot guarantee a model remains free or available forever.
