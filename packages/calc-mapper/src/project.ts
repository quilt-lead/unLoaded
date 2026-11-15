/**
 * The pipeline over one (element graph, calc package or calc set) pair, producing the shapes the retired
 * backend served: a mapping run (auto links + calc edges), /state pieces, /export, /impact.
 * Port of the reference pipeline.remap / state / export / impact_of.
 *
 * mapCalcs and impactOf are async: they hash the element graph (sha256 of its canonical JSON,
 * WebCrypto) so every record they produce names the documents it rests on. The run keeps those
 * hashes (`producers`, `inputs`), so buildState / buildExport stay synchronous.
 */
import { applyDecisions } from "./decisions.ts";
import { connectivity, graphElements, loadPath } from "./elements.ts";
import { inferCalcEdges } from "./calcdeps.ts";
import { sha256Json } from "./hash.ts";
import { propagate } from "./impact.ts";
import { BANDS, mapElements } from "./matcher.ts";
import { PACKAGE_NAME, PACKAGE_VERSION, inputList } from "./provenance.ts";
import { packageSha256 } from "./segment.ts";
import { isCalcSet, type CalcSet } from "./calcset.ts";
import {
  ENGINE_VERSION, type CalcPackage, type DecisionFields, type ElementState, type ElementStatus, type Export, type ExportInfo,
  type Impact, type ImpactMode, type Link, type MappingRun, type ProjectState, type RunProducers, type SerializedElementGraph,
} from "./types.ts";

export const PALETTE = ["#4e79a7", "#f28e2b", "#59a14f", "#b07aa1", "#e15759", "#76b7b2", "#edc948", "#9c755f", "#ff9da7",
  "#2b8c8c", "#8f6ed5", "#d4a017", "#3d9970", "#c2185b", "#5f7d95"];

/** sha256 of the calc package's PDF; throws for a package extracted before pages carried their document hash. */
function pdfSha256(pkg: CalcPackage): string {
  const fromPages = packageSha256(pkg.pages);
  if (pkg.source_sha256 && pkg.source_sha256 !== fromPages) {
    throw new Error("calc package source_sha256 does not match its pages' doc_sha256");
  }
  return fromPages;
}

/** The calcs a run reads: one package as is, or a calc set (calcset.ts) as its combined package. */
export type CalcInput = CalcPackage | CalcSet;

/** The package the engine reads (a set: its combined package, calc refs + set page numbers). */
export function packageOf(x: CalcInput): CalcPackage;
export function packageOf(x: CalcInput | null): CalcPackage | null;
export function packageOf(x: CalcInput | null): CalcPackage | null {
  return x === null ? null : isCalcSet(x) ? x.combined : x;
}

/** sha256 of every PDF the calcs rest on, in document order. */
function pdfShas(x: CalcInput): string[] {
  if (!isCalcSet(x)) return [pdfSha256(x)];
  for (const d of x.docs) {
    if (!x.combined.pages.some((p) => p.doc_sha256 === d.sha256)) throw new Error(`calc set document ${d.doc_id} has no pages`);
  }
  return x.docs.map((d) => d.sha256);
}

/** Producer records of one (graph, calc package) run: who made each input, and each input document's sha256. */
export async function runProducers(graph: SerializedElementGraph, calcs: CalcInput): Promise<RunProducers> {
  const shas = pdfShas(calcs);
  const pkg = packageOf(calcs);
  const set = isCalcSet(calcs) ? calcs : null;
  return {
    calc_mapper: { producer: `${PACKAGE_NAME}@${PACKAGE_VERSION}`, engine: ENGINE_VERSION },
    element_graph: {
      producer: `${graph.format}@${graph.version}`, format: graph.format, version: graph.version,
      source: graph.meta?.source ?? null, sha256: await sha256Json(graph),
    },
    // one PDF: the package record as before (a set of one PDF too); several: only calc_set
    ...(shas.length === 1 ? { calc_package: { name: set ? set.docs[0]!.name : pkg.source_name, sha256: shas[0]!, pages: pkg.pages.length } } : {}),
    ...(set ? {
      calc_set: set.docs.map((d) => ({ doc_id: d.doc_id, name: d.name, revision: d.revision, sha256: d.sha256, page_offset: d.page_offset, pages: d.pages })),
    } : {}),
  };
}

/** Map a calc package onto a graph: the auto links and the calc dependency edges of that run, with its producer records. */
export async function mapCalcs(graph: SerializedElementGraph, calcs: CalcInput): Promise<MappingRun> {
  const producers = await runProducers(graph, calcs);
  const pkg = packageOf(calcs);
  const r = mapElements(graphElements(graph), pkg.calcs, pkg.pages, producers.element_graph.sha256);
  return {
    engine: ENGINE_VERSION, links: r.links, calc_edges: inferCalcEdges(pkg.calcs, pkg.pages, r.links), groups: r.groups,
    group_links: r.group_links, findings: r.findings, producers,
    inputs: inputList([producers.element_graph.sha256, ...pdfShas(calcs)]),
  };
}

/**
 * Review status from the element's DESIGN links only (a loads-only link does not make an element
 * designed): confirmed when a design link is confirmed / made by hand or is high-confidence,
 * review when it has only weaker design links, unmapped when it has none.
 */
export function statusOf(links: Link[]): ElementStatus {
  const live = links.filter((l) => l.status !== "rejected" && (l.role ?? "design") === "design");
  if (!live.length) return "unmapped";
  return live.some((l) => l.status === "confirmed" || l.status === "manual" || l.conf >= BANDS.high) ? "confirmed" : "review";
}

