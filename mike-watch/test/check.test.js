import test from "node:test";
import assert from "node:assert/strict";
import { seal } from "../src/crypto.js";
import { runCheck } from "../src/check.js";
import { ntfyRequest } from "../src/notify.js";

const keyB64 = Buffer.alloc(32, 7).toString("base64");
function mkStore(init = {}) { const m = new Map(Object.entries(init));
  return { m, get: async k => m.get(k) ?? null, put: async (k, v) => { m.set(k, v); }, delete: async k => { m.delete(k); } }; }
const NOW = Date.parse("2026-11-05T18:00:00Z");
function mkFetch({ token = { status: 200, body: { access_token: "AT", scope: "https://www.googleapis.com/auth/gmail.readonly https://www.googleapis.com/auth/calendar.readonly", expires_in: 3600 } }, mail = [{ id: "m1" }], cal = [] } = {}) {
  const calls = [];
  const f = async (url, init) => { calls.push({ url, init });
    if (url.includes("oauth2.googleapis.com")) return token;
    if (url.includes("gmail")) return { status: 200, body: { messages: mail } };
    return { status: 200, body: { items: cal } }; };
  f.calls = calls; return f;
}

test("not connected does nothing", async () => {
  const push = async () => { throw new Error("no"); };
  assert.deepEqual(await runCheck({ store: mkStore(), fetchJson: mkFetch(), push, keyB64, clientId: "c", nowMs: NOW }), { status: "not_connected" });
});

test("new mail is pushed once, then deduped", async () => {
  const store = mkStore({ refresh_sealed: await seal("RT", keyB64) });
  const pushed = []; const push = async m => { pushed.push(m); };
  const f = mkFetch();
  const r1 = await runCheck({ store, fetchJson: f, push, keyB64, clientId: "c", nowMs: NOW });
  assert.equal(r1.pushed, true);
  assert.match(pushed[0].body, /1 new email\./);
  const r2 = await runCheck({ store, fetchJson: mkFetch(), push, keyB64, clientId: "c", nowMs: NOW + 60000 });
  assert.equal(r2.pushed, false);
  assert.equal(pushed.length, 1);
  assert.ok(!JSON.stringify([...store.m]).includes("m1"), "raw ids are not stored");
  assert.ok(!JSON.stringify(f.calls.map(c => c.url)).includes("RT"), "refresh token only goes to the token endpoint body");
});

test("events appear in the push", async () => {
  const store = mkStore({ refresh_sealed: await seal("RT", keyB64) });
  const pushed = []; 
  await runCheck({ store, fetchJson: mkFetch({ mail: [], cal: [{ id: "e1", summary: "Dentist", start: { dateTime: "2026-11-05T18:30:00Z" } }] }), push: async m => pushed.push(m), keyB64, clientId: "c", nowMs: NOW });
  assert.match(pushed[0].body, /Dentist/);
});

test("invalid_grant notifies once and stops", async () => {
  const store = mkStore({ refresh_sealed: await seal("RT", keyB64) });
  const pushed = [];
  const f = mkFetch({ token: { status: 400, body: { error: "invalid_grant" } } });
  const a = await runCheck({ store, fetchJson: f, push: async m => pushed.push(m), keyB64, clientId: "c", nowMs: NOW });
  const b = await runCheck({ store, fetchJson: f, push: async m => pushed.push(m), keyB64, clientId: "c", nowMs: NOW + 1000 });
  assert.equal(a.status, "needs_reconsent"); assert.equal(b.status, "needs_reconsent");
  assert.equal(pushed.length, 1);
});

test("failed push does not advance state (retries next run)", async () => {
  const store = mkStore({ refresh_sealed: await seal("RT", keyB64) });
  await assert.rejects(runCheck({ store, fetchJson: mkFetch(), push: async () => { throw new Error("down"); }, keyB64, clientId: "c", nowMs: NOW }));
  assert.equal(store.m.has("seen"), false);
  const pushed = [];
  await runCheck({ store, fetchJson: mkFetch(), push: async m => pushed.push(m), keyB64, clientId: "c", nowMs: NOW + 1000 });
  assert.equal(pushed.length, 1);
});

test("ntfy request is JSON, non-ASCII safe, and rejects guessable topics", () => {
  const r = ntfyRequest("https://ntfy.sh/", "mike-3f9a1c77d2b04e65", { title: "Mike", body: "Riunione è alle 9" });
  assert.equal(r.url, "https://ntfy.sh");
  assert.equal(JSON.parse(r.init.body).message, "Riunione è alle 9");
  assert.throws(() => ntfyRequest("https://ntfy.sh", "mike", { title: "t", body: "b" }));
});
