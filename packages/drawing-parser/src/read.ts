/**
 * Sheet readers: plans (framing + foundation), frame elevations, schedules, detail panels,
 * detail callouts and level statements. Each reader turns text phrases into facts; nothing here
 * infers connectivity - callouts are the only relations, because the drawing states them.
 */
import type { Facts, MemberFact } from "./facts.ts";
import { bracket, bubbleLabels, canonicalIntersection, intersection, nearestLine, type BuildingGrid, type SheetMap } from "./grid.ts";
import type { DrawingProfile } from "./profile.ts";
import {
  center, feetInches, inches, levelName, LEVEL_IN_TEXT, memberTag, r2, roundRect, slug, union, type MemberTag,
} from "./text.ts";
import type { Occurrence, OccurrenceHow, Phrase, Rect, Sheet, SheetGridLine } from "./types.ts";

/** A page segment of an element, for attributing callouts on that sheet. */
export interface Seg {
  id: string;
  kind: "beam" | "brace" | "column-base";
  p: [number, number];
  q: [number, number];
  /** End labels at p and q. */
  ends: [string, string];
}

export interface SheetCtx {
  sheet: Sheet;
  phr: Phrase[];
  pf: DrawingProfile;
  grid: BuildingGrid;
  facts: Facts;
  /** Plan sheets only. */
  lines?: SheetGridLine[];
  map?: SheetMap;
  segs: Seg[];
}

export const occ = (s: Sheet, rect: Rect, how: OccurrenceHow, text: string): Occurrence => ({
  file: s.file, sheet: s.number, page: s.page, rect: roundRect(rect), how, text,
});

const levelKey = (name: string) => slug(name);
const span = (a: string, b: string) => `${a}..${b}`;

/** Order two grid labels of one axis by building coordinate. */
function ordered(grid: BuildingGrid, axis: "x" | "y", a: string, b: string): [string, string] {
  const m = grid[axis];
  return (m.get(a) ?? 0) <= (m.get(b) ?? 0) ? [a, b] : [b, a];
}

/** Page position of the line a tag labels: just past the tag's descent edge (plan convention). */
function tagLine(p: Phrase): { axis: "x" | "y"; pos: number; along: number } | undefined {
  const gap = 0.4 * p.size;
  const [cx, cy] = center(p.rect);
  switch (p.rot) {
    case 0: return { axis: "y", pos: p.rect[3] + gap, along: cx };     // member along x, line below the tag
    case 180: return { axis: "y", pos: p.rect[1] - gap, along: cx };
    case 90: return { axis: "x", pos: p.rect[2] + gap, along: cy };    // member along y, line right of the tag
    case 270: return { axis: "x", pos: p.rect[0] - gap, along: cy };
    default: return undefined;
  }
}

// =============================================================================== plans

/**
 * Member tags on a plan: the tag labels the drawn line just below it (rotated tags: beside it);
 * the member spans between the grid lines either side of the tag; a line within 0.9 x the text
 * size of a grid line is that grid line (girder), otherwise an infill member at the measured offset.
 */
