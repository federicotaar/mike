// One scheduled check, with every outside effect injected (fetch, store, push)
// so it is tested with fixtures only. It never logs tokens or item contents.
import { open } from "./crypto.js";
import { newItems } from "./dedupe.js";
import { buildPush } from "./briefing.js";
import { parseTokenResponse, gmailListUrl, parseGmailList, calendarUrl, parseEvents } from "./google.js";

export const RECONSENT_PUSH = { title: "Mike", body: "Google sign-in expired. Open Mike to reconnect." };

export async function runCheck({ store, fetchJson, push, keyB64, clientId, nowMs }) {
  const sealed = await store.get("refresh_sealed");
  if (!sealed) return { status: "not_connected" };
  const refreshToken = await open(sealed, keyB64);
  const tok = await fetchJson("https://oauth2.googleapis.com/token", {
    method: "POST",
    body: new URLSearchParams({ client_id: clientId, grant_type: "refresh_token", refresh_token: refreshToken }).toString(),
    headers: { "content-type": "application/x-www-form-urlencoded" },
  });
  const parsed = parseTokenResponse(tok.status, tok.body);
  if (!parsed.ok) {
    if (parsed.needsReconsent) {
      // Tell the user once, not on every cron run.
      if (!(await store.get("reconsent_sent"))) { await push(RECONSENT_PUSH); await store.put("reconsent_sent", "1"); }
      return { status: "needs_reconsent" };
    }
    return { status: "error", error: parsed.error };
  }
  await store.delete("reconsent_sent");
  const auth = { authorization: `Bearer ${parsed.accessToken}` };
  const nowSec = Math.floor(nowMs / 1000);
  const last = Number(await store.get("last_check")) || nowSec - 3600;
  const [mailRes, calRes] = await Promise.all([
    fetchJson(gmailListUrl(last), { headers: auth }),
    fetchJson(calendarUrl(new Date(nowMs).toISOString(), new Date(nowMs + 2 * 3600e3).toISOString()), { headers: auth }),
  ]);
  if (mailRes.status !== 200 || calRes.status !== 200) return { status: "error", error: `http_${mailRes.status}_${calRes.status}` };
  const seen = JSON.parse((await store.get("seen")) || "[]");
  const items = [...parseGmailList(mailRes.body), ...parseEvents(calRes.body).map(e => ({ ...e, id: "ev:" + e.id }))];
  const { fresh, seen: nextSeen } = await newItems(items, seen);
  const freshIds = new Set(fresh.map(i => i.id));
  const message = buildPush({
    mail: parseGmailList(mailRes.body).filter(m => freshIds.has(m.id)),
    events: parseEvents(calRes.body).filter(e => freshIds.has("ev:" + e.id)),
  });
  // Advance state only after the push call returned, so a failed push retries.
  if (message) await push(message);
  await store.put("seen", JSON.stringify(nextSeen));
  await store.put("last_check", String(nowSec));
  return { status: "ok", pushed: Boolean(message) };
}
