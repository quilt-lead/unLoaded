/**
 * Element <-> calc mapping. Port of matcher.py (itself a port of the mockup's runMapping()).
 *
 * Tiers and confidences (deterministic, in this order of strength):
 *   exact    0.97  the element's mark appears as a token
 *   range    0.90  the mark falls inside a written range ("2B1 - 2B9", "C1 thru C12")
 *   loose    0.88  the mark matches ignoring punctuation ("SL2" for "SL-2")
 *   family   0.85  token names a mark family ("BR1" covers "BR1-1".."BR1-n")
 *   size     0.62  section size + element type (+ storey if the line names one), no mark
 *   partial  0.50  token is the tail of exactly one model mark ("CB1" -> "2CB1")
 *   xref     <=.45 any mark tier where the element type differs from the calc's type -
 *                  the calc mentions the element, it probably did not design it
 *   type     0.30  calc names no marks or sizes: covers unclaimed elements of its type
 * Scanned pages and front matter are never mapped. Every link keeps page, the exact
 * text span it matched, a snippet, word boxes for highlighting, and the rule.
 */
import { normProfile, profileFrom } from './elements.ts';
import { rectsForSpan } from './pdf.ts';
import { cmpStr, lineStart, pyRe } from './pyre.ts';
import { CAT_WORDS } from './segment.ts';
import type { Calc, CalcElement, CalcLink, CalcPage, LinkTier } from './types.ts';

export const CONF = {
  exact: 0.97,
  range: 0.9,
  loose: 0.88,
  family: 0.85,
  size: 0.62,
  partial: 0.5,
  type: 0.3,
} as const;

const DASHES = /[‐-―]/g;
const RANGE = pyRe(
  String.raw`\b([A-Z]{0,3}\d{0,2}[A-Z]{1,3})(\d{1,4})\s*(?:-|–|—|TO|THRU|THROUGH)\s*(?:\1)?(\d{1,4})\b`,
  'g',
);
const TOK = /[A-Z0-9]+(?:[-./][A-Z0-9]+)*/g;
const PROF = pyRe(
  String.raw`\b(?:W|HSS|WT|MC|UB|UC|PFC|SHS|RHS|CHS|IPE|HEA|HEB)\s?\d+(?:\.\d+)?X\d+(?:\.\d+)?(?:X\d+(?:/\d+)?(?:\.\d+)?)?\b` +
    String.raw`|\b\d{3,4}X\d{3,4}\b`,
  'g',
);
const FAMILY = /^(.+?)-\d{1,3}[A-Z]?$/;

export function normMark(s: string | null | undefined): string {
  return String(s ?? '')
    .toUpperCase()
    .replace(DASHES, '-')
    .replace(/\s+/g, '');
}

export function dashless(s: string | null | undefined): string {
  return normMark(s).replace(/[-./]/g, '');
}

function snippet(text: string, idx: number, n: number) {
  const a = Math.max(0, idx - 70);
  const b = Math.min(text.length, idx + n + 70);
  return {
    before: (a > 0 ? '…' : '') + text.slice(a, idx),
    match: text.slice(idx, idx + n),
    after: text.slice(idx + n, b) + (b < text.length ? '…' : ''),
  };
}

function pushTo<K, V>(m: Map<K, V[]>, k: K, v: V): void {
  const arr = m.get(k);
  if (arr) arr.push(v);
  else m.set(k, [v]);
}