export function readPlanMembers(ctx: SheetCtx): void {
  const { sheet, phr, pf, grid, facts } = ctx;
  const lines = ctx.lines!, map = ctx.map!;
  const level = sheet.level;
  if (!level) return;
  const infill: Array<{ m: MemberFact; across: number; key: string; seg: Seg }> = [];
  let diagonal = 0;
  for (const p of phr) {
    if (p.rect[2] > sheet.cutoff) continue;
    const tag = memberTag(p.text, pf.sfrsPrefix);
    if (!tag) continue;
    const tl = tagLine(p);
    if (!tl) {
      diagonal++;
      continue;
    }
    const alongAxis: "x" | "y" = tl.axis === "y" ? "x" : "y";
    const [lo, hi] = bracket(lines, alongAxis, tl.along);
    if (!lo || !hi) {
      facts.warnings.push(`${sheet.number}: tag "${p.text}" is outside the grid; skipped`);
      continue;
    }
    const [la, lb] = ordered(grid, alongAxis, lo.label, hi.label);
    const snap = nearestLine(lines, tl.axis, tl.pos);
    const pa = grid[alongAxis].get(la)!, pb = grid[alongAxis].get(lb)!;
    const pageSeg = (acrossPos: number): Pick<Seg, "p" | "q"> => {
      const pla = lines.find((l) => l.label === la && l.axis === alongAxis)!.pos;
      const plb = lines.find((l) => l.label === lb && l.axis === alongAxis)!.pos;
      return alongAxis === "x" ? { p: [pla, acrossPos], q: [plb, acrossPos] } : { p: [acrossPos, pla], q: [acrossPos, plb] };
    };
    const o = occ(sheet, p.rect, "plan_tag", p.text);
    const errFt = 1.5 * (tl.axis === "y" ? map.k.y : map.k.x);
    if (snap && snap.d <= 0.9 * p.size) {
      const across = grid[tl.axis].get(snap.line.label)!;
      const id = `beam:${levelKey(level)}:${span(la, lb)}:${snap.line.label}`;
      const m: MemberFact = {
        id, kind: "beam", role: "girder", level, ends: [la, lb], tag, grid: `${snap.line.label}/${span(la, lb)}`,
        a: alongAxis === "x" ? [pa, across] : [across, pa], b: alongAxis === "x" ? [pb, across] : [across, pb],
        rule: "plan tag on a grid line; spans the grid lines either side of the tag", planErrFt: 0, occ: o,
      };
      facts.members.push(m);
      ctx.segs.push({ id, kind: "beam", ...pageSeg(snap.line.pos), ends: [la, lb] });
    } else {
      const across = tl.axis === "y" ? map.toY(tl.pos) : map.toX(tl.pos);
      const [blo, bhi] = bracket(lines, tl.axis, tl.pos);
      const bay = blo && bhi ? span(...ordered(grid, tl.axis, blo.label, bhi.label)) : "edge";
      const key = `${levelKey(level)}:${span(la, lb)}:${bay}`;
      const m: MemberFact = {
        id: "", kind: "beam", role: "infill", level, ends: [la, lb], tag, grid: `${bay}/${span(la, lb)}`,
        a: alongAxis === "x" ? [pa, across] : [across, pa], b: alongAxis === "x" ? [pb, across] : [across, pb],
        rule: "plan tag between grid lines; line position measured from the tag (0.4 x text size past its descent edge)",
        planErrFt: r2(errFt), occ: o,
      };
      const seg: Seg = { id: "", kind: "beam", ...pageSeg(tl.pos), ends: [la, lb] };
      ctx.segs.push(seg);
      infill.push({ m, across, key, seg });
    }
  }
  // infill ids: ordinal across the bay (1 = nearest the bay's lower grid line); size stays out of the id
  const groups = new Map<string, typeof infill>();
  for (const x of infill) groups.set(x.key, [...(groups.get(x.key) ?? []), x]);
  for (const [key, xs] of groups) {
    xs.sort((a, b) => a.across - b.across);
    xs.forEach((x, i) => {
      const [lvl, sp, bay] = key.split(":");
      x.m.id = `beam:${lvl}:${sp}:${bay}#${i + 1}`;
      x.seg.id = x.m.id;
      facts.members.push(x.m);
    });
  }
  if (diagonal) facts.warnings.push(`${sheet.number}: ${diagonal} member tag(s) at a non-orthogonal angle skipped (plan members must run along a grid axis)`);
  // frame markers ("*SMF") beside a member tag
  for (const p of phr) {
    const fm = pf.frameMarker.exec(p.text);
    if (!fm || p.rect[2] > sheet.cutoff) continue;
    const c = center(p.rect);
    let best: { id: string; d: number } | undefined;
    for (const s of ctx.segs) {
      const d = segDist(c, s).d;
      if (d < 40 && (!best || d < best.d)) best = { id: s.id, d };
    }
    if (best) facts.frames.set(best.id, fm[1]!);
  }
}

