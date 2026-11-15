/**
 * Text helpers: words -> phrases (one text run on one baseline, any rotation), feet-inch
 * values, member tags, rectangles.
 */
import { normaliseProfile, profileFromText } from "@unloaded/ifc-parser";
import type { DrawingWord, Phrase, Rect } from "./types.ts";

export const FT = 0.3048;

export const r1 = (v: number): number => Math.round(v * 10) / 10;
export const r2 = (v: number): number => Math.round(v * 100) / 100;

export const center = (r: Rect): [number, number] => [(r[0] + r[2]) / 2, (r[1] + r[3]) / 2];
export const union = (rs: Rect[]): Rect => [
  Math.min(...rs.map((r) => r[0])), Math.min(...rs.map((r) => r[1])),
  Math.max(...rs.map((r) => r[2])), Math.max(...rs.map((r) => r[3])),
];
export const rectOf = (w: { x0: number; y0: number; x1: number; y1: number }): Rect => [w.x0, w.y0, w.x1, w.y1];
export const roundRect = (r: Rect): Rect => [r1(r[0]), r1(r[1]), r1(r[2]), r1(r[3])];

/** Unit reading direction (page coordinates, y down) of a rotation in degrees counter-clockwise. */
export function dirOf(rot: number): [number, number] {
  const a = (rot * Math.PI) / 180;
  return [Math.round(Math.cos(a) * 1e9) / 1e9, Math.round(-Math.sin(a) * 1e9) / 1e9];
}

/** Position of a word along its reading direction and across it (towards "down" = away from ascent). */
function frame(w: DrawingWord): { t0: number; t1: number; c: number } {
  const [ux, uy] = dirOf(w.rot);
  // "down" (descent side) is the reading direction turned 90 deg clockwise on the page
  const dx = -uy, dy = ux;
  const xs = [w.x0, w.x1];
  const ys = [w.y0, w.y1];
  const along: number[] = [];
  const across: number[] = [];
  for (const x of xs) for (const y of ys) {
    along.push(x * ux + y * uy);
    across.push(x * dx + y * dy);
  }
  return { t0: Math.min(...along), t1: Math.max(...along), c: (Math.min(...across) + Math.max(...across)) / 2 };
}

/**
 * Group words into phrases: same rotation and size, same baseline (across offset under 0.3 x size),
 * consecutive along the reading direction with a gap under `gapFactor` x size (a space is ~0.28).
 * Phrases come back in reading order (top to bottom, then left to right) for determinism.
 */
export function phrases(words: DrawingWord[], gapFactor = 0.8): Phrase[] {
  const items = words.map((w) => ({ w, ...frame(w) }));
  items.sort((a, b) => a.w.rot - b.w.rot || a.t0 - b.t0 || a.c - b.c);
  const open: Array<{ ws: typeof items; rot: number; size: number; c: number; t1: number }> = [];
  for (const it of items) {
    let best: (typeof open)[number] | undefined;
    let bestGap = Infinity;
    for (const p of open) {
      if (p.rot !== it.w.rot || Math.abs(p.size - it.w.size) > 0.5) continue;
      if (Math.abs(p.c - it.c) > 0.3 * it.w.size) continue;
      const gap = it.t0 - p.t1;
      if (gap < -0.2 * it.w.size || gap > gapFactor * it.w.size) continue;
      if (gap < bestGap) {
        bestGap = gap;
        best = p;
      }
    }
    if (best) {
      best.ws.push(it);
      best.t1 = Math.max(best.t1, it.t1);
    } else {
      open.push({ ws: [it], rot: it.w.rot, size: it.w.size, c: it.c, t1: it.t1 });
    }
  }
  const out: Phrase[] = open.map((p) => ({
    text: p.ws.map((x) => x.w.s).join(" "),
    words: p.ws.map((x) => x.w),
    rect: union(p.ws.map((x) => rectOf(x.w))),
    rot: p.rot,
    size: p.size,
  }));
  out.sort((a, b) => a.rect[1] - b.rect[1] || a.rect[0] - b.rect[0]);
  return out;
}

const FTIN = /([+-])?\s*(\d+)\s*'\s*-?\s*(\d+)(?:(?:\s+|\s*-\s*)(\d+)\s*\/\s*(\d+))?\s*"/;

/** Every feet-inch value in a string (5'-6", 5' - 6", -3'-0", 20'-1 1/2"), in feet. */
export function feetInches(s: string): number[] {
  const re = new RegExp(FTIN.source, "g");
  const out: number[] = [];
  let m: RegExpExecArray | null;
  while ((m = re.exec(s))) {
    let v = Number(m[2]) + Number(m[3]) / 12;
    if (m[4] && m[5] && Number(m[5]) !== 0) v += Number(m[4]) / Number(m[5]) / 12;
    out.push(m[1] === "-" ? -v : v);
  }
  return out;
}

/** "3-1/4" / "1/2" / "6" -> inches. */
export function inches(s: string): number | undefined {
  const m = /^(?:(\d+)(?:-|\s+))?(\d+)\/(\d+)$/.exec(s.trim());
  if (m) return (m[1] ? Number(m[1]) : 0) + Number(m[2]) / Number(m[3]);
  const n = Number(s.trim());
  return Number.isFinite(n) ? n : undefined;
}

/** A drawing scale "3/16" = 1'-0"" -> points per foot. */
export function scalePtPerFt(s: string): number | undefined {
  const m = /(\d+(?:-\d+\/\d+|\/\d+)?)\s*"\s*=\s*1\s*'\s*-?\s*0\s*"/.exec(s);
  if (!m || !m[1]) return undefined;
  const v = inches(m[1]);
  return v ? v * 72 : undefined;
}

