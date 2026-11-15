/**
 * Tool bodies. Every answer is engine output (via ./engine.ts) on the loaded Project, reshaped for
 * reading: lookups, filters, sorting and pagination only, never a second implementation of a rule.
 * The engine's records are passed through with their own fields (links with role / band / weighted
 * evidence / caveats / provenance, calc edges, findings, typical groups, impact, compare, move
 * impact). Every result carries `source` (the model and the calc PDFs involved, with sha256, the
 * project file when there is one, and the engine version).
 */
import {
  CONFIDENCE_BANDS,
  DECISION_ACTIONS,
  ENGINE_PRODUCERS,
  ENGINE_VERSION,
  buildExport,
  calcRegions,
  diffGraphs,
  moveColumn as engineMoveColumn,
  nextDecision,
  propagateImpact,
  rectsForSpan,
  type Calc,
  type Decision,
  type DecisionAction,
  type DecisionFields,
  type ImpactMode,
  type Link,
  type ModelEdge,
  type Move,
  type Rect,
} from "./engine.ts";
import { renderPage, type PageImage } from "./pageImage.ts";
import { maxOf, minOf, type CalcEdgeView, type PdfDoc, type Project } from "./project.ts";

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
const live = (l: Link) => l.status !== "rejected";

function countBy<T>(xs: readonly T[], key: (x: T) => string): Record<string, number> {
  const out: Record<string, number> = {};
  for (const x of xs) {
    const k = key(x) || "(none)";
    out[k] = (out[k] ?? 0) + 1;
  }
  return out;
}

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

/** The key of a calc ref "<docId>#<key>" without its document. */
const bareKey = (ref: string) => ref.slice(ref.indexOf("#") + 1);

/** A calc ref, a bare key that exactly one PDF has, or a title that names exactly one calc. */
export function resolveCalc(p: Project, key: string): string {
  if (typeof key !== "string" || !key.trim()) throw new ToolInputError("calc key is required");
  const q = key.trim();
  if (p.calcByKey.has(q)) return q;
  const bare = p.calcs.filter((c) => lc(bareKey(c.key)) === lc(q));
  if (bare.length === 1) return bare[0]!.key;
  if (bare.length > 1) {
    throw new ToolInputError(`calc key "${q}" is in ${bare.length} calc PDFs: name one (${bare.map((c) => c.key).join(", ")})`);
  }
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

/** A decision of the applied log, named by its origin and its id there (never the engine's shifted id). */
function decisionView(p: Project, d: DecisionFields | undefined) {
  if (!d) return null;
  const { origin, id } = p.decisionRef(d);
  return { origin, id, action: d.action, at: d.at, actor: d.actor ?? null, note: d.note ?? null };
}

/** An engine link with its calc title, PDF and effective decision. Every engine field is kept. */
function linkView(p: Project, l: Link) {
  const d = p.decisionFor(l.global_id, l.calc_key);
  return {
    global_id: l.global_id,
    calc_key: l.calc_key,
    calc_title: p.calcByKey.get(l.calc_key)?.title ?? "",
    pdf: pdfRef(p.pdfOfCalc.get(l.calc_key)),
    tier: l.tier,
    conf: l.conf,
    band: l.band,
    role: l.role,
    rule: l.rule,
    page: l.page,
    token: l.token,
    span: l.span,
    snippet: l.snippet,
    rects: l.rects,
    status: l.status ?? "auto",
    reasons: l.evidence,
    caveats: l.caveats,
    ...(l.via_group ? { via_group: l.via_group } : {}),
    provenance: l.provenance,
    ...(l.review_provenance ? { review_provenance: l.review_provenance } : {}),
    decision: d ? { ...decisionView(p, d)!, decided_at: l.decided_at ?? d.at, decided_by: l.decided_by ?? d.actor ?? null } : null,
  };
}

const byConf = (a: Link, b: Link) => b.conf - a.conf || cmp(a.calc_key, b.calc_key) || cmp(a.global_id, b.global_id);

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
    evidence: e.evidence.map((ev) => ({ ...ev, pdf: p.pdfOfCalc.get(ev.calc)?.name ?? null })),
    provenance: e.provenance,
  };
}

function edgePdfs(p: Project, edges: readonly CalcEdgeView[]): PdfDoc[] {
  return edges.flatMap((e) => [p.pdfOfCalc.get(e.src), p.pdfOfCalc.get(e.dst)]).filter((x): x is PdfDoc => !!x);
}