/** Footing / pier marks at grid intersections and grade-beam marks on grid lines (foundation plans). */
export function readFoundationMarks(ctx: SheetCtx): void {
  const { sheet, phr, pf, grid, facts } = ctx;
  const lines = ctx.lines!;
  const xs = lines.filter((l) => l.axis === "x"), ys = lines.filter((l) => l.axis === "y");
  for (const p of phr) {
    if (p.rect[2] > sheet.cutoff || p.words.length !== 1) continue;
    const t = p.text;
    const c = center(p.rect);
    if (pf.footingMark.test(t) || pf.pierMark.test(t)) {
      let best: { at: string; d: number; x: number; y: number } | undefined;
      for (const lx of xs) for (const ly of ys) {
        const d = Math.hypot(lx.pos - c[0], ly.pos - c[1]);
        if (!best || d < best.d) best = { at: intersection(lx.label, ly.label), d, x: lx.pos, y: ly.pos };
      }
      if (!best || best.d > pf.markMaxDist) continue;
      const footing = pf.footingMark.test(t);
      facts.points.push({
        id: `${footing ? "footing" : "pier"}:${best.at}`, kind: footing ? "footing" : "column", role: footing ? "footing" : "pier",
        at: best.at, mark: t, occ: occ(sheet, p.rect, "plan_tag", t), rule: "plan mark nearest a grid intersection",
      });
      if (!ctx.segs.some((s) => s.kind === "column-base" && s.id === `column:${best!.at}`)) {
        ctx.segs.push({ id: `column:${best.at}`, kind: "column-base", p: [best.x, best.y], q: [best.x, best.y], ends: ["base", "base"] });
      }
    } else if (pf.gradeBeamMark.test(t)) {
      const tl = tagLine(p);
      if (!tl) continue;
      const alongAxis: "x" | "y" = tl.axis === "y" ? "x" : "y";
      const snap = nearestLine(lines, tl.axis, tl.pos);
      const [lo, hi] = bracket(lines, alongAxis, tl.along);
      if (!snap || snap.d > 3 * p.size + 20 || !lo || !hi) continue;
      const [la, lb] = ordered(grid, alongAxis, lo.label, hi.label);
      const across = grid[tl.axis].get(snap.line.label)!;
      const pa = grid[alongAxis].get(la)!, pb = grid[alongAxis].get(lb)!;
      facts.members.push({
        id: `grade-beam:${span(la, lb)}:${snap.line.label}`, kind: "beam", role: "grade_beam", level: "Foundation",
        ends: [la, lb], mark: t, grid: `${snap.line.label}/${span(la, lb)}`,
        a: alongAxis === "x" ? [pa, across] : [across, pa], b: alongAxis === "x" ? [pb, across] : [across, pb],
        rule: "grade beam mark on the nearest grid line; spans the grid lines either side of the mark", planErrFt: 0,
        occ: occ(sheet, p.rect, "plan_tag", t),
      });
    }
  }
}

/** Deck / slab note on a plan: "FLOOR DECK: 3" ... 6-1/4" TOTAL ..." -> one slab at the sheet's level. */
export function readDeckNote(ctx: SheetCtx): void {
  const { sheet, phr, facts } = ctx;
  if (!sheet.level || sheet.kind !== "framing") return;
  const i = phr.findIndex((p) => p.rot === 0 && p.rect[0] >= sheet.cutoff && /\b(?:FLOOR|ROOF|COMPOSITE)?\s*DECK\s*:/.test(p.text));
  if (i < 0) return;
  const head = phr[i]!;
  // the note continues on the lines directly below, at the same indent
  const body = [head];
  let y = head.rect[3];
  for (const p of phr) {
    if (p === head || p.rot !== 0 || Math.abs(p.rect[0] - head.rect[0]) > 2 || p.rect[1] < y - 1 || p.rect[1] > y + 0.6 * head.size) continue;
    body.push(p);
    y = p.rect[3];
  }
  const text = body.map((p) => p.text).join(" ");
  const total = /(\d+(?:-\d+\/\d+)?)\s*"\s*TOTAL/.exec(text);
  const first = /(\d+(?:-\d+\/\d+)?)\s*"/.exec(text);
  const thickness = inches((total ?? first)?.[1] ?? "");
  facts.slabs.push({
    level: sheet.level, text, ...(thickness ? { thicknessIn: thickness } : {}),
    occ: occ(sheet, union(body.map((p) => p.rect)), "note", text),
  });
}

// =============================================================================== elevations

interface LevelMark {
  level: string;
  y: number;
  ft: number;
  rect: Rect;
}