/** Elements with review status, load path, calcs (+ colours), links with decisions applied, calc edges, counts. */
export function buildState(
  graph: SerializedElementGraph, calcInput: CalcInput | null, run: MappingRun | null, decisions: readonly DecisionFields[] = [],
): ProjectState {
  const pkg = packageOf(calcInput);
  const rows = graphElements(graph);
  const calcs = (pkg?.calcs ?? []).map((c, i) => ({ ...c, color: PALETTE[i % PALETTE.length]! }));
  const pages = pkg?.pages ?? [];
  const links = run && pkg
    ? applyDecisions(run.links, decisions, new Set(rows.map((e) => e.global_id)), new Set(calcs.map((c) => c.key)))
    : [];
  const calcEdges = run && pkg ? inferCalcEdges(pkg.calcs, pages, links) : [];
  const perEl = new Map<string, Link[]>();
  for (const l of links) (perEl.get(l.global_id) ?? perEl.set(l.global_id, []).get(l.global_id)!).push(l);
  const counts: Record<ElementStatus, number> = { confirmed: 0, review: 0, unmapped: 0 };
  const elements: ElementState[] = rows.map((e) => {
    const status = statusOf(perEl.get(e.global_id) ?? []);
    counts[status] += 1;
    return { ...e, status };
  });
  const rejected = new Set(links.filter((l) => l.status === "rejected").map((l) => `${l.global_id}\u0000${l.calc_key}`));
  return {
    elements, edges: loadPath(graph), calcs,
    pages: pages.map((p) => ({ n: p.n, text: p.text, scanned: p.scanned, width: p.width, height: p.height })),
    links, calc_edges: calcEdges, counts, groups: run?.groups ?? [], group_links: run?.group_links ?? [],
    findings: (run?.findings ?? []).filter((f) => !rejected.has(`${f.global_id}\u0000${f.calc_key}`)),
  };
}

const round2 = (v: number): number => Math.round(v * 100) / 100;

/** The backend's /export: elements with their calc links + evidence, calcs, calc edges, load path, connectivity. */
export function buildExport(
  graph: SerializedElementGraph, calcInput: CalcInput | null, run: MappingRun | null, decisions: readonly DecisionFields[] = [],
  info: ExportInfo = {},
): Export {
  const s = buildState(graph, calcInput, run, decisions);
  const pkg = packageOf(calcInput);
  const set = calcInput && isCalcSet(calcInput) ? calcInput : null;
  const cal = new Map(s.calcs.map((c) => [c.key, c]));
  const perEl = new Map<string, Link[]>();
  for (const l of s.links) (perEl.get(l.global_id) ?? perEl.set(l.global_id, []).get(l.global_id)!).push(l);
  return {
    model: info.model ?? graph.meta?.source?.file ?? null,
    model_revision: info.model_revision ?? null,
    calc_package: info.calc_package ?? pkg?.source_name ?? null,
    calc_revision: info.calc_revision ?? null,
    engine: ENGINE_VERSION,
    producers: {
      model: { element_graph: { format: graph.format, version: graph.version, source: graph.meta?.source ?? null } },
      mapping: { "calc-mapper": ENGINE_VERSION },
      ...(run ? { ...run.producers, inputs: run.inputs } : {}),
    },
    calcs: s.calcs.map((c) => ({
      key: c.key, title: c.title, software: c.software, element_type: c.cat, pages: c.pages, scanned: c.scanned,
      front_matter: c.front, title_box: c.title_box, spans: c.spans ?? [], provenance: c.provenance,
    })),
    calc_edges: s.calc_edges.map((e) => ({ src: e.src, dst: e.dst, rules: e.rules, evidence: e.evidence, provenance: e.provenance })),
    load_path: s.edges.map((e) => ({ src: e.src, dst: e.dst, rule: e.rule })),
    connectivity: connectivity(graph),
    elements: s.elements.map((e) => ({
      global_id: e.global_id, ifc_type: e.ifc_type, mark: e.mark, storey: e.storey, size: e.profile, status: e.status,
      calcs: [...(perEl.get(e.global_id) ?? [])].sort((p, q) => q.conf - p.conf).map((l) => ({
        calc: l.calc_key, title: cal.get(l.calc_key)?.title ?? l.calc_key, page: l.page, confidence: round2(l.conf),
        tier: l.tier, rule: l.rule, matched_text: l.token, review: l.status,
        evidence: { page: l.page, span: l.span, rects: l.rects, snippet: l.snippet },
        role: l.role, band: l.band, reasons: l.evidence, caveats: l.caveats, ...(l.via_group ? { via_group: l.via_group } : {}),
        provenance: l.provenance, ...(l.review_provenance ? { review_provenance: l.review_provenance } : {}),
      })),
    })),
    groups: s.groups, group_links: s.group_links, findings: s.findings,
    ...(set ? {
      documents: set.docs.map((d) => ({ doc_id: d.doc_id, name: d.name, revision: d.revision, sha256: d.sha256, page_offset: d.page_offset, pages: d.pages })),
    } : {}),
  };
}

/**
 * The backend's /impact: what a change to / removal of one element hits on the load path, and which
 * calcs go stale. Rests on the graph, and on the calc PDF when calcs are linked (a run is given).
 */
export async function impactOf(
  graph: SerializedElementGraph, calcInput: CalcInput | null, run: MappingRun | null, decisions: readonly DecisionFields[],
  gid: string, mode: ImpactMode,
): Promise<Impact> {
  const s = buildState(graph, calcInput, run, decisions);
  const inputs = [await sha256Json(graph), ...(run && calcInput ? pdfShas(calcInput) : [])];
  return propagate(gid, mode, s.edges, s.links, s.calc_edges, new Map(s.elements.map((e) => [e.global_id, e])), inputs);
}
