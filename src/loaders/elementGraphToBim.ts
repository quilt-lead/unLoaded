/**
 * ElementGraph (domain model) -> ElementTopology (view data).
 *
 * The element graph from @unloaded/element-graph is the ONE source of truth for elements and
 * structural topology: elements and connections are nodes, edges are physical connectivity
 * (`connects`), load path (`supports`: a is supported by b) and assembly (`part_of`). This adapter
 * is the only place an ElementGraph becomes view data. Calc data (links, evidence, review status)
 * comes from the backend through src/data/loadProject.ts; src/data/mergeProject.ts joins the two
 * by GlobalId (= graph node id).
 *
 * Mapping
 * - kind              -> category node (`cat-beam`, `cat-col`, ...)
 * - column chains     -> column-stack family nodes (columns linked by column -> column `supports`)
 * - other marks       -> mark-family nodes (2B13 -> B, ST-1 -> ST; unmarked elements share one)
 * - element           -> element node (label = mark ?? name, storey from levelId or elevation)
 * - supports          -> LoadPathEdge, source = supported, target = support (load flows source -> target)
 * - connects/part_of  -> ConnectivityEdge
 * Geometry is not mapped: the 3D view draws the real IFC meshes by GlobalId.
 */
import type { ElementGraph, LevelInput, ParamValue } from '@unloaded/element-graph';
import type { BimLink, BimNode, ConnectivityEdge, ElementTopology, LoadPathEdge } from '../types/bim';
import { computeRadialLayout } from '../utils/graphEngine';

export const PROJECT_NODE_ID = 'project';

interface KindCategory {
  id: string;
  label: string;
  /** Singular display name. */
  singular: string;
}

const KIND_CATEGORIES: Record<string, KindCategory> = {
  slab: { id: 'cat-slab', label: 'Slabs', singular: 'Slab' },
  beam: { id: 'cat-beam', label: 'Beams', singular: 'Beam' },
  brace: { id: 'cat-brace', label: 'Braces', singular: 'Brace' },
  connection: { id: 'cat-conn', label: 'Connections', singular: 'Connection' },
  fastener: { id: 'cat-fastener', label: 'Fasteners', singular: 'Fastener' },
  column: { id: 'cat-col', label: 'Columns', singular: 'Column' },
  wall: { id: 'cat-wall', label: 'Walls', singular: 'Wall' },
  footing: { id: 'cat-footing', label: 'Footings', singular: 'Footing' },
  pile: { id: 'cat-pile', label: 'Piles', singular: 'Pile' },
  other: { id: 'cat-other', label: 'Other', singular: 'Element' },
};

/** Category order around the radial layout (gravity order, top to bottom). */
const KIND_ORDER = Object.keys(KIND_CATEGORIES);

export function categoryFor(kind: string): KindCategory {
  const known = KIND_CATEGORIES[kind];
  if (known) return known;
  const pretty = kind.charAt(0).toUpperCase() + kind.slice(1);
  return { id: `cat-${kind.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`, label: `${pretty}s`, singular: pretty };
}

/** Mark family: the letters of a mark without the level prefix or the running number (2B13 -> B, ST-1 -> ST). */
export function markFamily(mark: string | undefined): string | null {
  const m = /^\d*([A-Za-z]+(?:-?[A-Za-z]+)*)/.exec((mark ?? '').trim());
  return m ? m[1]!.toUpperCase() : null;
}

function shortId(id: string): string {
  return id.length > 10 ? id.slice(0, 8) : id;
}

function str(v: ParamValue | undefined): string | undefined {
  return v === null || v === undefined || v === '' ? undefined : String(v);
}

