/**
 * The tool implementations: plain async functions (project, args) -> JSON, kept apart from the MCP
 * wiring (server.ts) so tests can call them directly and compare them with calc-mapper.
 *
 * Rule for every tool: the engine's records are passed through untouched (links with role / band /
 * caveats / reasons / provenance, calc edges, findings, groups, impact, compare), and anything added
 * around them is a lookup from the same project (a mark for a GlobalId, a title for a calc key) or a
 * count of the engine's own lists. Nothing is estimated or invented here. Each result carries
 * `source`: the project file and its sha256, the revisions used, the engine version and the run's
 * producer records (with the sha256 of the element graph and of the calc PDF).
 */
import { calcText, diffGraphs, impactOf, sha256Json, type ElementState, type ExportLink, type ImpactMode } from "@unloaded/calc-mapper";
import { impact as moveImpact, type Move } from "@unloaded/move-impact";
import { renderPage, type PageImage } from "./pageImage.ts";
import { ProjectFileError, type ProjectFileRevision } from "@unloaded/project-file";
import type { LoadedProject, View } from "./project.ts";

export class ToolInputError extends Error {
  name = "ToolInputError";
}

export interface RevisionArgs {
  /** Model revision id (list_revisions); default: the head model revision, as the app shows. */
  model_revision?: number | null;
  /** Calc revision id (list_revisions); default: the head calc package. */
  calc_revision?: number | null;
}

const lc = (s: unknown): string => String(s ?? "").toLowerCase();
const squash = (s: unknown): string => String(s ?? "").toUpperCase().replace(/\s+/g, "");

function countBy<T>(xs: readonly T[], key: (x: T) => string): Record<string, number> {
  const out: Record<string, number> = {};
  for (const x of xs) {
    const k = key(x) || "(none)";
    out[k] = (out[k] ?? 0) + 1;
  }
  return out;
}

/** Grid reference(s) the model states for an element: any param whose name contains "grid". */
export function gridOf(e: Pick<ElementState, "params">): string {
  return Object.entries(e.params ?? {})
    .filter(([k, v]) => /grid/i.test(k) && v != null && v !== "")
    .map(([, v]) => String(v))
    .join("; ");
}

function elementIndex(v: View): Map<string, ElementState> {
  return new Map(v.state.elements.map((e) => [e.global_id, e]));
}

const brief = (e: ElementState | undefined, gid: string) =>
  e ? { global_id: gid, mark: e.mark, kind: e.cat, ifc_type: e.ifc_type, storey: e.storey, size: e.profile } : { global_id: gid, mark: null };

/** An element by GlobalId, else by mark / name (case-insensitive, exact). Ambiguous or unknown -> a clear error. */
export function resolveElement(v: View, id: string): ElementState {
  const want = id.trim();
  const byId = v.state.elements.find((e) => e.global_id === want);
  if (byId) return byId;
  const hits = v.state.elements.filter((e) => lc(e.mark) === lc(want) || (!e.mark && lc(e.name) === lc(want)));
  if (hits.length === 1) return hits[0]!;
  if (hits.length > 1) {
    const list = hits.slice(0, 20).map((e) => `${e.global_id} (${e.cat}, ${e.storey || "no storey"})`).join(", ");
    throw new ToolInputError(`mark ${JSON.stringify(want)} is used by ${hits.length} elements: ${list} - pass the GlobalId`);
  }
  throw new ToolInputError(`no element with GlobalId or mark ${JSON.stringify(want)} in model revision ${v.model.rev.id}; try search_elements`);
}

function revisionRow(r: ProjectFileRevision, head: boolean) {
  return {
    id: r.id, kind: r.kind, seq: r.seq, label: r.label, source_name: r.sourceName, media_type: r.mediaType,
    created_at: r.createdAt, meta: r.meta, head,
  };
}

// ---------------------------------------------------------------- project_summary

