/**
 * Hashes.
 *
 * - SHA-1 (hex) over canonical JSON (object keys sorted, no whitespace): synchronous and
 *   dependency-free. Used for CHANGE DETECTION only (calc content_hash, element content_hash).
 * - SHA-256 (hex) via WebCrypto (`crypto.subtle.digest`, in browsers, Web Workers and Node >= 20):
 *   the DOCUMENT hashes provenance rests on - the calc PDF's bytes and the element graph's canonical
 *   JSON. These identify an input document in `Provenance.inputs` and the run's producer records.
 */

/** JSON with object keys sorted at every level; undefined values dropped (as JSON.stringify does). */
export function canonicalJson(v: unknown): string {
  if (v === null || typeof v !== "object") return JSON.stringify(v) ?? "null";
  if (Array.isArray(v)) return `[${v.map((x) => (x === undefined ? "null" : canonicalJson(x))).join(",")}]`;
  const o = v as Record<string, unknown>;
  return `{${Object.keys(o)
    .filter((k) => o[k] !== undefined)
    .sort()
    .map((k) => `${JSON.stringify(k)}:${canonicalJson(o[k])}`)
    .join(",")}}`;
}

export function sha1Json(v: unknown): string {
  return sha1(new TextEncoder().encode(canonicalJson(v)));
}

/** SHA-1 of bytes, lowercase hex. */
export function sha1(msg: Uint8Array): string {
  const ml = msg.length;
  const withPad = ((ml + 9 + 63) >> 6) << 6;
  const buf = new Uint8Array(withPad);
  buf.set(msg);
  buf[ml] = 0x80;
  const view = new DataView(buf.buffer);
  view.setUint32(withPad - 8, Math.floor((ml * 8) / 2 ** 32));
  view.setUint32(withPad - 4, (ml * 8) >>> 0);
  let h0 = 0x67452301, h1 = 0xefcdab89, h2 = 0x98badcfe, h3 = 0x10325476, h4 = 0xc3d2e1f0;
  const w = new Uint32Array(80);
  for (let off = 0; off < withPad; off += 64) {
    for (let i = 0; i < 16; i++) w[i] = view.getUint32(off + i * 4);
    for (let i = 16; i < 80; i++) {
      const x = w[i - 3]! ^ w[i - 8]! ^ w[i - 14]! ^ w[i - 16]!;
      w[i] = (x << 1) | (x >>> 31);
    }
    let a = h0, b = h1, c = h2, d = h3, e = h4;
    for (let i = 0; i < 80; i++) {
      const f = i < 20 ? (b & c) | (~b & d) : i < 40 ? b ^ c ^ d : i < 60 ? (b & c) | (b & d) | (c & d) : b ^ c ^ d;
      const k = i < 20 ? 0x5a827999 : i < 40 ? 0x6ed9eba1 : i < 60 ? 0x8f1bbcdc : 0xca62c1d6;
      const t = (((a << 5) | (a >>> 27)) + f + e + k + w[i]!) >>> 0;
      e = d;
      d = c;
      c = (b << 30) | (b >>> 2);
      b = a;
      a = t;
    }
    h0 = (h0 + a) >>> 0;
    h1 = (h1 + b) >>> 0;
    h2 = (h2 + c) >>> 0;
    h3 = (h3 + d) >>> 0;
    h4 = (h4 + e) >>> 0;
  }
  return [h0, h1, h2, h3, h4].map((x) => x.toString(16).padStart(8, "0")).join("");
}

/** The slice of WebCrypto used here (typed locally so this compiles under any lib: DOM, WebWorker or Node). */
interface SubtleLike {
  digest(algorithm: "SHA-256", data: Uint8Array): Promise<ArrayBuffer>;
}

function subtle(): SubtleLike {
  const c = (globalThis as unknown as { crypto?: { subtle?: SubtleLike } }).crypto;
  if (!c?.subtle) {
    throw new Error("WebCrypto (crypto.subtle) is not available: it needs a browser secure context, a Web Worker or Node >= 20");
  }
  return c.subtle;
}

/** A lowercase hex SHA-256: what `Provenance.inputs` and the producer records hold. */
export const SHA256_HEX = /^[0-9a-f]{64}$/;

/** SHA-256 of bytes, lowercase hex. */
export async function sha256(bytes: Uint8Array): Promise<string> {
  const d = new Uint8Array(await subtle().digest("SHA-256", bytes));
  let out = "";
  for (const b of d) out += b.toString(16).padStart(2, "0");
  return out;
}

/** SHA-256 of a value's canonical JSON (key order does not change it): the hash of a serialized element graph. */
export function sha256Json(v: unknown): Promise<string> {
  return sha256(new TextEncoder().encode(canonicalJson(v)));
}
