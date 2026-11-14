// THE ONLY PLACE backend shapes become view data.
//
//   backend /export (+ /state)  ──┐
//                                 ├─> toCalcData() ──> CalcData ──┐
//   export JSON loaded from file ─┘                               ├─> mergeProject() ──> ProjectViewModel
//   ElementGraph ──> src/loaders/elementGraphToBim.ts ──> ElementTopology ──┘   (src/data/mergeProject.ts)
//
// The element graph (packages/element-graph) is the source of truth for elements and topology; the
// backend is the calc engine (links, evidence, review status, calcs, calc dependencies, impact,
// revisions). /export is the calc contract (what "Download export JSON" saves and offline mode reads
// back); /state only adds calc colours and the model revision's project name.
// Impact, compare and revision payloads are converted here too (toImpactView, toModelDiff,
// toRevisionList) so no component ever reads an Api* type.
//
// exportToModelInput() exists for one case: an export opened from disk (or a backend revision whose
// serialized graph is not available) carries no element graph, so its elements and load path are
// turned into a ModelInput and go through the SAME buildGraph -> elementGraphToBim path as an IFC.
import { buildGraph, type ElementKind, type ModelInput, type ElementGraph } from '@unloaded/element-graph';
import type { ApiCompare, ApiExport, ApiImpact, ApiRevision, ApiRevisions, ApiState } from '../api/types';
import type {
  BimLink,
  BimNode,
  CalcData,
  CalcDependency,
  CalcLink,
  CalcPackage,
  ImpactView,
  MappingStatus,
  ModelDiff,
  NodeDiffMeta,
  RevisionInfo,
} from '../types/bim';
import { computeRadialLayout } from '../utils/graphEngine';
import { CALC_PALETTE } from '../utils/colors';

export const CALC_ROOT_ID = 'calc-root';
export const calcNodeId = (key: string) => `calc:${key}`;
const calcCategoryId = (type: string) => `calccat:${type || 'general'}`;

function metaProject(r: ApiRevision | null | undefined): string | null {
  if (!r) return null;
  let meta = r.meta;
  if (!meta && r.meta_json) {
    try {
      meta = JSON.parse(r.meta_json) as Record<string, unknown>;
    } catch {
      meta = undefined;
    }
  }
  const p = meta?.project;
  return typeof p === 'string' && p.trim() ? p.trim() : null;
}

function shortCalcLabel(title: string): string {
  const head = title.split(' - ')[0].trim();
  return head.length > 26 ? `${head.slice(0, 25)}…` : head;
}