// ---------------------------------------------------------------- member tags

const US_SHAPE = String.raw`(?:W|M|S|HP|C|MC|WT|MT|ST)\s?\d+(?:\.\d+)?\s*[xX×]\s*\d+(?:\.\d+)?`;
const FRAC = String.raw`\d+(?:\.\d+)?(?:-\d+\/\d+)?(?:\/\d+)?`;
const HSS = String.raw`HSS\s?${FRAC}(?:\s*[xX×]\s*${FRAC}){1,2}`;
const ANGLE = String.raw`L\s?${FRAC}\s*[xX×]\s*${FRAC}\s*[xX×]\s*${FRAC}`;
const PIPE = String.raw`PIPE\s?\d+(?:\.\d+)?\s*(?:STD|XS|XXS)?`;
const TAG = new RegExp(
  String.raw`^(\*)?\s*(${HSS}|${US_SHAPE}|${ANGLE}|${PIPE}|[A-Z]{2,4}\s?\d+(?:\s*[xX×]\s*\d+){0,2})` +
  String.raw`(?:\s*\((\d+)\))?(?:\s*c\s*=\s*(${FRAC})\s*")?$`,
);

export interface MemberTag {
  /** Normalised section designation (ifc-parser's normaliseProfile). */
  profile: string;
  /** Printed with the SFRS prefix ("*W18X40"). */
  sfrs: boolean;
  /** "(n)": number of shear studs. */
  studs?: number;
  /** "c=3/4"": camber in inches. */
  camberIn?: number;
}

/** A member size tag as printed on plans / elevations / schedules: `*W18X40 (30) c=3/4"`. */
export function memberTag(text: string, sfrsPrefix = "*"): MemberTag | undefined {
  const t = text.trim().replace(new RegExp(`^${sfrsPrefix.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}`), "*");
  const m = TAG.exec(t);
  if (!m || !m[2]) return undefined;
  const core = m[2];
  // the generic branch must still read as a section to ifc-parser (IPE300, HEA200, UB ...)
  if (!new RegExp(`^(?:${HSS}|${US_SHAPE}|${ANGLE}|${PIPE})$`).test(core) && profileFromText([core]) !== normaliseProfile(core)) {
    return undefined;
  }
  const out: MemberTag = { profile: normaliseProfile(core), sfrs: m[1] === "*" };
  if (m[3]) out.studs = Number(m[3]);
  if (m[4]) {
    const c = inches(m[4]);
    if (c !== undefined) out.camberIn = c;
  }
  return out;
}

/**
 * Nominal section depth / width (m) from a designation alone, no section table: W18X40 -> 18 in
 * deep; HSS6X4X1/4 -> 6 x 4 in. Flange widths of rolled shapes are not in the designation, so the
 * width is a rough fraction of the depth. Used only for the bbox and recorded as nominal.
 */
export function nominalSection(profile: string): { depth: number; width: number } | undefined {
  let m = /^HSS(\d+(?:\.\d+)?)X(\d+(?:\.\d+)?)(?:X|$)/.exec(profile);
  if (m) return { depth: Number(m[1]) * 0.0254, width: Number(m[2]) * 0.0254 };
  m = /^HSS(\d+(?:\.\d+)?)X[\d./-]+$/.exec(profile);
  if (m) return { depth: Number(m[1]) * 0.0254, width: Number(m[1]) * 0.0254 };
  m = /^(?:W|M|S|HP|C|MC|WT|MT|ST)(\d+(?:\.\d+)?)X/.exec(profile);
  if (m) {
    const d = Number(m[1]) * 0.0254;
    return { depth: d, width: Math.max(0.1, d * 0.45) };
  }
  m = /^L(\d+(?:\.\d+)?)X(\d+(?:\.\d+)?)/.exec(profile);
  if (m) return { depth: Number(m[1]) * 0.0254, width: Number(m[2]) * 0.0254 };
  m = /^PIPE(\d+(?:\.\d+)?)/.exec(profile);
  if (m) return { depth: (Number(m[1]) + 0.6) * 0.0254, width: (Number(m[1]) + 0.6) * 0.0254 };
  return undefined;
}

/** "LEVEL 2" / "L2" / "ROOF" / "RF" -> display name "Level 2" / "Roof"; anything else title-cased. */
export function levelName(s: string): string | undefined {
  const t = s.trim().toUpperCase().replace(/\s+/g, " ");
  let m = /^(?:LEVEL|LVL|L)\s?(\d+[A-Z]?)$/.exec(t);
  if (m) return `Level ${m[1]}`;
  if (/^(?:ROOF|RF|ROOF LEVEL)$/.test(t)) return "Roof";
  if (/^(?:FOUNDATION|FDN)$/.test(t)) return "Foundation";
  m = /^(BASEMENT|MEZZANINE|PENTHOUSE)(?: (\d+))?$/.exec(t);
  if (m) return `${m[1]!.charAt(0)}${m[1]!.slice(1).toLowerCase()}${m[2] ? ` ${m[2]}` : ""}`;
  return undefined;
}

/** Level phrases inside longer text: "LEVEL 2", "ROOF", "FOUNDATION". */
export const LEVEL_IN_TEXT = /\b(LEVEL\s*\d+[A-Z]?|ROOF|FOUNDATION|BASEMENT(?:\s*\d+)?|MEZZANINE|PENTHOUSE)\b/;

/** id-safe slug: "Level 2" -> "level-2". */
export const slug = (s: string): string => s.toLowerCase().replace(/[^a-z0-9.]+/g, "-").replace(/^-|-$/g, "");