/** "LEVEL 2" with "EL. 14'-0"" directly below it: level markers on elevations and sections. */
export function levelMarkers(phr: Phrase[]): LevelMark[] {
  const out: LevelMark[] = [];
  for (const n of phr) {
    if (n.rot !== 0) continue;
    const name = levelName(n.text);
    if (!name) continue;
    const el = phr.find((p) => p.rot === 0 && /^EL\.?\s/.test(p.text) && Math.abs(p.rect[0] - n.rect[0]) < 4 &&
      p.rect[1] > n.rect[3] - 1 && p.rect[1] - n.rect[3] < 3 * n.size);
    const ft = el ? feetInches(el.text)[0] : undefined;
    if (el && ft !== undefined) out.push({ level: name, y: (n.rect[3] + el.rect[1]) / 2, ft, rect: union([n.rect, el.rect]) });
  }
  return out;
}

/**
 * Frame elevations: a row of single grid bubbles (labels of one grid axis) with a drawing title
 * "... LINE <label>" under it is one elevation of that grid line. Level markers give the vertical
 * axis, the bubbles the horizontal one. Rotated tags beside a bubble are column storeys; flat tags
 * just above a level line are beams of that line; other flat tags inside a bay are braces.
 */
export function readElevations(ctx: SheetCtx): void {
  const { sheet, phr, pf, grid, facts } = ctx;
  const bubbles = bubbleLabels(phr, sheet.cutoff, pf);
  const rows: Phrase[][] = [];
  for (const b of [...bubbles].sort((p, q) => center(p.rect)[1] - center(q.rect)[1])) {
    const row = rows.find((r) => Math.abs(center(r[0]!.rect)[1] - center(b.rect)[1]) < 3);
    if (row) row.push(b);
    else rows.push([b]);
  }
  const marks = levelMarkers(phr);
  const views: Array<{ axis: "x" | "y"; line: string; bubbles: Phrase[]; y: number; top: number }> = [];
  let prevY = -Infinity;
  for (const r of rows.sort((a, b) => center(a[0]!.rect)[1] - center(b[0]!.rect)[1])) {
    const y = center(r[0]!.rect)[1];
    const axis = r.every((b) => grid.x.has(b.text)) ? "x" : r.every((b) => grid.y.has(b.text)) ? "y" : undefined;
    const x0 = Math.min(...r.map((b) => b.rect[0])), x1 = Math.max(...r.map((b) => b.rect[2]));
    const title = phr.find((p) => p.rot === 0 && p.rect[1] > y && p.rect[1] < y + 160 && p.rect[2] > x0 - 200 && p.rect[0] < x1 &&
      /\bLINE\s+([A-Z0-9.]+)\b/.test(p.text));
    const line = title ? /\bLINE\s+([A-Z0-9.]+)\b/.exec(title.text)![1]! : undefined;
    if (r.length >= 2 && axis && line && grid[axis === "x" ? "y" : "x"].has(line)) {
      views.push({ axis, line, bubbles: r.sort((a, b) => a.rect[0] - b.rect[0]), y, top: prevY });
    } else if (r.length >= 2 && axis) {
      facts.warnings.push(`${sheet.number}: elevation bubble row at y=${Math.round(y)} has no "LINE <grid>" title; skipped`);
    }
    if (r.length >= 2) prevY = y;
  }
  for (const v of views) {
    const lv = marks.filter((m) => m.y < v.y && m.y > v.top).sort((a, b) => b.y - a.y); // bottom first
    if (lv.length < 2) {
      facts.warnings.push(`${sheet.number}: elevation of line ${v.line} has fewer than two level markers; skipped`);
      continue;
    }
    const bx = v.bubbles.map((b) => ({ label: b.text, x: center(b.rect)[0], ft: grid[v.axis].get(b.text)! }));
    const xMin = bx[0]!.x - 80, xMax = bx[bx.length - 1]!.x + 80;
    const inter = (label: string) => (v.axis === "x" ? intersection(label, v.line) : intersection(v.line, label));
    const lineFt = grid[v.axis === "x" ? "y" : "x"].get(v.line)!;
    const plan = (u: number): [number, number] => (v.axis === "x" ? [u, lineFt] : [lineFt, u]);
    // column segments for callout attribution (base end)
    for (const b of bx) ctx.segs.push({ id: `column:${inter(b.label)}`, kind: "column-base", p: [b.x, lv[0]!.y], q: [b.x, lv[lv.length - 1]!.y], ends: ["base", "top"] });
    for (const p of phr) {
      const [cx, cy] = center(p.rect);
      if (cy >= v.y || cy <= v.top || cx < xMin || cx > xMax) continue;
      const tag = memberTag(p.text, pf.sfrsPrefix);
      if (!tag) continue;
      const o = occ(sheet, p.rect, "elevation_tag", p.text);
      const storey = lv.findIndex((m, i) => i + 1 < lv.length && m.y > cy && lv[i + 1]!.y < cy);
      if (p.rot === 90 || p.rot === 270) {
        const near = bx.reduce((a, b) => (Math.abs(b.x - cx) < Math.abs(a.x - cx) ? b : a));
        if (Math.abs(near.x - cx) > 2.5 * p.size + 10 || storey < 0) continue;
        facts.tiers.push({ at: inter(near.label), lo: lv[storey]!.level, hi: lv[storey + 1]!.level, tag, occ: o, rule: "elevation tag beside a grid bubble, between two level markers" });
        continue;
      }
      if (p.rot !== 0) continue;
      const lo = [...bx].reverse().find((b) => b.x <= cx), hi = bx.find((b) => b.x > cx);
      if (!lo || !hi) continue;
      const [la, lb] = ordered(grid, v.axis, lo.label, hi.label);
      const onLevel = lv.find((m) => m.y - p.rect[3] > -2 && m.y - p.rect[3] < 2.5 * p.size);
      if (onLevel) {
        const id = `beam:${levelKey(onLevel.level)}:${span(la, lb)}:${v.line}`;
        facts.members.push({
          id, kind: "beam", role: "frame_beam", level: onLevel.level, ends: [la, lb], tag, grid: `${v.line}/${span(la, lb)}`,
          a: plan(grid[v.axis].get(la)!), b: plan(grid[v.axis].get(lb)!),
          rule: "elevation tag just above a level line; spans the bubbles either side of the tag", planErrFt: 0, occ: o,
        });
        ctx.segs.push({ id, kind: "beam", p: [lo.x, onLevel.y], q: [hi.x, onLevel.y], ends: [lo.label, hi.label] });
      } else if (storey >= 0) {
        const mid = (lo.x + hi.x) / 2;
        const side = cx < mid ? lo : hi;
        const bot = lv[storey]!, top = lv[storey + 1]!;
        const id = `brace:${levelKey(bot.level)}:${v.line}:${span(la, lb)}:${side.label}`;
        facts.members.push({
          id, kind: "brace", role: "brace", level: bot.level, topLevel: top.level, ends: [side.label, "mid"], tag,
          grid: `${v.line}/${span(la, lb)}`, a: plan(side.ft), b: plan((lo.ft + hi.ft) / 2),
          rule: "elevation tag inside a bay between level markers: brace in the half bay holding the tag; " +
            "drawn from the outer grid line at the lower level to mid-bay at the upper level (chevron assumed: the " +
            "brace lines are vector graphics the text layer does not carry; the bbox holds for V or chevron)",
          planErrFt: 0, occ: o,
        });
        ctx.segs.push({ id, kind: "brace", p: [side.x, bot.y], q: [mid, top.y], ends: ["bottom", "top"] });
      }
    }
  }
}

