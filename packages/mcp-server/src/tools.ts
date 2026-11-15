/**
 * Tool bodies. Every answer is engine output (via ./engine.ts) on the loaded Project, reshaped for
 * reading: lookups, filters, sorting and pagination only, never a second implementation of a rule.
 * Every result carries `source` (model + the calc PDFs involved, with sha256, and the engine version).
 */
import {
  ENGINE_VERSION,
  exportMapping as engineExport,
  propagateImpact,
  rectsForSpan,
  type CalcEdgeEvidence,
  type CalcLink,
  type Decision,
  type DecisionAction,
  type ImpactMode,
  type ModelEdge,
  type Rect,
} from "./engine.ts";
import { renderPage, type PageImage } from "./pageImage.ts";
import type { CalcEdgeView, PdfDoc, Project } from "./project.ts";

export class ToolInputError extends Error {
  override name = "ToolInputError";
}

// ------------------------------------------------------------------ helpers

export interface Page<T> {
  total: number;
  offset: number;
  returned: number;
  next_offset: number | null;
  items: T[];
}

export function paginate<T>(all: readonly T[], offset = 0, limit = 50): Page<T> {
  const o = Math.max(0, offset);
  const items = all.slice(o, o + limit);
  return { total: all.length, offset: o, returned: items.length, next_offset: o + items.length < all.length ? o + items.length : null, items };
}

const cmp = (a: string, b: string) => (a < b ? -1 : a > b ? 1 : 0);
const norm = (s: string | null | undefined) => (s ?? "").toUpperCase().replace(/\s+/g, "").replace(/×/g, "X");
const lc = (s: string | null | undefined) => (s ?? "").toLowerCase();
const live = (l: CalcLink) => l.status !== "rejected";

function suggest(cands: string[], q: string, n = 8): string {
  const Q = q.toLowerCase();
  const hits = cands.filter((c) => c.toLowerCase().includes(Q) || Q.includes(c.toLowerCase())).slice(0, n);
  return hits.length ? ` Did you mean: ${hits.join(", ")}?` : "";
}

/** GlobalId, or a mark / name that names exactly one element. */
export function resolveElement(p: Project, id: string): string {
  if (typeof id !== "string" || !id.trim()) throw new ToolInputError("element id is required (a GlobalId or a mark)");
  const q = id.trim();
  if (p.elementById.has(q)) return q;
  const byMark = p.elements.filter((e) => e.mark && norm(e.mark) === norm(q));
  if (byMark.length === 1) return byMark[0]!.global_id;
  if (byMark.length > 1) {
    throw new ToolInputError(
      `mark "${q}" is on ${byMark.length} elements; pass a GlobalId: ` +
        byMark.slice(0, 20).map((e) => `${e.global_id} (${e.cat}, ${e.storey || "no storey"})`).join(", "),
    );
  }
  const byName = p.elements.filter((e) => e.name && lc(e.name) === lc(q));
  if (byName.length === 1) return byName[0]!.global_id;
  throw new ToolInputError(`no element with GlobalId or mark "${q}".${suggest([...new Set(p.elements.map((e) => e.mark).filter(Boolean))], q)} Use search_elements to find it.`);
}

export function resolveCalc(p: Project, key: string): string {
  if (typeof key !== "string" || !key.trim()) throw new ToolInputError("calc key is required");
  const q = key.trim();
  if (p.calcByKey.has(q)) return q;
  const ci = p.calcs.filter((c) => lc(c.key) === lc(q) || lc(c.title) === lc(q));
  if (ci.length === 1) return ci[0]!.key;
  throw new ToolInputError(`no calc "${q}".${suggest(p.calcs.map((c) => c.key), q)} Calc keys come from list_calcs / project_summary.`);
}

function elSummary(p: Project, gid: string) {
  const e = p.elementById.get(gid);
  const n = p.node(gid);
  return {
    global_id: gid,
    mark: e?.mark ?? n?.mark ?? "",
    name: e?.name ?? n?.name ?? "",
    kind: n?.kind ?? "",
    category: e?.cat ?? "",
    profile: e?.profile ?? "",
    storey: e?.storey ?? "",
    status: p.status.get(gid) ?? null,
  };
}

function pdfRef(pdf: PdfDoc | undefined) {
  return pdf ? { file: pdf.name, sha256: pdf.sha256, key_prefix: pdf.prefix } : null;
}

function linkView(p: Project, l: CalcLink) {
  const d = p.decisionFor(l.global_id, l.calc_key);
  return {
    global_id: l.global_id,
    calc_key: l.calc_key,
    calc_title: p.calcByKey.get(l.calc_key)?.title ?? "",
    pdf: pdfRef(p.pdfOfCalc.get(l.calc_key)),
    tier: l.tier,
    conf: l.conf,
    rule: l.rule,
    page: l.page,
    token: l.token,
    span: l.span,
    snippet: l.snippet,
    rects: l.rects,
    status: l.status ?? "auto",
    decision: d && d.action !== "undo"
      ? { action: d.action, decided_at: l.decided_at ?? d.at, decided_by: l.decided_by ?? d.actor ?? null, note: d.note ?? null }
      : null,
  };
}

