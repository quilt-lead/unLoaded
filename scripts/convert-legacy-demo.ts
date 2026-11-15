// One-off converter: a legacy hand-authored BIM graph JSON ({ projectName, nodes, links }, the format of
// Noah's Harborview demo) -> a model bundle (packages/calc-mapper/src/bundle.ts): the element graph and
// a DEMO calc graph built from the nodes' invented `documents`, side by side in one file.
//
// Usage: node scripts/convert-legacy-demo.ts <legacy.json> <out.bundle.json> [revision label]
//
// The app no longer reads the legacy format; the Harborview files in data/ were made with this script.
// To run it again, take the legacy files from git history (`git log --all -- data/harborview-tower-rev1-base.json`).
// The output is deterministic: the same input gives the same bytes.
//
// What carries over (unchanged from the old in-app loader, src/loaders/legacyBimJson.ts):
//   element: id, kind (from the category), mark, section size (profile), strength label (material),
//            storey (floor), the 3D box (pos3d/size3d, feet, Y up -> metres, Z up)
//   topology: explicit node -> node links become `connects` relations; buildGraph infers the rest
//   calcs:   each distinct document id is one demo calc (title, code, rev, date, summary of its first use);
//            its category is the kind most of its elements have; each (element, document) is one design link
// Invented engineering numbers (utilization, axial load, rated strength) are dropped.
import { readFileSync, writeFileSync } from 'node:fs';
import { basename } from 'node:path';
import { buildGraph, type ElementInput, type GeometrySummary, type ModelInput, type RelationInput, type Vec3 } from '@unloaded/element-graph';
import { makeBundle, parseBundle, type BundleCalc, type BundleCalcGraph, type BundleLink, type ElementCategory } from '@unloaded/calc-mapper';

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
  documents?: Record<string, unknown>[];
}

interface LegacyLink {
  source?: string | { id?: string };
  target?: string | { id?: string };
  relation?: string;
  rel?: string;
}

interface LegacyBimJson {
  projectName?: string;
  project?: string;
  nodes: LegacyNode[];
  links?: LegacyLink[];
}

/** Element-graph kind from a legacy category id or IFC label. */
function kindOf(category: LegacyNode | undefined, node: LegacyNode): string {
  const id = (category?.id ?? node.parent ?? '').toLowerCase();
  const ifc = (category?.label ?? category?.ifcType ?? node.ifcType ?? '').toLowerCase().replace(/^ifc/, '');
  const byId: Record<string, string> = {
    'cat-slab': 'slab', 'cat-roof': 'slab', 'cat-beam': 'beam', 'cat-mframe': 'beam', 'cat-col': 'column', 'cat-brace': 'brace',
    'cat-wall': 'wall', 'cat-conn': 'connection', 'cat-pcap': 'footing', 'cat-mat': 'footing', 'cat-footing': 'footing', 'cat-pile': 'pile',
  };
  if (byId[id]) return byId[id];
  const byIfc: Record<string, string> = {
    slab: 'slab', roof: 'slab', beam: 'beam', column: 'column', member: 'brace', wall: 'wall', wallstandardcase: 'wall',
    plate: 'connection', fastener: 'connection', mechanicalfastener: 'fastener', footing: 'footing', pile: 'pile',
  };
  return byIfc[ifc] ?? 'other';
}

/** Element-graph kind -> the calc category of the engine (elements.ts CAT). */
const CAT: Record<string, ElementCategory> = {
  beam: 'Beam', column: 'Column', slab: 'Slab', wall: 'Wall', footing: 'Footing', pile: 'Pile', brace: 'Brace', connection: 'Connection', fastener: 'Connection',
};

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
const str = (v: unknown): string | undefined => (typeof v === 'string' && v ? v : typeof v === 'number' ? String(v) : undefined);