// =============================================================================== schedules

/**
 * Column schedule: a header row "COLUMN LINE" whose cells are grid intersections ("1/A"), row
 * labels below it - storeys ("L1 - L2"), "BASE PLATE", "PIER", "FOOTING" - and one cell per column.
 */
export function readColumnSchedule(ctx: SheetCtx): void {
  const { sheet, phr, pf, grid, facts } = ctx;
  for (const h of phr) {
    if (h.rot !== 0 || !/^COLUMN\s+(?:LINE|GRID|MARK|LOCATION)S?$/.test(h.text)) continue;
    const hc = center(h.rect);
    const cols = phr
      .filter((p) => p.rot === 0 && Math.abs(center(p.rect)[1] - hc[1]) < 6 && p.rect[0] > h.rect[2])
      .map((p) => ({ p, at: canonicalIntersection(p.text, grid) }))
      .filter((c): c is { p: Phrase; at: string } => c.at !== undefined)
      .sort((a, b) => a.p.rect[0] - b.p.rect[0]);
    if (cols.length < 1) continue;
    const pitch = cols.length > 1 ? (center(cols[cols.length - 1]!.p.rect)[0] - center(cols[0]!.p.rect)[0]) / (cols.length - 1) : 60;
    const labels = phr.filter((p) => p.rot === 0 && Math.abs(p.rect[0] - h.rect[0]) < 6 && p.rect[1] > h.rect[3]);
    for (const lab of labels) {
      const ly = center(lab.rect)[1];
      const tier = /^(.+?)\s+-\s+(.+?)$/.exec(lab.text);
      const lo = tier ? levelName(tier[1]!) : undefined, hi = tier ? levelName(tier[2]!) : undefined;
      const what = lo && hi ? "tier" : /^BASE\s*PLATE/.test(lab.text) ? "base" : /^PIER/.test(lab.text) ? "pier" : /^FOOTING/.test(lab.text) ? "footing" : undefined;
      if (!what) continue;
      for (const c of cols) {
        const cx = center(c.p.rect)[0];
        const cell = phr.find((p) => p.rot === 0 && Math.abs(center(p.rect)[1] - ly) < 8 && Math.abs(center(p.rect)[0] - cx) < pitch / 2);
        if (!cell) continue;
        const o = occ(sheet, cell.rect, "schedule_row", cell.text);
        if (what === "tier") {
          const tag = memberTag(cell.text, pf.sfrsPrefix);
          if (tag) facts.tiers.push({ at: c.at, lo: lo!, hi: hi!, tag, occ: o, rule: "column schedule cell" });
        } else if (what === "base") {
          const type = pf.detailTypeMark.exec(cell.text)?.[1] ?? cell.text;
          facts.connections.push({
            id: `connection:base:${c.at}`, member: `column:${c.at}`, end: "base", type, occ: o, rule: "column schedule base plate row",
          });
        } else if (what === "pier" && pf.pierMark.test(cell.text)) {
          facts.points.push({ id: `pier:${c.at}`, kind: "column", role: "pier", at: c.at, mark: cell.text, occ: o, rule: "column schedule pier row" });
        } else if (what === "footing" && pf.footingMark.test(cell.text)) {
          facts.points.push({ id: `footing:${c.at}`, kind: "footing", role: "footing", at: c.at, mark: cell.text, occ: o, rule: "column schedule footing row" });
        }
      }
    }
  }
}