const byConf = (a: CalcLink, b: CalcLink) => b.conf - a.conf || cmp(a.calc_key, b.calc_key) || cmp(a.global_id, b.global_id);

function edgeView(p: Project, e: CalcEdgeView) {
  const sp = p.pdfOfCalc.get(e.src);
  const dp = p.pdfOfCalc.get(e.dst);
  return {
    src: e.src,
    dst: e.dst,
    src_title: p.calcByKey.get(e.src)?.title ?? "",
    dst_title: p.calcByKey.get(e.dst)?.title ?? "",
    src_pdf: sp?.name ?? null,
    dst_pdf: dp?.name ?? null,
    cross_pdf: e.cross_pdf,
    rules: e.rules,
    evidence: e.evidence.map((ev: CalcEdgeEvidence) => ({ ...ev, pdf: p.pdfOfCalc.get(ev.calc)?.name ?? null })),
  };
}

function edgePdfs(p: Project, edges: readonly CalcEdgeView[]): PdfDoc[] {
  return edges.flatMap((e) => [p.pdfOfCalc.get(e.src), p.pdfOfCalc.get(e.dst)]).filter((x): x is PdfDoc => !!x);
}

// ------------------------------------------------------------------ project_summary

export function projectSummary(p: Project) {
  const stats = p.graph.stats();
  const storeys = p.graph
    .levels()
    .slice()
    .sort((a, b) => a.elevation - b.elevation)
    .map((l) => ({ name: l.name, elevation_m: l.elevation, elements: p.elements.filter((e) => e.storey === l.name).length }));
  const byCat: Record<string, number> = {};
  for (const e of p.elements) byCat[e.cat] = (byCat[e.cat] ?? 0) + 1;
  const byTier: Record<string, number> = {};
  const byStatus: Record<string, number> = {};
  for (const l of p.links) {
    byStatus[l.status ?? "auto"] = (byStatus[l.status ?? "auto"] ?? 0) + 1;
    if (live(l)) byTier[l.tier] = (byTier[l.tier] ?? 0) + 1;
  }
  const byRule: Record<string, number> = {};
  for (const e of p.calcEdges) for (const r of e.rules) byRule[r] = (byRule[r] ?? 0) + 1;
  return {
    project: { name: p.model.project, model_format: p.model.format, schema: p.model.schema },
    model: {
      file: p.model.name,
      sha256: p.model.sha256,
      elements: p.elements.length,
      nodes_by_kind: stats.nodesByKind,
      elements_by_category: byCat,
      connections: stats.nodesByKind["connection"] ?? 0,
      storeys,
      edges_by_kind: stats.edgesByKind,
      supports_edges: stats.edgesByKind["supports"] ?? 0,
      edges_by_rule: stats.edgesByRule,
    },
    calc_pdfs: p.pdfs.map((d) => ({
      file: d.name,
      sha256: d.sha256,
      key_prefix: d.prefix,
      main: d.index === 0,
      title: d.title,
      pages: d.pages.length,
      calcs: d.calcs.length,
      links: p.links.filter((l) => live(l) && p.pdfOfCalc.get(l.calc_key) === d).length,
      no_text_pages: d.noTextPages,
    })),
    calcs: p.calcs.map((c) => ({
      key: c.key,
      title: c.title,
      software: c.software,
      category: c.cat,
      pdf: p.pdfOfCalc.get(c.key)!.name,
      pages: c.pages,
      scanned: c.scanned,
      front_matter: c.front,
      links: (p.linksByCalc.get(c.key) ?? []).filter(live).length,
    })),
    links: { total: p.links.length, live: p.links.filter(live).length, by_tier: byTier, by_status: byStatus },
    element_status: p.counts,
    calc_edges: {
      total: p.calcEdges.length,
      within_pdf: p.calcEdges.filter((e) => !e.cross_pdf).length,
      cross_pdf: p.calcEdges.filter((e) => e.cross_pdf).length,
      by_rule: byRule,
    },
    decisions: {
      file: p.decisions?.name ?? null,
      writable: !!p.decisions,
      exists: p.decisions?.exists ?? false,
      entries: p.log.length,
      effective: p.effective.size,
      not_applied: p.unappliedDecisions,
      actor: p.actor,
    },
    warnings: p.warnings,
    source: p.source({ decisions: true }),
  };
}

// ------------------------------------------------------------------ search_elements

export interface SearchElementsArgs {
  query?: string;
  mark?: string;
  name?: string;
  kind?: string;
  category?: string;
  profile?: string;
  storey?: string;
  status?: "confirmed" | "review" | "unmapped";
  calc?: string;
  offset?: number;
  limit?: number;
}

