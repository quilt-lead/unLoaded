/**
 * ElementGraph (domain model) -> BimGraphData (UI view model).
 *
 * The element graph from @unloaded/element-graph is the source of truth for
 * structural topology: elements and connections are nodes, edges are physical
 * connectivity (`connects`), load path (`supports`: a is supported by b) and
 * assembly (`part_of`). The UI renders BimNode / BimLink, so this adapter is
 * the single place where the two meet.
 *
 * Mapping
 * - kind            -> Category node (`cat-beam`, `cat-col`, ...; ids match CATEGORY_PALETTE)
 * - element         -> Instance node (label = mark ?? name, floor from levelId)
 * - column chains   -> ColumnStack nodes (columns linked by column -> column `supports`)
 * - geometry.bbox   -> pos3d / size3d (feet, Y-up, recentred in plan, base at y = 0)
 * - connects/part_of-> BimLink relation "connectivity"
 * - supports        -> BimLink relation "load-path", oriented source = supported, target = support
 * - node.links (kind "calc") -> BimNode.documents
 */
import type { ElementGraph, ElementNode, LevelInput, NodeLink, ParamValue, Vec3 } from '@unloaded/element-graph';
import type { BimDocument, BimGraphData, BimLink, BimNode } from '../types/bim';
import { CATEGORY_PALETTE, hashStringToJewelColor } from '../utils/colors';
import { normalizeGraphData } from '../utils/graphEngine';

const M_TO_FT = 3.28084;