/**
 * Mark-keyed schedules (footing, pier, grade beam, base plate ...): a mark in the first column
 * under a "MARK" / "TYPE" header, the row = the phrases on its line to the right (450 pt).
 */
export function readMarkSchedules(ctx: SheetCtx): void {
  const { sheet, phr, pf, facts } = ctx;
  const isMark = (t: string) => pf.footingMark.test(t) || pf.pierMark.test(t) || pf.gradeBeamMark.test(t) || /^[A-Z]{1,3}-\d{1,2}[A-Z]?$/.test(t);
  const heads = phr.filter((p) => p.rot === 0 && /^(MARK|TYPE)$/.test(p.text));
  const tbx = pf.titleBlockXFrac * sheet.width;
  for (const p of phr) {
    if (p.rot !== 0 || p.words.length !== 1 || !isMark(p.text)) continue;
    const head = heads.find((h) => Math.abs(h.rect[0] - p.rect[0]) < 5 && h.rect[1] < p.rect[1] && p.rect[1] - h.rect[1] < 400);
    if (!head) continue;
    const cy = center(p.rect)[1];
    // the row stops at the title block (a schedule in the notes column sits right next to it)
    const xEnd = Math.min(p.rect[0] + 450, p.rect[0] < tbx ? tbx : Infinity);
    const row = phr.filter((q) => q.rot === 0 && Math.abs(center(q.rect)[1] - cy) < 4 && q.rect[0] >= p.rect[0] && q.rect[2] <= xEnd)
      .sort((a, b) => a.rect[0] - b.rect[0]);
    if (row.length < 2) continue;
    const text = row.map((q) => q.text).join(" ");
    // schedule title: the nearest phrase ending in SCHEDULE above the header
    const title = phr.filter((q) => q.rot === 0 && /SCHEDULE$/.test(q.text) && q.rect[1] < head.rect[1] && head.rect[1] - q.rect[1] < 60 &&
      Math.abs(q.rect[0] - head.rect[0]) < 60)[0]?.text ?? "SCHEDULE";
    facts.rows.push({ mark: p.text, schedule: title, text, occ: occ(sheet, union(row.map((q) => q.rect)), "schedule_row", text) });
  }
}