export function searchElements(p: Project, a: SearchElementsArgs) {
  const calcKey = a.calc ? resolveCalc(p, a.calc) : null;
  const hits = p.elements.filter((e) => {
    const n = p.node(e.global_id);
    if (a.query) {
      const q = lc(a.query);
      const hay = [e.global_id, e.mark, e.name, e.profile, e.storey, n?.kind, e.cat, n?.source?.nativeType].map(lc);
      if (!hay.some((h) => h.includes(q)) && !norm(e.profile).includes(norm(a.query))) return false;
    }
    if (a.mark && !norm(e.mark).includes(norm(a.mark))) return false;
    if (a.name && !lc(e.name).includes(lc(a.name))) return false;
    if (a.kind && lc(n?.kind) !== lc(a.kind) && lc(n?.source?.nativeType) !== lc(a.kind)) return false;
    if (a.category && lc(e.cat) !== lc(a.category)) return false;
    if (a.profile && !norm(e.profile).includes(norm(a.profile))) return false;
    if (a.storey && !lc(e.storey).includes(lc(a.storey))) return false;
    if (a.status && p.status.get(e.global_id) !== a.status) return false;
    if (calcKey && !(p.linksByElement.get(e.global_id) ?? []).some((l) => live(l) && l.calc_key === calcKey)) return false;
    return true;
  });
  hits.sort((x, y) => cmp(x.mark || "￿", y.mark || "￿") || cmp(x.global_id, y.global_id));
  const page = paginate(hits, a.offset, a.limit ?? 50);
  return {
    ...page,
    items: page.items.map((e) => {
      const ls = (p.linksByElement.get(e.global_id) ?? []).filter(live).sort(byConf);
      const best = ls[0];
      return {
        ...elSummary(p, e.global_id),
        live_links: ls.length,
        best_link: best ? { calc_key: best.calc_key, tier: best.tier, conf: best.conf, status: best.status ?? "auto" } : null,
      };
    }),
    source: p.source(),
  };
}

// ------------------------------------------------------------------ get_element

function related(p: Project, from: string, ids: string[], kind?: string) {
  return ids.map((id) => ({
    ...elSummary(p, id),
    edges: p.graph
      .edgesBetween(from, id)
      .filter((e: ModelEdge) => kind === undefined || e.kind === kind)
      .map((e: ModelEdge) => ({ id: e.id, kind: e.kind, a: e.a, b: e.b, evidence: e.evidence })),
  }));
}

function hop(p: Project, m: Map<string, number>, self: string) {
  return [...m]
    .filter(([id, d]) => id !== self && d <= 1)
    .map(([id, d]) => ({ depth: d, ...elSummary(p, id) }))
    .sort((a, b) => a.depth - b.depth || cmp(a.mark, b.mark) || cmp(a.global_id, b.global_id));
}

export function getElement(p: Project, a: { id: string }) {
  const gid = resolveElement(p, a.id);
  const node = p.node(gid)!;
  const links = (p.linksByElement.get(gid) ?? []).slice().sort(byConf);
  const pdfs = links.map((l) => p.pdfOfCalc.get(l.calc_key)!).filter(Boolean);
  return {
    element: {
      ...elSummary(p, gid),
      material: node.material ?? null,
      level_id: node.levelId ?? null,
      ifc_type: node.source?.nativeType ?? null,
      params: node.params,
      geometry: node.geometry ?? null,
      source_ref: node.source,
    },
    status: p.status.get(gid),
    links: links.map((l) => linkView(p, l)),
    connectivity: {
      connections: related(p, gid, p.graph.connectionsOf(gid)),
      members: node.kind === "connection" ? related(p, gid, p.graph.membersOf(gid)) : [],
      parts: related(p, gid, p.graph.partsOf(gid), "part_of"),
      bears_on: related(p, gid, p.graph.supportsOf(gid), "supports"),
      carries: related(p, gid, p.graph.supportedBy(gid), "supports"),
      connected: related(p, gid, p.graph.connected(gid), "connects"),
    },
    load_path: {
      note: "one hop of loadPathDown / loadPathUp: connection nodes are pass-through, so the member beyond a connection shares its depth",
      down: hop(p, p.graph.loadPathDown(gid), gid),
      up: hop(p, p.graph.loadPathUp(gid), gid),
    },
    source: p.source({ pdfs, decisions: true }),
  };
}

// ------------------------------------------------------------------ list_calcs / get_calc