export async function projectSummary(p: LoadedProject, a: RevisionArgs = {}) {
  const v = await p.view(a.model_revision, a.calc_revision);
  const s = v.state, e = v.exp;
  return {
    project: { name: p.file.project.name, created_at: p.file.project.createdAt, exported_at: p.file.exportedAt },
    revisions: (await listRevisions(p)).revisions,
    counts: {
      elements: s.elements.length,
      element_status: s.counts,
      elements_by_kind: countBy(s.elements, (x) => x.cat),
      elements_by_storey: countBy(s.elements, (x) => x.storey),
      calcs: e.calcs.length,
      links: s.links.length,
      links_by_review: countBy(s.links, (l) => l.status),
      links_by_role: countBy(s.links, (l) => l.role),
      calc_edges: e.calc_edges.length,
      load_path_edges: e.load_path.length,
      connectivity_edges: e.connectivity.length,
      typical_groups: e.groups.length,
      group_links: e.group_links.length,
      findings: e.findings.length,
      decisions: v.decisions.length,
    },
    calcs: e.calcs.map((c) => ({
      key: c.key, title: c.title, software: c.software, element_type: c.element_type, pages: c.pages,
      scanned: c.scanned, front_matter: c.front_matter,
    })),
    source: await p.source(v),
  };
}

// ---------------------------------------------------------------- search_elements

export interface SearchArgs extends RevisionArgs {
  mark?: string | null;
  kind?: string | null;
  storey?: string | null;
  size?: string | null;
  grid?: string | null;
  status?: "confirmed" | "review" | "unmapped" | null;
  limit?: number | null;
}

export async function searchElements(p: LoadedProject, a: SearchArgs = {}) {
  const v = await p.view(a.model_revision, a.calc_revision);
  const limit = Math.max(1, Math.min(500, Math.trunc(a.limit ?? 50)));
  const links = new Map(v.exp.elements.map((x) => [x.global_id, x.calcs]));
  const hits = v.state.elements.filter((e) => {
    if (a.mark && ![e.mark, e.name, e.global_id].some((s) => lc(s).includes(lc(a.mark)))) return false;
    if (a.kind && ![e.cat, e.ifc_type].some((s) => lc(s).includes(lc(a.kind)))) return false;
    if (a.storey && !lc(e.storey).includes(lc(a.storey))) return false;
    if (a.size && !squash(e.profile).includes(squash(a.size))) return false;
    if (a.grid && !squash(gridOf(e)).includes(squash(a.grid))) return false;
    if (a.status && e.status !== a.status) return false;
    return true;
  });
  return {
    count: hits.length,
    returned: Math.min(limit, hits.length),
    limit,
    filters: Object.fromEntries(Object.entries({ mark: a.mark, kind: a.kind, storey: a.storey, size: a.size, grid: a.grid, status: a.status })
      .filter(([, x]) => x != null && x !== "")),
    elements: hits.slice(0, limit).map((e) => ({
      global_id: e.global_id, mark: e.mark, name: e.name, kind: e.cat, ifc_type: e.ifc_type, storey: e.storey, size: e.profile,
      grid: gridOf(e) || null, status: e.status,
      calcs: (links.get(e.global_id) ?? []).filter((l) => l.review !== "rejected")
        .map((l) => ({ calc: l.calc, role: l.role, band: l.band, confidence: l.confidence, review: l.review })),
    })),
    source: await p.source(v),
  };
}

// ---------------------------------------------------------------- get_element

export type GetElementArgs = { id: string } & RevisionArgs;

export async function getElement(p: LoadedProject, a: GetElementArgs) {
  const v = await p.view(a.model_revision, a.calc_revision);
  const e = resolveElement(v, a.id);
  const idx = elementIndex(v);
  const gid = e.global_id;
  const groups = v.exp.groups.filter((g) => g.members.includes(gid));
  const groupIds = new Set(groups.map((g) => g.id));
  return {
    element: e,
    grid: gridOf(e) || null,
    calcs: (v.exp.elements.find((x) => x.global_id === gid)?.calcs ?? []) as ExportLink[],
    typical_groups: groups.map((g) => ({ id: g.id, cat: g.cat, storey: g.storey, profile: g.profile, title: g.title, members: g.members.length })),
    group_links: v.exp.group_links.filter((l) => groupIds.has(l.group)),
    findings: v.exp.findings.filter((f) => f.global_id === gid),
    load_path: {
      /** supports edges where this element is supported by the other one (its load goes there). */
      bears_on: v.state.edges.filter((x) => x.src === gid).map((x) => ({ ...brief(idx.get(x.dst), x.dst), rule: x.rule, gap: x.gap })),
      /** supports edges where the other element is supported by this one. */
      carries: v.state.edges.filter((x) => x.dst === gid).map((x) => ({ ...brief(idx.get(x.src), x.src), rule: x.rule, gap: x.gap })),
    },
    connectivity: v.exp.connectivity.filter((c) => c.a === gid || c.b === gid).map((c) => {
      const other = c.a === gid ? c.b : c.a;
      return { ...brief(idx.get(other), other), rule: c.rule, explicit: c.explicit };
    }),
    decisions: v.decisions.filter((d) => d.global_id === gid),
    source: await p.source(v),
  };
}