/** Union-find over columns joined by column -> column `supports` edges (vertical stacks). */
function columnStacks(graph: ElementGraph): Map<string, string[]> {
  const parent = new Map<string, string>();
  const find = (x: string): string => {
    let r = x;
    while (parent.get(r) !== r) r = parent.get(r)!;
    let c = x;
    while (parent.get(c) !== r) {
      const next = parent.get(c)!;
      parent.set(c, r);
      c = next;
    }
    return r;
  };
  const columns = graph.nodesByKind('column');
  columns.forEach((c) => parent.set(c.id, c.id));
  for (const c of columns) {
    // Directly on a column, or through a splice / connection node that sits on one.
    const below = graph.supportsOf(c.id).flatMap((id) => (graph.getNode(id)?.kind === 'connection' ? graph.supportsOf(id) : [id]));
    for (const b of below) {
      if (parent.has(b) && b !== c.id) parent.set(find(c.id), find(b));
    }
  }
  const groups = new Map<string, string[]>();
  for (const c of columns) {
    const root = find(c.id);
    const list = groups.get(root);
    if (list) list.push(c.id);
    else groups.set(root, [c.id]);
  }
  return groups;
}

export interface ElementGraphToBimOptions {
  /** Project label; defaults to graph.meta.project. */
  projectName?: string;
}

