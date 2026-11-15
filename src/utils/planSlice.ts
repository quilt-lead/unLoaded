// The 2D plan: horizontal slices of the model at its floor levels, as a framing plan. Pure data, no
// React: which element is drawn on which level, and as what, from the element graph's plain geometry
// (bbox, centreline axis, section) - never the IFC meshes, so it works for IFC and IFC-less models.
//
// A level is a storey (IfcBuildingStorey) or a slab that no storey sits on. On a level at elevation E:
//   slab        -> its outline, when E lies within its thickness
//   beam        -> its centreline, when its top is at E (floor framing)
//   brace       -> its centreline, dashed, when it sits in the storey below E
//   column/wall -> cut just below E (the supports of this floor); a column that starts at E with
//                  nothing below it (a transfer column, or the ground floor) is drawn as "starts here"
//   footing/pile-> its footprint, when its top is just below E
//   connection  -> a symbol at its centre, when it lies in the floor zone around E
// The IFC convention that a storey's beams and slab are the ceiling of the storey below (a "L03"
// girder at the L04 elevation) is why membership is geometric, not by storey name.
import type { BimNode, ModelLevel } from '../types/bim';

/** Tolerances in metres. One place, so they can be tuned against real models. */
export const PLAN_TOLERANCES = {
  /** a storey within this of a slab's thickness is that slab's level */
  slabMatch: 0.3,
  /** a beam belongs to the floor when its top is within this of the level */
  beamTop: 0.45,
  /** columns and walls are cut this far below the level */
  cutBelow: 0.5,
  /** a column whose base is within this of the level starts on it */
  columnStart: 0.5,
  /** floor zone for connections: from this far below the level ... */
  zoneBelow: 1.2,
  /** ... to this far above it */
  zoneAbove: 0.3,
  /** braces in the storey below, down to this far below the level */
  braceBelow: 1.5,
  /** footings and piles whose top is within this below the level */
  foundationBelow: 1.5,
} as const;

export type Vec2 = [number, number];

export type PlanShape =
  | { type: 'line'; a: Vec2; b: Vec2; width: number }
  | { type: 'rect'; min: Vec2; max: Vec2 }
  | { type: 'point'; at: Vec2; size: number };

export type PlanRole = 'slab' | 'beam' | 'brace' | 'column' | 'column-start' | 'wall' | 'foundation' | 'connection' | 'other';

export interface PlanItem {
  id: string;
  node: BimNode;
  role: PlanRole;
  shape: PlanShape;
}

export interface PlanLevel {
  id: string;
  name: string;
  /** metres */
  elevation: number;
  /** a slab sits on this level */
  hasSlab: boolean;
}

export interface LevelPlan {
  level: PlanLevel;
  /** draw order: slabs, foundations, walls, braces, beams, columns, connections */
  items: PlanItem[];
  extents: { min: Vec2; max: Vec2 } | null;
}

export interface PlanIndex {
  /** levels that have something to draw, lowest first */
  levels: PlanLevel[];
  plans: Map<string, LevelPlan>;
  /** element id -> the levels it is drawn on, lowest first */
  levelsOf: Map<string, string[]>;
  /** model extents over every level, so stepping levels keeps the same frame */
  extents: { min: Vec2; max: Vec2 } | null;
}

const ROLE_ORDER: Record<PlanRole, number> = {
  slab: 0,
  foundation: 1,
  wall: 2,
  other: 3,
  brace: 4,
  beam: 5,
  'column-start': 6,
  column: 7,
  connection: 8,
};

type Box = NonNullable<BimNode['bbox']>;

const placed = (nodes: BimNode[]) => nodes.filter((n): n is BimNode & { bbox: Box } => n.kind === 'element' && Boolean(n.bbox));
const zMin = (n: { bbox: Box }) => n.bbox.min[2];
const zMax = (n: { bbox: Box }) => n.bbox.max[2];
const overlaps = (n: { bbox: Box }, lo: number, hi: number) => zMin(n) <= hi && zMax(n) >= lo;
const footprint = (n: { bbox: Box }): PlanShape => ({ type: 'rect', min: [n.bbox.min[0], n.bbox.min[1]], max: [n.bbox.max[0], n.bbox.max[1]] });

