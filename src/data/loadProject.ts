// THE ONLY PLACE backend shapes become the view model.
//
//   backend /export (+ /state)  ──┐
//                                 ├─> loadProject() ──> ProjectViewModel (src/types/bim.ts) ──> views
//   export JSON loaded from file ─┘
//
// /export is the contract (it is what "Export JSON" downloads and what offline mode reads back).
// /state, when the API is up, only enriches it with what export leaves out: element names, type
// names, the open parameter set, geometry-based storey order, calc colours and revision labels.
// Impact, compare and revision payloads are converted here too (toImpactView, toModelDiff,
// toRevisionList) so no component ever reads an Api* type.
import type {
  ApiCompare,
  ApiElement,
  ApiExport,
  ApiExportElement,
  ApiImpact,
  ApiRevision,
  ApiRevisions,
  ApiState,
} from '../api/types';
import type {
  BimLink,
  BimNode,
  CalcDependency,
  CalcLink,
  CalcPackage,
  DatabaseDiffSummary,
  DiffStatus,
  GhostSource,
  ImpactView,
  ModelDiff,
  NodeDiffMeta,
  LoadPathEdge,
  MappingStatus,
  ProjectViewModel,
  RevisionInfo,
} from '../types/bim';
import { computeRadialLayout } from '../utils/graphEngine';
import { CALC_PALETTE } from '../utils/colors';

export const PROJECT_NODE_ID = 'project';
export const CALC_ROOT_ID = 'calc-root';
export const calcNodeId = (key: string) => `calc:${key}`;
export const categoryNodeId = (ifcType: string) => `cat:${ifcType}`;
const familyNodeId = (ifcType: string, family: string) => `fam:${ifcType}:${family}`;
const calcCategoryId = (type: string) => `calccat:${type || 'general'}`;

export interface LoadInput {
  export: ApiExport;
  state?: ApiState | null;
}

export interface LoadOptions {
  source: 'api' | 'file';
  projectId: number | null;
}

/** Mark family: the letters of a mark without the level prefix or the running number (2B13 -> B, ST-1 -> ST). */
export function markFamily(mark: string): string | null {
  const m = /^\d*([A-Za-z]+(?:-?[A-Za-z]+)*)/.exec(mark.trim());
  return m ? m[1].toUpperCase() : null;
}

function storeyHeuristic(name: string, i: number): number {
  const s = name.toLowerCase();
  if (/found|footing|fdn|pile|basement/.test(s)) return -100 + i * 0.01;
  if (/roof/.test(s)) return 1000;
  const m = /(-?\d+)/.exec(s);
  if (m) return parseInt(m[1], 10);
  return 500 + i;
}

/** Storey -> order (bottom first): the mean element base height when geometry is known, else the name. */
function storeyOrdering(storeys: string[], stateEls: Map<string, ApiElement>, exportEls: ApiExportElement[]): Map<string, number> {
  const z = new Map<string, { sum: number; n: number }>();
  for (const e of exportEls) {
    const g = stateEls.get(e.global_id)?.geom;
    if (!g || g.min.length < 3) continue;
    const acc = z.get(e.storey) ?? { sum: 0, n: 0 };
    acc.sum += g.min[2];
    acc.n += 1;
    z.set(e.storey, acc);
  }
  const sorted = [...storeys].sort((a, b) => a.localeCompare(b, undefined, { numeric: true }));
  const out = new Map<string, number>();
  sorted.forEach((s, i) => {
    const acc = z.get(s);
    out.set(s, acc && acc.n ? acc.sum / acc.n : storeyHeuristic(s, i));
  });
  return out;
}

function projectNameOf(exp: ApiExport, state?: ApiState | null): string {
  const metaProject = (r: ApiRevision | null | undefined): string | null => {
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
  };
  return (
    metaProject(state?.model_rev) ||
    (exp.model ? exp.model.replace(/\.ifc$/i, '') : null) ||
    (exp.calc_package ? exp.calc_package.replace(/\.pdf$/i, '') : null) ||
    'Untitled project'
  );
}

function shortCalcLabel(title: string): string {
  const head = title.split(' - ')[0].trim();
  return head.length > 26 ? `${head.slice(0, 25)}…` : head;
}