export function elementGraphToBim(graph: ElementGraph, opts: ElementGraphToBimOptions = {}): ElementTopology {
  const projectName = opts.projectName || graph.meta?.project || graph.meta?.source.file || 'Imported model';
  const elements = graph.nodes();

  // Levels -> storey names and order (sorted by elevation, 1-based).
  const levels = [...graph.levels()].sort((a, b) => a.elevation - b.elevation);
  const storeyOf = new Map(levels.map((l, i) => [l.id, { name: l.name || `Level ${i + 1}`, order: i + 1 }]));
  // Elements without a storey: the highest level at or below their base (5 cm slack).
  const storeyByElevation = (z: number | undefined) => {
    if (z === undefined || levels.length === 0) return undefined;
    let best: LevelInput | undefined;
    for (const l of levels) if (l.elevation <= z + 0.05) best = l;
    return storeyOf.get((best ?? levels[0]!).id);
  };

  const nodes: BimNode[] = [
    {
      id: PROJECT_NODE_ID,
      label: projectName,
      kind: 'project',
      level: 0,
      r: 36,
      x: 0,
      y: 0,
      desc: `${elements.length} element${elements.length === 1 ? '' : 's'} · ${graph.edges().length} graph edges`,
    },
  ];
  const links: BimLink[] = [];

  // Categories, in gravity order then alphabetical for unknown kinds.
  const kinds = graph
    .kinds()
    .slice()
    .sort((a, b) => {
      const ia = KIND_ORDER.indexOf(a);
      const ib = KIND_ORDER.indexOf(b);
      return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib) || a.localeCompare(b);
    });
  for (const kind of kinds) {
    const cat = categoryFor(kind);
    const count = graph.nodesByKind(kind).length;
    nodes.push({
      id: cat.id,
      label: cat.label,
      kind: 'category',
      elementKind: kind,
      level: 1,
      parent: PROJECT_NODE_ID,
      r: 26,
      x: 0,
      y: 0,
      desc: `${cat.label} — ${count} element${count === 1 ? '' : 's'}`,
    });
    links.push({ source: PROJECT_NODE_ID, target: cat.id, relation: 'hierarchy' });
  }

  // Column stacks, when at least one multi-segment stack exists (then every column sits in one).
  const familyOf = new Map<string, string>();
  const stacks = columnStacks(graph);
  if ([...stacks.values()].some((s) => s.length > 1)) {
    const colCat = categoryFor('column');
    const elevation = (id: string) => graph.getNode(id)?.geometry?.bbox.min[2] ?? 0;
    const ordered = [...stacks.values()]
      .map((ids) => ids.sort((a, b) => elevation(a) - elevation(b)))
      .sort((a, b) => {
        const pa = graph.getNode(a[0]!)?.geometry?.bbox.min ?? [0, 0, 0];
        const pb = graph.getNode(b[0]!)?.geometry?.bbox.min ?? [0, 0, 0];
        return pa[1] - pb[1] || pa[0] - pb[0];
      });
    ordered.forEach((ids, i) => {
      const stackId = `stack-${String(i + 1).padStart(2, '0')}`;
      const base = graph.getNode(ids[0]!)!;
      ids.forEach((id) => familyOf.set(id, stackId));
      nodes.push({
        id: stackId,
        label: base.mark ? `${base.mark}` : `S${String(i + 1).padStart(2, '0')}`,
        kind: 'family',
        elementKind: 'column',
        level: 1.5,
        parent: colCat.id,
        categoryParent: colCat.id,
        r: 15,
        x: 0,
        y: 0,
        desc: `Column stack of ${ids.length} segment${ids.length === 1 ? '' : 's'} (column-on-column load path)`,
      });
      links.push({ source: colCat.id, target: stackId, relation: 'hierarchy' });
    });
  }

  // Mark families for everything not in a stack.
  const families = new Set<string>();
  const sorted = [...elements].sort(
    (a, b) => a.kind.localeCompare(b.kind) || (a.mark ?? '').localeCompare(b.mark ?? '', undefined, { numeric: true }) || a.id.localeCompare(b.id),
  );
  for (const el of sorted) {
    if (familyOf.has(el.id)) continue;
    const cat = categoryFor(el.kind);
    const fam = markFamily(el.mark) ?? 'Unmarked';
    const famId = `fam:${el.kind}:${fam}`;
    familyOf.set(el.id, famId);
    if (!families.has(famId)) {
      families.add(famId);
      nodes.push({
        id: famId,
        label: fam,
        kind: 'family',
        elementKind: el.kind,
        level: 1.5,
        parent: cat.id,
        categoryParent: cat.id,
        r: 15,
        x: 0,
        y: 0,
        desc: fam === 'Unmarked' ? `${cat.label} without a mark` : `Mark family ${fam}`,
      });
      links.push({ source: cat.id, target: famId, relation: 'hierarchy' });
    }
  }

  // Unmarked elements fall back to their name; number repeated names ("girder 1", "girder 2").
  const nameCount = new Map<string, number>();
  for (const el of elements) if (!el.mark && el.name) nameCount.set(el.name, (nameCount.get(el.name) ?? 0) + 1);
  const nameSeen = new Map<string, number>();

  for (const el of sorted) {
    const cat = categoryFor(el.kind);
    const storey = (el.levelId ? storeyOf.get(el.levelId) : undefined) ?? storeyByElevation(el.geometry?.bbox.min[2]);
    let label = el.mark || el.name || `${cat.singular} ${shortId(el.id)}`;
    if (!el.mark && el.name && (nameCount.get(el.name) ?? 0) > 1) {
      const k = (nameSeen.get(el.name) ?? 0) + 1;
      nameSeen.set(el.name, k);
      label = `${el.name} ${k}`;
    }
    const famId = familyOf.get(el.id)!;
    const params: Record<string, string> = {};
    for (const [k, v] of Object.entries(el.params)) {
      const s = str(v);
      if (s !== undefined) params[k] = s;
    }
    nodes.push({
      id: el.id,
      label,
      kind: 'element',
      elementKind: el.kind,
      level: 2,
      parent: famId,
      categoryParent: cat.id,
      ifcType: el.source.nativeType,
      storey: storey?.name,
      storeyOrder: storey?.order,
      mark: el.mark,
      size: el.profile,
      name: el.name,
      typeName: str(el.params['Attr.TypeName']),
      material: el.material,
      params,
      r: 8,
      x: 0,
      y: 0,
      desc: [el.name && el.name !== el.mark ? el.name : el.source.nativeType ?? cat.singular, storey?.name].filter(Boolean).join(' · '),
    });
    links.push({ source: famId, target: el.id, relation: 'hierarchy' });
  }

  // Topology. `supports` keeps its direction (a supported by b == load flows source -> target).
  const loadPath: LoadPathEdge[] = [];
  const connectivity: ConnectivityEdge[] = [];
  const rules = (e: { evidence: { rule: string }[] }) => [...new Set(e.evidence.map((v) => v.rule))].join('; ');
  for (const e of graph.edges()) {
    if (e.kind === 'supports') loadPath.push({ source: e.a, target: e.b, rule: rules(e) });
    else if (e.kind === 'connects' || e.kind === 'part_of') connectivity.push({ source: e.a, target: e.b, kind: e.kind, rule: rules(e) });
  }

  return { projectName, elementNodes: computeRadialLayout(nodes), hierarchyLinks: links, loadPath, connectivity };
}
