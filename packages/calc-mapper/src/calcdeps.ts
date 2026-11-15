/**
 * Calc dependency graph: the output of one calc feeds the input of another. Port of the
 * reference calcdeps.infer(); two deterministic rules, each edge keeps its evidence:
 *
 * 1. page reference - "page 7", "pages 5-8", "p. 12" inside a calc points at the calc that holds
 *    that page. Direction from the nearest cue word earlier on the same line: "to" means this
 *    calc's output goes TO that page's calc (this -> that); "from" / "per" / "see" / "using" or
 *    no cue means it is an input (that -> this).
 * 2. cross-reference - a calc that mentions (xref tier) an element designed by another calc takes
 *    that calc's output as input (designer -> this), unless the same line has a "to" cue before
 *    the mention ("carried to ST-1 design"), then this -> designer.
 */
import { rectsForSpan } from "./pdf.ts";
import type { Calc, CalcEdge, CalcEdgeEvidence, CalcPage, Link } from "./types.ts";

const PAGE = /\b(?:PAGES?|PP?\.)\s*(\d{1,4})(?:\s*(?:-|–|TO)\s*(\d{1,4}))?/g;
const CUE = /\b(FROM|PER|SEE|USING|TO)\b/g;

const lineStart = (U: string, i: number): number => (i > 0 ? U.lastIndexOf("\n", i - 1) + 1 : 0);
const lastCue = (s: string): string | undefined => [...s.matchAll(CUE)].pop()?.[1];
const cmp = (p: string, q: string): number => (p < q ? -1 : p > q ? 1 : 0);

export function inferCalcEdges(calcs: Calc[], pages: CalcPage[], links: Link[]): CalcEdge[] {
  const pageOwner = new Map<number, Calc>();
  for (const c of calcs) for (const n of c.pages) pageOwner.set(n, c);
  const pageByN = new Map(pages.map((p) => [p.n, p]));
  const edges = new Map<string, CalcEdge>();
  const add = (src: string, dst: string, rule: string, ev: CalcEdgeEvidence) => {
    if (src === dst) return;
    const k = `${src}\u0000${dst}`;
    let e = edges.get(k);
    if (!e) edges.set(k, (e = { src, dst, rules: [], evidence: [] }));
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
        const a = Number(m[1]);
        const b = Number(m[2] ?? a);
        const start = m.index, end = m.index + m[0].length;
        const ls = lineStart(U, start);
        const out = lastCue(U.slice(ls, start)) === "TO";
        const targets: Calc[] = [];
        for (let n = a; n <= Math.min(b, a + 50); n++) {
          const o = pageOwner.get(n);
          if (o && !o.front && o.key !== c.key && !targets.includes(o)) targets.push(o);
        }
        for (const o of targets) {
          const le = U.indexOf("\n", end);
          const ev: CalcEdgeEvidence = {
            calc: c.key, page: pn, text: pg.text.slice(start, end), line: pg.text.slice(ls, le >= 0 ? le : undefined),
            rects: rectsForSpan(pg, start, end),
          };
          if (out) add(c.key, o.key, "page reference (output to)", ev);
          else add(o.key, c.key, "page reference (input from)", ev);
        }
      }
    }
  }

  const designer = new Map<string, Link>();
  for (const l of links) {
    if (l.tier !== "xref" && l.status !== "rejected") {
      const cur = designer.get(l.global_id);
      if (!cur || l.conf > cur.conf) designer.set(l.global_id, l);
    }
  }
  for (const l of links) {
    const d = designer.get(l.global_id);
    if (l.tier !== "xref" || l.status === "rejected" || !d || l.page === null || !l.span) continue;
    const pg = pageByN.get(l.page);
    if (!pg) continue;
    const U = pg.text.toUpperCase();
    const ls = lineStart(U, l.span[0]);
    const to = lastCue(U.slice(ls, l.span[0])) === "TO";
    const [src, dst] = to ? [l.calc_key, d.calc_key] : [d.calc_key, l.calc_key];
    add(src, dst, "cross-reference (mentions an element the other calc designs)",
      { calc: l.calc_key, page: l.page, text: l.token, global_id: l.global_id, rects: l.rects });
  }
  return [...edges.values()].sort((p, q) => cmp(p.src, q.src) || cmp(p.dst, q.dst));
}
