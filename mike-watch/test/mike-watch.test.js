import test from "node:test";
import assert from "node:assert/strict";
import { seal, open } from "../src/crypto.js";
import { newItems, fingerprint } from "../src/dedupe.js";
import { buildPush } from "../src/briefing.js";

const KEY = Buffer.alloc(32, 7).toString("base64");

test("seal then open round-trips and never contains the plaintext", async () => {
  const sealed = await seal("1//refresh-token-example", KEY);
  assert.ok(sealed.startsWith("v1."));
  assert.ok(!sealed.includes("refresh-token-example"));
  assert.equal(await open(sealed, KEY), "1//refresh-token-example");
});

test("each seal uses a fresh IV", async () => {
  assert.notEqual(await seal("same", KEY), await seal("same", KEY));
});

test("wrong key and tampering both fail", async () => {
  const sealed = await seal("secret", KEY);
  await assert.rejects(open(sealed, Buffer.alloc(32, 9).toString("base64")));
  const parts = sealed.split(".");
  parts[2] = parts[2].slice(0, -4) + "AAAA";
  await assert.rejects(open(parts.join("."), KEY));
});

test("bad key length is refused", async () => {
  await assert.rejects(seal("x", Buffer.alloc(16).toString("base64")), /32 bytes/);
});

test("dedupe returns only unseen items and keeps hashes, not content", async () => {
  const first = await newItems([{ id: "a", subject: "S" }, { id: "b" }], []);
  assert.equal(first.fresh.length, 2);
  assert.ok(first.seen.every(h => /^[0-9a-f]{16}$/.test(h)));
  const second = await newItems([{ id: "a" }, { id: "b" }, { id: "c" }], first.seen);
  assert.deepEqual(second.fresh.map(i => i.id), ["c"]);
  assert.ok(second.seen.includes(await fingerprint("c")));
});

test("dedupe history is bounded", async () => {
  const items = Array.from({ length: 50 }, (_, i) => ({ id: `m${i}` }));
  const { seen } = await newItems(items, [], 10);
  assert.equal(seen.length, 10);
});

test("nothing new means no push", () => {
  assert.equal(buildPush({}), null);
});

test("push text counts mail and events", () => {
  const p = buildPush({ mail: [{}, {}], events: [{ title: "Math test", time: "08:00" }] });
  assert.equal(p.body, "2 new emails; 1 event soon (next: Math test at 08:00).");
});

test("push text handles events with missing title or time", () => {
  const noTitle = buildPush({ events: [{ time: "09:00" }] });
  assert.ok(noTitle.body.includes("untitled event at 09:00"));
  const noTime = buildPush({ events: [{ title: "Dentist" }] });
  assert.ok(noTime.body.includes("next: Dentist"));
  assert.ok(!noTime.body.includes("undefined"));
});
