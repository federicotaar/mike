// Encrypts the Google refresh token before it is stored. The key is a Worker
// secret (base64, 32 bytes) and never sits next to the ciphertext.
const enc = new TextEncoder();
const dec = new TextDecoder();

function b64(bytes) { return btoa(String.fromCharCode(...bytes)); }
function unb64(text) { return Uint8Array.from(atob(text), c => c.charCodeAt(0)); }

async function importKey(keyB64) {
  const raw = unb64(keyB64);
  if (raw.length !== 32) throw new Error("MIKE_TOKEN_KEY must be 32 bytes, base64");
  return crypto.subtle.importKey("raw", raw, "AES-GCM", false, ["encrypt", "decrypt"]);
}

export async function seal(plaintext, keyB64) {
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const key = await importKey(keyB64);
  const ct = new Uint8Array(await crypto.subtle.encrypt({ name: "AES-GCM", iv }, key, enc.encode(plaintext)));
  return `v1.${b64(iv)}.${b64(ct)}`;
}

export async function open(sealed, keyB64) {
  const [version, iv, ct] = String(sealed).split(".");
  if (version !== "v1" || !iv || !ct) throw new Error("unknown sealed format");
  const key = await importKey(keyB64);
  const pt = await crypto.subtle.decrypt({ name: "AES-GCM", iv: unb64(iv) }, key, unb64(ct));
  return dec.decode(pt);
}