// ---------------------------------------------------------------- get_calc

export type GetCalcArgs = { key: string; include_text?: boolean | null; max_chars?: number | null } & RevisionArgs;

export async function getCalc(p: LoadedProject, a: GetCalcArgs) {
  const v = await p.view(a.model_revision, a.calc_revision);
  if (!v.set) throw new ToolInputError("this project has no calc package yet");
  const want = a.key.trim();
  // a calc ref ("d1#beam-design"), else a bare key when exactly one document has it, else a title
  const bare = v.exp.calcs.filter((c) => c.key.slice(c.key.indexOf("#") + 1) === want);
  const calc = v.exp.calcs.find((c) => c.key === want) ?? (bare.length === 1 ? bare[0] : undefined)
    ?? v.exp.calcs.find((c) => lc(c.title) === lc(want));
  if (!calc && bare.length > 1) {
    throw new ToolInputError(`calc key ${JSON.stringify(want)} is in ${bare.length} calc documents: name one (${bare.map((c) => c.key).join(", ")})`);
  }
  if (!calc) {
    const keys = v.exp.calcs.slice(0, 60).map((c) => c.key).join(", ");
    throw new ToolInputError(`no calc ${JSON.stringify(want)} in calc revisions ${v.calcRevs.map((c) => c.rev.id).join(", ")}; calc keys: ${keys}`);
  }
  const idx = elementIndex(v);
  const titles = new Map(v.exp.calcs.map((c) => [c.key, c.title]));
  const linked = v.exp.elements.flatMap((x) => x.calcs.filter((l) => l.calc === calc.key).map((l) => {
    const el = idx.get(x.global_id);
    const { calc: _c, title: _t, ...link } = l;
    return { ...brief(el, x.global_id), element_status: x.status, ...link };
  })).sort((p1, p2) => p2.confidence - p1.confidence);
  let text: { text: string; chars: number; truncated: boolean } | null = null;
  if (a.include_text) {
    const full = calcText(v.set.combined, calc);
    const max = Math.max(500, Math.min(200_000, Math.trunc(a.max_chars ?? 20_000)));
    text = { text: full.slice(0, max), chars: full.length, truncated: full.length > max };
  }
  return {
    calc,
    linked_elements: linked,
    group_links: v.exp.group_links.filter((l) => l.calc_key === calc.key),
    findings: v.exp.findings.filter((f) => f.calc_key === calc.key),
    calc_edges: {
      /** this calc's output feeds these calcs */
      feeds: v.exp.calc_edges.filter((x) => x.src === calc.key).map((x) => ({ ...x, dst_title: titles.get(x.dst) ?? null })),
      /** these calcs feed this calc */
      fed_by: v.exp.calc_edges.filter((x) => x.dst === calc.key).map((x) => ({ ...x, src_title: titles.get(x.src) ?? null })),
    },
    /** The calc's own text (its regions of the PDF), only with include_text. */
    text,
    source: await p.source(v),
  };
}

// ---------------------------------------------------------------- impact_of_change

export type ImpactArgs = { id: string; mode?: ImpactMode | null } & RevisionArgs;