interface KindCategory {
  id: string;
  label: string;
  /** Singular display name used as the instance `type`. */
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

function categoryFor(kind: string): KindCategory {
  const known = KIND_CATEGORIES[kind];
  if (known) return known;
  const pretty = kind.charAt(0).toUpperCase() + kind.slice(1);
  return { id: `cat-${kind.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`, label: `${pretty}s`, singular: pretty };
}

function categoryColor(cat: KindCategory): string {
  return CATEGORY_PALETTE[cat.id] || hashStringToJewelColor(cat.id);
}

function shortId(id: string): string {
  return id.length > 10 ? id.slice(0, 8) : id;
}

function elementLabel(n: ElementNode, cat: KindCategory): string {
  return n.mark || n.name || `${cat.singular} ${shortId(n.id)}`;
}

function str(v: ParamValue | undefined): string | undefined {
  return v === null || v === undefined || v === '' ? undefined : String(v);
}

function calcLinkToDocument(link: NodeLink): BimDocument {
  const d = link.data ?? {};
  const num = (v: ParamValue | undefined, fallback: number) => (typeof v === 'number' ? v : fallback);
  return {
    id: link.target,
    title: str(d.title) ?? link.target,
    type: str(d.type) ?? 'Calculation (PDF)',
    code: str(d.code) ?? '',
    rev: str(d.rev) ?? 'Rev A',
    pages: num(d.pages, 1),
    pageRef: str(d.pageRef),
    date: str(d.date) ?? '',
    summary: str(d.summary) ?? '',
    calcCategory: str(d.calcCategory),
  };
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
    const below = graph.supportsOf(c.id).flatMap((id) =>
      graph.getNode(id)?.kind === 'connection' ? graph.supportsOf(id) : [id]
    );
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

export function elementGraphToBim(
  graph: ElementGraph,
  opts: ElementGraphToBimOptions = {}
): { graph: BimGraphData; rawLinks: BimLink[] } {
  const projectName = opts.projectName || graph.meta?.project || graph.meta?.source.file || 'Imported model';
  const elements = graph.nodes();

  // Levels -> floor labels / numbers (sorted by elevation, 1-based).
  const levels = [...graph.levels()].sort((a, b) => a.elevation - b.elevation);
  const floorOf = new Map(levels.map((l, i) => [l.id, { name: l.name || `Level ${i + 1}`, num: i + 1 }]));

  // World frame: recentre in plan, put the lowest point at y = 0, convert to feet, Z-up -> Y-up.
  const boxes = elements.map((e) => e.geometry?.bbox).filter((b): b is { min: Vec3; max: Vec3 } => Boolean(b));
  let cx = 0;
  let cy = 0;
  let zMin = 0;
  if (boxes.length > 0) {
    const min: Vec3 = [Infinity, Infinity, Infinity];
    const max: Vec3 = [-Infinity, -Infinity, -Infinity];
    for (const b of boxes) {
      for (let i = 0; i < 3; i++) {
        min[i] = Math.min(min[i]!, b.min[i]!);
        max[i] = Math.max(max[i]!, b.max[i]!);
      }
    }
    cx = (min[0] + max[0]) / 2;
    cy = (min[1] + max[1]) / 2;
    zMin = min[2];
  }

  const nodes: BimNode[] = [];
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
      type: 'Category',
      level: 1,
      floor: 'ALL',
      floorNum: 0,
      r: 26,
      x: 0,
      y: 0,
      color: categoryColor(cat),
      desc: `${cat.label} — ${count} element${count === 1 ? '' : 's'}.`,
    });
  }

  // Column stacks (only when at least one multi-segment stack exists; the radial
  // layout then expects every column of the category to sit in a stack).
  const stacks = columnStacks(graph);
  const stackOf = new Map<string, string>();
  const useStacks = [...stacks.values()].some((s) => s.length > 1);
  if (useStacks) {
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
      ids.forEach((id) => stackOf.set(id, stackId));
      nodes.push({
        id: stackId,
        label: base.mark ? `${base.mark} stack` : `Stack ${String(i + 1).padStart(2, '0')}`,
        type: 'ColumnStack',
        level: 1.5,
        parent: colCat.id,
        floor: 'ALL',
        floorNum: 0,
        r: 15,
        x: 0,
        y: 0,
        desc: `Vertical column stack of ${ids.length} segment${ids.length === 1 ? '' : 's'} (column-on-column load path).`,
      });
      links.push({ source: colCat.id, target: stackId, relation: 'hierarchy' });
    });
  }

  // Elements without a storey: take the highest level at or below their base (5 cm slack).
  const floorByElevation = (z: number | undefined) => {
    if (z === undefined || levels.length === 0) return undefined;
    let best: LevelInput | undefined;
    for (const l of levels) if (l.elevation <= z + 0.05) best = l;
    return floorOf.get((best ?? levels[0]!).id);
  };

  // Unmarked elements fall back to their name; number repeated names ("girder 1", "girder 2").
  const nameCount = new Map<string, number>();
  for (const el of elements) if (!el.mark && el.name) nameCount.set(el.name, (nameCount.get(el.name) ?? 0) + 1);
  const nameSeen = new Map<string, number>();

  for (const el of elements) {
    const cat = categoryFor(el.kind);
    const floor = (el.levelId ? floorOf.get(el.levelId) : undefined) ?? floorByElevation(el.geometry?.bbox.min[2]);
    let label = elementLabel(el, cat);
    if (!el.mark && el.name && (nameCount.get(el.name) ?? 0) > 1) {
      const k = (nameSeen.get(el.name) ?? 0) + 1;
      nameSeen.set(el.name, k);
      label = `${el.name} ${k}`;
    }
    const stackId = stackOf.get(el.id);
    const bbox = el.geometry?.bbox;

    let pos3d: [number, number, number] | undefined;
    let size3d: [number, number, number] | undefined;
    if (bbox) {
      const [x0, y0, z0] = bbox.min;
      const [x1, y1, z1] = bbox.max;
      // three.js frame: X = east, Y = up, Z = -north.
      pos3d = [((x0 + x1) / 2 - cx) * M_TO_FT, ((z0 + z1) / 2 - zMin) * M_TO_FT, -((y0 + y1) / 2 - cy) * M_TO_FT];
      const MIN_FT = 0.15; // keep zero-thickness elements visible / pickable
      size3d = [
        Math.max((x1 - x0) * M_TO_FT, MIN_FT),
        Math.max((z1 - z0) * M_TO_FT, MIN_FT),
        Math.max((y1 - y0) * M_TO_FT, MIN_FT),
      ];
    }

    const nativeType = el.source.nativeType;
    const details = [
      nativeType,
      el.name && el.name !== el.mark ? el.name : undefined,
      el.material ? `Material: ${el.material}` : undefined,
      `Id: ${el.id}`,
    ].filter(Boolean);
    const docs = el.links.filter((l) => l.kind === 'calc').map(calcLinkToDocument);

    nodes.push({
      id: el.id,
      label,
      type: cat.singular,
      ifcType: nativeType ? nativeType.toUpperCase() : undefined,
      level: 2,
      parent: stackId ?? cat.id,
      categoryParent: stackId ? cat.id : undefined,
      floor: floor?.name,
      floorNum: floor?.num,
      sectionSize: el.profile,
      strengthLabel: [el.profile, el.material].filter(Boolean).join(' • ') || undefined,
      r: 11,
      x: 0,
      y: 0,
      color: categoryColor(cat),
      pos3d,
      size3d,
      shape3d: pos3d ? (el.kind === 'connection' || el.kind === 'fastener' ? 'joint' : 'box') : undefined,
      desc: details.join(' • '),
      documents: docs.length > 0 ? docs : undefined,
    });
    links.push({ source: stackId ?? cat.id, target: el.id, relation: 'hierarchy' });
  }

  // Topology. `supports` keeps its direction (a supported by b == load flows source -> target).
  for (const e of graph.edges()) {
    if (e.kind === 'supports') {
      links.push({ source: e.a, target: e.b, relation: 'load-path' });
    } else if (e.kind === 'connects' || e.kind === 'part_of') {
      links.push({ source: e.a, target: e.b, relation: 'connectivity' });
    }
  }

  return {
    graph: normalizeGraphData({ projectName, nodes, links }, projectName),
    rawLinks: links,
  };
}
