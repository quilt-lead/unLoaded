/**
 * Element <-> calc mapping. Port of the reference run_mapping() (itself a faithful port of the
 * mockup's runMapping()); tiers, confidences and order unchanged:
 *
 *   exact    0.97  the element's mark appears as a token
 *   range    0.90  the mark falls inside a written range ("2B1 - 2B9", "C1 thru C12")
 *   loose    0.88  the mark matches ignoring punctuation ("SL2" for "SL-2")
 *   family   0.85  token names a mark family ("BR1" covers "BR1-1".."BR1-n")
 *   size     0.62  section size + element type (+ storey if the line names one), no mark
 *   partial  0.50  token is the tail of exactly one model mark ("CB1" -> "2CB1")
 *   xref     <=.45 any mark tier where the element type differs from the calc's type -
 *                  the calc mentions the element, it probably did not design it
 *   type     0.30  calc names no marks or sizes: covers unclaimed elements of its type
 * Scanned pages and front matter are never mapped. Every link keeps page, the exact text span it
 * matched, a snippet, word boxes for highlighting, and the rule.
 */
import { rectsForSpan } from "./pdf.ts";
import { CAT_WORDS } from "./segment.ts";
import type { Calc, CalcPage, ElementRow, Link, Snippet, Tier } from "./types.ts";

export const CONF = { exact: 0.97, range: 0.9, loose: 0.88, family: 0.85, size: 0.62, partial: 0.5, type: 0.3 } as const;
export const XREF_CAP = 0.45;

const DASHES = /[‐-―]/g;
const RANGE = /\b([A-Z]{0,3}\d{0,2}[A-Z]{1,3})(\d{1,4})\s*(?:-|–|—|TO|THRU|THROUGH)\s*(?:\1)?(\d{1,4})\b/g;
const TOK = /[A-Z0-9]+(?:[-./][A-Z0-9]+)*/g;
const PROF = /\b(?:W|HSS|WT|MC|UB|UC|PFC|SHS|RHS|CHS|IPE|HEA|HEB)\s?\d+(?:\.\d+)?X\d+(?:\.\d+)?(?:X\d+(?:\/\d+)?(?:\.\d+)?)?\b|\b\d{3,4}X\d{3,4}\b/g;
const PROFILE_RE = /\b(?:W|HSS|WT|MC|C|L|UB|UC|PFC|SHS|RHS|CHS|IPE|HEA|HEB)\s?\d+(?:\.\d+)?X\d+(?:\.\d+)?(?:X\d+(?:\.\d+)?)?\b|\b\d{3,4}X\d{3,4}\b/;

/** Section designation as one comparable string (upper case, no spaces, × -> X). */
export const normProfile = (s: string): string => (s ? s.toUpperCase().replaceAll(" ", "").replaceAll("×", "X") : "");

/** First section designation found in the given strings (the mockup's profileFrom()). */
export function profileFrom(...strs: (string | null | undefined)[]): string {
  for (const s of strs) {
    if (!s) continue;
    const m = PROFILE_RE.exec(String(s).toUpperCase().replaceAll("×", "X"));
    if (m) return normProfile(m[0]);
  }
  return "";
}

export const normMark = (s: string | null | undefined): string =>
  String(s ?? "").toUpperCase().replace(DASHES, "-").replace(/\s+/g, "");
export const dashless = (s: string | null | undefined): string => normMark(s).replace(/[-./]/g, "");

function snippet(text: string, idx: number, n: number): Snippet {
  const a = Math.max(0, idx - 70);
  const b = Math.min(text.length, idx + n + 70);
  return {
    before: (a > 0 ? "…" : "") + text.slice(a, idx), match: text.slice(idx, idx + n),
    after: text.slice(idx + n, b) + (b < text.length ? "…" : ""),
  };
}

const push = <K, V>(m: Map<K, V[]>, k: K, v: V): void => {
  const l = m.get(k);
  if (l) l.push(v);
  else m.set(k, [v]);
};
const cmp = (p: string, q: string): number => (p < q ? -1 : p > q ? 1 : 0);
/** Start of the line containing index i (Python's U.rfind("\n", 0, i) + 1). */
const lineStart = (U: string, i: number): number => (i > 0 ? U.lastIndexOf("\n", i - 1) + 1 : 0);

/**
 * Map elements to calcs. `elements` = graphElements(graph); `calcs` + `pages` = the calc package.
 * Returns auto links (status "auto"), sorted by (calc_key, global_id).
 */
