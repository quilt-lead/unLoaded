/**
 * Calc dependency graph: the output of one calc feeds the input of another. Port of the
 * reference calcdeps.infer(); two deterministic rules, each edge keeps its evidence:
 *
 * 1. page reference - "page 7", "pages 5-8", "p. 12" inside a calc points at the calc that holds
 *    that page. Direction from the nearest cue word earlier on the same line: "to" means this
 *    calc's output goes TO that page's calc (this -> that); "from" / "per" / "see" / "using" or
 *    no cue means it is an input (that -> this). A page NUMBER is not a reference (`pageReferences`):
 *    "Page 7 of 40", "Page 2/5", or a bare "Page 7" ending its line with no cue word before it (a
 *    running footer / header, often the calc software's own numbering, not the PDF's).
 * 2. cross-reference - a calc that mentions (xref tier) an element designed by another calc takes
 *    that calc's output as input (designer -> this), unless the same line has a "to" cue before
 *    the mention ("carried to ST-1 design"), then this -> designer. The designer is `designerOf`.
 *
 * Provenance: producer calc-mapper/calcdeps, rule = the ids of the edge's rules joined with "+"
 * (`calcdeps.page-reference.input|output`, `calcdeps.cross-reference`), inputs = the PDF of every
 * page the evidence sits on, plus, for a cross-reference, the inputs of the links it was read from.
 */
import { rectsForSpan } from "./pdf.ts";
import { RULES, inputList, ruleProvenance } from "./provenance.ts";
import { calcRegions } from "./segment.ts";
import { foldText } from "./text.ts";
import type { Calc, CalcEdge, CalcEdgeEvidence, CalcPage, Link } from "./types.ts";

// text is read folded (text.ts), so "-" is the only dash
const PAGE = /\b(?:PAGES?|PP?\.)\s*(\d{1,4})(?:\s*(?:-|TO)\s*(\d{1,4}))?/g;
const CUE = /\b(FROM|PER|SEE|USING|TO)\b/g;
/** "of 40" / "/ 5" right after a page number: pagination ("Page 7 of 40", "Page 2/5"), not a reference. */
const PAGINATION = /^\s*(?:OF|\/)\s*\d/;

const lineStart = (U: string, i: number): number => (i > 0 ? U.lastIndexOf("\n", i - 1) + 1 : 0);
const lineEnd = (U: string, i: number): number => {
  const e = U.indexOf("\n", i);
  return e >= 0 ? e : U.length;
};
const lastCue = (s: string): string | undefined => [...s.matchAll(CUE)].pop()?.[1];
const cmp = (p: string, q: string): number => (p < q ? -1 : p > q ? 1 : 0);

/** A page reference in folded text: [start, end), the pages it names (a..b) and the cue word before it on its line. */
export interface PageReference {
  start: number;
  end: number;
  from: number;
  to: number;
  cue: string | undefined;
}

/**
 * The page REFERENCES in folded text (text.ts `foldText`): every "page 7" / "pages 5-8" / "p. 12"
 * except page numbers - one followed by "of N" or "/N", or a bare one that ends its line with no cue
 * word before it on that line (a running footer such as "RISA-3D Version 19 ... Page 3").
 */
export function pageReferences(U: string): PageReference[] {
  const out: PageReference[] = [];
  for (const m of U.matchAll(PAGE)) {
    const start = m.index, end = m.index + m[0].length;
    const le = lineEnd(U, end);
    if (PAGINATION.test(U.slice(end, le))) continue;
    const cue = lastCue(U.slice(lineStart(U, start), start));
    if (!cue && !U.slice(end, le).trim()) continue;
    const from = Number(m[1]);
    out.push({ start, end, from, to: Number(m[2] ?? from), cue });
  }
  return out;
}

const tierConf = (l: Link): number => (l.evidence?.[0]?.kind === "tier" ? l.evidence[0].weight : l.conf);
/** Design before loads (a link without a role - an older stored one - counts as design, as statusOf reads it). */
const roleRank = (l: Link): number => ((l.role ?? "design") === "design" ? 0 : 1);

