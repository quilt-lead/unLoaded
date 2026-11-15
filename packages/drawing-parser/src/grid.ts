/**
 * Grids: bubble pairs -> grid lines per plan sheet; dimension strings between adjacent bubbles ->
 * scale (ft per pt) and building coordinates of every grid line; per-sheet page <-> building maps.
 *
 * Building frame (feet): x grows to the right of the plan, y grows up the plan (plan north up is
 * assumed), origin at the left-most x-line and the bottom-most y-line of the reference plan (the
 * plan sheet with the most grid lines). A grid line's coordinate comes from the cumulative written
 * dimension strings of the reference plan - each accepted only when it agrees with the calibrated
 * scale (`agrees`), so an overall dimension or a neighbouring bay's string never stands in for a
 * span - falling back to measured points x scale, recorded as measured. On every sheet a
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
  /** Dimension string read between the two lines, ft, whether or not it was accepted. */
  writtenFt?: number;
  /**
   * Accepted written dimension, ft: set only when `writtenFt` agrees with the calibrated scale
   * (`agrees`). Undefined when no string was found or the string disagrees (an overall dimension,
   * another bay's string): the span is then measured (pt x scale), not stated.
   */
  ft?: number;
}

/**
 * A written dimension is accepted for a span only within this of the calibrated scale x the measured
 * distance: 20 % or 3 in, whichever is larger. The bound sits in the gap between the two things it
 * separates. A misread string is far off: an overall dimension over n >= 2 bays is >= 50 % long when
 * adjacent bays differ by at most 2:1, and one bay's string on a pair spanning two bays (middle line not
 * drawn) is >= 33 % short. Drafting distortion - a grid line moved without its dimension, a bay drawn
 * "not to scale" - is a few percent and rarely past 10 to 15 %, and there the WRITTEN dimension is the
 * truth, so a tighter bound (R1's 3 %) replaced correct written dimensions by measured ones. 20 % accepts
 * distortion up to that and still leaves 13 points to the nearest misread.
 */
export const DIM_TOL = { rel: 0.2, absFt: 0.25 } as const;

/** Does a written dimension `ft` agree with `dpt` page points at `k` ft per pt? */
export function agrees(ft: number, dpt: number, k: number): boolean {
  return Number.isFinite(k) && Number.isFinite(ft) && Math.abs(k * dpt - ft) <= Math.max(DIM_TOL.absFt, DIM_TOL.rel * Math.abs(ft));
}

export interface Calibration {
  /** ft per pt, per axis. */
  k: { x: number; y: number };
  pairs: DimPair[];
  /** How the scale was found: "dimension strings", "scale note", "profile fallback scale", or "none". */
  source: string;
  /** Which scale note was used and why (source "scale note"). */
  scaleRule?: string;
  /** RMS of (scale x measured pt - written dimension) over the accepted dimensions, inches. */
  rmsResidualIn?: number;
  /** Two or more dimension strings support different scales equally and no scale note decides. */
  ambiguous?: boolean;
}

/**
 * A title naming the sheet's plan: "LEVEL 2 FRAMING PLAN", "FOUNDATION PLAN". A detail drawn as a plan -
 * "ENLARGED PLAN", "PARTIAL PLAN", "KEY PLAN", "PART PLAN", "DETAIL PLAN", "BLOW-UP PLAN" - is at its
 * own (larger or smaller) scale and is not the plan.
 */
export function planTitle(text: string): boolean {
  return /\bPLAN\b/.test(text) && !/\b(?:ENLARGED|PARTIAL|PART|KEY|DETAIL|BLOW-?UP)\b/.test(text);
}

/**
 * The scale note that governs the plan: one in, or directly under, a title naming the plan (`planTitle`); else the
 * smallest scale on the sheet (a detail drawn on a plan sheet is at a larger scale than the plan, so
 * the first note in reading order may be a detail's). Undefined when the sheet has no scale note.
 */
