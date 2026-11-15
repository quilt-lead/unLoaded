/**
 * The pipeline over one (element graph, calc package) pair, producing the shapes the retired
 * backend served: a mapping run (auto links + calc edges), /state pieces, /export, /impact.
 * Port of the reference pipeline.remap / state / export / impact_of.
 */
import { applyDecisions } from "./decisions.ts";
import { connectivity, graphElements, loadPath } from "./elements.ts";
import { inferCalcEdges } from "./calcdeps.ts";
import { propagate } from "./impact.ts";
import { BANDS, mapElements } from "./matcher.ts";
import {
  ENGINE_VERSION, type CalcPackage, type Decision, type ElementState, type ElementStatus, type Export, type ExportInfo,
  type Impact, type ImpactMode, type Link, type MappingRun, type ProjectState, type SerializedElementGraph,
} from "./types.ts";

export const PALETTE = ["#4e79a7", "#f28e2b", "#59a14f", "#b07aa1", "#e15759", "#76b7b2", "#edc948", "#9c755f", "#ff9da7",
  "#2b8c8c", "#8f6ed5", "#d4a017", "#3d9970", "#c2185b", "#5f7d95"];

/** Map a calc package onto a graph: the auto links and the calc dependency edges of that run. */
export function mapCalcs(graph: SerializedElementGraph, pkg: CalcPackage): MappingRun {
  const r = mapElements(graphElements(graph), pkg.calcs, pkg.pages);
  return {
    engine: ENGINE_VERSION, links: r.links, calc_edges: inferCalcEdges(pkg.calcs, pkg.pages, r.links), groups: r.groups,
    group_links: r.group_links, findings: r.findings,
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
  graph: SerializedElementGraph, pkg: CalcPackage | null, run: MappingRun | null, decisions: readonly Decision[] = [],
): ProjectState {
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
  graph: SerializedElementGraph, pkg: CalcPackage | null, run: MappingRun | null, decisions: readonly Decision[] = [],
  info: ExportInfo = {},
): Export {
  const s = buildState(graph, pkg, run, decisions);
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
    },
    calcs: s.calcs.map((c) => ({
      key: c.key, title: c.title, software: c.software, element_type: c.cat, pages: c.pages, scanned: c.scanned,
      front_matter: c.front, title_box: c.title_box, spans: c.spans ?? [],
    })),
    calc_edges: s.calc_edges.map((e) => ({ src: e.src, dst: e.dst, rules: e.rules, evidence: e.evidence })),
    load_path: s.edges.map((e) => ({ src: e.src, dst: e.dst, rule: e.rule })),
    connectivity: connectivity(graph),
    elements: s.elements.map((e) => ({
      global_id: e.global_id, ifc_type: e.ifc_type, mark: e.mark, storey: e.storey, size: e.profile, status: e.status,
      calcs: [...(perEl.get(e.global_id) ?? [])].sort((p, q) => q.conf - p.conf).map((l) => ({
        calc: l.calc_key, title: cal.get(l.calc_key)?.title ?? l.calc_key, page: l.page, confidence: round2(l.conf),
        tier: l.tier, rule: l.rule, matched_text: l.token, review: l.status,
        evidence: { page: l.page, span: l.span, rects: l.rects, snippet: l.snippet },
        role: l.role, band: l.band, reasons: l.evidence, caveats: l.caveats, ...(l.via_group ? { via_group: l.via_group } : {}),
      })),
    })),
    groups: s.groups, group_links: s.group_links, findings: s.findings,
  };
}

/** The backend's /impact: what a change to / removal of one element hits on the load path, and which calcs go stale. */
export function impactOf(
  graph: SerializedElementGraph, pkg: CalcPackage | null, run: MappingRun | null, decisions: readonly Decision[],
  gid: string, mode: ImpactMode,
): Impact {
  const s = buildState(graph, pkg, run, decisions);
  return propagate(gid, mode, s.edges, s.links, s.calc_edges, new Map(s.elements.map((e) => [e.global_id, e])));
}
