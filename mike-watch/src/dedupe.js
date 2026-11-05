// Decide what is new since the last check, remembering only short hashes
// (never subjects, senders or bodies).
export async function fingerprint(text) {
  const bytes = new TextEncoder().encode(text);
  const hash = new Uint8Array(await crypto.subtle.digest("SHA-256", bytes));
  return Array.from(hash.slice(0, 8)).map(b => b.toString(16).padStart(2, "0")).join("");
}

export async function newItems(items, seenHashes, keep = 200) {
  const seen = new Set(seenHashes);
  const fresh = [];
  const all = [];
  for (const item of items) {
    const h = await fingerprint(item.id);
    all.push(h);
    if (!seen.has(h)) fresh.push(item);
  }
  const next = [...all, ...seenHashes.filter(h => !all.includes(h))].slice(0, keep);
  return { fresh, seen: next };
}
