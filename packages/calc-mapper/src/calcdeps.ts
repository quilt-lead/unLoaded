/**
 * Calc dependency graph: the output of one calc feeds the input of another. Port of the
 * reference calcdeps.infer(); two deterministic rules, each edge keeps its evidence:
 *
 * 1. page reference - "page 7", "pages 5-8", "p. 12" inside a calc points at the calc that holds
 *    that page. Direction from the nearest cue word earlier on the same line: "to" means this
 *    calc's output goes TO that page's calc (this -> that); "from" / "per" / "see" / "using" or
 *    no cue means it is an input (that -> this). A page NUMBER is not a reference (`pageReferences`):
 *    "Page 7 of 40", "Page 2/5", or one on a running header / footer - a line in the top or bottom
 *    band that recurs on other pages with only its page number changed (`runningLines`, detected per
 *    document; often the calc software's own numbering, not the PDF's).
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
/** How many non-empty lines at the top and at the bottom of a page make its header / footer band. */
export const RUNNING_BAND = 3;

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

/** The non-empty lines of a page's top and bottom bands: [start offset, band, text] (a line can be in both). */
function bandLines(U: string): [number, "top" | "bottom", string][] {
  const lines: [number, string][] = [];
  let pos = 0;
  for (const line of U.split("\n")) {
    if (line.trim()) lines.push([pos, line]);
    pos += line.length + 1;
  }
  const top = lines.slice(0, RUNNING_BAND).map(([st, t]) => [st, "top", t] as [number, "top", string]);
  // a short page's line can sit in both bands (a two-line page: its footer is also among its first lines)
  const bottom = lines.slice(-RUNNING_BAND).map(([st, t]) => [st, "bottom", t] as [number, "bottom", string]);
  return [...top, ...bottom];
}

/** A band line with its page numbers blanked: two pages' running lines differ in nothing else. */
const runningKey = (band: string, line: string): string =>
  `${band}\u0000${line.replace(PAGE, (m) => m.replace(/\d+/g, "#")).replace(/\s+/g, " ").trim()}`;

/**
 * The running headers / footers of one document, detected from the document itself: a line in a
 * page's top or bottom band (RUNNING_BAND non-empty lines) that names a page and recurs in the same
 * band on another page with only its page numbers changed ("RISA-3D Version 19 ... Page 3",
 * "Designed per AISC 360-16    Page 3", "Page 4   Project: ..."). Returns, per page number, the line
 * starts (offsets in the folded page text) of its running lines. A cue word on such a line does not
 * make it a reference; a line that names a page and does not recur stays one.
 */
export function runningLines(pages: readonly Pick<CalcPage, "n" | "text">[]): Map<number, Set<number>> {
  const seen = new Map<string, { pages: Set<number>; at: [number, number][] }>();
  for (const pg of pages) {
    const U = foldText(pg.text);
    for (const [st, band, line] of bandLines(U)) {
      if (line.search(PAGE) < 0) continue;
      const k = runningKey(band, line);
      let e = seen.get(k);
      if (!e) seen.set(k, (e = { pages: new Set(), at: [] }));
      e.pages.add(pg.n);
      e.at.push([pg.n, st]);
    }
  }
  const out = new Map<number, Set<number>>();
  for (const { pages: ps, at } of seen.values()) {
    if (ps.size < 2) continue;
    for (const [n, st] of at) {
      let s = out.get(n);
      if (!s) out.set(n, (s = new Set()));
      s.add(st);
    }
  }
  return out;
}

/**
 * The page REFERENCES in folded text (text.ts `foldText`): every "page 7" / "pages 5-8" / "p. 12"
 * except page numbers - one followed by "of N" or "/N" (pagination), or one on a running header /
 * footer line (`running`: the line starts `runningLines` found for this page). Anything else that
 * names a page is a reference, cue word or not ("max end reaction: page 7").
 */
export function pageReferences(U: string, running: ReadonlySet<number> = new Set()): PageReference[] {
  const out: PageReference[] = [];
  for (const m of U.matchAll(PAGE)) {
    const start = m.index, end = m.index + m[0].length;
    if (PAGINATION.test(U.slice(end, lineEnd(U, end)))) continue;
    const ls = lineStart(U, start);
    if (running.has(ls)) continue;
    const from = Number(m[1]);
    out.push({ start, end, from, to: Number(m[2] ?? from), cue: lastCue(U.slice(ls, start)) });
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
  // A calc SET (calcset.ts) holds several PDFs with set page numbers: a page reference names a page of
  // the referring page's own PDF. Each document's pages are numbered 1..n shifted by its offset, so the
  // offset is its lowest page number - 1 (0 for a single PDF: references resolve as before).
  const docPages = new Map<string, CalcPage[]>();
  for (const p of pages) (docPages.get(p.doc_sha256) ?? docPages.set(p.doc_sha256, []).get(p.doc_sha256)!).push(p);
  const docRange = new Map<string, { offset: number; last: number }>();
  for (const [sha, ps] of docPages) {
    const ns = ps.map((p) => p.n);
    docRange.set(sha, { offset: Math.min(...ns) - 1, last: Math.max(...ns) });
  }
  // running headers / footers are detected over each whole document, not page by page
  const running = new Map<number, Set<number>>();
  for (const ps of docPages.values()) for (const [n, s] of runningLines(ps)) running.set(n, s);
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
      for (const { start, end, from: a, to: b, cue } of pageReferences(U, running.get(pn))) {
        if (start < r.start || end > r.end) continue;
        const ls = lineStart(U, start);
        const out = cue === "TO";
        const targets: Calc[] = [];
        const dr = docRange.get(pg.doc_sha256) ?? { offset: 0, last: Infinity };
        for (let n = a; n <= Math.min(b, a + 50); n++) {
          if (n + dr.offset > dr.last) break;
          const o = pageOwner.get(n + dr.offset);
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
