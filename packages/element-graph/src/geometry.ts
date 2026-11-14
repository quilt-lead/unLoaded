/** Small, allocation-light geometry helpers over BBox / Vec3. */
import type { BBox, Vec3 } from "./model/input.ts";
import type { ElementNode } from "./model/graph-types.ts";

export interface Axis {
  start: Vec3;
  end: Vec3;
}

/** Euclidean distance between two boxes (0 when overlapping / touching). */
export function bboxGap(a: BBox, b: BBox): number {
  let s = 0;
  for (let i = 0; i < 3; i++) {
    const d = Math.max(0, a.min[i]! - b.max[i]!, b.min[i]! - a.max[i]!);
    s += d * d;
  }
  return Math.sqrt(s);
}

/** Distance from a point to a box (0 inside). */
export function pointBoxDist(p: Vec3, b: BBox): number {
  let s = 0;
  for (let i = 0; i < 3; i++) {
    const d = Math.max(0, b.min[i]! - p[i]!, p[i]! - b.max[i]!);
    s += d * d;
  }
  return Math.sqrt(s);
}

/** Plan (XY) distance from a point to a box's footprint. */
export function planPointBoxDist(p: Vec3, b: BBox): number {
  const dx = Math.max(0, b.min[0] - p[0], p[0] - b.max[0]);
  const dy = Math.max(0, b.min[1] - p[1], p[1] - b.max[1]);
  return Math.hypot(dx, dy);
}

/** Plan (XY) overlap area of two boxes. */
export function planOverlapArea(a: BBox, b: BBox): number {
  const ox = Math.min(a.max[0], b.max[0]) - Math.max(a.min[0], b.min[0]);
  const oy = Math.min(a.max[1], b.max[1]) - Math.max(a.min[1], b.min[1]);
  return ox > 0 && oy > 0 ? ox * oy : 0;
}

export function bboxCenter(b: BBox): Vec3 {
  return [(b.min[0] + b.max[0]) / 2, (b.min[1] + b.max[1]) / 2, (b.min[2] + b.max[2]) / 2];
}

const VERTICAL_KINDS = new Set(["column", "pile", "wall"]);

/**
 * Analytical axis of a linear member. Uses geometry.axis when present,
 * otherwise derives one from the bbox. Vertical members (column, pile, wall)
 * are returned bottom -> top.
 */
export function memberAxis(node: ElementNode): Axis | undefined {
  const g = node.geometry;
  if (!g) return undefined;
  let axis: Axis;
  if (g.axis) {
    axis = { start: g.axis.start, end: g.axis.end };
  } else {
    const b = g.bbox;
    const c = bboxCenter(b);
    const dx = b.max[0] - b.min[0];
    const dy = b.max[1] - b.min[1];
    const dz = b.max[2] - b.min[2];
    if (VERTICAL_KINDS.has(node.kind) || (dz >= dx && dz >= dy)) {
      axis = { start: [c[0], c[1], b.min[2]], end: [c[0], c[1], b.max[2]] };
    } else if (dx >= dy) {
      axis = { start: [b.min[0], c[1], c[2]], end: [b.max[0], c[1], c[2]] };
    } else {
      axis = { start: [c[0], b.min[1], c[2]], end: [c[0], b.max[1], c[2]] };
    }
  }
  if (VERTICAL_KINDS.has(node.kind) && axis.start[2] > axis.end[2]) axis = { start: axis.end, end: axis.start };
  return axis;
}

/** Angle in degrees between two axes (direction-agnostic, 0..90). */
export function axisAngleDeg(a: Axis, b: Axis): number {
  const u = sub(a.end, a.start);
  const v = sub(b.end, b.start);
  const lu = Math.hypot(...u);
  const lv = Math.hypot(...v);
  if (lu === 0 || lv === 0) return 90;
  const cos = Math.min(1, Math.abs((u[0] * v[0] + u[1] * v[1] + u[2] * v[2]) / (lu * lv)));
  return (Math.acos(cos) * 180) / Math.PI;
}

function sub(a: Vec3, b: Vec3): Vec3 {
  return [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
}