function calcItem(p: Project, key: string) {
  const c = p.calcByKey.get(key)!;
  const ls = (p.linksByCalc.get(key) ?? []).filter(live);
  const byTier: Record<string, number> = {};
  for (const l of ls) byTier[l.tier] = (byTier[l.tier] ?? 0) + 1;
  return {
    key: c.key,
    title: c.title,
    software: c.software,
    category: c.cat,
    pdf: pdfRef(p.pdfOfCalc.get(key)),
    pages: c.pages,
    scanned: c.scanned,
    front_matter: c.front,
    links: { live: ls.length, by_tier: byTier },
    elements: new Set(ls.map((l) => l.global_id)).size,
    feeds: p.calcEdges.filter((e) => e.src === key).length,
    fed_by: p.calcEdges.filter((e) => e.dst === key).length,
  };
}

export interface ListCalcsArgs {
  pdf?: string;
  category?: string;
  software?: string;
  query?: string;
  offset?: number;
  limit?: number;
}

export function listCalcs(p: Project, a: ListCalcsArgs) {
  const pdf = a.pdf ? p.pdfByName(a.pdf) : null;
  const hits = p.calcs.filter((c) => {
    if (pdf && p.pdfOfCalc.get(c.key) !== pdf) return false;
    if (a.category && lc(c.cat) !== lc(a.category)) return false;
    if (a.software && !lc(c.software).includes(lc(a.software))) return false;
    if (a.query && !lc(`${c.key} ${c.title}`).includes(lc(a.query))) return false;
    return true;
  });
  const page = paginate(hits, a.offset, a.limit ?? 100);
  return { ...page, items: page.items.map((c) => calcItem(p, c.key)), source: p.source({ pdfs: pdf ? [pdf] : "all" }) };
}

export interface GetCalcArgs {
  key: string;
  include_text?: boolean;
  page_offset?: number;
  page_limit?: number;
  element_offset?: number;
  element_limit?: number;
}

export function getCalc(p: Project, a: GetCalcArgs) {
  const key = resolveCalc(p, a.key);
  const c = p.calcByKey.get(key)!;
  const pdf = p.pdfOfCalc.get(key)!;
  const links = (p.linksByCalc.get(key) ?? []).slice().sort(byConf);
  const lp = paginate(links, a.element_offset, a.element_limit ?? 200);
  const feeds = p.calcEdges.filter((e) => e.src === key);
  const fedBy = p.calcEdges.filter((e) => e.dst === key);
  const out: Record<string, unknown> = {
    calc: calcItem(p, key),
    linked_elements: {
      ...lp,
      items: lp.items.map((l) => ({
        element: elSummary(p, l.global_id),
        tier: l.tier,
        conf: l.conf,
        rule: l.rule,
        page: l.page,
        token: l.token,
        status: l.status ?? "auto",
        decided_at: l.decided_at ?? null,
        decided_by: l.decided_by ?? null,
      })),
    },
    calc_edges: { feeds: feeds.map((e) => edgeView(p, e)), fed_by: fedBy.map((e) => edgeView(p, e)) },
  };
  if (a.include_text) {
    const pages = c.pages.map((n) => pdf.pages.find((pg) => pg.n === n)).filter((x): x is NonNullable<typeof x> => x !== undefined);
    const tp = paginate(pages, a.page_offset, a.page_limit ?? 5);
    out.text = { ...tp, items: tp.items.map((pg) => ({ page: pg.n, text: pg.text })) };
  }
  out.source = p.source({ pdfs: [pdf, ...edgePdfs(p, [...feeds, ...fedBy])], decisions: true });
  return out;
}

// ------------------------------------------------------------------ search_calc_text

export interface SearchTextArgs {
  query: string;
  pdf?: string;
  calc?: string;
  case_sensitive?: boolean;
  offset?: number;
  limit?: number;
}

export function searchCalcText(p: Project, a: SearchTextArgs) {
  if (!a.query || !a.query.trim()) throw new ToolInputError("query is required");
  const pdfs = a.pdf ? [p.pdfByName(a.pdf)] : p.pdfs;
  const calcKey = a.calc ? resolveCalc(p, a.calc) : null;
  const needle = a.case_sensitive ? a.query : a.query.toLowerCase();
  const hits: Array<{ pdf: PdfDoc; page: number; calc: string | null; start: number; end: number; text: string }> = [];
  for (const pdf of pdfs) {
    for (const pg of pdf.pages) {
      const owner = pdf.pageOwner.get(pg.n) ?? null;
      if (calcKey && owner !== calcKey) continue;
      const hay = a.case_sensitive ? pg.text : pg.text.toLowerCase();
      for (let i = hay.indexOf(needle); i >= 0; i = hay.indexOf(needle, i + Math.max(1, needle.length))) {
        hits.push({ pdf, page: pg.n, calc: owner, start: i, end: i + needle.length, text: pg.text });
      }
    }
  }
  const page = paginate(hits, a.offset, a.limit ?? 50);
  return {
    ...page,
    items: page.items.map((h) => {
      const pg = h.pdf.pages.find((x) => x.n === h.page)!;
      const s = Math.max(0, h.start - 70);
      const e = Math.min(h.text.length, h.end + 70);
      return {
        pdf: h.pdf.name,
        page: h.page,
        calc_key: h.calc,
        calc_title: h.calc ? (p.calcByKey.get(h.calc)?.title ?? "") : null,
        span: [h.start, h.end] as [number, number],
        snippet: {
          before: (s > 0 ? "…" : "") + h.text.slice(s, h.start),
          match: h.text.slice(h.start, h.end),
          after: h.text.slice(h.end, e) + (e < h.text.length ? "…" : ""),
        },
        rects: rectsForSpan(pg, h.start, h.end),
      };
    }),
    source: p.source({ pdfs }),
  };
}