/**
 * The calc whose region (the engine's `calcRegions`) of `page` holds `offset`; with offset null, the
 * calc that starts the page, else the only calc on it. null when no calc, or more than one, fits:
 * never a guess (text between two calcs' regions belongs to neither).
 */
export function calcAt(pdf: PdfDoc, page: number, offset: number | null): Calc | null {
  const fits = pdf.calcs.filter((c) =>
    calcRegions(c, pdf.pages).some((r) => r.page === page && (offset === null ? r.start === 0 : r.start <= offset && offset < r.end)),
  );
  if (fits.length === 1) return fits[0]!;
  if (offset === null && !fits.length) {
    const on = pdf.calcs.filter((c) => c.pages.includes(page));
    return on.length === 1 ? on[0]! : null;
  }
  return null;
}

/** Every PDF holding one of these calc keys (for a result's `source` block). */
function pdfsOf(p: Project, keys: Iterable<string | null | undefined>): PdfDoc[] {
  const out: PdfDoc[] = [];
  for (const k of keys) {
    const d = k ? p.pdfOfCalc.get(k) : undefined;
    if (d) out.push(d);
  }
  return out;
}

function modelRevisions(p: Project) {
  return p.models.map((m) => ({
    revision: m.revision,
    label: m.label,
    file: m.name,
    sha256: m.sha256,
    graph_sha256: m.model.graphSha256,
    format: m.model.format,
    elements: m.model.elements().length,
    current: m === p.current,
  }));
}

// ------------------------------------------------------------------ project_summary

