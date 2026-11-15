/**
 * Legacy / hand-authored BIM graph JSON ({ projectName, nodes, links }) -> element graph.
 *
 * This is the format of Noah's demo files (data/bim-database.json, data/harborview-*.json). They used to
 * be loaded straight into the old view model; now they go through the same path as every model:
 * legacy JSON -> ModelInput -> buildGraph (connectivity + load path inferred from the boxes) ->
 * ElementGraph -> src/loaders/elementGraphToBim.ts, so two of them can be compared with the one diff
 * (`diffGraphs` in @unloaded/calc-mapper) like two IFC revisions.
 *
 * What carries over: id, kind (from the category), label/mark, section size (profile), the strength
 * label (as material), storey (floor), and the 3D box (pos3d/size3d, feet, Y up -> metres, Z up).
 * Explicit node -> node links become `connects` relations. The invented `documents` are attached as
 * node links of kind DEMO_DOCUMENT_LINK and shown labelled "demo data", never as calc links.
 * Invented engineering numbers (utilization, axial load, rated strength) are dropped.
 */
import { buildGraph, type ElementGraph, type ElementInput, type GeometrySummary, type ModelInput, type RelationInput, type Vec3 } from '@unloaded/element-graph';
import { DEMO_DOCUMENT_LINK } from './elementGraphToBim';

const FT = 0.3048;

interface LegacyNode {
  id?: string;
  label?: string;
  name?: string;
  mark?: string;
  type?: string;
  level?: number;
  parent?: string;
  categoryParent?: string;
  ifcType?: string;
  floor?: string;
  floorNum?: number;
  sectionSize?: string;
  strengthLabel?: string;
  pos3d?: number[];
  size3d?: number[];
  desc?: string;
  colNumber?: string;
  documents?: Record<string, unknown>[];
}

interface LegacyLink {
  source?: string | { id?: string };
  target?: string | { id?: string };
  relation?: string;
  rel?: string;
}

export interface LegacyBimJson {
  projectName?: string;
  project?: string;
  nodes: LegacyNode[];
  links?: LegacyLink[];
}

/** A legacy BIM graph: `{ nodes: [...] }` with typed nodes and no element-graph / ModelInput markers. */
export function isLegacyBimJson(d: unknown): d is LegacyBimJson {
  if (!d || typeof d !== 'object') return false;
  const o = d as { nodes?: unknown; format?: unknown; meta?: unknown; elements?: unknown };
  return Array.isArray(o.nodes) && o.format === undefined && o.meta === undefined && o.elements === undefined;
}

/** Element-graph kind from a legacy category id or IFC label. */
function kindOf(category: LegacyNode | undefined, node: LegacyNode): string {
  const id = (category?.id ?? node.parent ?? '').toLowerCase();
  const ifc = (category?.label ?? category?.ifcType ?? node.ifcType ?? '').toLowerCase().replace(/^ifc/, '');
  const byId: Record<string, string> = {
    'cat-slab': 'slab',
    'cat-roof': 'slab',
    'cat-beam': 'beam',
    'cat-mframe': 'beam',
    'cat-col': 'column',
    'cat-brace': 'brace',
    'cat-wall': 'wall',
    'cat-conn': 'connection',
    'cat-pcap': 'footing',
    'cat-mat': 'footing',
    'cat-footing': 'footing',
    'cat-pile': 'pile',
  };
  if (byId[id]) return byId[id];
  const byIfc: Record<string, string> = {
    slab: 'slab',
    roof: 'slab',
    beam: 'beam',
    column: 'column',
    member: 'brace',
    wall: 'wall',
    wallstandardcase: 'wall',
    plate: 'connection',
    fastener: 'connection',
    mechanicalfastener: 'fastener',
    footing: 'footing',
    pile: 'pile',
  };
  return byIfc[ifc] ?? 'other';
}

/** pos3d/size3d (feet, three.js frame X east, Y up, Z = -north) -> IFC-style bbox (metres, Z up). */
function geometryOf(n: LegacyNode, kind: string): GeometrySummary | undefined {
  const p = n.pos3d;
  const s = n.size3d;
  if (!Array.isArray(p) || !Array.isArray(s) || p.length < 3 || s.length < 3) return undefined;
  const [px, py, pz] = p.map((v) => Number(v) * FT) as [number, number, number];
  const [sx, sy, sz] = s.map((v) => Math.abs(Number(v)) * FT) as [number, number, number];
  const min: Vec3 = [px - sx / 2, -pz - sz / 2, py - sy / 2];
  const max: Vec3 = [px + sx / 2, -pz + sz / 2, py + sy / 2];
  const geom: GeometrySummary = { bbox: { min, max } };
  const c: Vec3 = [(min[0] + max[0]) / 2, (min[1] + max[1]) / 2, (min[2] + max[2]) / 2];
  if (kind === 'column' || kind === 'pile') {
    geom.axis = { start: [c[0], c[1], min[2]], end: [c[0], c[1], max[2]] };
  } else if (kind === 'beam' || kind === 'brace') {
    geom.axis = sx >= sz ? { start: [min[0], c[1], c[2]], end: [max[0], c[1], c[2]] } : { start: [c[0], min[1], c[2]], end: [c[0], max[1], c[2]] };
  }
  return geom;
}