// ------------------------------------------------------------------ trace_load_path

export interface TraceArgs {
  id: string;
  direction?: "down" | "up" | "both";
  max_depth?: number;
}

export function traceLoadPath(p: Project, a: TraceArgs) {
  const gid = resolveElement(p, a.id);
  const dir = a.direction ?? "down";
  const max = a.max_depth ?? 50;
  const walk = (m: Map<string, number>) => {
    const all = [...m].filter(([id]) => id !== gid);
    const kept = all
      .filter(([, d]) => d <= max)
      .map(([id, d]) => {
        const best = (p.linksByElement.get(id) ?? []).filter(live).sort(byConf)[0];
        return { depth: d, ...elSummary(p, id), best_calc: best ? { calc_key: best.calc_key, tier: best.tier, conf: best.conf } : null };
      })
      .sort((x, y) => x.depth - y.depth || cmp(x.mark, y.mark) || cmp(x.global_id, y.global_id));
    return { elements: kept, deepest: Math.max(0, ...all.map(([, d]) => d)), truncated: all.length > kept.length };
  };
  const down = dir !== "up" ? walk(p.graph.loadPathDown(gid)) : null;
  const up = dir !== "down" ? walk(p.graph.loadPathUp(gid)) : null;
  const visited = new Set([gid, ...(down?.elements ?? []).map((e) => e.global_id), ...(up?.elements ?? []).map((e) => e.global_id)]);
  const edges = p.graph.loadEdges().filter((e) => visited.has(e.src) && visited.has(e.dst));
  return {
    start: elSummary(p, gid),
    direction: dir,
    max_depth: max,
    note: "supports edges: src is supported by dst (load flows src -> dst). Connection nodes are pass-through for depth.",
    down,
    up,
    supports_edges: edges,
    source: p.source({ pdfs: [] }),
  };
}

// ------------------------------------------------------------------ calc_dependencies

export interface CalcDepsArgs {
  key?: string;
  depth?: number;
  direction?: "feeds" | "fed_by" | "both";
  cross_pdf_only?: boolean;
  offset?: number;
  limit?: number;
}

export function calcDependencies(p: Project, a: CalcDepsArgs) {
  let edges: CalcEdgeView[];
  let center: string | null = null;
  if (a.key) {
    center = resolveCalc(p, a.key);
    const depth = a.depth ?? 1;
    const dir = a.direction ?? "both";
    const seen = new Set([center]);
    const picked = new Set<CalcEdgeView>();
    let frontier = [center];
    for (let d = 0; d < depth && frontier.length; d++) {
      const next: string[] = [];
      for (const k of frontier) {
        for (const e of p.calcEdges) {
          const out = dir !== "fed_by" && e.src === k;
          const inn = dir !== "feeds" && e.dst === k;
          if (!out && !inn) continue;
          picked.add(e);
          const other = out ? e.dst : e.src;
          if (!seen.has(other)) {
            seen.add(other);
            next.push(other);
          }
        }
      }
      frontier = next;
    }
    edges = p.calcEdges.filter((e) => picked.has(e));
  } else {
    edges = p.calcEdges.slice();
  }
  if (a.cross_pdf_only) edges = edges.filter((e) => e.cross_pdf);
  const page = paginate(edges, a.offset, a.limit ?? 100);
  return {
    center,
    note: "edge src -> dst: the output of src feeds the input of dst. cross_pdf edges come only from the engine's cross-reference rule.",
    ...page,
    items: page.items.map((e) => edgeView(p, e)),
    source: p.source({ pdfs: center ? [p.pdfOfCalc.get(center)!, ...edgePdfs(p, edges)] : "all", decisions: true }),
  };
}

// ------------------------------------------------------------------ impact_of_change