/**
 * The calc that designs each element: among its live (not rejected), non-xref links, a design-role
 * link beats a loads-role one; then the higher TIER confidence (evidence item 1, as the reference
 * engine ranked); then the smaller calc key. The order of `links` never matters.
 */
export function designerOf(links: readonly Link[]): Map<string, Link> {
  const better = (l: Link, cur: Link): boolean =>
    (roleRank(l) - roleRank(cur) || tierConf(cur) - tierConf(l) || cmp(l.calc_key, cur.calc_key)) < 0;
  const designer = new Map<string, Link>();
  for (const l of links) {
    if (l.tier === "xref" || l.status === "rejected") continue;
    const cur = designer.get(l.global_id);
    if (!cur || better(l, cur)) designer.set(l.global_id, l);
  }
  return designer;
}

export function inferCalcEdges(calcs: Calc[], pages: CalcPage[], links: Link[]): CalcEdge[] {
  // "page 7" points at the calc that holds page 7 (with a page shared by two calcs: the one that starts it)
  const pageOwner = new Map<number, Calc>();
  for (const c of calcs) {
    for (const r of calcRegions(c, pages)) if (!pageOwner.has(r.page) || r.start === 0) pageOwner.set(r.page, c);
  }
  const pageByN = new Map(pages.map((p) => [p.n, p]));
  const edges = new Map<string, Omit<CalcEdge, "provenance"> & { ruleIds: string[]; inputs: string[] }>();
  const add = (src: string, dst: string, rule: string, ruleId: string, ev: CalcEdgeEvidence, inputs: readonly string[]) => {
    if (src === dst) return;
    const k = `${src}\u0000${dst}`;
    let e = edges.get(k);
    if (!e) edges.set(k, (e = { src, dst, rules: [], evidence: [], ruleIds: [], inputs: [] }));
    if (!e.rules.includes(rule)) e.rules.push(rule);
    if (!e.ruleIds.includes(ruleId)) e.ruleIds.push(ruleId);
    e.inputs = inputList(e.inputs, inputs);
    if (e.evidence.length < 6) e.evidence.push(ev);
  };

  for (const c of calcs) {
    if (c.front || c.scanned) continue;
    for (const r of calcRegions(c, pages)) {
      const pn = r.page;
      const pg = pageByN.get(pn);
      if (!pg) continue;
      const U = foldText(pg.text);
      for (const { start, end, from: a, to: b, cue } of pageReferences(U)) {
        if (start < r.start || end > r.end) continue;
        const ls = lineStart(U, start);
        const out = cue === "TO";
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
          if (out) add(c.key, o.key, "page reference (output to)", RULES.calcdeps.pageOutput, ev, [pg.doc_sha256]);
          else add(o.key, c.key, "page reference (input from)", RULES.calcdeps.pageInput, ev, [pg.doc_sha256]);
        }
      }
    }
  }

  const designer = designerOf(links);
  for (const l of links) {
    const d = designer.get(l.global_id);
    if (l.tier !== "xref" || l.status === "rejected" || !d || l.page === null || !l.span) continue;
    const pg = pageByN.get(l.page);
    if (!pg) continue;
    const U = foldText(pg.text);
    const ls = lineStart(U, l.span[0]);
    const to = lastCue(U.slice(ls, l.span[0])) === "TO";
    const [src, dst] = to ? [l.calc_key, d.calc_key] : [d.calc_key, l.calc_key];
    add(src, dst, "cross-reference (mentions an element the other calc designs)", RULES.calcdeps.crossReference,
      { calc: l.calc_key, page: l.page, text: l.token, global_id: l.global_id, rects: l.rects },
      [...l.provenance.inputs, pg.doc_sha256, ...d.provenance.inputs]);
  }
  return [...edges.values()]
    .map(({ ruleIds, inputs, ...e }): CalcEdge => ({ ...e, provenance: ruleProvenance("calcdeps", ruleIds.join("+"), inputs) }))
    .sort((p, q) => cmp(p.src, q.src) || cmp(p.dst, q.dst));
}
