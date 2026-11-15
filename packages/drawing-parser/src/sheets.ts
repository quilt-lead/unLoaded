/**
 * Sheet header (number + title) from the title block, sheet kind and level from the title,
 * and the drawing area's right edge (plan notes column or title block).
 */
import type { DrawingProfile } from "./profile.ts";
import { LEVEL_IN_TEXT, levelName, rectOf, roundRect } from "./text.ts";
import type { DrawingPage, Phrase, Sheet, SheetKind } from "./types.ts";

/**
 * Sheet number = the tallest word in the title-block strip matching the sheet-number pattern.
 * Title = the words of at least `titleMinSize` within `titleWindow` above it, row by row.
 * Pages without a sheet number are not drawing sheets (cover letters, calcs) and are skipped.
 */
export function readSheet(page: DrawingPage, phr: Phrase[], pf: DrawingProfile): Sheet | undefined {
  const tbx = pf.titleBlockXFrac * page.width;
  const tb = page.words.filter((w) => w.x0 > tbx && w.rot === 0);
  const nos = tb.filter((w) => pf.sheetNumber.test(w.s));
  if (!nos.length) return undefined;
  const sn = nos.reduce((a, b) => (b.y1 - b.y0 > a.y1 - a.y0 ? b : a));
  const cand = tb.filter((w) => w !== sn && w.size >= pf.titleMinSize && w.y1 <= sn.y0 + 1 && w.y0 >= sn.y0 - pf.titleWindow);
  const rows = new Map<number, typeof cand>();
  for (const w of cand) {
    const k = Math.round(w.y1 / 6);
    rows.set(k, [...(rows.get(k) ?? []), w]);
  }
  const title = [...rows.entries()]
    .sort((a, b) => a[0] - b[0])
    .map(([, ws]) => ws.sort((a, b) => a.x0 - b.x0).map((w) => w.s).join(" "))
    .join(" ")
    .replace(pf.titleStrip, "")
    .trim();
  const kind = sheetKind(title, pf);
  const sheet: Sheet = {
    file: page.file, page: page.n, number: sn.s, title, kind, numberRect: roundRect(rectOf(sn)),
    cutoff: tbx, width: page.width, height: page.height,
  };
  const lv = sheetLevel(title, kind);
  if (lv) sheet.level = lv;
  sheet.cutoff = drawingCutoff(page, phr, sheet, pf);
  return sheet;
}

export function sheetKind(title: string, pf: DrawingProfile): SheetKind {
  const t = title.toUpperCase();
  for (const r of pf.sheetKinds) if (t.includes(r.contains)) return r.kind;
  return "other";
}

/** Plans only: "LEVEL 2 FRAMING PLAN" -> "Level 2", "ROOF FRAMING PLAN" -> "Roof", foundation plan -> "Foundation". */
export function sheetLevel(title: string, kind: SheetKind): string | undefined {
  if (kind === "foundation") return "Foundation";
  if (kind !== "framing") return undefined;
  const m = LEVEL_IN_TEXT.exec(title.toUpperCase());
  return m ? levelName(m[1]!) : undefined;
}

/**
 * Right edge of the drawing area: left of the plan notes column when the sheet has a heading
 * ending in "NOTES" right of `notesXFrac` of the width (the whole heading line counts, e.g.
 * "FRAMING PLAN NOTES"), else the title block.
 */
function drawingCutoff(page: DrawingPage, phr: Phrase[], sheet: Sheet, pf: DrawingProfile): number {
  const tbx = pf.titleBlockXFrac * page.width;
  const heads = phr.filter((p) => p.rot === 0 && p.rect[0] > pf.notesXFrac * page.width && p.rect[0] < tbx &&
    p.text.split(" ").at(-1) === pf.notesHeadingWord);
  if (!heads.length || (sheet.kind !== "framing" && sheet.kind !== "foundation" && sheet.kind !== "elevation")) return tbx;
  return Math.min(...heads.map((p) => p.rect[0])) - pf.notesMargin;
}