/**
 * Plan levels: every storey, plus each slab no storey sits on (named after the slab), lowest first.
 * Slabs mark the storey they sit on with `hasSlab`.
 */
export function planLevels(nodes: BimNode[], storeys: ModelLevel[] = [], tol = PLAN_TOLERANCES): PlanLevel[] {
  const levels: PlanLevel[] = storeys.map((s) => ({ id: s.id, name: s.name, elevation: s.elevation, hasSlab: false }));
  for (const slab of placed(nodes).filter((n) => n.elementKind === 'slab')) {
    const on = levels.find((l) => l.elevation >= zMin(slab) - tol.slabMatch && l.elevation <= zMax(slab) + tol.slabMatch);
    if (on) on.hasSlab = true;
    else {
      const top = zMax(slab);
      levels.push({ id: `slab:${top.toFixed(3)}`, name: slab.mark || slab.label, elevation: top, hasSlab: true });
    }
  }
  return levels.sort((a, b) => a.elevation - b.elevation);
}

/** A linear member as a centreline with a width; null when it is vertical in plan. */
function memberLine(n: BimNode & { bbox: Box }): PlanShape | null {
  const { min, max } = n.bbox;
  const dx = max[0] - min[0];
  const dy = max[1] - min[1];
  if (n.axis) {
    const a: Vec2 = [n.axis.start[0], n.axis.start[1]];
    const b: Vec2 = [n.axis.end[0], n.axis.end[1]];
    const len = Math.hypot(b[0] - a[0], b[1] - a[1]);
    if (len > 1e-3) {
      const ux = Math.abs(b[0] - a[0]) / len;
      const uy = Math.abs(b[1] - a[1]) / len;
      // an axis-aligned member's bbox width across the axis is its section width
      const across = uy < 1e-3 ? dy : ux < 1e-3 ? dx : undefined;
      return { type: 'line', a, b, width: Math.max(0.05, n.section?.width ?? across ?? 0.2) };
    }
  }
  if (Math.max(dx, dy) < 1e-3) return null;
  const cx = (min[0] + max[0]) / 2;
  const cy = (min[1] + max[1]) / 2;
  return dx >= dy
    ? { type: 'line', a: [min[0], cy], b: [max[0], cy], width: Math.max(0.05, n.section?.width ?? dy) }
    : { type: 'line', a: [cx, min[1]], b: [cx, max[1]], width: Math.max(0.05, n.section?.width ?? dx) };
}

const rectsTouch = (a: PlanShape, b: PlanShape) =>
  a.type === 'rect' && b.type === 'rect' && a.min[0] <= b.max[0] && a.max[0] >= b.min[0] && a.min[1] <= b.max[1] && a.max[1] >= b.min[1];