const linkId = (v: LegacyLink['source']) => (typeof v === 'object' && v !== null ? v.id : v) ?? '';

function legacyToModelInput(d: LegacyBimJson, fileName: string): { input: ModelInput; documents: Map<string, Record<string, unknown>[]> } {
  const byId = new Map<string, LegacyNode>();
  d.nodes.forEach((n, i) => byId.set(n.id ?? `el-${i}`, n));
  const isGroup = (n: LegacyNode) => n.type === 'Project' || n.type === 'Category' || n.type === 'ColumnStack' || n.level === 0 || n.level === 1 || n.level === 1.5;
  const categoryOf = (n: LegacyNode): LegacyNode | undefined => {
    let p = n.categoryParent ? byId.get(n.categoryParent) : n.parent ? byId.get(n.parent) : undefined;
    while (p && p.type === 'ColumnStack' && p.parent) p = byId.get(p.parent);
    return p;
  };

  const elements: ElementInput[] = [];
  const documents = new Map<string, Record<string, unknown>[]>();
  const floors = new Map<string, { num: number; zs: number[] }>();
  d.nodes.forEach((n, i) => {
    if (isGroup(n)) return;
    const id = n.id ?? `el-${i}`;
    const kind = kindOf(categoryOf(n), n);
    const geometry = geometryOf(n, kind);
    if (n.floor && n.floor !== 'ALL') {
      const f = floors.get(n.floor) ?? { num: typeof n.floorNum === 'number' ? n.floorNum : 0, zs: [] };
      if (geometry) f.zs.push(geometry.bbox.min[2]);
      floors.set(n.floor, f);
    }
    elements.push({
      id,
      kind,
      mark: n.mark ?? n.label ?? n.name,
      name: n.desc,
      profile: n.sectionSize,
      material: n.strengthLabel,
      levelId: n.floor && n.floor !== 'ALL' ? `floor:${n.floor}` : undefined,
      params: { 'Legacy.Category': categoryOf(n)?.label ?? null },
      geometry,
      source: { format: 'legacy-bim-json', file: fileName, nativeId: id, nativeType: categoryOf(n)?.label ?? n.ifcType },
    });
    if (Array.isArray(n.documents) && n.documents.length) documents.set(id, n.documents);
  });

  const ids = new Set(elements.map((e) => e.id));
  const relations: RelationInput[] = [];
  const seen = new Set<string>();
  for (const l of d.links ?? []) {
    const a = linkId(l.source);
    const b = linkId(l.target);
    if (!ids.has(a) || !ids.has(b) || a === b) continue;
    const [x, y] = a < b ? [a, b] : [b, a];
    if (seen.has(`${x}|${y}`)) continue;
    seen.add(`${x}|${y}`);
    relations.push({ a: x, b: y, kind: 'connects', evidence: { rule: `legacy demo link${l.relation || l.rel ? ` (${l.relation ?? l.rel})` : ''}`, source: 'explicit' } });
  }

  const input: ModelInput = {
    meta: {
      version: 1,
      project: d.projectName || d.project || fileName.replace(/\.json$/i, ''),
      units: 'm',
      source: { format: 'legacy-bim-json', file: fileName },
    },
    levels: [...floors.entries()].map(([name, f]) => ({
      id: `floor:${name}`,
      name,
      // the floor's lowest element base when boxes exist, else ~12 ft per floor number
      elevation: f.zs.length ? Math.min(...f.zs) : f.num * 3.66,
    })),
    elements,
    relations,
    warnings: [],
  };
  return { input, documents };
}

/** Legacy JSON -> ElementGraph (topology inferred from the boxes), with demo documents as node links. */
export function legacyToElementGraph(d: LegacyBimJson, fileName: string): { graph: ElementGraph; projectName: string; warnings: string[] } {
  const { input, documents } = legacyToModelInput(d, fileName);
  const { graph, warnings } = buildGraph(input);
  graph.batch(() => {
    for (const [id, docs] of documents) {
      const node = graph.getNode(id);
      if (!node) continue;
      graph.updateNode(id, {
        links: [
          ...node.links,
          ...docs.map((doc, i) => ({
            target: String(doc.id ?? `${id}-doc-${i + 1}`),
            kind: DEMO_DOCUMENT_LINK,
            data: Object.fromEntries(
              Object.entries(doc)
                .filter(([, v]) => v === null || ['string', 'number', 'boolean'].includes(typeof v))
                .map(([k, v]) => [k, v as string | number | boolean | null]),
            ),
          })),
        ],
      });
    }
  });
  return {
    graph,
    projectName: input.meta.project ?? fileName,
    warnings: ['legacy demo JSON: invented documents are shown as demo data; utilization / loads are not imported', ...warnings.map((w) => `graph: ${w}`)],
  };
}
