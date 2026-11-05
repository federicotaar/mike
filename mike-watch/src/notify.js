// Builds the ntfy publish request. HTTP headers must be ASCII, so the title
// is sent as a JSON field instead. Delivery to a closed iPhone app is NOT
// verified; ntfy's own docs call its iOS app limited.
export function ntfyRequest(baseUrl, topic, { title, body }) {
  if (!/^[A-Za-z0-9_-]{16,}$/.test(topic)) throw new Error("topic must be a long unguessable id");
  return {
    url: String(baseUrl).replace(/\/+$/, ""),
    init: { method: "POST", headers: { "content-type": "application/json" },
            body: JSON.stringify({ topic, title, message: body, priority: 3 }) },
  };
}