/** Calc engine output -> CalcData: calcs, the calc graph, and every element's links by GlobalId. */
export function toCalcData(exp: ApiExport, state?: ApiState | null): CalcData {
  const stateCalcColor = new Map<string, string>((state?.calcs ?? []).map((c) => [c.key, c.color]));

  const calcs: CalcPackage[] = exp.calcs.map((c, i) => ({
    key: c.key,
    title: c.title || c.key,
    software: c.software || '',
    elementType: c.element_type || '',
    pages: Array.isArray(c.pages) ? c.pages : [],
    scanned: Boolean(c.scanned),
    frontMatter: Boolean(c.front_matter),
    titleBox: c.title_box ? { page: c.title_box.page, rects: c.title_box.rects ?? [] } : null,
    color: stateCalcColor.get(c.key) ?? CALC_PALETTE[i % CALC_PALETTE.length],
  }));
  const calcByKey = new Map(calcs.map((c) => [c.key, c]));

  const calcDependencies: CalcDependency[] = exp.calc_edges.map((e) => ({
    source: e.src,
    target: e.dst,
    rules: e.rules ?? [],
    evidence: (e.evidence ?? []).map((ev) => ({ calcKey: ev.calc, page: ev.page, text: ev.text, line: ev.line ?? null, rects: ev.rects ?? [] })),
  }));

  const linksByElement = new Map<string, CalcLink[]>();
  const statusByElement = new Map<string, MappingStatus>();
  const calcToElementIds = new Map<string, string[]>();
  for (const e of exp.elements) {
    const links: CalcLink[] = (e.calcs ?? [])
      .map((l) => ({
        elementId: e.global_id,
        calcKey: l.calc,
        confidence: typeof l.confidence === 'number' ? l.confidence : 0,
        tier: l.tier,
        rule: l.rule,
        matchedText: l.matched_text ?? '',
        review: l.review,
        evidence: { page: l.evidence?.page ?? l.page ?? null, rects: l.evidence?.rects ?? [], snippet: l.evidence?.snippet ?? null },
      }))
      .sort((a, b) => b.confidence - a.confidence);
    linksByElement.set(e.global_id, links);
    statusByElement.set(e.global_id, e.status ?? 'unmapped');
    for (const l of links) {
      if (l.review === 'rejected' || !calcByKey.has(l.calcKey)) continue;
      const arr = calcToElementIds.get(l.calcKey) ?? [];
      if (!arr.includes(e.global_id)) arr.push(e.global_id);
      calcToElementIds.set(l.calcKey, arr);
    }
  }

  // calc graph: root -> element type the calc designs -> calc, plus calc -> calc dependencies
  const calcNodes: BimNode[] = [
    {
      id: CALC_ROOT_ID,
      label: 'Calc package',
      kind: 'calc-root',
      level: 0,
      r: 36,
      x: 0,
      y: 0,
      desc: `${exp.calc_package ?? 'No calc package'} · ${calcs.length} calculation${calcs.length === 1 ? '' : 's'}`,
    },
  ];
  const calcLinks: BimLink[] = [];
  const seen = new Set<string>();
  for (const c of calcs) {
    const type = c.frontMatter ? 'Front matter' : c.elementType;
    const cid = calcCategoryId(type);
    if (!seen.has(cid)) {
      seen.add(cid);
      calcNodes.push({
        id: cid,
        label: type ? (type === 'Front matter' ? type : `${type} calcs`) : 'General',
        kind: 'calc-category',
        level: 1,
        parent: CALC_ROOT_ID,
        r: 26,
        x: 0,
        y: 0,
        desc: type ? `Calculations that design ${type.toLowerCase()} elements` : 'Calculations not tied to one element type',
      });
      calcLinks.push({ source: CALC_ROOT_ID, target: cid, relation: 'hierarchy' });
    }
    const linked = calcToElementIds.get(c.key)?.length ?? 0;
    calcNodes.push({
      id: calcNodeId(c.key),
      label: shortCalcLabel(c.title),
      kind: 'calc',
      level: 2,
      parent: cid,
      categoryParent: cid,
      calcKey: c.key,
      color: c.color,
      r: linked > 40 ? 17 : linked > 0 ? 14 : 11,
      x: 0,
      y: 0,
      desc: `${c.title}${c.software ? ` · ${c.software}` : ''} · ${linked} linked element${linked === 1 ? '' : 's'}`,
    });
    calcLinks.push({ source: cid, target: calcNodeId(c.key), relation: 'hierarchy' });
  }
  for (const d of calcDependencies) {
    if (!calcByKey.has(d.source) || !calcByKey.has(d.target)) continue;
    calcLinks.push({ source: calcNodeId(d.source), target: calcNodeId(d.target), relation: 'calc-dependency' });
  }

  return {
    projectName: metaProject(state?.model_rev),
    modelName: exp.model,
    modelRevisionId: exp.model_revision,
    calcPackageName: exp.calc_package,
    calcRevisionId: exp.calc_revision,
    engine: exp.engine || '',
    calcs,
    calcDependencies,
    calcNodes: computeRadialLayout(calcNodes),
    calcLinks,
    calcToElementIds,
    linksByElement,
    statusByElement,
  };
}

/** Element-graph kind of an exported element: the backend category when /state gives it, else the IFC type. */
function kindOf(ifcType: string, cat: string | undefined): ElementKind {
  const c = (cat ?? '').toLowerCase();
  if (c && c !== 'other') return c;
  const t = ifcType.toLowerCase().replace(/standardcase$|elementedcase$/, '');
  const table: Record<string, ElementKind> = {
    ifcbeam: 'beam',
    ifccolumn: 'column',
    ifcslab: 'slab',
    ifcroof: 'slab',
    ifcwall: 'wall',
    ifcfooting: 'footing',
    ifcpile: 'pile',
    ifcmember: 'brace',
    ifcplate: 'connection',
    ifcdiscreteaccessory: 'connection',
    ifcbearing: 'connection',
    ifcmechanicalfastener: 'fastener',
    ifcfastener: 'fastener',
  };
  return table[t] ?? 'other';
}

function storeyRank(name: string, i: number): number {
  const s = name.toLowerCase();
  if (/found|footing|fdn|pile|basement/.test(s)) return -100 + i * 0.01;
  if (/roof/.test(s)) return 1000;
  const m = /(-?\d+)/.exec(s);
  return m ? parseInt(m[1], 10) : 500 + i;
}

/**
 * An export without its element graph -> ModelInput (elements, storeys, the backend's load path as
 * `supports` relations), for the shared buildGraph -> elementGraphToBim path. No geometry, so no
 * inference: the topology is exactly what the export recorded.
 */
