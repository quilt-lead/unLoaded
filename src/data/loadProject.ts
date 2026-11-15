// THE ONLY PLACE calc-engine output becomes view data.
//
//   @unloaded/calc-mapper Export ──> toCalcData() ──> CalcData ──┐
//   (from the worker, or an export JSON opened from disk)        ├─> mergeProject() ──> ProjectViewModel
//   ElementGraph ──> src/loaders/elementGraphToBim.ts ──> ElementTopology ┘   (src/data/mergeProject.ts)
//
// The element graph (packages/element-graph) is the source of truth for elements and topology; the
// calc engine (packages/calc-mapper, in a Web Worker) gives links, evidence, review status, calcs,
// calc dependencies, impact and the revision diff. Impact, diff and the store's revision list are
// converted here too (toImpactView, toModelDiff, toRevisionList) so no component reads an engine type.
//
// exportToElementGraph() exists for one case: an export opened from disk carries no element graph,
// so its elements, load path and connectivity are turned into a ModelInput and go through the SAME
// buildGraph -> elementGraphToBim path as an IFC.
import { buildGraph, type ElementKind, type ModelInput, type ElementGraph } from '@unloaded/element-graph';
import type { Compare, Export, ExportProducers, Impact, Provenance } from '@unloaded/calc-mapper/types';
import type { CalcSetDiff } from '@unloaded/calc-mapper';
import { docIdOf, type ProjectFileDocument } from '@unloaded/project-file';
import type { RevisionRecord } from './projectStore';
import type {
  BimLink,
  BimNode,
  CalcData,
  CalcDocumentInfo,
  CalcRevisionDiffView,
  CalcDependency,
  CalcLink,
  CalcOrigin,
  CalcPackage,
  FindingView,
  ImpactView,
  TypicalGroupView,
  MappingStatus,
  ModelDiff,
  NodeDiffMeta,
  ProducerRecords,
  ProvenanceView,
  RevisionInfo,
} from '../types/bim';
import { computeRadialLayout, getCalcBubbleLayout } from '../utils/graphEngine';
import { CALC_PALETTE } from '../utils/colors';

export const CALC_ROOT_ID = 'calc-root';
export const calcNodeId = (key: string) => `calc:${key}`;
const calcCategoryId = (type: string) => `calccat:${type || 'general'}`;
/** The calc engine's category for load criteria / load analysis calcs (calc-mapper `CalcCategory`). */
const LOADING = 'Loading';

function shortCalcLabel(title: string): string {
  const head = title.split(' - ')[0].trim();
  return head.length > 26 ? `${head.slice(0, 25)}…` : head;
}

/**
 * The calc document a calc ref names ("d2#beam-design" -> "d2"); null for a bare key (an export of one package).
 * Every page number in the view belongs to a calc, so its document comes from that calc's ref.
 */
export const docIdOfCalc = (calcKey: string | null | undefined): string | null => {
  const i = calcKey ? calcKey.indexOf('#') : -1;
  return i > 0 ? calcKey!.slice(0, i) : null;
};

