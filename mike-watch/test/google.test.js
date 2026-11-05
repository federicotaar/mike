import test from "node:test";
import assert from "node:assert/strict";
import { SCOPES, pkcePair, buildAuthUrl, parseTokenResponse, gmailListUrl, parseGmailList, calendarUrl, parseEvents } from "../src/google.js";

test("scopes are read-only", () => {
  assert.ok(SCOPES.every(s => s.endsWith(".readonly")));
});

test("PKCE challenge matches the RFC 7636 example", async () => {
  const bytes = Uint8Array.from([116,24,223,180,151,153,224,37,79,250,96,125,216,173,187,186,22,212,37,77,105,214,191,240,91,88,5,88,83,132,141,121]);
  const { verifier, challenge } = await pkcePair(bytes);
  assert.equal(verifier, "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk");
  assert.equal(challenge, "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM");
});

test("auth URL asks for offline read-only access with PKCE and state", () => {
  const url = new URL(buildAuthUrl({ clientId: "cid", redirectUri: "https://x.example/cb", state: "st", challenge: "ch" }));
  assert.equal(url.origin + url.pathname, "https://accounts.google.com/o/oauth2/v2/auth");
  const p = url.searchParams;
  assert.equal(p.get("access_type"), "offline");
  assert.equal(p.get("code_challenge_method"), "S256");
  assert.equal(p.get("state"), "st");
  assert.equal(p.get("scope"), SCOPES.join(" "));
  assert.equal(p.get("response_type"), "code");
});

test("auth URL refuses missing pieces", () => {
  assert.throws(() => buildAuthUrl({ clientId: "c", redirectUri: "r", state: "", challenge: "x" }));
});

test("token response: success, extra and missing scopes are reported", () => {
  const ok = parseTokenResponse(200, { access_token: "a", refresh_token: "r", expires_in: 3599,
    scope: "https://www.googleapis.com/auth/gmail.readonly https://www.googleapis.com/auth/drive" });
  assert.equal(ok.ok, true);
  assert.deepEqual(ok.extraScopes, ["https://www.googleapis.com/auth/drive"]);
  assert.deepEqual(ok.missingScopes, ["https://www.googleapis.com/auth/calendar.readonly"]);
});

test("token response: invalid_grant asks for re-consent, other errors do not", () => {
  assert.deepEqual(parseTokenResponse(400, { error: "invalid_grant" }), { ok: false, error: "invalid_grant", needsReconsent: true });
  assert.equal(parseTokenResponse(500, {}).needsReconsent, false);
  assert.equal(parseTokenResponse(500, null).error, "http_500");
});

test("gmail list URL is inbox-only, bounded and parses ids only", () => {
  const u = new URL(gmailListUrl(1762300000.9, 500));
  assert.equal(u.searchParams.get("q"), "in:inbox after:1762300000");
  assert.equal(u.searchParams.get("maxResults"), "50");
  assert.deepEqual(parseGmailList({ messages: [{ id: "1", threadId: "t" }] }), [{ id: "1" }]);
  assert.deepEqual(parseGmailList({}), []);
});

test("calendar parsing skips cancelled and all-day items and formats local time", () => {
  const events = parseEvents({ items: [
    { id: "a", status: "confirmed", summary: "Math test", start: { dateTime: "2026-11-06T07:00:00Z" } },
    { id: "b", status: "cancelled", summary: "x", start: { dateTime: "2026-11-06T09:00:00Z" } },
    { id: "c", summary: "Holiday", start: { date: "2026-11-07" } },
  ] });
  assert.deepEqual(events, [{ id: "a", title: "Math test", time: "08:00" }]);
  assert.ok(calendarUrl("2026-11-06T00:00:00Z", "2026-11-06T12:00:00Z").includes("singleEvents=true"));
});
