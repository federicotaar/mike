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
  "requestsSentToday": 0,
  "localDailyCap": 0,
  "paused": false,
  "version": "0.4.4-preview.1",
  "uptimeSeconds": 3721,
  "memoryCount": 12
}
```

`quotaRemainingToday` is honestly `null`: the provider's remaining free quota
cannot be read, so Mike does not guess it. `uptimeSeconds` is measured from
the core's process start. `/status` also returns
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

### `GET /approvals/{id}`

One approval in any status, for a detail view. Unknown id returns a real 404.

### `POST /approvals/{id}`

Body: `{"approve": true|false}`. Deciding an already-decided or unknown
approval returns a real 404.

### `GET /memories`

Active memories, newest first: `[{"id", "kind", "text"}]`. Optional
`limit` (1-500, default 50) and `kind` (`preference`, `fact` or `feedback`).

### `GET /memories/search?q=...`

Case-insensitive substring search over active memories, newest first:
`[{"id", "kind", "text"}]`. A blank `q` returns a real 400. Optional
`kind` restricts the search to one memory kind.

### `GET /memories/export`

Portable backup of every active memory with creation times:
`[{"id", "kind", "text", "createdAt"}]`. Superseded memories are excluded.

### `POST /memories/{id}`

Body: `{"text": "..."}` (non-empty). Corrects a memory: the old text stays
as history, the new text becomes the active one. Returns
`{"corrected": true, "newId": "..."}`. Unknown id returns a real 404.

### `DELETE /memories/{id}`

Deletes a memory for good. Unknown id returns a real 404.

### `GET /activity`

Recent activity: `[{"id", "kind", "summary", "time"}]`. The optional `kind`
query parameter filters to one activity kind (for example `?kind=chat`);
optional `limit` (1-500, default 100) caps how many entries come back.

### `POST /stop`, `POST /start`

Pause and resume the agent.

## Backup restore and memory detail

`POST /memories/import` accepts `{"memories": [...]}` where the list uses
`GET /memories/export` records. At most 1000 records can be restored per request.
Each must have a supported `kind` and nonblank `text` of at most 4000 characters.
Optional `createdAt` is a finite, nonnegative Unix timestamp. IDs are ignored.
Invalid records reject the entire batch (400); nothing is partially restored.
An oversized list is rejected by request validation (422).

The response is `{"imported": 2, "skipped": 1}`. Records with the same kind and
exact text as an active memory or an earlier record in the batch are skipped.
Repeated imports are safe. This restores memories only, never approvals or
execution permissions. A successful nonempty restore adds one activity entry.

`GET /memories/{id}` returns one active record including `createdAt` and a
string `id`. Unknown and superseded IDs return 404.
`GET /memories/counts` returns active totals for `fact`, `preference` and
`feedback`, including zero-count categories.

## Filtering and paging

`GET /memories/search` accepts `kind` and `limit` (1-500, default 50).
`GET /approvals` accepts `status` (`pending`, `approved`, `denied`) and `limit`
(1-500, default 100). Invalid filters and out-of-range limits return 400.

`GET /activity` is newest-insertion-first and supports `before_id`: request
older entries using the last entry's ID from the preceding page. The cursor
is exclusive, positive and can be combined with `kind` and `limit`. This avoids
duplicate entries when new activity arrives between pages. An empty result
means there are no older matching entries, not that the cursor is invalid.
`GET /approvals/stale?days=3` lists pending approvals older than `days` (a positive number,
default 3), oldest first. It never approves or denies anything.
`GET /approvals/search?q=` matches the summary or detail text literally (case-insensitive,
`%` and `_` are not wildcards) and accepts `status` and `limit`. A blank `q` returns 400.
`GET /activity/kinds` and `GET /memories/kinds` return the kinds present in the log and the
supported memory kinds, so clients can build filter menus without hard-coding them.
`GET /activity/page` returns `{items, nextBeforeId}` like `/memories/page` and `/approvals/page`:
limit 1-500, an exclusive `before_id` cursor and an optional `kind`. `nextBeforeId` is
null on the last page.
All these endpoints use the same bearer-token protection as the rest of the API.