export function impactOfChange(p: Project, a: { id: string; mode?: ImpactMode }) {
  const gid = resolveElement(p, a.id);
  const mode = a.mode ?? "change";
  const impact = propagateImpact(gid, mode, p.graph.loadEdges(), p.links, p.calcEdges, p.elementById);
  const stale = Object.entries(impact.stale).map(([k, reason]) => ({
    calc_key: k,
    title: p.calcByKey.get(k)?.title ?? "",
    pdf: p.pdfOfCalc.get(k)?.name ?? null,
    pages: p.calcByKey.get(k)?.pages ?? [],
    reason,
  }));
  return {
    element: elSummary(p, gid),
    mode,
    impact,
    removed: impact.removed.map((id) => ({ ...elSummary(p, id), why: impact.why[id] ?? null })),
    hit: Object.entries(impact.hit)
      .map(([id, wave]) => ({ wave, ...elSummary(p, id), why: impact.why[id] ?? null }))
      .sort((x, y) => x.wave - y.wave || cmp(x.mark, y.mark) || cmp(x.global_id, y.global_id)),
    stale_calcs: stale,
    counts: { removed: impact.removed.length, hit: Object.keys(impact.hit).length, waves: impact.waves, stale_calcs: stale.length },
    source: p.source({ pdfs: stale.map((s) => p.pdfOfCalc.get(s.calc_key)!).filter(Boolean), decisions: true }),
  };
}

// ------------------------------------------------------------------ review_status

export function reviewStatus(p: Project, a: { offset?: number; limit?: number; low_conf_below?: number }) {
  const thr = a.low_conf_below ?? 0.8;
  const limit = a.limit ?? 50;
  const review = p.elements.filter((e) => p.status.get(e.global_id) === "review");
  const unmapped = p.elements.filter((e) => p.status.get(e.global_id) === "unmapped");
  const low = p.links.filter((l) => live(l) && (l.status ?? "auto") === "auto" && l.conf < thr).sort((x, y) => x.conf - y.conf || cmp(x.calc_key, y.calc_key) || cmp(x.global_id, y.global_id));
  const rp = paginate(review, a.offset, limit);
  const up = paginate(unmapped, a.offset, limit);
  const lp = paginate(low, a.offset, limit);
  return {
    counts: p.counts,
    note: "status per element (engine statusOf): confirmed = a confirmed/manual link or one with conf >= 0.8; review = only lower-confidence live links; unmapped = no live link",
    needs_review: {
      ...rp,
      items: rp.items.map((e) => ({
        ...elSummary(p, e.global_id),
        links: (p.linksByElement.get(e.global_id) ?? []).filter(live).sort(byConf).map((l) => ({ calc_key: l.calc_key, tier: l.tier, conf: l.conf, page: l.page, token: l.token, rule: l.rule })),
      })),
    },
    unmapped: { ...up, items: up.items.map((e) => elSummary(p, e.global_id)) },
    low_confidence_links: {
      threshold: thr,
      ...lp,
      items: lp.items.map((l) => ({ element: elSummary(p, l.global_id), calc_key: l.calc_key, tier: l.tier, conf: l.conf, page: l.page, token: l.token, rule: l.rule })),
    },
    source: p.source({ decisions: true }),
  };
}

// ------------------------------------------------------------------ export_mapping

export function exportInput(p: Project) {
  return {
    model: p.model.name,
    modelRevision: p.model.sha256.slice(0, 12),
    calcPackage: p.pdfs.map((d) => d.name).join(" + "),
    calcRevision: p.pdfs.map((d) => d.sha256.slice(0, 12)).join(" + "),
    engine: ENGINE_VERSION,
    elements: p.elements.map((e) => ({ ...e, ifc_type: p.node(e.global_id)?.source?.nativeType ?? "" })),
    calcs: p.calcs,
    links: p.links,
    calcEdges: p.calcEdges,
    loadPath: p.graph.loadEdges(),
  };
}

export function exportMappingTool(p: Project, a: { element_offset?: number; element_limit?: number }) {
  const report = engineExport(exportInput(p));
  const out: Record<string, unknown> = { report };
  if (a.element_limit !== undefined || a.element_offset !== undefined) {
    const pg = paginate(report.elements, a.element_offset, a.element_limit ?? 100);
    out.report = { ...report, elements: pg.items };
    out.elements_page = { total: pg.total, offset: pg.offset, returned: pg.returned, next_offset: pg.next_offset };
  }
  out.calc_pdfs = p.pdfs.map((d) => ({ file: d.name, sha256: d.sha256, key_prefix: d.prefix, calcs: d.calcs.map((c) => c.key) }));
  out.source = p.source({ decisions: true });
  return out;
}

// ------------------------------------------------------------------ get_page_image

export interface PageImageArgs {
  pdf?: string;
  page?: number;
  global_id?: string;
  calc_key?: string;
  span?: [number, number];
  edge_src?: string;
  edge_dst?: string;
  evidence_index?: number;
  highlight?: number[][];
  crop?: boolean;
  tight?: boolean;
  padding?: number;
  rect?: number[];
  width?: number;
}