export function runMapping(elements: ElementRow[], calcs: Calc[], pages: CalcPage[]): Link[] {
  const links = new Map<string, Link>();
  if (!elements.length || !calcs.length) return [];
  const els = [...elements].sort((p, q) => cmp(p.global_id, q.global_id));
  const pageByN = new Map(pages.map((p) => [p.n, p]));
  const exact = new Map<string, ElementRow[]>();
  const loose = new Map<string, ElementRow[]>();
  const families = new Map<string, ElementRow[]>();
  for (const el of els) {
    if (!el.mark) continue;
    const n = normMark(el.mark);
    push(exact, n, el);
    push(loose, dashless(el.mark), el);
    const fam = /^(.+?)-\d{1,3}[A-Z]?$/.exec(n);
    if (fam) push(families, fam[1]!, el);
  }
  const allMarks = [...exact.keys()];
  const byProfile = new Map<string, ElementRow[]>();
  for (const el of els) if (el.profile) push(byProfile, `${el.profile}|${el.cat}`, el);
  // longest first; equal lengths alphabetically (deterministic)
  const storeys = [...new Set(els.map((e) => e.storey).filter((s) => s && s.length > 2))]
    .sort((p, q) => q.length - p.length || cmp(p, q));
  const markHits = new Map<string, number>();

  const link = (el: ElementRow, c: Calc, conf0: number, tier0: Tier, rule0: string, pg: CalcPage, idx: number, n: number) => {
    let conf = conf0, tier = tier0, rule = rule0;
    if (c.cat && el.cat !== c.cat && el.cat !== "Other" && tier !== "size" && tier !== "type") {
      conf = Math.min(conf, XREF_CAP);
      tier = "xref";
      rule = `${el.cat} "${el.mark}" is mentioned in a ${c.cat.toLowerCase()} calc - likely a cross-reference`;
    }
    const k = `${el.global_id}\u0000${c.key}`;
    const rec: Link = {
      global_id: el.global_id, calc_key: c.key, conf, tier, rule, page: pg.n, span: [idx, idx + n],
      token: pg.text.slice(idx, idx + n), snippet: snippet(pg.text, idx, n), rects: rectsForSpan(pg, idx, idx + n),
      status: "auto",
    };
    const ex = links.get(k);
    if (!ex || conf > ex.conf) links.set(k, rec);
  };
  const hit = (c: Calc) => markHits.set(c.key, (markHits.get(c.key) ?? 0) + 1);

  for (const c of calcs) {
    if (c.scanned || c.front) continue;
    markHits.set(c.key, 0);
    for (const pn of c.pages) {
      const pg = pageByN.get(pn);
      if (!pg) continue;
      const U = pg.text.toUpperCase();
      // 1. ranges
      for (const m of U.matchAll(RANGE)) {
        const pre = m[1]!, a = Number(m[2]), b = Number(m[3]);
        if (!(b > a && b - a < 300)) continue;
        if (exact.has(normMark(m[0]))) continue;
        let any = false;
        for (let i = a; i <= b; i++) {
          for (const el of exact.get(`${pre}${i}`) ?? []) {
            link(el, c, CONF.range, "range", `In range ${pre}${a}–${pre}${b}`, pg, m.index, m[0].length);
            any = true;
          }
        }
        if (any) hit(c);
      }
      // 2. tokens
      for (const m of U.matchAll(TOK)) {
        const tok = m[0];
        if (!/[A-Z]/.test(tok) || !/\d/.test(tok) || tok.length < 2) continue;
        let h = exact.get(tok);
        if (h) {
          for (const el of h) link(el, c, CONF.exact, "exact", `Mark "${el.mark}" named in calc`, pg, m.index, tok.length);
          hit(c);
          continue;
        }
        h = loose.get(dashless(tok));
        if (h) {
          for (const el of h) {
            link(el, c, CONF.loose, "loose", `"${tok}" matches mark "${el.mark}" ignoring punctuation`, pg, m.index, tok.length);
          }
          hit(c);
          continue;
        }
        h = families.get(tok);
        if (h) {
          for (const el of h) link(el, c, CONF.family, "family", `"${tok}" covers mark family ${tok}-n`, pg, m.index, tok.length);
          hit(c);
          continue;
        }
        if (/^[A-Z]+\d+$/.test(tok) && !profileFrom(tok)) {
          const cands = allMarks.filter(
            (mk) => mk.length > tok.length && mk.endsWith(tok) && /^[0-9A-Z]/.test(mk[mk.length - tok.length - 1]!),
          );
          if (cands.length === 1) {
            for (const el of exact.get(cands[0]!)!) {
              link(el, c, CONF.partial, "partial", `"${tok}" is a partial mark - only "${el.mark}" ends with it`, pg, m.index, tok.length);
            }
            hit(c);
          }
        }
      }
      // 3. section size + element type (+ storey named on the line)
      if (c.cat) {
        for (const m of U.matchAll(PROF)) {
          const p = normProfile(m[0]);
          const ls = lineStart(U, m.index);
          const le = U.indexOf("\n", m.index);
          const line = U.slice(ls, le >= 0 ? le : undefined);
          const lineCat = CAT_WORDS.find(([, rx]) => rx.test(line))?.[0] || c.cat;
          const lineStorey = storeys.find((st) => line.includes(st.toUpperCase())) ?? null;
          for (const el of byProfile.get(`${p}|${lineCat}`) ?? []) {
            if (lineStorey && el.storey !== lineStorey) continue;
            if (el.mark && links.has(`${el.global_id}\u0000${c.key}`)) continue;
            link(el, c, CONF.size, "size",
              `Size ${p} + element type ${lineCat}${lineStorey ? " on " + lineStorey : ""} (no mark given)`,
              pg, m.index, m[0].length);
          }
        }
      }
    }
  }
  // 4. element type only
  const claimed = new Set([...links.values()].map((l) => l.global_id));
  const linkedCalcs = new Set([...links.values()].map((l) => l.calc_key));
  for (const c of calcs) {
    if (c.scanned || c.front || !c.cat || markHits.get(c.key) || linkedCalcs.has(c.key)) continue;
    const pg = pageByN.get(c.pages[0]!);
    if (!pg) continue;
    const rx = CAT_WORDS.find(([k]) => k === c.cat)?.[1];
    if (!rx) continue;
    const mm = rx.exec(pg.text);
    const [idx, n] = mm ? [mm.index, mm[0].length] : [0, 0];
    for (const el of els) {
      if (el.cat === c.cat && !claimed.has(el.global_id)) {
        link(el, c, CONF.type, "type", `Calc covers ${c.cat.toLowerCase()}s but names no marks or sizes`, pg, idx, n);
      }
    }
  }
  return [...links.values()].sort((p, q) => cmp(p.calc_key, q.calc_key) || cmp(p.global_id, q.global_id));
}
