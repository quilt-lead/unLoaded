/**
 * Orchestration: PDF bytes -> pages of words (calc-mapper's extractPdfWords) -> sheets -> facts ->
 * ModelInput. `parseDrawingPages` is the pure core (no PDF library) and what the tests drive.
 */
import { extractPdfWords, type PdfjsLike } from "@unloaded/calc-mapper";
import type { ModelInput } from "@unloaded/element-graph/input";
import { assemble } from "./assemble.ts";
import { emptyFacts } from "./facts.ts";
import { buildingGrid, calibrate, planGrid, sheetMap, type BuildingGrid, type Calibration } from "./grid.ts";
import { resolveProfile, type DrawingProfile } from "./profile.ts";
import {
  attributeCallouts, readCallouts, readColumnSchedule, readDeckNote, readDetailPanels, readElevations, readFoundationMarks,
  readLevelStatements, readMarkSchedules, readPlanMembers, type Callout, type SheetCtx,
} from "./read.ts";
import { readSheet } from "./sheets.ts";
import { phrases } from "./text.ts";
import type { DrawingPage, Phrase, Sheet, SheetGridLine } from "./types.ts";

export interface DrawingParseOptions {
  /** Overrides of the generic drawing-set conventions. */
  profile?: Partial<DrawingProfile>;
  /** pdf.js module; in Node pass `await import("pdfjs-dist/legacy/build/pdf.mjs")`. Browser default: "pdfjs-dist". */
  pdfjs?: PdfjsLike;
}

export interface DrawingFile {
  name: string;
  data: Uint8Array;
}

/** Parse one or more drawing PDFs (one set: sheets may be split across files). */
export async function parseDrawingSet(files: DrawingFile[], opts: DrawingParseOptions = {}): Promise<ModelInput> {
  const pages: DrawingPage[] = [];
  for (const f of files) {
    const { pages: ps } = await extractPdfWords(f.data, opts.pdfjs ? { pdfjs: opts.pdfjs } : {});
    for (const p of ps) {
      pages.push({
        file: f.name, n: p.n, width: p.width, height: p.height,
        words: p.words.map((w) => ({ s: w.s, x0: w.x0, y0: w.y0, x1: w.x1, y1: w.y1, rot: w.rot ?? 0, size: w.size ?? w.y1 - w.y0 })),
      });
    }
  }
  return parseDrawingPages(pages, { files: files.map((f) => f.name), ...(opts.profile ? { profile: opts.profile } : {}) });
}

/** Pure core: pages of words -> ModelInput. */
export function parseDrawingPages(pages: DrawingPage[], opts: { files?: string[]; profile?: Partial<DrawingProfile> } = {}): ModelInput {
  const pf = resolveProfile(opts.profile);
  const facts = emptyFacts();
  const read: Array<{ page: DrawingPage; phr: Phrase[]; sheet: Sheet }> = [];
  for (const page of pages) {
    const phr = phrases(page.words);
    const sheet = readSheet(page, phr, pf);
    if (sheet) read.push({ page, phr, sheet });
    else facts.warnings.push(`${page.file} p${page.n}: no sheet number in the title block; page skipped`);
  }
  const dup = new Map<string, number>();
  for (const r of read) dup.set(r.sheet.number, (dup.get(r.sheet.number) ?? 0) + 1);
  for (const [n, c] of dup) if (c > 1) facts.warnings.push(`sheet ${n} appears ${c} times; occurrences keep their page`);

  // grids of the plan sheets; the reference plan (most grid lines) defines the building grid
  const planKinds = new Set(["framing", "foundation"]);
  const plans = read
    .filter((r) => planKinds.has(r.sheet.kind))
    .map((r) => {
      const lines = planGrid(r.phr, r.sheet, pf);
      return { ...r, lines, cal: calibrate(r.phr, lines, r.sheet, pf) };
    });
  const ref = [...plans]
    .filter((p) => p.lines.some((l) => l.axis === "x") && p.lines.some((l) => l.axis === "y") && Number.isFinite(p.cal.k.x))
    .sort((a, b) => b.lines.length - a.lines.length || b.cal.pairs.filter((x) => x.ft).length - a.cal.pairs.filter((x) => x.ft).length)[0];
  const grid: BuildingGrid | undefined = ref ? buildingGrid(ref.sheet, ref.lines, ref.cal) : undefined;
  const calibration = new Map<string, { source: string; ftPerPt: number; rmsResidualIn?: number }>();
  for (const p of plans) {
    calibration.set(`${p.sheet.file}|${p.sheet.page}`, {
      source: p.cal.source, ftPerPt: Number.isFinite(p.cal.k.x) ? p.cal.k.x : grid?.k.x ?? NaN,
      ...(p.cal.rmsResidualIn !== undefined ? { rmsResidualIn: p.cal.rmsResidualIn } : {}),
    });
    if (grid) {
      const missing = p.lines.filter((l) => !grid[l.axis].has(l.label)).map((l) => l.label);
      if (missing.length) facts.warnings.push(`${p.sheet.number}: grid line(s) ${missing.join(", ")} not on the reference plan ${grid.reference}; ignored`);
    }
  }
  if (!grid && plans.length) facts.warnings.push("no plan sheet has both grid directions and a scale: geometry and grid placement unavailable");

  const sheetKinds = new Map(read.map((r) => [r.sheet.number, r.sheet.kind] as const));
  const ctxs: Array<{ ctx: SheetCtx; callouts: Callout[] }> = [];
  for (const r of read) {
    const plan = plans.find((p) => p.sheet === r.sheet);
    const ctx: SheetCtx = { sheet: r.sheet, phr: r.phr, pf, grid: grid ?? { x: new Map(), y: new Map(), reference: "", k: { x: NaN, y: NaN } }, facts, segs: [] };
    readLevelStatements(ctx);
    readDetailPanels(ctx);
    readMarkSchedules(ctx);
    if (grid) {
      if (plan) {
        const lines: SheetGridLine[] = plan.lines.filter((l) => grid[l.axis].has(l.label));
        ctx.lines = lines;
        ctx.map = sheetMap(lines, grid, plan.cal as Calibration);
        if (r.sheet.kind === "framing") readPlanMembers(ctx);
        if (r.sheet.kind === "foundation") readFoundationMarks(ctx);
        readDeckNote(ctx);
      }
      if (r.sheet.kind === "elevation") readElevations(ctx);
      readColumnSchedule(ctx);
    }
    ctxs.push({ ctx, callouts: readCallouts(ctx) });
  }
  // callouts last: they need every detail panel of the set (detail sheets come after the plans)
  for (const { ctx, callouts } of ctxs) attributeCallouts(ctx, callouts, sheetKinds);

  return assemble({ facts, sheets: read.map((r) => r.sheet), ...(grid ? { grid } : {}), files: opts.files ?? [...new Set(pages.map((p) => p.file))], calibration });
}

/** Sheets of a parsed set (title-block reading only), e.g. to show what was recognised. */
export function readSheets(pages: DrawingPage[], profile?: Partial<DrawingProfile>): Sheet[] {
  const pf = resolveProfile(profile);
  return pages.map((p) => readSheet(p, phrases(p.words), pf)).filter((s): s is Sheet => s !== undefined);
}