// =============================================================================== details + callouts

/** Number word with a sheet-number word centred under it: a detail bubble (own sheet) or a callout (other sheet). */
function stacks(phr: Phrase[], pf: DrawingProfile): Array<{ num: string; sheet: string; rect: Rect; numRect: Rect }> {
  const out: Array<{ num: string; sheet: string; rect: Rect; numRect: Rect }> = [];
  const shs = phr.filter((p) => p.rot === 0 && p.words.length === 1 && pf.sheetNumber.test(p.text));
  for (const n of phr) {
    if (n.rot !== 0 || n.words.length !== 1 || !pf.calloutNumber.test(n.text)) continue;
    const nc = center(n.rect);
    const s = shs.find((q) => Math.abs(center(q.rect)[0] - nc[0]) < 4 && q.rect[1] >= n.rect[3] - 1 && q.rect[1] - n.rect[3] < 1.5 * n.size && q.size < n.size);
    if (s) out.push({ num: n.text, sheet: s.text, rect: union([n.rect, s.rect]), numRect: n.rect });
  }
  return out;
}

/** Detail panels: a bubble with this sheet's own number under the detail number, title to its right. */
export function readDetailPanels(ctx: SheetCtx): void {
  const { sheet, phr, pf, facts } = ctx;
  for (const st of stacks(phr, pf)) {
    if (st.sheet !== sheet.number) continue;
    const nc = center(st.numRect);
    const title = phr
      .filter((p) => p.rot === 0 && p.rect[0] > st.numRect[2] + 4 && p.rect[0] < st.numRect[2] + 90 && Math.abs(center(p.rect)[1] - nc[1]) < 8 &&
        /[A-Z]{3,}/.test(p.text))
      .sort((a, b) => a.rect[0] - b.rect[0])[0];
    if (!title) continue;
    const ref = `${st.num}/${sheet.number}`;
    const type = pf.detailTypeMark.exec(title.text)?.[1];
    facts.details.set(ref, { ref, title: title.text, ...(type ? { type } : {}), occ: occ(sheet, union([st.rect, title.rect]), "note", title.text) });
  }
}

export interface Callout {
  ref: string;
  sheet: string;
  rect: Rect;
}

export function readCallouts(ctx: SheetCtx): Callout[] {
  return stacks(ctx.phr, ctx.pf).filter((s) => s.sheet !== ctx.sheet.number).map((s) => ({ ref: `${s.num}/${s.sheet}`, sheet: s.sheet, rect: s.rect }));
}

/** Distance from a point to a page segment, with the parameter (0 at p, 1 at q) of the foot. */
export function segDist(c: [number, number], s: Pick<Seg, "p" | "q">): { d: number; t: number } {
  const [px, py] = s.p, [qx, qy] = s.q;
  const L2 = (qx - px) ** 2 + (qy - py) ** 2;
  const t = L2 > 0 ? Math.max(0, Math.min(1, ((c[0] - px) * (qx - px) + (c[1] - py) * (qy - py)) / L2)) : 0;
  return { d: Math.hypot(c[0] - (px + t * (qx - px)), c[1] - (py + t * (qy - py))), t };
}

/** Which element kinds a detail can be attached to, from its title. */
export function detailTargets(title: string | undefined): Seg["kind"][] {
  const t = (title ?? "").toUpperCase();
  if (/BRACE|GUSSET/.test(t)) return ["brace"];
  if (/BASE\s*PLATE|BASEPLATE|COLUMN BASE|ANCHOR/.test(t)) return ["column-base"];
  if (/MOMENT|SHEAR TAB|SINGLE.PLATE|DRAG|COLLECTOR|BEAM|CLIP|SEAT|SPLICE/.test(t)) return ["beam"];
  return ["beam", "brace", "column-base"];
}

/**
 * A callout becomes a connection at the end of the nearest member of a kind its detail fits
 * (nearest member segment to the bubble, then the end nearer the bubble's foot on it). The leader
 * line is vector graphics, so it is not traced: the attribution is by proximity, recorded as such.
 */