/** What is drawn on one level, in draw order. */
export function buildLevelPlan(nodes: BimNode[], level: PlanLevel, tol = PLAN_TOLERANCES): LevelPlan {
  const E = level.elevation;
  const cut = E - tol.cutBelow;
  const items: PlanItem[] = [];
  const starts: PlanItem[] = [];
  for (const n of placed(nodes)) {
    const kind = n.elementKind ?? 'other';
    const add = (role: PlanRole, shape: PlanShape | null) => shape && items.push({ id: n.id, node: n, role, shape });
    switch (kind) {
      case 'slab':
        if (E >= zMin(n) - tol.slabMatch && E <= zMax(n) + tol.slabMatch) add('slab', footprint(n));
        break;
      case 'beam':
        if (Math.abs(zMax(n) - E) <= tol.beamTop) add('beam', memberLine(n));
        break;
      case 'brace':
        if (overlaps(n, E - tol.braceBelow, E - 0.05) && zMax(n) <= E + tol.beamTop) add('brace', memberLine(n));
        break;
      case 'column':
        if (zMin(n) < cut && zMax(n) >= cut) add('column', footprint(n));
        else if (Math.abs(zMin(n) - E) <= tol.columnStart) starts.push({ id: n.id, node: n, role: 'column-start', shape: footprint(n) });
        break;
      case 'wall':
        if (zMin(n) < cut && zMax(n) >= cut) add('wall', footprint(n));
        break;
      case 'footing':
      case 'pile':
        if (zMax(n) <= E + tol.zoneAbove && zMax(n) >= E - tol.foundationBelow) add('foundation', footprint(n));
        break;
      case 'connection':
      case 'fastener':
        if (overlaps(n, E - tol.zoneBelow, E + tol.zoneAbove)) {
          const { min, max } = n.bbox;
          add('connection', { type: 'point', at: [(min[0] + max[0]) / 2, (min[1] + max[1]) / 2], size: Math.max(0.25, max[0] - min[0], max[1] - min[1]) });
        }
        break;
      default:
        if (overlaps(n, cut, E + tol.zoneAbove)) add('other', footprint(n));
    }
  }
  // a column that starts here is news only where nothing below carries it
  const cutColumns = items.filter((i) => i.role === 'column');
  for (const s of starts) if (!cutColumns.some((c) => rectsTouch(c.shape, s.shape))) items.push(s);
  items.sort((a, b) => ROLE_ORDER[a.role] - ROLE_ORDER[b.role]);
  return { level, items, extents: extentsOf(items) };
}

function extentsOf(items: PlanItem[]): LevelPlan['extents'] {
  if (items.length === 0) return null;
  const min: Vec2 = [Infinity, Infinity];
  const max: Vec2 = [-Infinity, -Infinity];
  const grow = (x: number, y: number, pad = 0) => {
    min[0] = Math.min(min[0], x - pad);
    min[1] = Math.min(min[1], y - pad);
    max[0] = Math.max(max[0], x + pad);
    max[1] = Math.max(max[1], y + pad);
  };
  for (const { shape: s } of items) {
    if (s.type === 'line') {
      grow(s.a[0], s.a[1], s.width / 2);
      grow(s.b[0], s.b[1], s.width / 2);
    } else if (s.type === 'rect') {
      grow(s.min[0], s.min[1]);
      grow(s.max[0], s.max[1]);
    } else grow(s.at[0], s.at[1], s.size / 2);
  }
  return { min, max };
}

/** Every level's plan; levels with nothing to draw are dropped. */
export function buildPlanIndex(nodes: BimNode[], storeys: ModelLevel[] = [], tol = PLAN_TOLERANCES): PlanIndex {
  const plans = new Map<string, LevelPlan>();
  const levelsOf = new Map<string, string[]>();
  const levels: PlanLevel[] = [];
  const all: PlanItem[] = [];
  for (const level of planLevels(nodes, storeys, tol)) {
    const plan = buildLevelPlan(nodes, level, tol);
    if (plan.items.length === 0) continue;
    levels.push(level);
    plans.set(level.id, plan);
    for (const it of plan.items) {
      const ls = levelsOf.get(it.id);
      if (ls) ls.push(level.id);
      else levelsOf.set(it.id, [level.id]);
      all.push(it);
    }
  }
  return { levels, plans, levelsOf, extents: extentsOf(all) };
}

/** The level to show an element on: the current one if it is drawn there, else its lowest level. */
export function levelForElement(index: PlanIndex, id: string, current: string | null): string | null {
  const ls = index.levelsOf.get(id);
  if (!ls || ls.length === 0) return null;
  return current && ls.includes(current) ? current : ls[0]!;
}

/** The next level up (+1) or down (-1), or null at the top / bottom. */
export function stepLevel(index: PlanIndex, current: string | null, dir: 1 | -1): string | null {
  const i = index.levels.findIndex((l) => l.id === current);
  if (i < 0) return index.levels[0]?.id ?? null;
  return index.levels[i + dir]?.id ?? null;
}

/** "+11.582 m" / "−7.163 m" / "±0.000 m" */
export function formatElevation(m: number): string {
  const v = Math.abs(m) < 0.0005 ? 0 : m;
  return `${v === 0 ? '±' : v > 0 ? '+' : '−'}${Math.abs(v).toFixed(3)} m`;
}