export function exportToElementGraph(exp: ApiExport, state?: ApiState | null): ElementGraph {
  const stateEls = new Map((state?.elements ?? []).map((e) => [e.global_id, e]));
  const storeyNames = [...new Set(exp.elements.map((e) => e.storey).filter(Boolean))].sort((a, b) => a.localeCompare(b, undefined, { numeric: true }));
  const z = (name: string): number | null => {
    const zs = exp.elements.filter((e) => e.storey === name).map((e) => stateEls.get(e.global_id)?.geom?.min[2]).filter((v): v is number => typeof v === 'number');
    return zs.length ? zs.reduce((a, b) => a + b, 0) / zs.length : null;
  };
  const input: ModelInput = {
    meta: {
      version: 1,
      project: metaProject(state?.model_rev) ?? (exp.model ? exp.model.replace(/\.ifc$/i, '') : undefined),
      units: 'm',
      source: { format: 'calc-graph-export', file: exp.model ?? undefined },
    },
    levels: storeyNames.map((name, i) => ({ id: `storey:${name}`, name, elevation: z(name) ?? storeyRank(name, i) })),
    elements: exp.elements.map((e) => {
      const se = stateEls.get(e.global_id);
      return {
        id: e.global_id,
        kind: kindOf(e.ifc_type, se?.cat),
        mark: e.mark || undefined,
        name: se?.name || undefined,
        profile: e.size || se?.profile || undefined,
        levelId: e.storey ? `storey:${e.storey}` : undefined,
        params: { ...(se?.params ?? {}), ...(se?.type_name ? { 'Attr.TypeName': se.type_name } : {}) },
        source: { format: 'ifc', file: exp.model ?? undefined, nativeType: e.ifc_type },
      };
    }),
    relations: exp.load_path.map((l) => ({ a: l.src, b: l.dst, kind: 'supports', evidence: { rule: l.rule || 'calc-graph load path', source: 'inferred' as const } })),
    warnings: [],
  };
  return buildGraph(input, { infer: false }).graph;
}

/** A calc-graph export JSON (GET /api/projects/{pid}/export) - told apart from a ModelInput by `calcs` and no `meta`. */
export function isCalcGraphExport(d: unknown): d is ApiExport {
  if (!d || typeof d !== 'object') return false;
  const o = d as Partial<ApiExport> & { meta?: unknown };
  return Array.isArray(o.elements) && Array.isArray(o.calcs) && o.meta === undefined;
}

/** Normalise an export read from disk (older files may miss the optional arrays). */
export function normaliseExport(o: ApiExport): ApiExport {
  return {
    model: o.model ?? null,
    model_revision: o.model_revision ?? null,
    calc_package: o.calc_package ?? null,
    calc_revision: o.calc_revision ?? null,
    engine: o.engine ?? '',
    calcs: o.calcs,
    calc_edges: Array.isArray(o.calc_edges) ? o.calc_edges : [],
    load_path: Array.isArray(o.load_path) ? o.load_path : [],
    elements: o.elements,
  };
}

export function toImpactView(i: ApiImpact): ImpactView {
  return {
    elementId: i.global_id,
    mode: i.mode,
    removed: i.removed ?? [],
    hit: new Map(Object.entries(i.hit ?? {})),
    why: new Map(Object.entries(i.why ?? {})),
    stale: new Map(Object.entries(i.stale ?? {})),
    waves: i.waves ?? 0,
  };
}

const fmtValue = (v: unknown): string => (v === null || v === undefined || v === '' ? '—' : String(v));

const FIELD_LABELS: Record<string, string> = {
  mark: 'Mark',
  profile: 'Section / Profile',
  storey: 'Level / Storey',
  type_name: 'Type',
  geometry: 'Geometry',
};

/** GET /compare -> the diff view model (per element status + before/after field changes). */
export function toModelDiff(c: ApiCompare): ModelDiff {
  const meta = new Map<string, NodeDiffMeta>();
  for (const x of c.added) {
    meta.set(x.global_id, { status: 'added', changes: [{ field: 'Presence', before: `Not in rev A`, after: `Added in rev B` }] });
  }
  for (const x of c.removed) {
    meta.set(x.global_id, { status: 'removed', changes: [{ field: 'Presence', before: `Present in rev A`, after: `Removed in rev B` }] });
  }
  for (const x of c.changed) {
    meta.set(x.global_id, {
      status: 'modified',
      changes: Object.entries(x.fields).map(([field, pair]) => ({
        field: FIELD_LABELS[field] ?? field,
        before: fmtValue(Array.isArray(pair) ? pair[0] : undefined),
        after: fmtValue(Array.isArray(pair) ? pair[1] : undefined),
      })),
    });
  }
  return {
    a: c.a,
    b: c.b,
    meta,
    onlyInA: c.removed.map((x) => ({ elementId: x.global_id, mark: x.mark || '', category: x.cat || '' })),
    onlyInB: c.added.map((x) => ({ elementId: x.global_id, mark: x.mark || '', category: x.cat || '' })),
    edgesAdded: c.edges_added.length,
    edgesRemoved: c.edges_removed.length,
  };
}

/** Every ingest makes its revision the head of its kind, so the head is the newest of each kind. */
export function toRevisionList(r: ApiRevisions): RevisionInfo[] {
  const head = new Map<string, number>();
  for (const x of r.revisions) head.set(x.kind, Math.max(head.get(x.kind) ?? 0, x.id));
  return r.revisions
    .map((x) => ({
      id: x.id,
      kind: x.kind,
      seq: x.seq,
      label: x.label || x.source_name,
      sourceName: x.source_name,
      createdAt: x.created_at,
      count: typeof x.count === 'number' ? x.count : null,
      isHead: head.get(x.kind) === x.id,
    }))
    .sort((a, b) => b.id - a.id);
}