export function loadProject(input: LoadInput, opts: LoadOptions): ProjectViewModel {
  const exp = input.export;
  const state = input.state ?? null;
  const stateEls = new Map<string, ApiElement>((state?.elements ?? []).map((e) => [e.global_id, e]));
  const stateCalcColor = new Map<string, string>((state?.calcs ?? []).map((c) => [c.key, c.color]));
  const projectName = projectNameOf(exp, state);

  // ---- calcs
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
    evidence: (e.evidence ?? []).map((ev) => ({
      calcKey: ev.calc,
      page: ev.page,
      text: ev.text,
      line: ev.line ?? null,
      rects: ev.rects ?? [],
    })),
  }));

  const loadPath: LoadPathEdge[] = exp.load_path.map((e) => ({ source: e.src, target: e.dst, rule: e.rule }));

  // ---- element hierarchy: project -> IFC type -> mark family -> element
  const storeys = [...new Set(exp.elements.map((e) => e.storey).filter(Boolean))];
  const storeyOrder = storeyOrdering(storeys, stateEls, exp.elements);

  const elementNodes: BimNode[] = [
    {
      id: PROJECT_NODE_ID,
      label: projectName,
      kind: 'project',
      level: 0,
      r: 36,
      x: 0,
      y: 0,
      desc: [exp.model, exp.calc_package].filter(Boolean).join(' ⇄ ') || 'No model or calc package loaded',
    },
  ];
  const hierarchyLinks: BimLink[] = [];
  const seen = new Set<string>();
  const calcToElementIds = new Map<string, string[]>();
  const counts: Record<MappingStatus, number> = { confirmed: 0, review: 0, unmapped: 0 };

  const sortedEls = [...exp.elements].sort(
    (a, b) =>
      a.ifc_type.localeCompare(b.ifc_type) ||
      (a.mark || '').localeCompare(b.mark || '', undefined, { numeric: true }) ||
      (storeyOrder.get(a.storey) ?? 0) - (storeyOrder.get(b.storey) ?? 0),
  );

  for (const e of sortedEls) {
    const ifcType = e.ifc_type || 'IfcBuildingElementProxy';
    const catId = categoryNodeId(ifcType);
    if (!seen.has(catId)) {
      seen.add(catId);
      elementNodes.push({ id: catId, label: ifcType, kind: 'category', level: 1, parent: PROJECT_NODE_ID, ifcType, r: 26, x: 0, y: 0 });
      hierarchyLinks.push({ source: PROJECT_NODE_ID, target: catId, relation: 'hierarchy' });
    }
    const fam = markFamily(e.mark || '') ?? 'Unmarked';
    const famId = familyNodeId(ifcType, fam);
    if (!seen.has(famId)) {
      seen.add(famId);
      elementNodes.push({
        id: famId,
        label: fam,
        kind: 'family',
        level: 1.5,
        parent: catId,
        categoryParent: catId,
        ifcType,
        r: 15,
        x: 0,
        y: 0,
      });
      hierarchyLinks.push({ source: catId, target: famId, relation: 'hierarchy' });
    }

    const se = stateEls.get(e.global_id);
    const calcLinks: CalcLink[] = (e.calcs ?? [])
      .map((l) => ({
        elementId: e.global_id,
        calcKey: l.calc,
        confidence: typeof l.confidence === 'number' ? l.confidence : 0,
        tier: l.tier,
        rule: l.rule,
        matchedText: l.matched_text ?? '',
        review: l.review,
        evidence: {
          page: l.evidence?.page ?? l.page ?? null,
          rects: l.evidence?.rects ?? [],
          snippet: l.evidence?.snippet ?? null,
        },
      }))
      .sort((a, b) => b.confidence - a.confidence);
    for (const l of calcLinks) {
      if (l.review === 'rejected' || !calcByKey.has(l.calcKey)) continue;
      const arr = calcToElementIds.get(l.calcKey) ?? [];
      if (!arr.includes(e.global_id)) arr.push(e.global_id);
      calcToElementIds.set(l.calcKey, arr);
    }
    const status: MappingStatus = e.status ?? 'unmapped';
    counts[status] = (counts[status] ?? 0) + 1;

    const name = se?.name || '';
    elementNodes.push({
      id: e.global_id,
      label: e.mark || name || ifcType.replace(/^Ifc/, ''),
      kind: 'element',
      level: 2,
      parent: famId,
      categoryParent: catId,
      ifcType,
      storey: e.storey || undefined,
      storeyOrder: e.storey ? storeyOrder.get(e.storey) : undefined,
      mark: e.mark || undefined,
      size: e.size || se?.profile || undefined,
      name: name || undefined,
      typeName: se?.type_name || undefined,
      params: se?.params,
      mappingStatus: status,
      calcLinks,
      r: 8,
      x: 0,
      y: 0,
      desc: [name || ifcType, e.storey].filter(Boolean).join(' · '),
    });
    hierarchyLinks.push({ source: famId, target: e.global_id, relation: 'hierarchy' });
  }

  // ---- calc graph: root -> element type the calc designs -> calc, plus calc -> calc dependencies
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
    source: opts.source,
    projectId: opts.projectId,
    projectName,
    modelName: exp.model,
    modelRevisionId: exp.model_revision,
    calcPackageName: exp.calc_package,
    calcRevisionId: exp.calc_revision,
    engine: exp.engine || '',
    elementNodes: computeRadialLayout(elementNodes),
    hierarchyLinks,
    loadPath,
    calcs,
    calcDependencies,
    calcNodes: computeRadialLayout(calcNodes),
    calcLinks,
    calcToElementIds,
    counts,
    hasUtilization: elementNodes.some((n) => typeof n.utilization === 'number'),
  };
}