export function attributeCallouts(ctx: SheetCtx, callouts: Callout[], sheetKinds: Map<string, string>): void {
  const { sheet, facts } = ctx;
  for (const co of callouts) {
    if (sheetKinds.get(co.sheet) === "sections") continue; // a section cut, not a detail
    const det = facts.details.get(co.ref);
    const kinds = detailTargets(det?.title);
    const c = center(co.rect);
    const ranked = ctx.segs
      .filter((s) => s.id && kinds.includes(s.kind))
      .map((s) => ({ s, ...segDist(c, s) }))
      .filter((x) => x.d <= ctx.pf.calloutMaxDist)
      .sort((p, q) => p.d - q.d || (p.s.id < q.s.id ? -1 : 1));
    // one entry per element (an elevation column has one segment, a plan member one per sheet)
    const seen = new Set<string>();
    const cands = ranked.filter((x) => (seen.has(x.s.id) ? false : (seen.add(x.s.id), true)));
    const best = cands[0];
    const runner = cands[1];
    const o = occ(sheet, co.rect, "detail_callout", co.ref);
    if (!best) {
      facts.warnings.push(`${sheet.number}: callout ${co.ref} has no ${kinds.join("/")} within ${ctx.pf.calloutMaxDist} pt; not attributed`);
      continue;
    }
    const s = best.s;
    const end = s.kind === "column-base" ? "base" : best.t <= 0.5 ? s.ends[0] : s.ends[1];
    const id = s.kind === "column-base" ? `connection:base:${s.id.slice("column:".length)}` : `connection:${s.id}@${end}`;
    facts.connections.push({
      id, member: s.id, end, detailRef: co.ref, ...(det?.type ? { type: det.type } : {}), occ: o, rule: "detail callout",
      attribution: "nearest member of a kind the detail fits, to the callout bubble (leader line not traced: text layer only)",
      distPt: Math.round(best.d),
      // another member almost as near: the attribution is a guess between the two
      ...(runner && runner.d < 1.5 * best.d ? { runnerUp: runner.s.id, runnerUpDistPt: Math.round(runner.d) } : {}),
    });
  }
}

// =============================================================================== levels

/**
 * Level elevations stated anywhere: "LEVEL 2" over "EL. 14'-0"" (elevations, sections),
 * "ROOF EL. 40'-0"" on one line (schedules), "TOP OF STEEL (T.O.S.) EL. 14'-0"" on a level's own
 * plan, and the foundation datums "TOP OF FOOTING EL." / "TOP OF PIER EL.".
 */
export function readLevelStatements(ctx: SheetCtx): void {
  const { sheet, phr, facts } = ctx;
  for (const m of levelMarkers(phr)) facts.levels.push({ level: m.level, ft: m.ft, how: "level marker", occ: occ(sheet, m.rect, "note", `${m.level} EL.`) });
  for (const p of phr) {
    if (p.rot !== 0) continue;
    const one = new RegExp(`^${LEVEL_IN_TEXT.source}\\s+EL\\.?\\s*(.+)$`).exec(p.text);
    if (one) {
      const name = levelName(one[1]!), ft = feetInches(one[2]!)[0];
      if (name && ft !== undefined) facts.levels.push({ level: name, ft, how: "level row", occ: occ(sheet, p.rect, "note", p.text) });
    }
    if (sheet.level && sheet.kind === "framing" && /T\.O\.S\.?\)?\s*EL\.?|TOP OF STEEL[^.]*EL\./.test(p.text)) {
      const ft = feetInches(p.text.slice(p.text.search(/EL\./)))[0];
      if (ft !== undefined) facts.levels.push({ level: sheet.level, ft, how: "top of steel note", occ: occ(sheet, p.rect, "note", p.text) });
    }
    for (const [re, name] of [[/TOP OF FOOTING\s+EL\.?\s*/, "top of footing"], [/TOP OF PIER\s+EL\.?\s*/, "top of pier"]] as const) {
      const i = p.text.search(re);
      if (i < 0) continue;
      const ft = feetInches(p.text.slice(i))[0];
      if (ft !== undefined) facts.datums.push({ level: name, ft, how: "foundation note", occ: occ(sheet, p.rect, "note", p.text) });
    }
  }
}

export type { MemberTag };
