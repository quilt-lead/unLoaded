/**
 * The one text fold every rule that reads calc text or model marks goes through: upper case, and the
 * Unicode hyphens / dashes U+2010-U+2015 ("‐", "‑", "‒", "–", "—", "―") as an ASCII "-". So "SL‐2"
 * (U+2010) in a calc and the mark "SL-2" in the model read the same, in the token rule, the range rule
 * ("2B1 – 2B9"), page references ("pages 5–8") and section detection alike.
 *
 * The fold keeps one UTF-16 unit for one, so an offset into the folded text is the same offset into
 * the page text: spans, snippets and highlight rects stay exact. A character whose upper case is longer
 * (German "ß" -> "SS") is left as it is rather than shifting every later offset.
 */

/** Unicode hyphens and dashes (U+2010-U+2015), folded to "-". */
export const DASHES = /[‐-―]/g;

/** Upper case + dashes folded, offset-preserving (see the module comment). */
export function foldText(s: string): string {
  const up = s.toUpperCase();
  // upper-casing never shortens a string, so equal lengths mean every character kept its width
  if (up.length === s.length) return up.replace(DASHES, "-");
  let out = "";
  for (const ch of s) {
    const u = ch.toUpperCase();
    out += u.length === ch.length ? u : ch;
  }
  return out.replace(DASHES, "-");
}
