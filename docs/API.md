# Core HTTP API

The iPhone app's "Your own backend" mode talks to these endpoints. Base URL
is wherever the user runs the core (default `http://127.0.0.1:8787`).

## Authentication

Every endpoint requires `Authorization: Bearer $MIKE_TOKEN` once
`MIKE_TOKEN` is set in `.env`. With no token set, the core is expected on
loopback only - never expose it on a network without a token.

## Endpoints

### `GET /status`

```json
{
  "providerConfigured": true,
  "quotaRemainingToday": null,
  "paused": false,
  "version": "0.4.3"
}
```

`quotaRemainingToday` is honestly `null`: the provider's remaining free quota
cannot be read, so Mike does not guess it. `/status` also returns
`requestsSentToday` (requests Mike itself counted today) and `localDailyCap`
(the optional cap from `MIKE_LOCAL_DAILY_CAP`, `0` meaning no cap).

### `POST /chat`

Body: `{"message": "..."}` (must be non-empty, else 422).
Replies: `{"reply": "..."}`. When paused, out of quota, without an approved
key, or when the network fails, the reply says so in plain language instead
of an error code.

### `POST /feedback`

Body: `{"text": "..."}` (non-empty). Stores a correction as memory.

### `GET /approvals/pending`

Pending approvals, oldest first:
`[{"id", "summary", "detail", "createdAt", "status"}]`.

### `GET /approvals`

Full decision history (pending, approved, denied), newest first.

### `POST /approvals/{id}`

Body: `{"approve": true|false}`. Deciding an already-decided or unknown
approval returns a real 404.

### `DELETE /memories/{id}`

Deletes a memory for good. Unknown id returns a real 404.

### `GET /activity`

Recent activity: `[{"id", "kind", "summary", "time"}]`.

### `POST /stop`, `POST /start`

Pause and resume the agent.
