// Turns already-fetched, already-new items into one short push. Pure text:
// no network, no storage. Says nothing when there is nothing to say.
export function buildPush({ mail = [], events = [] }) {
  if (mail.length === 0 && events.length === 0) return null;
  const parts = [];
  if (mail.length) parts.push(`${mail.length} new email${mail.length === 1 ? "" : "s"}`);
  if (events.length) {
    const next = events[0] || {};
    const title = String(next.title || "").trim() || "untitled event";
    const time = String(next.time || "").trim();
    const detail = time ? `${title} at ${time}` : title;
    parts.push(`${events.length} event${events.length === 1 ? "" : "s"} soon (next: ${detail})`);
  }
  return { title: "Mike", body: parts.join("; ") + "." };
}
