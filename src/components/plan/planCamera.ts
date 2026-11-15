// The 2D plan's camera: a centre in model metres and a scale in screen px per metre. Plan y is up,
// screen y is down. Pure functions, so pan / zoom / fit are testable without a DOM.
import type { Vec2 } from '../../utils/planSlice';

export interface PlanCamera {
  cx: number;
  cy: number;
  /** px per metre */
  s: number;
}

export interface Viewport {
  w: number;
  h: number;
}

export const MIN_SCALE = 0.5;
export const MAX_SCALE = 600;
const clampScale = (s: number) => Math.min(MAX_SCALE, Math.max(MIN_SCALE, s));

export const toScreen = (c: PlanCamera, v: Viewport, p: Vec2): Vec2 => [v.w / 2 + (p[0] - c.cx) * c.s, v.h / 2 - (p[1] - c.cy) * c.s];
export const toWorld = (c: PlanCamera, v: Viewport, q: Vec2): Vec2 => [c.cx + (q[0] - v.w / 2) / c.s, c.cy - (q[1] - v.h / 2) / c.s];

/** Frame `ext` with `pad` px of margin on every side. */
export function fitCamera(ext: { min: Vec2; max: Vec2 }, v: Viewport, pad = 40): PlanCamera {
  const w = Math.max(ext.max[0] - ext.min[0], 0.5);
  const h = Math.max(ext.max[1] - ext.min[1], 0.5);
  const s = clampScale(Math.min((v.w - 2 * pad) / w, (v.h - 2 * pad) / h));
  return { cx: (ext.min[0] + ext.max[0]) / 2, cy: (ext.min[1] + ext.max[1]) / 2, s: Number.isFinite(s) && s > 0 ? s : 10 };
}

/** Zoom by `factor`, keeping the model point under screen point `q` where it is. */
export function zoomAt(c: PlanCamera, v: Viewport, factor: number, q: Vec2): PlanCamera {
  const s = clampScale(c.s * factor);
  const p = toWorld(c, v, q);
  return { s, cx: p[0] - (q[0] - v.w / 2) / s, cy: p[1] + (q[1] - v.h / 2) / s };
}

/** Pan by a screen delta in px (drag direction). */
export const panBy = (c: PlanCamera, dx: number, dy: number): PlanCamera => ({ ...c, cx: c.cx - dx / c.s, cy: c.cy + dy / c.s });

/** Whether model point `p` is on screen with `margin` px to spare. */
export function inView(c: PlanCamera, v: Viewport, p: Vec2, margin = 24): boolean {
  const [x, y] = toScreen(c, v, p);
  return x >= margin && x <= v.w - margin && y >= margin && y <= v.h - margin;
}

/** A scale bar length (1-2-5 steps) close to `targetPx` on screen. */
export function scaleBarMetres(s: number, targetPx = 96): number {
  const raw = targetPx / s;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 5, 10].find((k) => k * mag >= raw * 0.75) ?? 10;
  return step * mag;
}