function convert(d: LegacyBimJson, fileName: string, label: string | undefined) {
  const byId = new Map<string, LegacyNode>();
  d.nodes.forEach((n, i) => byId.set(n.id ?? `el-${i}`, n));
  const isGroup = (n: LegacyNode) => n.type === 'Project' || n.type === 'Category' || n.type === 'ColumnStack' || n.level === 0 || n.level === 1 || n.level === 1.5;
  const categoryOf = (n: LegacyNode): LegacyNode | undefined => {
    let p = n.categoryParent ? byId.get(n.categoryParent) : n.parent ? byId.get(n.parent) : undefined;
    while (p && p.type === 'ColumnStack' && p.parent) p = byId.get(p.parent);
    return p;
  };

  const elements: ElementInput[] = [];
  const floors = new Map<string, { num: number; zs: number[] }>();
  // the demo calc graph: documents in first-seen order, and every (element, document) pair
  const docs = new Map<string, { doc: Record<string, unknown>; kinds: string[] }>();
  const links: BundleLink[] = [];
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
    for (const [j, doc] of (n.documents ?? []).entries()) {
      const key = str(doc.id) ?? `${id}-doc-${j + 1}`;
      const seen = docs.get(key) ?? docs.set(key, { doc, kinds: [] }).get(key)!;
      seen.kinds.push(kind);
      const note = str(doc.summary);
      links.push({ element: id, calc: key, role: 'design', review: 'auto', conf: 1, ...(note ? { note } : {}) });
    }
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

  const project = d.projectName || d.project || fileName.replace(/\.json$/i, '');
  const input: ModelInput = {
    meta: { version: 1, project, units: 'm', source: { format: 'legacy-bim-json', file: fileName } },
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
  const { graph, warnings } = buildGraph(input);

  /** The kind most of a document's elements have (first seen wins a tie). */
  const commonest = (kinds: string[]): string => {
    const count = new Map<string, number>();
    for (const k of kinds) count.set(k, (count.get(k) ?? 0) + 1);
    return [...count.entries()].reduce((a, b) => (b[1] > a[1] ? b : a))[0];
  };
  const calcs: BundleCalc[] = [...docs.entries()].map(([key, { doc, kinds }]) => {
    const extra = Object.fromEntries((['code', 'rev', 'date', 'summary'] as const).map((f) => [f, str(doc[f])]).filter(([, v]) => v !== undefined));
    return { key, title: str(doc.title) ?? key, cat: CAT[commonest(kinds)] ?? 'Other', ...extra };
  });
  const calcGraph: BundleCalcGraph = { source: { kind: 'demo' }, calcs, edges: [], links };

  const bundle = makeBundle(graph.serialize(), calcGraph, {
    project: project.replace(/\s+[—–-]\s+Rev\s*\S+$/i, ''),
    ...(label ? { label } : {}),
    demo: true,
  });
  parseBundle(JSON.parse(JSON.stringify(bundle))); // refuse to write a file the app would refuse to read
  return { bundle, warnings };
}

const [inPath, outPath, label] = process.argv.slice(2);
if (!inPath || !outPath) {
  console.error('Usage: node scripts/convert-legacy-demo.ts <legacy.json> <out.bundle.json> [revision label]');
  process.exit(2);
}
const legacy = JSON.parse(readFileSync(inPath, 'utf8')) as LegacyBimJson;
if (!Array.isArray(legacy.nodes)) throw new Error(`${inPath}: not a legacy BIM graph (no nodes list)`);
const { bundle, warnings } = convert(legacy, basename(inPath), label);
writeFileSync(outPath, `${JSON.stringify(bundle, null, 1)}\n`);
const cg = bundle.calcGraph!;
console.log(`${outPath}: ${bundle.elementGraph.nodes.length} elements, ${bundle.elementGraph.edges.length} edges, ${cg.calcs.length} demo calcs, ${cg.links.length} links`);
if (warnings.length) console.log(`graph warnings (${warnings.length}):`, warnings.slice(0, 5));
