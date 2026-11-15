/**
 * Grids: bubble pairs -> grid lines per plan sheet; dimension strings between adjacent bubbles ->
 * scale (ft per pt) and building coordinates of every grid line; per-sheet page <-> building maps.
 *
 * Building frame (feet): x grows to the right of the plan, y grows up the plan (plan north up is
 * assumed), origin at the left-most x-line and the bottom-most y-line of the reference plan (the
 * plan sheet with the most grid lines). A grid line's coordinate comes from the cumulative written
 * dimension strings of the reference plan, falling back to measured points x scale. On every sheet a
 * page point maps piecewise-linearly between that sheet's own grid lines, so each sheet registers to
 * the same grid even if it was plotted at a slightly different scale or offset.
 */
import type { DrawingProfile } from "./profile.ts";
import { center, feetInches, r2, scalePtPerFt } from "./text.ts";
import type { Phrase, Sheet, SheetGridLine } from "./types.ts";

/** Single-word grid-bubble labels in the drawing area. */
export function bubbleLabels(phr: Phrase[], cutoff: number, pf: DrawingProfile): Phrase[] {
  const [lo, hi] = pf.bubbleSize;
  return phr.filter((p) => p.rot === 0 && p.words.length === 1 && pf.gridLabel.test(p.text) &&
    p.size >= lo && p.size <= hi && p.rect[2] < cutoff);
}

/** Plan grid lines: the same label printed twice far apart at the same x (x-line) or the same y (y-line). */
export function planGrid(phr: Phrase[], sheet: Sheet, pf: DrawingProfile): SheetGridLine[] {
  const by = new Map<string, Phrase[]>();
  for (const p of bubbleLabels(phr, sheet.cutoff, pf)) by.set(p.text, [...(by.get(p.text) ?? []), p]);
  const out: SheetGridLine[] = [];
  for (const [label, ps] of by) {
    let best: SheetGridLine | undefined;
    for (let i = 0; i < ps.length; i++) for (let j = i + 1; j < ps.length; j++) {
      const [ax, ay] = center(ps[i]!.rect);
      const [bx, by_] = center(ps[j]!.rect);
      if (Math.abs(ax - bx) < pf.bubblePairTol && Math.abs(ay - by_) > pf.bubblePairMinSep) {
        best = { label, axis: "x", pos: r2((ax + bx) / 2), rects: [ps[i]!.rect, ps[j]!.rect] };
      } else if (Math.abs(ay - by_) < pf.bubblePairTol && Math.abs(ax - bx) > pf.bubblePairMinSep) {
        best = { label, axis: "y", pos: r2((ay + by_) / 2), rects: [ps[i]!.rect, ps[j]!.rect] };
      }
    }
    if (best) out.push(best);
  }
  return out.sort((a, b) => (a.axis === b.axis ? a.pos - b.pos : a.axis < b.axis ? -1 : 1));
}

export interface DimPair {
  axis: "x" | "y";
  a: string;
  b: string;
  /** Distance between the two lines on the page, pt. */
  dpt: number;
  /** Written dimension, ft (undefined when no dimension string was found between them). */
  ft?: number;
}

export interface Calibration {
  /** ft per pt, per axis. */
  k: { x: number; y: number };
  pairs: DimPair[];
  /** How the scale was found: "dimension strings", "scale note", or "none". */
  source: string;
  /** RMS of (scale x measured pt - written dimension), inches. */
  rmsResidualIn?: number;
}

/**
 * Scale from the dimension strings written between adjacent grid lines (a feet-inch phrase whose
 * centre lies between the two lines, reading along them, outside the grid on the bubble side), else
 * from a "SCALE: 3/16" = 1'-0"" note, else none.
 */