export async function getPageImage(p: Project, a: PageImageArgs): Promise<{ image: PageImage; meta: Record<string, unknown> }> {
  let pdf: PdfDoc;
  let page: number | undefined = a.page;
  let rects: Rect[] = [];
  let what: Record<string, unknown> = {};
  if (a.global_id || a.calc_key) {
    if (!a.global_id || !a.calc_key) throw new ToolInputError("pass both global_id and calc_key to highlight a link");
    const gid = resolveElement(p, a.global_id);
    const key = resolveCalc(p, a.calc_key);
    const l = (p.linksByElement.get(gid) ?? []).find((x) => x.calc_key === key);
    if (!l) throw new ToolInputError(`no link between ${gid} and calc ${key} (get_element lists an element's links)`);
    if (l.page === null) throw new ToolInputError(`the link ${gid} -> ${key} was made by hand and has no page evidence; pass page to see the calc`);
    pdf = p.pdfOfCalc.get(key)!;
    page ??= l.page;
    if (page === l.page) rects = l.rects.map((r) => [...r] as Rect);
    what = { link: { global_id: gid, calc_key: key, tier: l.tier, conf: l.conf, token: l.token } };
  } else if (a.edge_src || a.edge_dst) {
    if (!a.edge_src || !a.edge_dst) throw new ToolInputError("pass both edge_src and edge_dst to highlight calc-edge evidence");
    const src = resolveCalc(p, a.edge_src);
    const dst = resolveCalc(p, a.edge_dst);
    const e = p.calcEdges.find((x) => x.src === src && x.dst === dst);
    if (!e) throw new ToolInputError(`no calc edge ${src} -> ${dst} (calc_dependencies lists them)`);
    const i = a.evidence_index ?? 0;
    const ev = e.evidence[i];
    if (!ev) throw new ToolInputError(`calc edge ${src} -> ${dst} has ${e.evidence.length} evidence item(s); evidence_index ${i} is out of range`);
    if (ev.page === null) throw new ToolInputError(`that evidence has no page`);
    pdf = p.pdfOfCalc.get(ev.calc)!;
    page ??= ev.page;
    if (page === ev.page) rects = ev.rects.map((r) => [...r] as Rect);
    what = { calc_edge: { src, dst, evidence_index: i, rules: e.rules, text: ev.text } };
  } else {
    pdf = p.pdfByName(a.pdf);
    if (page === undefined) throw new ToolInputError("page is required (or pass global_id + calc_key, or edge_src + edge_dst, to take the page from the evidence)");
  }
  if (a.pdf && (a.global_id || a.edge_src) && p.pdfByName(a.pdf) !== pdf) {
    throw new ToolInputError(`the evidence is in ${pdf.name}, not ${a.pdf}`);
  }
  if (page === undefined) throw new ToolInputError("page is required");
  const pg = pdf.pages.find((x) => x.n === page);
  if (!pg) throw new ToolInputError(`page ${page} is not in ${pdf.name} (pages 1-${pdf.pages.length}). Page numbers are per PDF.`);
  if (a.span) {
    const [s, e] = a.span;
    if (!(Number.isInteger(s) && Number.isInteger(e) && s >= 0 && e > s && e <= pg.text.length)) {
      throw new ToolInputError(`span must be [start, end) within the page text (0..${pg.text.length})`);
    }
    rects.push(...rectsForSpan(pg, s, e));
    what.span = a.span;
  }
  for (const r of a.highlight ?? []) {
    if (r.length !== 4) throw new ToolInputError("each highlight must be [x0, y0, x1, y1] in PDF points");
    rects.push([r[0]!, r[1]!, r[2]!, r[3]!]);
  }
  let crop: number[] | null = a.rect ?? null;
  if (!crop && a.crop !== false && rects.length && (a.crop === true || what.link || what.calc_edge || what.span)) {
    // full-width band around the evidence (the whole line reads in context); tight = pad all four sides
    const pad = a.padding ?? 48;
    crop = [
      a.tight ? Math.min(...rects.map((r) => r[0])) - pad : 0,
      Math.min(...rects.map((r) => r[1])) - pad,
      a.tight ? Math.max(...rects.map((r) => r[2])) + pad : pg.width,
      Math.max(...rects.map((r) => r[3])) + pad,
    ];
  }
  const image = await renderPage(pdf.bytes, page, { rect: crop, highlight: rects, width: a.width ?? null });
  const owner = pdf.pageOwner.get(page) ?? null;
  return {
    image,
    meta: {
      pdf: pdf.name,
      page,
      page_count: pdf.pages.length,
      calc_key: owner,
      calc_title: owner ? (p.calcByKey.get(owner)?.title ?? "") : null,
      ...what,
      highlight: rects,
      area_pt: image.area,
      pixels: [image.width, image.height],
      scale_px_per_pt: image.scale,
      frame: "PDF points, origin top-left, y down",
      source: p.source({ pdfs: [pdf] }),
    },
  };
}

// ------------------------------------------------------------------ record_decision(s)

export interface DecisionInput {
  global_id: string;
  calc_key: string;
  action: DecisionAction;
  note?: string | null;
}