export async function impactOfChange(p: LoadedProject, a: ImpactArgs) {
  const v = await p.view(a.model_revision, a.calc_revision);
  const e = resolveElement(v, a.id);
  const mode: ImpactMode = a.mode ?? "change";
  // the same call, on the same inputs, as the app's projectService.impactOf
  const imp = await impactOf(v.model.graph, v.set, v.run, v.decisions, e.global_id, mode);
  const idx = elementIndex(v);
  const titles = new Map(v.exp.calcs.map((c) => [c.key, c.title]));
  return {
    impact: imp,
    summary: { removed: imp.removed.length, hit: Object.keys(imp.hit).length, stale_calcs: Object.keys(imp.stale).length, waves: imp.waves },
    hit_elements: Object.entries(imp.hit).sort((x, y) => x[1] - y[1] || (x[0] < y[0] ? -1 : 1))
      .map(([gid, wave]) => ({ ...brief(idx.get(gid), gid), wave, why: imp.why[gid] ?? null })),
    stale_calcs: Object.entries(imp.stale).map(([key, why]) => ({ calc: key, title: titles.get(key) ?? null, why })),
    source: await p.source(v),
  };
}

// ---------------------------------------------------------------- list_revisions / compare_revisions

export async function listRevisions(p: LoadedProject) {
  const hm = p.head("model")?.id ?? null, hc = p.head("calcs")?.id ?? null;
  const revs = p.revisions;
  return {
    revisions: {
      model: revs.filter((r) => r.kind === "model").map((r) => revisionRow(r, r.id === hm)),
      calcs: revs.filter((r) => r.kind === "calcs").map((r) => revisionRow(r, r.id === hc)),
    },
    head: { model: hm, calcs: hc },
    decisions: p.decisions.length,
    source: { project_file_sha256: p.sha256, project: p.file.project.name, exported_at: p.file.exportedAt },
  };
}

export type CompareArgs = { a?: number | null; b?: number | null };

export async function compareRevisions(p: LoadedProject, a: CompareArgs = {}) {
  const models = p.revisions.filter((r) => r.kind === "model");
  const bId = a.b ?? p.head("model")?.id ?? null;
  const aId = a.a ?? [...models].filter((r) => bId == null || r.id < bId).pop()?.id ?? null;
  if (aId == null || bId == null) throw new ToolInputError(`compare needs two model revisions; this project has ${models.length}`);
  const [ma, mb] = await Promise.all([p.model(aId), p.model(bId)]);
  // the app's compareRevisions passes the revision ids as labels
  const compare = diffGraphs(ma.graph, mb.graph, { a: aId, b: bId });
  return {
    compare,
    summary: {
      removed: compare.removed.length, added: compare.added.length, changed: compare.changed.length,
      edges_removed: compare.edges_removed.length, edges_added: compare.edges_added.length,
    },
    source: {
      project_file_sha256: p.sha256,
      a: { id: aId, label: ma.rev.label, source_name: ma.rev.sourceName, graph_sha256: await sha256Json(ma.graph) },
      b: { id: bId, label: mb.rev.label, source_name: mb.rev.sourceName, graph_sha256: await sha256Json(mb.graph) },
    },
  };
}

// ---------------------------------------------------------------- list_findings / list_typical_groups

export type FindingsArgs = { calc?: string | null; element?: string | null; limit?: number | null } & RevisionArgs;

export async function listFindings(p: LoadedProject, a: FindingsArgs = {}) {
  const v = await p.view(a.model_revision, a.calc_revision);
  const gid = a.element ? resolveElement(v, a.element).global_id : null;
  const all = v.exp.findings.filter((f) => (!a.calc || f.calc_key === a.calc) && (!gid || f.global_id === gid));
  const limit = Math.max(1, Math.min(500, Math.trunc(a.limit ?? 100)));
  const idx = elementIndex(v);
  const titles = new Map(v.exp.calcs.map((c) => [c.key, c.title]));
  const shown = all.slice(0, limit);
  return {
    count: all.length,
    returned: shown.length,
    findings: shown,
    labels: {
      elements: Object.fromEntries(shown.map((f) => [f.global_id, idx.get(f.global_id)?.mark ?? null])),
      calcs: Object.fromEntries(shown.map((f) => [f.calc_key, titles.get(f.calc_key) ?? null])),
    },
    note: "Findings of links a reviewer rejected are left out (as in the app).",
    source: await p.source(v),
  };
}