/** Offline mode: a calc-graph export JSON (GET /api/projects/{pid}/export, saved to disk). */
export function loadProjectFromFile(text: string): ProjectViewModel {
  let parsed: unknown;
  try {
    parsed = JSON.parse(text.replace(/^﻿/, ''));
  } catch {
    throw new Error('That file is not JSON.');
  }
  const o = parsed as Partial<ApiExport> | null;
  if (!o || typeof o !== 'object' || !Array.isArray(o.elements) || !Array.isArray(o.calcs)) {
    throw new Error('Not a calc-graph export: expected "elements" and "calcs" arrays.');
  }
  const exp: ApiExport = {
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
  return loadProject({ export: exp }, { source: 'file', projectId: null });
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

const GHOST_CATEGORY_ID = 'cat:not-in-head';

/**
 * Lay a backend diff over the head-model view: every element gets its diff status and field
 * changes, and elements of the diff that the head model does not have (removed ones when B is the
 * head, added ones when A is) become ghost nodes placed in their mark family, with their geometry
 * to be drawn from the revision that has them.
 */
export function applyModelDiff(
  view: ProjectViewModel,
  diff: ModelDiff,
  names: { base: string; compare: string },
): { view: ProjectViewModel; summary: DatabaseDiffSummary; ghosts: GhostSource[] } {
  const present = new Set(view.elementNodes.filter((n) => n.kind === 'element').map((n) => n.id));
  const families = view.elementNodes.filter((n) => n.kind === 'family');
  const nodes: BimNode[] = view.elementNodes.map((n) => {
    if (n.kind !== 'element') return n;
    const m = diff.meta.get(n.id);
    return { ...n, diffStatus: m?.status ?? 'unchanged', diffChanges: m?.changes ?? [] };
  });
  const links = [...view.hierarchyLinks];
  const ghostIds = new Map<number, string[]>();
  let needGhostCategory = false;

  const addGhost = (g: { elementId: string; mark: string; category: string }, status: DiffStatus, rid: number) => {
    if (present.has(g.elementId)) return;
    const fam = markFamily(g.mark);
    const famNode = fam ? families.find((f) => f.label === fam) : undefined;
    const parent = famNode?.id ?? GHOST_CATEGORY_ID;
    if (!famNode) needGhostCategory = true;
    nodes.push({
      id: g.elementId,
      label: g.mark || g.category || 'Element',
      kind: 'element',
      level: 2,
      parent,
      categoryParent: famNode?.categoryParent ?? GHOST_CATEGORY_ID,
      ifcType: famNode?.ifcType,
      mark: g.mark || undefined,
      calcLinks: [],
      r: 8,
      x: 0,
      y: 0,
      desc: `${g.category || 'Element'} · only in revision ${rid}`,
      diffStatus: status,
      diffChanges: diff.meta.get(g.elementId)?.changes ?? [],
      isGhost: true,
    });
    links.push({ source: parent, target: g.elementId, relation: 'hierarchy' });
    (ghostIds.get(rid) ?? ghostIds.set(rid, []).get(rid)!).push(g.elementId);
  };
  diff.onlyInA.forEach((g) => addGhost(g, 'removed', diff.a));
  diff.onlyInB.forEach((g) => addGhost(g, 'added', diff.b));
  if (needGhostCategory) {
    nodes.push({ id: GHOST_CATEGORY_ID, label: 'Not in head', kind: 'category', level: 1, parent: PROJECT_NODE_ID, r: 26, x: 0, y: 0, desc: 'Diff elements whose mark family is not in the head model' });
    links.push({ source: PROJECT_NODE_ID, target: GHOST_CATEGORY_ID, relation: 'hierarchy' });
  }

  const els = nodes.filter((n) => n.kind === 'element');
  const count = (s: DiffStatus) => els.filter((n) => n.diffStatus === s).length;
  const summary: DatabaseDiffSummary = {
    baseName: names.base,
    compareName: names.compare,
    baseRevisionId: diff.a,
    compareRevisionId: diff.b,
    addedCount: diff.onlyInB.length,
    removedCount: diff.onlyInA.length,
    modifiedCount: count('modified'),
    unchangedCount: count('unchanged'),
    edgesAdded: diff.edgesAdded,
    edgesRemoved: diff.edgesRemoved,
  };
  return {
    view: { ...view, elementNodes: computeRadialLayout(nodes), hierarchyLinks: links },
    summary,
    ghosts: [...ghostIds.entries()].map(([revisionId, elementIds]) => ({ revisionId, elementIds })),
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