export function projectSummary(p: Project) {
  const stats = p.graph.stats();
  const storeys = p.graph
    .levels()
    .slice()
    .sort((a, b) => a.elevation - b.elevation)
    .map((l) => ({ name: l.name, elevation_m: l.elevation, elements: p.elements.filter((e) => e.storey === l.name).length }));
  const liveLinks = p.links.filter(live);
  const byRule: Record<string, number> = {};
  for (const e of p.calcEdges) for (const r of e.rules) byRule[r] = (byRule[r] ?? 0) + 1;
  const linkedGroups = new Set(p.groupLinks.map((g) => g.group));
  return {
    project: {
      name: p.projectFile?.project ?? p.graph.project,
      model_format: p.graph.format,
      schema: p.graph.schema,
      ...(p.projectFile ? { project_file: p.projectFile.name, exported_at: p.projectFile.exportedAt } : {}),
    },
    model: {
      file: p.current.name,
      sha256: p.current.sha256,
      graph_sha256: p.graph.graphSha256,
      revision: p.current.revision,
      elements: p.elements.length,
      nodes_by_kind: stats.nodesByKind,
      elements_by_category: countBy(p.elements, (e) => e.cat),
      connections: stats.nodesByKind["connection"] ?? 0,
      storeys,
      edges_by_kind: stats.edgesByKind,
      supports_edges: stats.edgesByKind["supports"] ?? 0,
      edges_by_rule: stats.edgesByRule,
    },
    model_revisions: modelRevisions(p),
    calc_pdfs: p.pdfs.map((d) => ({
      file: d.name,
      sha256: d.sha256,
      doc_id: d.docId,
      document: d.docName,
      key_prefix: d.prefix,
      main: d.index === 0,
      title: d.title,
      pages: d.pages.length,
      calcs: d.calcs.length,
      links: liveLinks.filter((l) => p.pdfOfCalc.get(l.calc_key) === d).length,
      no_text_pages: d.noTextPages,
      extraction: d.extraction,
      ...(d.extractionNote ? { extraction_note: d.extractionNote } : {}),
      ...(d.revision ? { revision: d.revision } : {}),
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
    links: {
      total: p.links.length,
      live: liveLinks.length,
      by_tier: countBy(liveLinks, (l) => l.tier),
      by_role: countBy(liveLinks, (l) => l.role),
      by_band: countBy(liveLinks, (l) => l.band),
      by_status: countBy(p.links, (l) => l.status ?? "auto"),
    },
    element_status: p.counts,
    calc_edges: {
      total: p.calcEdges.length,
      within_pdf: p.calcEdges.filter((e) => !e.cross_pdf).length,
      cross_pdf: p.calcEdges.filter((e) => e.cross_pdf).length,
      by_rule: byRule,
    },
    typical_groups: { total: p.groups.length, linked: linkedGroups.size, group_links: p.groupLinks.length },
    findings: { total: p.findings.length, by_kind: countBy(p.findings, (f) => f.kind) },
    decisions: {
      file: p.decisions?.name ?? null,
      writable: !!p.decisions,
      exists: p.decisions?.exists ?? false,
      entries: p.fileLog.length,
      ...(p.projectFile ? { project_file_entries: p.baseLog.length } : {}),
      effective: p.effective.size,
      not_applied: p.unappliedDecisions,
      problem: p.decisions?.problem ?? null,
      id_scheme:
        'decision ids are per origin: "decisions_file" ids are the ids in the decisions file (what record_decision returns), ' +
        '"project_file" ids number the project file\'s decision log 1..n in file order',
      actor: p.actor,
    },
    warnings: p.allWarnings,
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
      const hay = [e.global_id, e.mark, e.name, e.profile, e.storey, n?.kind, e.cat, e.ifc_type].map(lc);
      if (!hay.some((h) => h.includes(q)) && !norm(e.profile).includes(norm(a.query))) return false;
    }
    if (a.mark && !norm(e.mark).includes(norm(a.mark))) return false;
    if (a.name && !lc(e.name).includes(lc(a.name))) return false;
    if (a.kind && lc(n?.kind) !== lc(a.kind) && lc(e.ifc_type) !== lc(a.kind)) return false;
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
        best_link: best ? { calc_key: best.calc_key, tier: best.tier, conf: best.conf, band: best.band, role: best.role, status: best.status ?? "auto" } : null,
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
  const row = p.elementById.get(gid)!;
  const links = (p.linksByElement.get(gid) ?? []).slice().sort(byConf);
  const groups = p.groups.filter((g) => g.members.includes(gid));
  const groupIds = new Set(groups.map((g) => g.id));
  const groupLinks = p.groupLinks.filter((l) => groupIds.has(l.group));
  const findings = p.findings.filter((f) => f.global_id === gid);
  const decisions = p.log.filter((d) => d.global_id === gid);
  const pdfs = pdfsOf(p, [...links, ...groupLinks, ...findings, ...decisions].map((x) => x.calc_key));
  return {
    element: {
      ...elSummary(p, gid),
      ifc_type: row.ifc_type,
      type_name: row.type_name,
      material: node.material ?? null,
      level_id: node.levelId ?? null,
      params: node.params,
      geometry: node.geometry ?? null,
      source_ref: node.source,
      content_hash: row.content_hash,
    },
    status: p.status.get(gid),
    links: links.map((l) => linkView(p, l)),
    typical_groups: groups.map((g) => ({ id: g.id, category: g.cat, storey: g.storey, profile: g.profile, title: g.title, members: g.members.length })),
    group_links: groupLinks,
    findings,
    decisions: decisions.map((d) => ({ ...decisionView(p, d)!, calc_key: d.calc_key })),
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
  return {
    key: c.key,
    title: c.title,
    software: c.software,
    category: c.cat,
    pdf: pdfRef(p.pdfOfCalc.get(key)),
    pages: c.pages,
    scanned: c.scanned,
    front_matter: c.front,
    links: { live: ls.length, by_tier: countBy(ls, (l) => l.tier), by_role: countBy(ls, (l) => l.role) },
    elements: new Set(ls.map((l) => l.global_id)).size,
    group_links: p.groupLinks.filter((g) => g.calc_key === key).length,
    findings: p.findings.filter((f) => f.calc_key === key).length,
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
    calc: { ...calcItem(p, key), title_box: c.title_box, spans: c.spans ?? [], content_hash: c.content_hash, provenance: c.provenance },
    linked_elements: {
      ...lp,
      items: lp.items.map((l) => ({
        element: elSummary(p, l.global_id),
        tier: l.tier,
        conf: l.conf,
        band: l.band,
        role: l.role,
        rule: l.rule,
        page: l.page,
        token: l.token,
        status: l.status ?? "auto",
        caveats: l.caveats,
        ...(l.via_group ? { via_group: l.via_group } : {}),
        decided_at: l.decided_at ?? null,
        decided_by: l.decided_by ?? null,
      })),
    },
    group_links: p.groupLinks.filter((g) => g.calc_key === key),
    findings: p.findings.filter((f) => f.calc_key === key),
    calc_edges: { feeds: feeds.map((e) => edgeView(p, e)), fed_by: fedBy.map((e) => edgeView(p, e)) },
  };
  if (a.include_text) {
    const pages = c.pages.map((n) => pdf.pages.find((pg) => pg.n === n)).filter((x): x is NonNullable<typeof x> => x !== undefined);
    const tp = paginate(pages, a.page_offset, a.page_limit ?? 5);
    out.text = {
      ...tp,
      note: "text is the whole page; calc_regions are the [start, end) ranges of it that belong to this calc (a calc can start or end mid-page)",
      items: tp.items.map((pg) => ({
        page: pg.n,
        text: pg.text,
        calc_regions: (c.spans ?? []).flatMap((s) => s.regions).filter((r) => r.page === pg.n).map((r) => [r.start, r.end]),
      })),
    };
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
  // matched IN the page text itself (a regex, case-folded with the i flag), so every offset indexes the
  // original text: lowercasing first would shift offsets wherever a character changes length ("İ")
  const re = new RegExp(a.query.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), a.case_sensitive ? "gu" : "giu");
  const hits: Array<{ pdf: PdfDoc; page: number; calc: string | null; start: number; end: number; text: string }> = [];
  for (const pdf of pdfs) {
    for (const pg of pdf.pages) {
      for (const m of pg.text.matchAll(re)) {
        const owner = calcAt(pdf, pg.n, m.index)?.key ?? null;
        if (calcKey && owner !== calcKey) continue;
        hits.push({ pdf, page: pg.n, calc: owner, start: m.index, end: m.index + m[0].length, text: pg.text });
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
        return { depth: d, ...elSummary(p, id), best_calc: best ? { calc_key: best.calc_key, tier: best.tier, conf: best.conf, role: best.role } : null };
      })
      .sort((x, y) => x.depth - y.depth || cmp(x.mark, y.mark) || cmp(x.global_id, y.global_id));
    return { elements: kept, deepest: maxOf(all.map(([, d]) => d), 0), truncated: all.length > kept.length };
  };
  const down = dir !== "up" ? walk(p.graph.loadPathDown(gid)) : null;
  const up = dir !== "down" ? walk(p.graph.loadPathUp(gid)) : null;
  const visited = new Set([gid, ...(down?.elements ?? []).map((e) => e.global_id), ...(up?.elements ?? []).map((e) => e.global_id)]);
  const edges = p.graph.loadEdges().filter((e) => visited.has(e.src) && visited.has(e.dst));
  return {
    start: elSummary(p, gid),
    direction: dir,
    max_depth: max,
    note: "supports edges: src is supported by dst (load flows src -> dst), with the gap the graph measured. Connection nodes are pass-through for depth.",
    down,
    up,
    supports_edges: edges,
    source: p.source({ pdfs: pdfsOf(p, [...(down?.elements ?? []), ...(up?.elements ?? [])].map((e) => e.best_calc?.calc_key)) }),
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

/** The engine's impact (`propagate`, as `impactOf` calls it) over every PDF's effective links and calc edges. */
export function impactOf(p: Project, gid: string, mode: ImpactMode) {
  return propagateImpact(gid, mode, p.graph.loadEdges(), p.links, p.calcEdges, p.elementById, [p.graph.graphSha256, ...p.pdfs.map((d) => d.sha256)]);
}

export function impactOfChange(p: Project, a: { id: string; mode?: ImpactMode }) {
  const gid = resolveElement(p, a.id);
  const mode = a.mode ?? "change";
  const impact = impactOf(p, gid, mode);
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
    // the impact rests on every PDF's links and calc edges (its provenance inputs name every PDF)
    source: p.source({ pdfs: "all", decisions: true }),
  };
}

// ------------------------------------------------------------------ review_status

export function reviewStatus(p: Project, a: { offset?: number; limit?: number; low_conf_below?: number }) {
  const thr = a.low_conf_below ?? CONFIDENCE_BANDS.high;
  const limit = a.limit ?? 50;
  const review = p.elements.filter((e) => p.status.get(e.global_id) === "review");
  const unmapped = p.elements.filter((e) => p.status.get(e.global_id) === "unmapped");
  const low = p.links
    .filter((l) => live(l) && (l.status ?? "auto") === "auto" && l.conf < thr)
    .sort((x, y) => x.conf - y.conf || cmp(x.calc_key, y.calc_key) || cmp(x.global_id, y.global_id));
  const rp = paginate(review, a.offset, limit);
  const up = paginate(unmapped, a.offset, limit);
  const lp = paginate(low, a.offset, limit);
  const brief = (l: Link) => ({ calc_key: l.calc_key, tier: l.tier, conf: l.conf, band: l.band, role: l.role, page: l.page, token: l.token, rule: l.rule, caveats: l.caveats });
  return {
    counts: p.counts,
    note:
      `status per element (engine statusOf, DESIGN links only): confirmed = a confirmed / manual design link, or a design link with ` +
      `conf >= ${CONFIDENCE_BANDS.high} (high band); review = only weaker design links; unmapped = no live design link (an element ` +
      `only referenced for loads is unmapped)`,
    needs_review: {
      ...rp,
      items: rp.items.map((e) => ({ ...elSummary(p, e.global_id), links: (p.linksByElement.get(e.global_id) ?? []).filter(live).sort(byConf).map(brief) })),
    },
    unmapped: {
      ...up,
      items: up.items.map((e) => ({ ...elSummary(p, e.global_id), loads_links: (p.linksByElement.get(e.global_id) ?? []).filter(live).sort(byConf).map(brief) })),
    },
    low_confidence_links: {
      threshold: thr,
      ...lp,
      items: lp.items.map((l) => ({ element: elSummary(p, l.global_id), ...brief(l) })),
    },
    source: p.source({ decisions: true }),
  };
}

// ------------------------------------------------------------------ list_findings

export interface FindingsArgs {
  calc?: string;
  element?: string;
  pdf?: string;
  offset?: number;
  limit?: number;
}

export function listFindings(p: Project, a: FindingsArgs) {
  const key = a.calc ? resolveCalc(p, a.calc) : null;
  const gid = a.element ? resolveElement(p, a.element) : null;
  const pdf = a.pdf ? p.pdfByName(a.pdf) : null;
  const all = p.findings.filter((f) => (!key || f.calc_key === key) && (!gid || f.global_id === gid) && (!pdf || p.pdfOfCalc.get(f.calc_key) === pdf));
  const page = paginate(all, a.offset, a.limit ?? 100);
  return {
    note: "size-mismatch findings: a design line names the element's mark and a different size than the model gives. Findings on links a reviewer rejected are left out (as in the app).",
    ...page,
    items: page.items.map((f) => ({
      ...f,
      element: elSummary(p, f.global_id),
      calc_title: p.calcByKey.get(f.calc_key)?.title ?? "",
      pdf: p.pdfOfCalc.get(f.calc_key)?.name ?? null,
    })),
    source: p.source({ pdfs: pdf ? [pdf] : all.map((f) => p.pdfOfCalc.get(f.calc_key)!).filter(Boolean), decisions: true }),
  };
}

// ------------------------------------------------------------------ list_typical_groups

export interface GroupsArgs {
  kind?: string;
  storey?: string;
  profile?: string;
  linked_only?: boolean;
  offset?: number;
  limit?: number;
}

export function listTypicalGroups(p: Project, a: GroupsArgs) {
  const byGroup = new Map<string, typeof p.groupLinks>();
  for (const l of p.groupLinks) (byGroup.get(l.group) ?? byGroup.set(l.group, []).get(l.group)!).push(l);
  const rows = p.groups.filter(
    (g) =>
      (!a.kind || lc(g.cat).includes(lc(a.kind))) &&
      (!a.storey || lc(g.storey).includes(lc(a.storey))) &&
      (!a.profile || norm(g.profile).includes(norm(a.profile))) &&
      (!a.linked_only || byGroup.has(g.id)),
  );
  const page = paginate(rows, a.offset, a.limit ?? 100);
  const linkedPdfs = rows.flatMap((g) => (byGroup.get(g.id) ?? []).map((l) => p.pdfOfCalc.get(l.calc_key)!)).filter(Boolean);
  return {
    note: "a typical group is the elements of one kind, storey and size; a size on a line that names no mark links the calc to the group once (group_links), and members carry a size link marked via_group",
    ...page,
    items: page.items.map((g) => ({
      ...g,
      member_marks: g.members.map((m) => p.elementById.get(m)?.mark ?? ""),
      group_links: (byGroup.get(g.id) ?? []).map((l) => ({ ...l, calc_title: p.calcByKey.get(l.calc_key)?.title ?? "", pdf: p.pdfOfCalc.get(l.calc_key)?.name ?? null })),
    })),
    source: p.source({ pdfs: linkedPdfs }),
  };
}

// ------------------------------------------------------------------ compare_revisions

export interface CompareArgs {
  a?: string | number;
  b?: string | number;
  limit?: number;
}

export function compareRevisions(p: Project, a: CompareArgs) {
  if (p.models.length < 2) {
    throw new ToolInputError(
      "compare needs two model revisions and this server has one. Start it with an older revision too: repeat --model, oldest first " +
        "(the last is the current model), or use a project file with several model revisions.",
    );
  }
  const rb = a.b !== undefined ? p.modelRevision(a.b) : p.current;
  const ra = a.a !== undefined ? p.modelRevision(a.a) : (p.models.filter((m) => m.index < rb.index).at(-1) ?? p.models.find((m) => m !== rb)!);
  if (ra === rb) throw new ToolInputError(`a and b are the same revision (${ra.revision} = ${ra.name})`);
  // labels as the app (project file: revision ids) or calc-mapper's CLI (file names) passes them
  const labels = p.projectFile ? { a: ra.revision, b: rb.revision } : { a: ra.name, b: rb.name };
  const compare = diffGraphs(ra.model.graph, rb.model.graph, labels);
  const limit = a.limit ?? 500;
  // calcs linked (live links on the current model) to an element the diff names
  let affected: Array<{ calc_key: string; title: string; pdf: string | null; elements: string[] }> | null = null;
  if (rb === p.current || ra === p.current) {
    const touched = new Set([...compare.changed.map((c) => c.global_id), ...compare.removed.map((r) => r.global_id), ...compare.added.map((r) => r.global_id)]);
    const by = new Map<string, Set<string>>();
    for (const l of p.links) {
      if (!live(l) || !touched.has(l.global_id)) continue;
      (by.get(l.calc_key) ?? by.set(l.calc_key, new Set()).get(l.calc_key)!).add(l.global_id);
    }
    affected = [...by].map(([k, gids]) => ({ calc_key: k, title: p.calcByKey.get(k)?.title ?? "", pdf: p.pdfOfCalc.get(k)?.name ?? null, elements: [...gids].sort() })).sort((x, y) => cmp(x.calc_key, y.calc_key));
  }
  const cut = <T>(xs: T[]) => xs.slice(0, limit);
  return {
    a: { revision: ra.revision, file: ra.name, sha256: ra.sha256, graph_sha256: ra.model.graphSha256 },
    b: { revision: rb.revision, file: rb.name, sha256: rb.sha256, graph_sha256: rb.model.graphSha256 },
    counts: {
      removed: compare.removed.length,
      added: compare.added.length,
      changed: compare.changed.length,
      edges_removed: compare.edges_removed.length,
      edges_added: compare.edges_added.length,
    },
    truncated: [compare.removed, compare.added, compare.changed, compare.edges_removed, compare.edges_added].some((x) => x.length > limit),
    compare: {
      ...compare,
      removed: cut(compare.removed),
      added: cut(compare.added),
      changed: cut(compare.changed),
      edges_removed: cut(compare.edges_removed),
      edges_added: cut(compare.edges_added),
    },
    calcs_linked_to_diff: affected,
    note:
      "diffGraphs keys elements on GlobalId; changed = content hash differs, with each changed field's [before, after]. " +
      "calcs_linked_to_diff lists calcs whose live links on the current model touch an element in the diff (null when neither side is the current model).",
    source: { ...p.source({ pdfs: affected ? affected.map((x) => p.pdfOfCalc.get(x.calc_key)!).filter(Boolean) : [] }), compared: [ra.name, rb.name] },
  };
}

// ------------------------------------------------------------------ move_column

export interface MoveArgs {
  column: string;
  dx?: number;
  dy?: number;
  remove?: boolean;
}

export function moveColumn(p: Project, a: MoveArgs) {
  const gid = resolveElement(p, a.column);
  const row = p.elementById.get(gid)!;
  if (row.cat !== "Column") throw new ToolInputError(`${a.column} is a ${row.cat || p.node(gid)?.kind || "element"}, not a column`);
  const dx = a.dx ?? 0;
  const dy = a.dy ?? 0;
  if (!a.remove && dx === 0 && dy === 0) throw new ToolInputError("give dx and/or dy (metres, plan), or remove: true");
  const move: Move = a.remove ? { column: gid, remove: true } : { column: gid, dx, dy };
  const result = engineMoveColumn({ graph: p.graph.graph, graphSha256: p.graph.graphSha256, move, links: p.links });
  return {
    column: elSummary(p, gid),
    result,
    note:
      "What-if only: nothing is changed or saved. Topological and geometric screen on the current model, with the reviewed links " +
      "for stale calcs. No calc facts are given (calc-mapper does not read calc row values yet), so there are no utilisation " +
      "estimates and no health band.",
    // move-impact reads every PDF's reviewed links
    source: { ...p.source({ pdfs: "all", decisions: true }), move_impact: ENGINE_PRODUCERS.move_impact, move_impact_engine: result.engine },
  };
}

// ------------------------------------------------------------------ export_mapping

/** The engine's buildExport on the calc set, with the header labels the app's projectSnapshot passes. */
export function exportReport(p: Project) {
  const one = p.pdfs.length === 1 ? p.pdfs[0]! : null;
  return buildExport(p.graph.graph, p.set, p.run, p.log, {
    model: p.current.name,
    model_revision: p.current.revision,
    calc_package: one ? one.name : `${p.pdfs.length} calc documents`,
    calc_revision: one ? (one.revision?.id ?? null) : null,
  });
}

export function exportMappingTool(p: Project, a: { element_offset?: number; element_limit?: number }) {
  const report = exportReport(p);
  const paged = a.element_limit !== undefined || a.element_offset !== undefined;
  const pg = paged ? paginate(report.elements, a.element_offset, a.element_limit ?? 100) : null;
  return {
    note:
      "the engine's buildExport on the calc set, as the app exports it. Page numbers in the report are SET pages (as the app's " +
      "export has them): a PDF's own page = set page - its page_offset in calc_documents. Every other tool gives a PDF's own pages.",
    calc_documents: p.pdfs.map((d) => ({ doc_id: d.docId, file: d.name, page_offset: d.offset, pages: d.pages.length })),
    report: pg ? { ...report, elements: pg.items } : report,
    ...(pg ? { elements_page: { total: pg.total, offset: pg.offset, returned: pg.returned, next_offset: pg.next_offset } } : {}),
    source: p.source({ decisions: true }),
  };
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
    if (page === l.page) rects = l.rects.map((r) => [...r] as unknown as Rect);
    what = { link: { global_id: gid, calc_key: key, tier: l.tier, conf: l.conf, role: l.role, token: l.token } };
  } else if (a.edge_src || a.edge_dst) {
    if (!a.edge_src || !a.edge_dst) throw new ToolInputError("pass both edge_src and edge_dst to highlight calc-edge evidence");
    const src = resolveCalc(p, a.edge_src);
    const dst = resolveCalc(p, a.edge_dst);
    const e = p.calcEdges.find((x) => x.src === src && x.dst === dst);
    if (!e) throw new ToolInputError(`no calc edge ${src} -> ${dst} (calc_dependencies lists them)`);
    const i = a.evidence_index ?? 0;
    const ev = e.evidence[i];
    if (!ev) throw new ToolInputError(`calc edge ${src} -> ${dst} has ${e.evidence.length} evidence item(s); evidence_index ${i} is out of range`);
    pdf = p.pdfOfCalc.get(ev.calc)!;
    page ??= ev.page;
    if (page === ev.page) rects = (ev.rects ?? []).map((r) => [...r] as unknown as Rect);
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
    rects.push([r[0]!, r[1]!, r[2]!, r[3]!] as unknown as Rect);
  }
  let crop: number[] | null = a.rect ?? null;
  if (!crop && a.crop !== false && rects.length && (a.crop === true || what.link || what.calc_edge || what.span)) {
    // full-width band around the evidence (the whole line reads in context); tight = pad all four sides
    const pad = a.padding ?? 48;
    crop = [
      a.tight ? minOf(rects.map((r) => r[0])) - pad : 0,
      minOf(rects.map((r) => r[1])) - pad,
      a.tight ? maxOf(rects.map((r) => r[2])) + pad : pg.width,
      maxOf(rects.map((r) => r[3])) + pad,
    ];
  }
  const image = await renderPage(pdf.bytes, page, { rect: crop, highlight: rects as unknown as number[][], width: a.width ?? null });
  const onPage = pdf.calcs.filter((c) => c.pages.includes(page!));
  const owner = calcAt(pdf, page, null);
  return {
    image,
    meta: {
      pdf: pdf.name,
      page,
      page_count: pdf.pages.length,
      calc_key: owner?.key ?? null,
      calc_title: owner?.title ?? null,
      calcs_on_page: onPage.map((c) => c.key),
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

function brief(l: Link | undefined) {
  return l ? { tier: l.tier, conf: l.conf, role: l.role, status: l.status ?? "auto", decided_at: l.decided_at ?? null, decided_by: l.decided_by ?? null } : null;
}

/**
 * Validate and append decisions (all or none). Each one is made by the engine's `addDecision` on the
 * decisions file's log (next id, human provenance naming the model graph and the calc's PDF).
 */
export async function recordDecisions(p: Project, a: { decisions: DecisionInput[] }) {
  const store = p.decisions;
  if (!store) throw new ToolInputError(READ_ONLY_MESSAGE);
  if (!Array.isArray(a.decisions) || !a.decisions.length) throw new ToolInputError("decisions must be a non-empty array");
  if (a.decisions.length > 500) throw new ToolInputError("at most 500 decisions per call");
  const rawPairs = new Set(p.rawLinks.map((l) => pk(l.global_id, l.calc_key)));
  const built: { on: readonly DecisionFields[] | null } = { on: null };

  // build runs under the cross-process lock: only cheap work here (no recompute: it would block the event
  // loop, and with it the lock's heartbeat)
  const appending = store.append((current) => {
    built.on = current;
    const errors: string[] = [];
    // effective decision per pair as the log stands (project file + this file), updated as the batch is simulated
    const eff = new Map(p.effectiveOver(current));
    const at = new Date().toISOString();
    const log: DecisionFields[] = [...current];
    const out: Decision[] = [];
    a.decisions.forEach((d, i) => {
      const tag = a.decisions.length > 1 ? `decision ${i}: ` : "";
      if (!(DECISION_ACTIONS as readonly string[]).includes(d.action)) {
        errors.push(`${tag}action must be ${DECISION_ACTIONS.join(", ")}`);
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
      // a calc ref, or a bare key exactly one PDF has (recorded as its calc ref, as the app records it)
      const refs = p.calcKeys.has(d.calc_key) ? [d.calc_key] : p.calcs.filter((c) => bareKey(c.key) === d.calc_key).map((c) => c.key);
      if (refs.length !== 1) {
        errors.push(
          refs.length
            ? `${tag}calc key "${d.calc_key}" is in ${refs.length} calc PDFs: name one (${refs.join(", ")})`
            : `${tag}no calc "${d.calc_key}".${suggest(p.calcs.map((c) => c.key), d.calc_key ?? "")}`,
        );
        return;
      }
      d = { ...d, calc_key: refs[0]! };
      const key = pk(d.global_id, d.calc_key);
      if ((d.action === "confirm" || d.action === "reject") && !rawPairs.has(key)) {
        const manual = eff.get(key)?.action === "manual";
        errors.push(
          `${tag}there is no automatic link between ${d.global_id} and ${d.calc_key} to ${d.action}` +
            (manual ? " (it was linked by hand: use undo to remove that)" : "; use manual to link them by hand"),
        );
        return;
      }
      if (d.action === "undo" && !eff.has(key)) {
        errors.push(`${tag}there is no decision on ${d.global_id} / ${d.calc_key} to undo`);
        return;
      }
      if (d.note !== undefined && d.note !== null && typeof d.note !== "string") {
        errors.push(`${tag}note must be a string`);
        return;
      }
      const rec = nextDecision(log, { global_id: d.global_id, calc_key: d.calc_key, action: d.action, actor: p.actor, note: d.note ?? null }, { at, ...p.decisionContext(d.calc_key) });
      log.push(rec);
      out.push(rec);
      if (d.action === "undo") eff.delete(key);
      else eff.set(key, rec);
    });
    if (errors.length) throw new ToolInputError(`nothing was written:\n- ${errors.join("\n- ")}`);
    return out;
  });
  const { appended, reloaded } = await appending.catch((e: unknown) => {
    if (p.computedLog !== store.log) p.recompute(); // the append re-read the file, then wrote nothing
    throw e;
  });
  // the lock is released: "before" is the state the batch was built on (applied again only when someone
  // else had appended since the last applied read), then the new log is applied once
  if (built.on && p.computedLog !== built.on) p.recompute(built.on);
  const before = new Map<string, { link: ReturnType<typeof brief>; status: string | undefined }>();
  for (const d of appended) {
    const l = (p.linksByElement.get(d.global_id) ?? []).find((x) => x.calc_key === d.calc_key);
    before.set(pk(d.global_id, d.calc_key), { link: brief(l), status: p.status.get(d.global_id) });
  }
  if (p.computedLog !== store.log) p.recompute();
  return {
    recorded: appended.map((d) => {
      const l = (p.linksByElement.get(d.global_id) ?? []).find((x) => x.calc_key === d.calc_key);
      const b = before.get(pk(d.global_id, d.calc_key));
      return {
        decision: { origin: "decisions_file" as const, ...d },
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

export function decisionsLog(p: Project) {
  return {
    file: p.decisions?.path ?? null,
    writable: !!p.decisions,
    format: "calc-mapper decision log: [{id, global_id, calc_key, action, actor, note, at, model_rev, calc_rev, provenance}], oldest first",
    id_scheme:
      'ids are per origin: entries (origin "decisions_file") carry the decisions file\'s own ids; project_file_entries (origin ' +
      '"project_file") are numbered 1..n in the project file\'s order. get_element and record_decision name decisions the same way.',
    ...(p.decisions?.problem ? { problem: p.decisions.problem } : {}),
    entries: p.fileLog,
    ...(p.projectFile ? { project_file_entries: p.baseLog } : {}),
    source: p.source({ decisions: true, pdfs: [] }),
  };
}

export { ENGINE_VERSION };