export type GroupsArgs = { kind?: string | null; storey?: string | null; size?: string | null; linked_only?: boolean | null; limit?: number | null } & RevisionArgs;

export async function listTypicalGroups(p: LoadedProject, a: GroupsArgs = {}) {
  const v = await p.view(a.model_revision, a.calc_revision);
  const idx = elementIndex(v);
  const limit = Math.max(1, Math.min(500, Math.trunc(a.limit ?? 100)));
  const byGroup = new Map<string, typeof v.exp.group_links>();
  for (const l of v.exp.group_links) (byGroup.get(l.group) ?? byGroup.set(l.group, []).get(l.group)!).push(l);
  const rows = v.exp.groups
    .filter((g) => (!a.kind || lc(g.cat).includes(lc(a.kind))) && (!a.storey || lc(g.storey).includes(lc(a.storey))) &&
      (!a.size || squash(g.profile).includes(squash(a.size))) && (!a.linked_only || byGroup.has(g.id)))
    .map((g) => ({ group: g, member_marks: g.members.map((m) => idx.get(m)?.mark ?? null), links: byGroup.get(g.id) ?? [] }));
  return { count: rows.length, returned: Math.min(limit, rows.length), groups: rows.slice(0, limit), source: await p.source(v) };
}

// ---------------------------------------------------------------- get_page_image

export type PageImageArgs = { page: number; calc_revision?: number | null; rect?: number[] | null; highlight?: number[][] | null; width?: number | null };

export async function getPageImage(p: LoadedProject, a: PageImageArgs): Promise<{ image: PageImage; meta: Record<string, unknown> }> {
  const heads = p.headSet();
  if (a.calc_revision == null && heads.length > 1) {
    throw new ToolInputError(`this project has ${heads.length} calc documents: name one with calc_revision (${heads.map((r) => `${r.id} = ${r.sourceName}`).join(", ")}); page is that PDF's own page`);
  }
  const cid = a.calc_revision ?? heads[0]?.id ?? null;
  if (cid == null) throw new ToolInputError("this project has no calc package yet");
  const c = await p.calcRevision(cid);
  const image = await renderPage(c.bytes, a.page, { rect: a.rect ?? null, highlight: a.highlight ?? null, width: a.width ?? null });
  return {
    image,
    meta: {
      page: image.page.n, page_count: image.page.count, page_size_pt: [image.page.width, image.page.height],
      area_pt: image.area, pixels: [image.width, image.height], scale_px_per_pt: image.scale,
      frame: "sheet: PDF points, origin top-left, y down (the frame of every rect the other tools return)",
      source: {
        project_file_sha256: p.sha256, calc_revision: c.rev.id, source_name: c.rev.sourceName, pdf_sha256: c.pkg.source_sha256,
      },
    },
  };
}

// ---------------------------------------------------------------- move_column (@unloaded/move-impact)

export type MoveArgs = { column: string; dx?: number | null; dy?: number | null; remove?: boolean | null } & RevisionArgs;

export async function moveColumn(p: LoadedProject, a: MoveArgs) {
  const v = await p.view(a.model_revision, a.calc_revision);
  const col = resolveElement(v, a.column);
  if (col.cat !== "Column") throw new ToolInputError(`${a.column} is a ${col.cat}, not a column`);
  const dx = a.dx ?? 0, dy = a.dy ?? 0;
  if (!a.remove && dx === 0 && dy === 0) throw new ToolInputError("give dx and/or dy (metres), or remove: true");
  const move: Move = a.remove ? { column: col.global_id, remove: true } : { column: col.global_id, dx, dy };
  // links with the decision log applied (move-impact ignores rejected ones); no calc facts: calc-mapper
  // does not extract calc row values yet, so no utilisation estimate or health band can be stated
  const result = moveImpact({ graph: v.model.graph, graphSha256: v.graphSha256, move, links: v.state.links });
  return {
    result,
    note: "What-if only: nothing is changed or saved. No calc facts are given (the calc engine does not read calc row " +
      "values yet), so this is the topological and geometric screen only: no utilisation estimates and no health band.",
    source: await p.source(v),
  };
}

export { ProjectFileError };
