# mike-watch (local preparation, not deployed)

Planned always-on piece for Mike's proactive checks. Nothing here talks to
Google, Cloudflare or any push service yet, and it has not been deployed.
What exists and is tested locally with `npm test`:

- `src/crypto.js` - AES-GCM sealing for the Google refresh token. The key is a
  Worker secret; only ciphertext is ever stored.
- `src/dedupe.js` - remembers short SHA-256 prefixes of item ids, never
  subjects, senders or bodies.
- `src/briefing.js` - builds one short push, or nothing when there is nothing new.
- `src/google.js` - read-only OAuth (PKCE) URL, token and Gmail/Calendar request builders and parsers.
- `src/check.js` - one scheduled check with fetch, storage and push injected; tested with fixtures only (dedupe, one-time re-consent notice, retry after a failed push).
- `src/notify.js` - ntfy publish request builder. Closed-app delivery to an iPhone is not verified.

Not built or verified: Google OAuth, Gmail/Calendar reads, cron trigger,
push delivery to an iPhone, any account or hosting setup. Those need Fred's
consent and account choices first. Read-only Google scopes only; acting on
Google stays behind approvals and is out of scope here.