export const READ_ONLY_MESSAGE =
  "This server is read-only: it was started without --decisions. Add `--decisions /absolute/path/to/decisions.json` " +
  "to the server's args in your MCP client config (the file is created on the first decision) and restart the server.";

const pk = (g: string, k: string) => `${g}\u0000${k}`;

/** Validate and append decisions (all or none). */
export async function recordDecisions(p: Project, a: { decisions: DecisionInput[] }) {
  const store = p.decisions;
  if (!store) throw new ToolInputError(READ_ONLY_MESSAGE);
  if (!Array.isArray(a.decisions) || !a.decisions.length) throw new ToolInputError("decisions must be a non-empty array");
  if (a.decisions.length > 500) throw new ToolInputError("at most 500 decisions per call");
  const before = new Map<string, { link: ReturnType<typeof brief>; status: string | undefined }>();
  const rawPairs = new Set(p.rawLinks.map((l) => pk(l.global_id, l.calc_key)));

  const { appended, reloaded } = await store.append((current) => {
    const errors: string[] = [];
    // effective decision per pair as the log stands, updated as the batch is simulated
    const eff = new Map<string, Decision>();
    for (const d of current) eff.set(pk(d.global_id, d.calc_key), d);
    const at = new Date().toISOString();
    const out: Decision[] = [];
    a.decisions.forEach((d, i) => {
      const tag = a.decisions.length > 1 ? `decision ${i}: ` : "";
      if (!["confirm", "reject", "manual", "undo"].includes(d.action)) {
        errors.push(`${tag}action must be confirm, reject, manual or undo`);
        return;
      }
      if (!p.gids.has(d.global_id)) {
        const marks = p.elements.filter((e) => e.mark && norm(e.mark) === norm(d.global_id ?? ""));
        errors.push(
          `${tag}no element with GlobalId "${d.global_id}"` +
            (marks.length ? ` ("${d.global_id}" is a mark; its GlobalId is ${marks.map((e) => e.global_id).join(" or ")})` : ""),
        );
        return;
      }
      if (!p.calcKeys.has(d.calc_key)) {
        errors.push(`${tag}no calc "${d.calc_key}".${suggest(p.calcs.map((c) => c.key), d.calc_key ?? "")}`);
        return;
      }
      const key = pk(d.global_id, d.calc_key);
      if ((d.action === "confirm" || d.action === "reject") && !rawPairs.has(key)) {
        const manual = eff.get(key)?.action === "manual";
        errors.push(
          `${tag}there is no automatic link between ${d.global_id} and ${d.calc_key} to ${d.action}` +
            (manual ? " (it was linked by hand: use undo to remove that)" : "; use manual to link them by hand"),
        );
        return;
      }
      if (d.action === "undo") {
        const cur = eff.get(key);
        if (!cur || cur.action === "undo") {
          errors.push(`${tag}there is no decision on ${d.global_id} / ${d.calc_key} to undo`);
          return;
        }
      }
      if (d.note !== undefined && d.note !== null && typeof d.note !== "string") {
        errors.push(`${tag}note must be a string`);
        return;
      }
      const rec: Decision = { global_id: d.global_id, calc_key: d.calc_key, action: d.action, at, actor: p.actor, note: d.note ?? null };
      out.push(rec);
      eff.set(key, rec);
    });
    if (errors.length) throw new ToolInputError(`nothing was written:\n- ${errors.join("\n- ")}`);
    // capture the state before applying (after any reload of external changes)
    if (store.log !== p.computedLog) p.recompute();
    for (const d of out) {
      const l = (p.linksByElement.get(d.global_id) ?? []).find((x) => x.calc_key === d.calc_key);
      before.set(pk(d.global_id, d.calc_key), { link: brief(l), status: p.status.get(d.global_id) });
    }
    return out;
  });
  p.recompute();
  return {
    recorded: appended.map((d) => {
      const l = (p.linksByElement.get(d.global_id) ?? []).find((x) => x.calc_key === d.calc_key);
      const b = before.get(pk(d.global_id, d.calc_key));
      return {
        decision: d,
        element: elSummary(p, d.global_id),
        link_before: b?.link ?? null,
        link_after: brief(l),
        status_before: b?.status ?? null,
        status_after: p.status.get(d.global_id) ?? null,
      };
    }),
    reloaded_external_changes: reloaded,
    element_status: p.counts,
    source: p.source({ pdfs: appended.map((d) => p.pdfOfCalc.get(d.calc_key)!).filter(Boolean), decisions: true }),
  };
}

function brief(l: CalcLink | undefined) {
  return l ? { tier: l.tier, conf: l.conf, status: l.status ?? "auto", decided_at: l.decided_at ?? null, decided_by: l.decided_by ?? null } : null;
}

export function decisionsLog(p: Project) {
  return {
    file: p.decisions?.path ?? null,
    writable: !!p.decisions,
    entries: p.log,
    source: p.source({ decisions: true, pdfs: [] }),
  };
}