export function calibrate(phr: Phrase[], lines: SheetGridLine[], sheet: Sheet, pf: DrawingProfile): Calibration {
  const dims = phr.filter((p) => p.rect[2] < sheet.cutoff && /^[+-]?\d+\s*'\s*-?\s*\d+(?:[\s-]+\d+\/\d+)?\s*"$/.test(p.text));
  const pairs: DimPair[] = [];
  for (const axis of ["x", "y"] as const) {
    const gl = lines.filter((l) => l.axis === axis).sort((a, b) => a.pos - b.pos);
    const other = lines.filter((l) => l.axis !== axis);
    if (gl.length < 2) continue;
    // the dimension strings run between the bubbles and the first grid line of the other axis
    const otherMin = other.length ? Math.min(...other.map((l) => l.pos)) : Infinity;
    for (let i = 0; i + 1 < gl.length; i++) {
      const a = gl[i]!, b = gl[i + 1]!;
      const mid = (a.pos + b.pos) / 2;
      const cand = dims.filter((p) => {
        const [cx, cy] = center(p.rect);
        const along = axis === "x" ? cx : cy;
        const across = axis === "x" ? cy : cx;
        const readsAlong = axis === "x" ? p.rot === 0 : p.rot === 90 || p.rot === 270;
        return readsAlong && along > a.pos && along < b.pos && across < otherMin;
      });
      const best = cand.sort((p, q) => Math.abs(alongOf(p, axis) - mid) - Math.abs(alongOf(q, axis) - mid) ||
        acrossOf(q, axis) - acrossOf(p, axis))[0];
      const pair: DimPair = { axis, a: a.label, b: b.label, dpt: b.pos - a.pos };
      const ft = best ? feetInches(best.text)[0] : undefined;
      if (ft !== undefined && ft > 0) pair.ft = ft;
      pairs.push(pair);
    }
  }
  const fit = (axis: "x" | "y"): number | undefined => {
    const ps = pairs.filter((p) => p.axis === axis && p.ft !== undefined);
    if (!ps.length) return undefined;
    // median of the per-pair ratios: robust against an overall dimension picked for one bay
    const ks = ps.map((p) => p.ft! / p.dpt).sort((a, b) => a - b);
    return ks[Math.floor(ks.length / 2)]!;
  };
  const kx = fit("x"), ky = fit("y");
  if (kx !== undefined || ky !== undefined) {
    const k = { x: kx ?? ky!, y: ky ?? kx! };
    const res = pairs.filter((p) => p.ft !== undefined).map((p) => (k[p.axis] * p.dpt - p.ft!) * 12);
    return { k, pairs, source: "dimension strings", rmsResidualIn: r2(Math.sqrt(res.reduce((s, r) => s + r * r, 0) / res.length)) };
  }
  const note = phr.map((p) => scalePtPerFt(p.text)).find((v) => v !== undefined) ?? pf.fallbackPtPerFt;
  if (note) return { k: { x: 1 / note, y: 1 / note }, pairs, source: "scale note" };
  return { k: { x: NaN, y: NaN }, pairs, source: "none" };
}

const alongOf = (p: Phrase, axis: "x" | "y") => (axis === "x" ? center(p.rect)[0] : center(p.rect)[1]);
const acrossOf = (p: Phrase, axis: "x" | "y") => (axis === "x" ? center(p.rect)[1] : center(p.rect)[0]);

/** Building coordinates (ft) of every grid line, from the reference plan. */
export interface BuildingGrid {
  x: Map<string, number>;
  y: Map<string, number>;
  /** Sheet the coordinates were taken from. */
  reference: string;
  k: { x: number; y: number };
}

export function buildingGrid(sheet: Sheet, lines: SheetGridLine[], cal: Calibration): BuildingGrid {
  const out: BuildingGrid = { x: new Map(), y: new Map(), reference: sheet.number, k: cal.k };
  for (const axis of ["x", "y"] as const) {
    // y: bottom of the page first (north up)
    const gl = lines.filter((l) => l.axis === axis).sort((a, b) => (axis === "x" ? a.pos - b.pos : b.pos - a.pos));
    let pos = 0;
    gl.forEach((l, i) => {
      if (i > 0) {
        const prev = gl[i - 1]!;
        const pair = cal.pairs.find((p) => p.axis === axis && ((p.a === prev.label && p.b === l.label) || (p.a === l.label && p.b === prev.label)));
        pos += pair?.ft ?? Math.abs(l.pos - prev.pos) * cal.k[axis];
      }
      out[axis].set(l.label, r2(pos * 1000) / 1000);
    });
  }
  return out;
}

/** Page <-> building mapping of one plan sheet. */
export interface SheetMap {
  toX(px: number): number;
  toY(py: number): number;
  /** Building ft -> page pt (inverse), used to place callout attribution geometry. */
  fromX(x: number): number;
  fromY(y: number): number;
  /** ft per pt on this sheet. */
  k: { x: number; y: number };
}

function interp(v: number, pts: Array<[number, number]>, slope: number): number {
  const s = [...pts].sort((a, b) => a[0] - b[0]);
  if (!s.length) return NaN;
  if (s.length === 1) return s[0]![1] + (v - s[0]![0]) * slope;
  const end = (p: [number, number], q: [number, number]) => (q[1] - p[1]) / (q[0] - p[0]);
  if (v <= s[0]![0]) return s[0]![1] + (v - s[0]![0]) * end(s[0]!, s[1]!);
  const last = s.length - 1;
  if (v >= s[last]![0]) return s[last]![1] + (v - s[last]![0]) * end(s[last - 1]!, s[last]!);
  for (let i = 0; i < last; i++) {
    const p = s[i]!, q = s[i + 1]!;
    if (v >= p[0] && v <= q[0]) return p[1] + ((v - p[0]) / (q[0] - p[0])) * (q[1] - p[1]);
  }
  return NaN;
}

export function sheetMap(lines: SheetGridLine[], grid: BuildingGrid, cal: Calibration): SheetMap {
  const xs: Array<[number, number]> = lines.filter((l) => l.axis === "x" && grid.x.has(l.label)).map((l) => [l.pos, grid.x.get(l.label)!]);
  const ys: Array<[number, number]> = lines.filter((l) => l.axis === "y" && grid.y.has(l.label)).map((l) => [l.pos, grid.y.get(l.label)!]);
  const kx = Number.isFinite(cal.k.x) ? cal.k.x : grid.k.x;
  const ky = Number.isFinite(cal.k.y) ? cal.k.y : grid.k.y;
  const inv = (pts: Array<[number, number]>) => pts.map(([a, b]) => [b, a] as [number, number]);
  return {
    toX: (px) => interp(px, xs, kx),
    toY: (py) => interp(py, ys, -ky),
    fromX: (x) => interp(x, inv(xs), 1 / kx),
    fromY: (y) => interp(y, inv(ys), -1 / ky),
    k: { x: kx, y: ky },
  };
}

/** Lines of one axis bracketing a page coordinate: [below, above] by page position (either may be missing). */
export function bracket(lines: SheetGridLine[], axis: "x" | "y", pos: number): [SheetGridLine | undefined, SheetGridLine | undefined] {
  const gl = lines.filter((l) => l.axis === axis).sort((a, b) => a.pos - b.pos);
  let lo: SheetGridLine | undefined, hi: SheetGridLine | undefined;
  for (const l of gl) {
    if (l.pos <= pos) lo = l;
    else if (!hi) hi = l;
  }
  return [lo, hi];
}

/** Nearest line of one axis to a page coordinate, with its distance in pt. */
export function nearestLine(lines: SheetGridLine[], axis: "x" | "y", pos: number): { line: SheetGridLine; d: number } | undefined {
  let best: { line: SheetGridLine; d: number } | undefined;
  for (const l of lines) if (l.axis === axis) {
    const d = Math.abs(l.pos - pos);
    if (!best || d < best.d) best = { line: l, d };
  }
  return best;
}

/** Canonical intersection label: x-line label, slash, y-line label ("1/A"). */
export const intersection = (xLabel: string, yLabel: string): string => `${xLabel}/${yLabel}`;

/** "1/A" or "A/1" as printed -> canonical, using which axis each label belongs to. */
export function canonicalIntersection(text: string, grid: BuildingGrid): string | undefined {
  const m = /^([A-Z0-9.]+)\s*\/\s*([A-Z0-9.]+)$/.exec(text.trim());
  if (!m) return undefined;
  const a = m[1]!, b = m[2]!;
  if (grid.x.has(a) && grid.y.has(b)) return intersection(a, b);
  if (grid.x.has(b) && grid.y.has(a)) return intersection(b, a);
  return undefined;
}

