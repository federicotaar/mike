// Account-independent Google request builders and response parsers.
// Pure functions: no network, no storage. Read-only scopes only.
export const SCOPES = [
  "https://www.googleapis.com/auth/gmail.readonly",
  "https://www.googleapis.com/auth/calendar.readonly",
];

function b64url(bytes) {
  return btoa(String.fromCharCode(...bytes)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

export async function pkcePair(randomBytes = crypto.getRandomValues(new Uint8Array(32))) {
  const verifier = b64url(randomBytes);
  const digest = new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(verifier)));
  return { verifier, challenge: b64url(digest) };
}

export function buildAuthUrl({ clientId, redirectUri, state, challenge }) {
  if (!clientId || !redirectUri || !state || !challenge) throw new Error("missing auth parameter");
  const u = new URL("https://accounts.google.com/o/oauth2/v2/auth");
  u.search = new URLSearchParams({
    client_id: clientId,
    redirect_uri: redirectUri,
    response_type: "code",
    scope: SCOPES.join(" "),
    access_type: "offline",
    prompt: "consent",
    state,
    code_challenge: challenge,
    code_challenge_method: "S256",
    include_granted_scopes: "false",
  }).toString();
  return u.toString();
}

// Interprets a token endpoint response. invalid_grant means the refresh token
// is dead (revoked, or the 7-day Testing expiry): the caller must tell the user
// to sign in again instead of failing silently.
export function parseTokenResponse(status, body) {
  if (status === 200 && body && body.access_token) {
    const granted = String(body.scope || "").split(" ").filter(Boolean);
    const extra = granted.filter(s => !SCOPES.includes(s));
    return { ok: true, accessToken: body.access_token, refreshToken: body.refresh_token || null,
             expiresIn: body.expires_in || 0, extraScopes: extra,
             missingScopes: SCOPES.filter(s => !granted.includes(s)) };
  }
  const error = body && body.error ? String(body.error) : `http_${status}`;
  return { ok: false, error, needsReconsent: error === "invalid_grant" };
}

export function gmailListUrl(sinceEpochSeconds, max = 20) {
  const q = `in:inbox after:${Math.floor(sinceEpochSeconds)}`;
  const u = new URL("https://gmail.googleapis.com/gmail/v1/users/me/messages");
  u.search = new URLSearchParams({ q, maxResults: String(Math.min(max, 50)) }).toString();
  return u.toString();
}

export function parseGmailList(body) {
  return ((body && body.messages) || []).map(m => ({ id: String(m.id) }));
}

export function calendarUrl(nowIso, untilIso) {
  const u = new URL("https://www.googleapis.com/calendar/v3/calendars/primary/events");
  u.search = new URLSearchParams({ timeMin: nowIso, timeMax: untilIso, singleEvents: "true",
    orderBy: "startTime", maxResults: "10" }).toString();
  return u.toString();
}

export function parseEvents(body, timeZone = "Europe/Rome") {
  return ((body && body.items) || [])
    .filter(e => e.status !== "cancelled" && e.start && e.start.dateTime)
    .map(e => ({
      id: String(e.id),
      title: e.summary || "(no title)",
      time: new Date(e.start.dateTime).toLocaleTimeString("it-IT", { hour: "2-digit", minute: "2-digit", timeZone }),
    }));
}