export function planScaleNote(phr: Phrase[]): { ptPerFt: number; rule: string } | undefined {
  const notes = phr.map((p) => ({ p, v: scalePtPerFt(p.text) })).filter((n): n is { p: Phrase; v: number } => n.v !== undefined);
  if (!notes.length) return undefined;
  const PLAN = { test: planTitle };
  const underPlanTitle = (p: Phrase) => PLAN.test(p.text) || phr.some((q) => q !== p && q.rot === p.rot && PLAN.test(q.text) &&
    q.rect[3] <= p.rect[1] + 1 && p.rect[1] - q.rect[3] < 2.5 * Math.max(p.size, q.size) && q.rect[0] < p.rect[2] && p.rect[0] < q.rect[2]);
  const titled = notes.find((n) => underPlanTitle(n.p));
  if (titled) return { ptPerFt: titled.v, rule: "scale note in / under the plan title" };
  const v = Math.min(...notes.map((n) => n.v));
  return {
    ptPerFt: v,
    rule: notes.length > 1 && notes.some((n) => n.v !== v)
      ? "smallest of the sheet's scale notes (no plan title names one; details are drawn at larger scales than the plan)"
      : "the sheet's scale note",
  };
}

/**
 * Scale from the dimension strings written between adjacent grid lines (a feet-inch phrase whose
 * centre lies between the two lines, reading along them, outside the grid on the bubble side), else
 * from the plan's "SCALE: 3/16" = 1'-0"" note (`planScaleNote`), else the profile's fallback, else none.
 *
 * The scale is found per axis - the ratio the most of that axis's strings agree with (a tie goes to the
 * scale note, else to the other axis's scale) - then refit as the median of the strings that agree. Per
 * axis, because a plan can be plotted at different x and y scales: pooling them let the axis with more
 * strings reject every string of the other. An axis with a single string that disagrees with the other
 * axis's scale (when at least two strings agree on it) or else with the scale note is a misread, not a
 * scale: that axis takes the other's scale (or the note's). An axis with no strings takes the other's.
 * A string is kept as the span's stated dimension (`pair.ft`) only if it agrees with its axis's scale
 * (`agrees`); the others keep `writtenFt` only.
 */
