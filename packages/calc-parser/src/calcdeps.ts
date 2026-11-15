/**
 * Calc dependency graph: output of one calc feeds the input of another. Port of calcdeps.py.
 *
 * Two deterministic rules, each edge keeps its evidence:
 *
 * 1. page reference - "page 7", "pages 5-8", "p. 12" inside a calc points at the calc
 *    that holds that page. Direction from the nearest cue word earlier on the same
 *    line: "to" means this calc's output goes TO that page's calc (this -> that);
 *    "from" / "per" / "see" / "using" or no cue means it is an input (that -> this).
 * 2. cross-reference - a calc that mentions (xref tier) an element designed by another
 *    calc takes that calc's output as input (designer -> this), unless the same line
 *    has a "to" cue before the mention ("carried to ST-1 design"), then this -> designer.
 */
import { rectsForSpan } from './pdf.ts';
import { cmpStr, lineStart, pyRe } from './pyre.ts';
import type { Calc, CalcEdge, CalcEdgeEvidence, CalcLink, CalcPage } from './types.ts';

const PAGE = pyRe(String.raw`\b(?:PAGES?|PP?\.)\s*(\d{1,4})(?:\s*(?:-|–|TO)\s*(\d{1,4}))?`, 'g');
const CUE = pyRe(String.raw`\b(FROM|PER|SEE|USING|TO)\b`, 'g');

function lastCue(s: string): string | undefined {
  let last: string | undefined;
  for (const m of s.matchAll(CUE)) last = m[1];
  return last;
}

export function inferCalcDeps(
  calcs: ReadonlyArray<Pick<Calc, 'key' | 'pages' | 'front' | 'scanned'>>,
  pages: ReadonlyArray<Pick<CalcPage, 'n' | 'text' | 'words'>>,
  links: readonly CalcLink[],
): CalcEdge[] {
  const pageOwner = new Map<number, (typeof calcs)[number]>();
  for (const c of calcs) for (const n of c.pages) pageOwner.set(n, c);
  const pageByN = new Map(pages.map((p) => [p.n, p]));
  const edges = new Map<string, CalcEdge>();

  const add = (src: string, dst: string, rule: string, ev: CalcEdgeEvidence) => {
    if (src === dst) return;
    const k = `${src}\u0000${dst}`;
    let e = edges.get(k);
    if (!e) {
      e = { src, dst, rules: [], evidence: [] };
      edges.set(k, e);
    }
    if (!e.rules.includes(rule)) e.rules.push(rule);
    if (e.evidence.length < 6) e.evidence.push(ev);
  };

  for (const c of calcs) {
    if (c.front || c.scanned) continue;
    for (const pn of c.pages) {
      const pg = pageByN.get(pn);
      if (!pg) continue;
      const U = pg.text.toUpperCase();
      for (const m of U.matchAll(PAGE)) {
        const start = m.index;
        const end = start + m[0].length;
        const a = parseInt(m[1]!, 10);
        const b = m[2] ? parseInt(m[2], 10) : a;
        const ls = lineStart(U, start);
        const out = lastCue(U.slice(ls, start)) === 'TO';
        const targets: (typeof calcs)[number][] = [];
        for (let n = a; n <= Math.min(b, a + 50); n++) {
          const o = pageOwner.get(n);
          if (o && !o.front && o.key !== c.key && !targets.includes(o)) targets.push(o);
        }
        for (const o of targets) {
          const le = U.indexOf('\n', end);
          const ev: CalcEdgeEvidence = {
            calc: c.key,
            page: pn,
            text: pg.text.slice(start, end),
            line: pg.text.slice(ls, le >= 0 ? le : undefined),
            rects: rectsForSpan(pg, start, end),
          };
          if (out) add(c.key, o.key, 'page reference (output to)', ev);
          else add(o.key, c.key, 'page reference (input from)', ev);
        }
      }
    }
  }

  const designer = new Map<string, CalcLink>();
  for (const l of links) {
    if (l.tier !== 'xref' && l.status !== 'rejected') {
      const cur = designer.get(l.global_id);
      if (cur === undefined || l.conf > cur.conf) designer.set(l.global_id, l);
    }
  }
  for (const l of links) {
    if (l.tier !== 'xref' || l.status === 'rejected') continue;
    const d = designer.get(l.global_id);
    if (!d || l.page === null || !l.span) continue;
    const pg = pageByN.get(l.page);
    if (!pg) continue;
    const U = pg.text.toUpperCase();
    const ls = lineStart(U, l.span[0]);
    const toCue = lastCue(U.slice(ls, l.span[0])) === 'TO';
    const [src, dst] = toCue ? [l.calc_key, d.calc_key] : [d.calc_key, l.calc_key];
    add(src, dst, 'cross-reference (mentions an element the other calc designs)', {
      calc: l.calc_key,
      page: l.page,
      text: l.token,
      global_id: l.global_id,
      rects: l.rects,
    });
  }
  return [...edges.values()].sort((a, b) => cmpStr(a.src, b.src) || cmpStr(a.dst, b.dst));
}