export function runMapping(
  elements: readonly CalcElement[],
  calcs: Calc[],
  pages: ReadonlyArray<Pick<CalcPage, 'n' | 'text' | 'words'>>,
): CalcLink[] {
  const links = new Map<string, CalcLink>();
  if (!elements.length || !calcs.length) return [];
  const keyOf = (gid: string, calcKey: string) => `${gid}\u0000${calcKey}`;
  const pageByN = new Map(pages.map((p) => [p.n, p]));

  const exact = new Map<string, CalcElement[]>();
  const loose = new Map<string, CalcElement[]>();
  const families = new Map<string, CalcElement[]>();
  for (const el of elements) {
    if (!el.mark) continue;
    const n = normMark(el.mark);
    pushTo(exact, n, el);
    pushTo(loose, dashless(el.mark), el);
    const fam = FAMILY.exec(n);
    if (fam) pushTo(families, fam[1]!, el);
  }
  const allMarks = [...exact.keys()];
  const byProfile = new Map<string, CalcElement[]>();
  for (const el of elements) if (el.profile) pushTo(byProfile, `${el.profile}|${el.cat}`, el);
  // longest first; ties alphabetical (Python iterates a set here, so its tie order is arbitrary)
  const storeys = [...new Set(elements.map((e) => e.storey).filter((s) => s && s.length > 2))].sort(
    (a, b) => b.length - a.length || cmpStr(a, b),
  );

  const link = (
    el: CalcElement,
    c: Calc,
    conf: number,
    tier: LinkTier,
    rule: string,
    pg: Pick<CalcPage, 'n' | 'text' | 'words'>,
    idx: number,
    n: number,
  ) => {
    if (c.cat && el.cat !== c.cat && el.cat !== 'Other' && tier !== 'size' && tier !== 'type') {
      conf = Math.min(conf, 0.45);
      tier = 'xref';
      rule = `${el.cat} "${el.mark}" is mentioned in a ${c.cat.toLowerCase()} calc - likely a cross-reference`;
    }
    const k = keyOf(el.global_id, c.key);
    const rec: CalcLink = {
      global_id: el.global_id,
      calc_key: c.key,
      conf,
      tier,
      rule,
      page: pg.n,
      span: [idx, idx + n],
      token: pg.text.slice(idx, idx + n),
      snippet: snippet(pg.text, idx, n),
      rects: rectsForSpan(pg, idx, idx + n),
    };
    const ex = links.get(k);
    if (ex === undefined || conf > ex.conf) links.set(k, rec);
  };

  for (const c of calcs) {
    if (c.scanned || c.front) continue;
    c.mark_hits = 0;
    for (const pn of c.pages) {
      const pg = pageByN.get(pn);
      if (!pg) continue;
      const U = pg.text.toUpperCase();
      // 1. ranges
      for (const m of U.matchAll(RANGE)) {
        const pre = m[1]!;
        const a = parseInt(m[2]!, 10);
        const b = parseInt(m[3]!, 10);
        if (!(b > a && b - a < 300)) continue;
        if (exact.has(normMark(m[0]))) continue;
        let hit = false;
        for (let i = a; i <= b; i++) {
          for (const el of exact.get(`${pre}${i}`) ?? []) {
            link(el, c, CONF.range, 'range', `In range ${pre}${a}–${pre}${b}`, pg, m.index, m[0].length);
            hit = true;
          }
        }
        if (hit) c.mark_hits += 1;
      }
      // 2. tokens
      for (const m of U.matchAll(TOK)) {
        const tok = m[0];
        if (!/[A-Z]/.test(tok) || !/\d/.test(tok) || tok.length < 2) continue;
        let hit = exact.get(tok);
        if (hit) {
          for (const el of hit) link(el, c, CONF.exact, 'exact', `Mark "${el.mark}" named in calc`, pg, m.index, tok.length);
          c.mark_hits += 1;
          continue;
        }
        hit = loose.get(dashless(tok));
        if (hit) {
          for (const el of hit) {
            link(el, c, CONF.loose, 'loose', `"${tok}" matches mark "${el.mark}" ignoring punctuation`, pg, m.index, tok.length);
          }
          c.mark_hits += 1;
          continue;
        }
        hit = families.get(tok);
        if (hit) {
          for (const el of hit) link(el, c, CONF.family, 'family', `"${tok}" covers mark family ${tok}-n`, pg, m.index, tok.length);
          c.mark_hits += 1;
          continue;
        }
        if (/^[A-Z]+\d+$/.test(tok) && !profileFrom(tok)) {
          const cands = allMarks.filter(
            (mk) => mk.length > tok.length && mk.endsWith(tok) && /^[0-9A-Z]/.test(mk[mk.length - tok.length - 1]!),
          );
          if (cands.length === 1) {
            for (const el of exact.get(cands[0]!)!) {
              link(el, c, CONF.partial, 'partial', `"${tok}" is a partial mark - only "${el.mark}" ends with it`, pg, m.index, tok.length);
            }
            c.mark_hits += 1;
          }
        }
      }
      // 3. section size + element type (+ storey named on the line)
      if (c.cat) {
        for (const m of U.matchAll(PROF)) {
          const p = normProfile(m[0]);
          const ls = lineStart(U, m.index);
          const le = U.indexOf('\n', m.index);
          const line = U.slice(ls, le >= 0 ? le : undefined);
          const lineCat = CAT_WORDS.find(([, rx]) => rx.test(line))?.[0] || c.cat;
          const lineStorey = storeys.find((st) => line.includes(st.toUpperCase()));
          for (const el of byProfile.get(`${p}|${lineCat}`) ?? []) {
            if (lineStorey && el.storey !== lineStorey) continue;
            if (el.mark && links.has(keyOf(el.global_id, c.key))) continue;
            link(
              el,
              c,
              CONF.size,
              'size',
              `Size ${p} + element type ${lineCat}${lineStorey ? ' on ' + lineStorey : ''} (no mark given)`,
              pg,
              m.index,
              m[0].length,
            );
          }
        }
      }
    }
  }
  // 4. element type only
  const claimed = new Set([...links.values()].map((l) => l.global_id));
  const linkedCalcs = new Set([...links.values()].map((l) => l.calc_key));
  for (const c of calcs) {
    if (c.scanned || c.front || !c.cat || c.mark_hits || linkedCalcs.has(c.key)) continue;
    const pg = pageByN.get(c.pages[0]!);
    if (!pg) continue;
    const rx = CAT_WORDS.find(([k]) => k === c.cat)![1];
    const mm = rx.exec(pg.text);
    const [idx, n] = mm ? [mm.index, mm[0].length] : [0, 0];
    for (const el of elements) {
      if (el.cat === c.cat && !claimed.has(el.global_id)) {
        link(el, c, CONF.type, 'type', `Calc covers ${c.cat.toLowerCase()}s but names no marks or sizes`, pg, idx, n);
      }
    }
  }
  return [...links.values()].sort((a, b) => cmpStr(a.calc_key, b.calc_key) || cmpStr(a.global_id, b.global_id));
}