/** Calc engine output -> CalcData: calcs, the calc graph, and every element's links by GlobalId. */
export function toCalcData(exp: Export, info: { projectName?: string | null; modelRevisionId?: number | null; calcRevisionId?: number | null } = {}): CalcData {
  // A calc-set export numbers pages across its PDFs (set page = PDF page + the document's offset). The
  // view shows each PDF's OWN page numbers: every page below is converted here, by the document of the
  // calc it belongs to, so no component ever sees a set page.
  const docs = new Map((exp.documents ?? []).map((d) => [d.doc_id, d]));
  const own = (calcKey: string | null | undefined, page: number): number => page - (docs.get(docIdOfCalc(calcKey) ?? '')?.page_offset ?? 0);
  const ownOrNull = (calcKey: string | null | undefined, page: number | null | undefined): number | null => (page == null ? null : own(calcKey, page));

  const calcs: CalcPackage[] = exp.calcs.map((c, i) => {
    const doc = docs.get(docIdOfCalc(c.key) ?? '');
    return {
      key: c.key,
      title: c.title || c.key,
      software: c.software || '',
      elementType: c.element_type || '',
      pages: Array.isArray(c.pages) ? c.pages.map((p) => own(c.key, p)) : [],
      scanned: Boolean(c.scanned),
      frontMatter: Boolean(c.front_matter),
      titleBox: c.title_box ? { page: own(c.key, c.title_box.page), rects: c.title_box.rects ?? [] } : null,
      color: CALC_PALETTE[i % CALC_PALETTE.length],
      regions: (c.spans ?? []).flatMap((sp) => sp.regions.map((r) => ({ page: own(c.key, r.page), rect: [...r.rect] }))),
      docId: doc?.doc_id ?? null,
      docName: doc?.name ?? null,
      ...(c.meta ? { meta: c.meta } : {}),
    };
  });
  const calcOrigin: CalcOrigin = exp.calc_source ? (exp.calc_source.kind === 'demo' ? 'bundle-demo' : 'bundle-pdf') : 'pdf';
  const calcByKey = new Map(calcs.map((c) => [c.key, c]));

  const calcDependencies: CalcDependency[] = exp.calc_edges.map((e) => ({
    source: e.src,
    target: e.dst,
    rules: e.rules ?? [],
    evidence: (e.evidence ?? []).map((ev) => ({ calcKey: ev.calc, page: own(ev.calc, ev.page), text: ev.text, line: ev.line ?? null, rects: ev.rects ?? [] })),
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
        evidence: { page: ownOrNull(l.calc, l.evidence?.page ?? l.page), rects: l.evidence?.rects ?? [], snippet: l.evidence?.snippet ?? null },
        // exports written before roles existed: treat as design links, banded by confidence
        role: l.role ?? 'design',
        band: l.band ?? (l.confidence >= 0.8 ? 'high' : l.confidence >= 0.5 ? 'medium' : 'low'),
        reasons: (l.reasons ?? []).map((r) => ({ kind: r.kind, weight: r.weight, note: r.note, page: ownOrNull(l.calc, r.page), rects: r.rects ?? [] })),
        caveats: l.caveats ?? [],
        viaGroup: l.via_group,
        provenance: toProvenance(l.provenance),
        reviewProvenance: toProvenance(l.review_provenance),
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
      label: calcOrigin === 'bundle-demo' ? 'Demo calcs' : docs.size > 1 ? 'Calc set' : 'Calc package',
      kind: 'calc-root',
      level: 0,
      r: Math.max(36, getCalcBubbleLayout(calcOrigin === 'bundle-demo' ? 'Demo calcs' : docs.size > 1 ? 'Calc set' : 'Calc package').radius),
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
      // Front matter and Loading name themselves: a Loading calc designs no element, it feeds other calcs
      const label = type ? (type === 'Front matter' || type === LOADING ? type : `${type} calcs`) : 'General';
      calcNodes.push({
        id: cid,
        label,
        kind: 'calc-category',
        level: 1,
        parent: CALC_ROOT_ID,
        r: Math.max(26, getCalcBubbleLayout(label).radius),
        x: 0,
        y: 0,
        desc:
          type === LOADING
            ? 'Gravity, wind and seismic load calculations: they design no element and feed the calculations that cite them'
            : type
              ? `Calculations that design ${type.toLowerCase()} elements`
              : 'Calculations not tied to one element type',
      });
      calcLinks.push({ source: CALC_ROOT_ID, target: cid, relation: 'hierarchy' });
    }
    const linked = calcToElementIds.get(c.key)?.length ?? 0;
    const label = shortCalcLabel(c.title);
    calcNodes.push({
      id: calcNodeId(c.key),
      label,
      kind: 'calc',
      level: 2,
      parent: cid,
      categoryParent: cid,
      calcKey: c.key,
      color: c.color,
      r: getCalcBubbleLayout(label).radius,
      x: 0,
      y: 0,
      desc: `${c.title}${c.software ? ` · ${c.software}` : ''}${docs.size > 1 && c.docName ? ` · ${c.docName}` : ''} · ${linked} linked element${linked === 1 ? '' : 's'}`,
    });
    calcLinks.push({ source: cid, target: calcNodeId(c.key), relation: 'hierarchy' });
  }
  for (const d of calcDependencies) {
    if (!calcByKey.has(d.source) || !calcByKey.has(d.target)) continue;
    calcLinks.push({ source: calcNodeId(d.source), target: calcNodeId(d.target), relation: 'calc-dependency' });
  }

  const groupLinks = exp.group_links ?? [];
  const groups: TypicalGroupView[] = (exp.groups ?? []).map((g) => ({
    id: g.id,
    category: g.cat,
    storey: g.storey,
    profile: g.profile,
    title: g.title,
    members: g.members,
    links: groupLinks
      .filter((gl) => gl.group === g.id && calcByKey.has(gl.calc_key))
      .map((gl) => ({ calcKey: gl.calc_key, confidence: gl.conf, band: gl.band, role: gl.role, rule: gl.rule, page: ownOrNull(gl.calc_key, gl.page), rects: gl.rects ?? [], caveats: gl.caveats ?? [] }))
      .sort((a, b) => b.confidence - a.confidence),
  }));
  const findings: FindingView[] = (exp.findings ?? []).map((f) => ({
    kind: f.kind,
    elementId: f.global_id,
    calcKey: f.calc_key,
    modelSize: f.model_size,
    calcSize: f.calc_size,
    page: own(f.calc_key, f.page),
    rects: f.rects ?? [],
    snippet: f.snippet ?? null,
    note: f.note,
  }));

  const pr: ExportProducers = exp.producers ?? {};
  const producers: ProducerRecords | null =
    pr.calc_mapper || pr.element_graph || pr.calc_package
      ? {
          engine: exp.engine,
          engineProducer: pr.calc_mapper?.producer ?? null,
          graph: pr.element_graph
            ? { producer: pr.element_graph.producer, source: describeSource(pr.element_graph.source), sha256: pr.element_graph.sha256 }
            : null,
          calcPackage: pr.calc_package ? { name: pr.calc_package.name, sha256: pr.calc_package.sha256, pages: pr.calc_package.pages } : null,
        }
      : null;

  return {
    groups,
    findings,
    producers,
    projectName: info.projectName ?? null,
    modelName: exp.model,
    modelRevisionId: info.modelRevisionId ?? (typeof exp.model_revision === 'number' ? exp.model_revision : null),
    calcPackageName: exp.calc_package,
    calcRevisionId: info.calcRevisionId ?? (typeof exp.calc_revision === 'number' ? exp.calc_revision : null),
    engine: exp.engine || '',
    calcs,
    calcDependencies,
    calcNodes: computeRadialLayout(calcNodes),
    calcLinks,
    calcToElementIds,
    linksByElement,
    statusByElement,
    calcOrigin,
  };
}

function toProvenance(p: Provenance | undefined): ProvenanceView | null {
  if (!p) return null; // exports written before the provenance contract
  return { producer: p.producer, rule: p.rule, method: p.method, inputs: p.inputs ?? [], actor: p.actor ?? null, at: p.at ?? null };
}

/** An element graph's meta.source ({ format, file }) in words. */
function describeSource(src: unknown): string {
  if (!src || typeof src !== 'object') return '';
  const o = src as { format?: unknown; file?: unknown };
  return [typeof o.file === 'string' ? o.file : null, typeof o.format === 'string' ? `(${o.format})` : null].filter(Boolean).join(' ');
}

/** Element-graph kind of an exported element, from its IFC type. */
function kindOf(ifcType: string): ElementKind {
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
 * An export without its element graph -> ModelInput (elements, storeys, the engine's load path as
 * `supports` relations), for the shared buildGraph -> elementGraphToBim path. No geometry, so no
 * inference: the topology is exactly what the export recorded.
 */
export function exportToElementGraph(exp: Export): ElementGraph {
  const storeyNames = [...new Set(exp.elements.map((e) => e.storey).filter(Boolean))].sort((a, b) => a.localeCompare(b, undefined, { numeric: true }));
  const ids = new Set(exp.elements.map((e) => e.global_id));
  const input: ModelInput = {
    meta: {
      version: 1,
      project: exp.model ? exp.model.replace(/\.ifc$/i, '') : undefined,
      units: 'm',
      source: { format: 'calc-graph-export', file: exp.model ?? undefined },
    },
    levels: storeyNames.map((name, i) => ({ id: `storey:${name}`, name, elevation: storeyRank(name, i) })),
    elements: exp.elements.map((e) => ({
      id: e.global_id,
      kind: kindOf(e.ifc_type),
      mark: e.mark || undefined,
      profile: e.size || undefined,
      levelId: e.storey ? `storey:${e.storey}` : undefined,
      params: {},
      source: { format: 'ifc', file: exp.model ?? undefined, nativeType: e.ifc_type },
    })),
    relations: [
      ...exp.load_path
        .filter((l) => ids.has(l.src) && ids.has(l.dst))
        .map((l) => ({ a: l.src, b: l.dst, kind: 'supports', evidence: { rule: l.rule || 'calc-graph load path', source: 'inferred' as const } })),
      ...(exp.connectivity ?? [])
        .filter((c) => ids.has(c.a) && ids.has(c.b))
        .map((c) => ({ a: c.a, b: c.b, kind: 'connects', evidence: { rule: c.rule, source: c.explicit ? ('explicit' as const) : ('inferred' as const) } })),
    ],
    warnings: [],
  };
  return buildGraph(input, { infer: false }).graph;
}

/** A calc-graph export JSON ("Download export JSON") - told apart from a ModelInput by `calcs` and no `meta`. */
export function isCalcGraphExport(d: unknown): d is Export {
  if (!d || typeof d !== 'object') return false;
  const o = d as Partial<Export> & { meta?: unknown };
  return Array.isArray(o.elements) && Array.isArray(o.calcs) && o.meta === undefined;
}

/** Normalise an export read from disk (older files may miss the optional arrays). */
export function normaliseExport(o: Export): Export {
  return {
    model: o.model ?? null,
    model_revision: o.model_revision ?? null,
    calc_package: o.calc_package ?? null,
    calc_revision: o.calc_revision ?? null,
    engine: o.engine,
    producers: o.producers ?? {},
    calcs: o.calcs,
    calc_edges: Array.isArray(o.calc_edges) ? o.calc_edges : [],
    load_path: Array.isArray(o.load_path) ? o.load_path : [],
    connectivity: Array.isArray(o.connectivity) ? o.connectivity : [],
    elements: o.elements,
    groups: Array.isArray(o.groups) ? o.groups : [],
    group_links: Array.isArray(o.group_links) ? o.group_links : [],
    findings: Array.isArray(o.findings) ? o.findings : [],
  };
}

export function toImpactView(i: Impact): ImpactView {
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

/**
 * The engine's revision diff -> the diff view model (per element status + before/after field changes).
 * `kinds`: the element-graph kind of each element only one side has (compareRevisions); the
 * onlyInA / onlyInB `category` is that kind, so a ghost lands in its own kind's family and category
 * (the engine's `cat` folds kinds together, e.g. fastener into Connection, so it is only the fallback).
 */
export function toModelDiff(c: Compare, kinds: ReadonlyMap<string, string> = new Map()): ModelDiff {
  const kindOf = (x: Compare['removed'][number]) => kinds.get(x.global_id) ?? (x.cat || 'other').toLowerCase();
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
    a: Number(c.a),
    b: Number(c.b),
    meta,
    onlyInA: c.removed.map((x) => ({ elementId: x.global_id, mark: x.mark || '', category: kindOf(x) })),
    onlyInB: c.added.map((x) => ({ elementId: x.global_id, mark: x.mark || '', category: kindOf(x) })),
    edgesAdded: c.edges_added.length,
    edgesRemoved: c.edges_removed.length,
  };
}

/** The store's revisions -> the revision panel's list (newest first; heads from the project record). */
export function toRevisionList(revs: RevisionRecord[], heads: { model: number | null; calcs: number | null }, counts: Map<number, number>): RevisionInfo[] {
  return revs
    .map((x) => ({
      id: x.id,
      kind: x.kind,
      seq: x.seq,
      label: x.label || x.sourceName,
      sourceName: x.sourceName,
      createdAt: x.createdAt,
      count: counts.get(x.id) ?? null,
      isHead: (x.kind === 'model' ? heads.model : heads.calcs) === x.id,
      isIfc: x.mediaType === 'application/x-step',
    }))
    .sort((a, b) => b.id - a.id);
}

/** Calc documents with their revisions (newest first; `isHead` = the document's head, the revision the set maps). */
export function toCalcDocuments(documents: ProjectFileDocument[], revs: RevisionRecord[], counts: Map<number, number>): CalcDocumentInfo[] {
  const list = toRevisionList(revs, { model: null, calcs: null }, counts);
  return documents.map((d) => {
    const mine = list.filter((r) => r.kind === 'calcs' && docIdOf(revs.find((x) => x.id === r.id)!) === d.docId);
    return { docId: d.docId, name: d.name, removed: d.removed, revisions: mine.map((r, i) => ({ ...r, isHead: i === 0 })) };
  });
}

/** The engine's calc diff of two revisions of one document, as view data (keys bare: both are the same document). */
export function toCalcRevisionDiff(d: CalcSetDiff, a: number, b: number): CalcRevisionDiffView {
  return {
    a,
    b,
    added: d.added.map((x) => ({ key: x.key, title: x.title })),
    removed: d.removed.map((x) => ({ key: x.key, title: x.title })),
    changed: d.changed.map((x) => ({ key: x.key, title: x.title, beforeTitle: x.before_title })),
    moved: d.moved.map((x) => ({ key: x.key, title: x.title, beforePages: x.before_pages, afterPages: x.after_pages })),
    unchanged: d.unchanged,
  };
}
