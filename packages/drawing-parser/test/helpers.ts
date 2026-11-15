/**
 * Builds drawing pages from text runs (no PDF): Helvetica-like metrics (advance 0.55 x size,
 * ascent 0.718, descent -0.207, as pdf.js reports for the base-14 font), boxes as calc-mapper's
 * extractPdfWords returns them. The mini set below is invented for the tests.
 */
import type { DrawingPage, DrawingWord } from "../src/index.ts";

const ADV = 0.55, ASC = 0.718, DESC = 0.207, SPACE = 0.28;

/** Words of a text run starting at (x, baseline), reading left to right (rot 0) or bottom to top (rot 90). */
export function run(text: string, x: number, base: number, size: number, rot: 0 | 90 = 0): DrawingWord[] {
  const out: DrawingWord[] = [];
  let t = 0;
  for (const s of text.split(" ")) {
    const w = s.length * ADV * size;
    if (rot === 0) out.push({ s, x0: x + t, x1: x + t + w, y0: base - ASC * size, y1: base + DESC * size, rot, size });
    else out.push({ s, x0: x - ASC * size, x1: x + DESC * size, y0: base - t - w, y1: base - t, rot, size });
    t += w + SPACE * size;
  }
  return out;
}

export const width = (text: string, size: number) => {
  const ws = text.split(" ");
  return ws.reduce((s, w) => s + w.length * ADV * size, 0) + (ws.length - 1) * SPACE * size;
};

/** A run centred on (cx, cy). */
export function centred(text: string, cx: number, cy: number, size: number, rot: 0 | 90 = 0): DrawingWord[] {
  const w = width(text, size);
  const mid = (DESC - ASC) / 2 * size; // box centre relative to the baseline
  return rot === 0 ? run(text, cx - w / 2, cy - mid, size) : run(text, cx + mid, cy + w / 2, size, 90);
}

const W = 2592, H = 1728;

export function titleBlock(number: string, title: string): DrawingWord[] {
  return [...run(number, 2364, 1652, 54), ...run(title, 2326, 1382, 17)];
}

export function page(n: number, words: DrawingWord[], file = "set.pdf"): DrawingPage {
  return { file, n, width: W, height: H, words };
}

/**
 * Plan of a 1-bay frame, 3/16" = 1'-0" (13.5 pt/ft): x-lines 1 (x=300) and 2 (x=705), y-lines
 * A (y=1200) and B (y=795), 30 ft each way. Girder on line 1 (rotated tag), girder on line A,
 * an infill beam 10 ft north of A, a callout to detail 3/S-501 near the infill beam's west end.
 */
export function framingPlan(): DrawingPage {
  const words: DrawingWord[] = [
    ...titleBlock("S-201", "LEVEL 2 FRAMING PLAN"),
    // bubbles at both ends of every grid line
    ...centred("1", 300, 200, 16), ...centred("1", 300, 1500, 16),
    ...centred("2", 705, 200, 16), ...centred("2", 705, 1500, 16),
    ...centred("A", 150, 1200, 16), ...centred("A", 1900, 1200, 16),
    ...centred("B", 150, 795, 16), ...centred("B", 1900, 795, 16),
    // dimension strings between the bubbles and the grid
    ...centred(`30'-0"`, 502.5, 250, 9), ...centred(`30'-0"`, 200, 997.5, 9, 90),
    // tags: the drawn line is 0.4 x size past the tag's descent edge
    ...run("*W24X55 (30)", 300 - 0.4 * 9 - DESC * 9, 997.5 + width("*W24X55 (30)", 9) / 2, 9, 90),
    ...run("W21X44", 502.5 - width("W21X44", 9) / 2, 1200 - 0.4 * 9 - DESC * 9, 9),
    ...run(`W16X26 (12) c=3/4"`, 502.5 - width(`W16X26 (12) c=3/4"`, 9) / 2, 1065 - 0.4 * 9 - DESC * 9, 9),
    ...centred("*SMF", 502.5, 1216, 8),
    // callout 3/S-501 just above-right of the infill beam's west end
    ...centred("3", 390, 1014, 10), ...centred("S-501", 390, 1028, 7),
    // notes column
    ...run("FRAMING PLAN NOTES", 2006, 80, 11),
    ...run(`TOP OF STEEL (T.O.S.) EL. 14'-0" U.N.O.`, 2022, 104, 8),
    ...run(`FLOOR DECK: 3" COMPOSITE DECK, 6-1/4" TOTAL.`, 2022, 130, 8),
  ];
  return page(1, words);
}

/** Column schedule: one column 1/A, W10X33 in both storeys; level elevations in the row labels. */
export function schedule(): DrawingPage {
  const row = (label: string, base: number) => run(label, 70, base, 8.5);
  return page(2, [
    ...titleBlock("S-401", "COLUMN SCHEDULE"),
    ...row("COLUMN LINE", 129), ...centred("1/A", 304, 126, 9),
    ...row(`ROOF EL. 28'-0"`, 159),
    ...row("L2 - ROOF", 189), ...centred("W10X33", 304, 186, 8.5),
    ...row(`LEVEL 2 EL. 14'-0"`, 219),
    ...row("L1 - L2", 249), ...centred("W10X33", 304, 246, 8.5),
    ...row(`LEVEL 1 EL. 0'-0"`, 279),
    ...row("BASE PLATE", 309), ...centred("BP-1", 304, 306, 8.5),
  ]);
}

/** Typical details: detail 3 = single-plate shear tab ST-3. */
export function details(): DrawingPage {
  return page(3, [
    ...titleBlock("S-501", "TYPICAL STEEL CONNECTION DETAILS"),
    ...centred("3", 117, 545, 11), ...centred("S-501", 117, 560, 6.5),
    ...run("SINGLE-PLATE SHEAR TAB ST-3", 143, 551, 12),
    ...centred("4", 700, 545, 11), ...centred("S-501", 700, 560, 6.5),
    ...run("COLUMN BASE PLATE BP-1", 726, 551, 12),
  ]);
}