export function calibrate(phr: Phrase[], lines: SheetGridLine[], sheet: Sheet, pf: DrawingProfile): Calibration {
  const dims = phr.filter((p) => p.rect[2] < sheet.cutoff && /^[+-]?\d+\s*'\s*-?\s*\d+(?:[\s-]+\d+\/\d+)?\s*"$/.test(p.text));
  const pairs: DimPair[] = [];
  // every string read between a pair's lines, nearest its middle first
  const candidates = new Map<DimPair, number[]>();
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
      const fts = cand
        .sort((p, q) => Math.abs(alongOf(p, axis) - mid) - Math.abs(alongOf(q, axis) - mid) || acrossOf(q, axis) - acrossOf(p, axis))
        .map((p) => feetInches(p.text)[0])
        .filter((ft): ft is number => ft !== undefined && ft > 0);
      const pair: DimPair = { axis, a: a.label, b: b.label, dpt: b.pos - a.pos };
      if (fts.length) pair.writtenFt = fts[0]!;
      candidates.set(pair, fts);
      pairs.push(pair);
    }
  }
  const note = planScaleNote(phr);
  const written = pairs.filter((p) => p.writtenFt !== undefined);
  if (written.length) {
    type Consensus = { r: number; s: number; tie?: boolean };
    // consensus on one axis: the ratio the most of its strings agree with; a tie goes to the scale note,
    // else to `prefer` (the other axis's scale), else is flagged
    const consensus = (ws: DimPair[], prefer?: number): Consensus | undefined => {
      const support = (r: number) => ws.filter((p) => agrees(p.writtenFt!, p.dpt, r)).length;
      let best: Consensus | undefined;
      for (const p of ws) {
        const r = p.writtenFt! / p.dpt;
        const s = support(r);
        if (!best || s > best.s) best = { r, s };
        else if (s === best.s && !agrees(best.r * p.dpt, p.dpt, r)) {
          const ref = note ? 1 / note.ptPerFt : prefer;
          if (ref === undefined) best.tie = true;
          else if (Math.abs(r / ref - 1) < Math.abs(best.r / ref - 1)) best = { r, s };
        }
      }
      return best;
    };
    const wx = written.filter((p) => p.axis === "x"), wy = written.filter((p) => p.axis === "y");
    let cx = consensus(wx), cy = consensus(wy, cx?.r);
    if (cx?.tie && cy) cx = consensus(wx, cy.r); // an x tie broken by y's scale
    // a lone string that disagrees with the other axis's agreed scale (else the note) is a misread
    const lone = (c: Consensus | undefined, other: Consensus | undefined): Consensus | undefined => {
      if (!c || c.s >= 2) return c;
      const ref = other && other.s >= 2 ? other.r : note ? 1 / note.ptPerFt : undefined;
      return ref !== undefined && Math.abs(c.r / ref - 1) > DIM_TOL.rel ? { r: ref, s: 0 } : c;
    };
    [cx, cy] = [lone(cx, cy), lone(cy, cx)];
    const ambiguous = !!(cx?.tie || cy?.tie);
    const fit = (c: { r: number; s: number } | undefined, ws: DimPair[]): number | undefined => {
      if (!c) return undefined;
      const ks = ws.filter((p) => agrees(p.writtenFt!, p.dpt, c.r)).map((p) => p.writtenFt! / p.dpt).sort((a, b) => a - b);
      return ks.length ? ks[Math.floor(ks.length / 2)]! : c.r;
    };
    const kx = fit(cx, wx), ky = fit(cy, wy);
    const k = { x: kx ?? ky!, y: ky ?? kx! };
    // only a string that agrees with the scale states the span (the nearest-to-middle one that does);
    // a pair with none is measured
    for (const p of written) {
      const ok = candidates.get(p)!.find((ft) => agrees(ft, p.dpt, k[p.axis]));
      if (ok !== undefined) p.ft = p.writtenFt = ok;
    }
    const res = pairs.filter((p) => p.ft !== undefined).map((p) => (k[p.axis] * p.dpt - p.ft!) * 12);
    return {
      k, pairs, source: "dimension strings",
      ...(res.length ? { rmsResidualIn: r2(Math.sqrt(res.reduce((s, r) => s + r * r, 0) / res.length)) } : {}),
      ...(ambiguous ? { ambiguous } : {}),
    };
  }
  if (note) return { k: { x: 1 / note.ptPerFt, y: 1 / note.ptPerFt }, pairs, source: "scale note", scaleRule: note.rule };
  if (pf.fallbackPtPerFt) return { k: { x: 1 / pf.fallbackPtPerFt, y: 1 / pf.fallbackPtPerFt }, pairs, source: "profile fallback scale" };
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
  /**
   * Spans placed by measured distance x scale, not by a stated dimension: no string was read
   * between the two lines, or the string read (`writtenFt`) disagrees with the scale.
   */
  measured: Array<{ axis: "x" | "y"; a: string; b: string; ft: number; writtenFt?: number }>;
}

export function buildingGrid(sheet: Sheet, lines: SheetGridLine[], cal: Calibration): BuildingGrid {
  const out: BuildingGrid = { x: new Map(), y: new Map(), reference: sheet.number, k: cal.k, measured: [] };
  for (const axis of ["x", "y"] as const) {
    // y: bottom of the page first (north up)
    const gl = lines.filter((l) => l.axis === axis).sort((a, b) => (axis === "x" ? a.pos - b.pos : b.pos - a.pos));
    let pos = 0;
    gl.forEach((l, i) => {
      if (i > 0) {
        const prev = gl[i - 1]!;
        const pair = cal.pairs.find((p) => p.axis === axis && ((p.a === prev.label && p.b === l.label) || (p.a === l.label && p.b === prev.label)));
        const dpt = Math.abs(l.pos - prev.pos);
        // the same acceptance test as calibrate(), whoever built the Calibration
        const stated = pair?.ft !== undefined && agrees(pair.ft, dpt, cal.k[axis]) ? pair.ft : undefined;
        const measured = dpt * cal.k[axis];
        if (stated === undefined) {
          out.measured.push({ axis, a: prev.label, b: l.label, ft: r2(measured * 1000) / 1000, ...(pair?.writtenFt !== undefined ? { writtenFt: pair.writtenFt } : {}) });
        }
        pos += stated ?? measured;
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

