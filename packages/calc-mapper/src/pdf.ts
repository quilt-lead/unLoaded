/**
 * Calc package PDF -> pages of text with word boxes, using pdf.js (pdfjs-dist 4.10.38, the
 * version the app renders with). Port of the Python reference reader (PyMuPDF `get_text("words")`
 * + the mockup's line rebuild), normalised so both produce the same page text:
 *
 * 1. pdf.js text items are cut into WORDS the way MuPDF cuts them: on whitespace, and an item
 *    that continues the previous one on the same baseline with no whitespace and no visible gap
 *    (a font change or a kerning break inside one word) is glued to the previous word.
 * 2. Words are grouped into rows by their bottom edge (|dy| < 3 pt, first row that fits, words
 *    visited in (bottom rounded to 0.1, x0) order), rows sorted top to bottom, words left to
 *    right, joined by " " within a row and "\n" between rows.
 * Every word keeps its box in PDF points (top-left origin, y down) and its [start, end) span in
 * the page text, so any match can be turned back into highlight rectangles (rectsForSpan).
 *
 * Runs in a browser (main thread or a Web Worker - configure pdf.js's GlobalWorkerOptions /
 * workerPort as the app already does) and in Node: pass the legacy build there,
 *   extractPdf(bytes, { pdfjs: await import("pdfjs-dist/legacy/build/pdf.mjs") })
 * No Node-only imports here.
 *
 * The PDF's bytes are hashed (sha256, WebCrypto) here, once: every page carries that hash
 * (`doc_sha256`), so everything segmented, matched or found on a page can name the document it
 * rests on (provenance.ts) without a caller having to remember to pass it.
 */
import { sheetRect } from "./frames.ts";
import { sha256 } from "./hash.ts";
import type { CalcPage, PdfText, Rect, WordBox } from "./types.ts";

/** The slice of the pdf.js API this module uses (the real module satisfies it). */
export interface PdfjsLike {
  getDocument(src: { data: Uint8Array; verbosity?: number; isEvalSupported?: boolean }): {
    promise: Promise<PdfjsDocument>;
  };
}
interface PdfjsDocument {
  numPages: number;
  getPage(n: number): Promise<PdfjsPage>;
  getMetadata(): Promise<{ info?: unknown }>;
  destroy(): Promise<void>;
}
interface PdfjsPage {
  getViewport(o: { scale: number }): { width: number; height: number; convertToViewportPoint(x: number, y: number): number[] };
  getTextContent(): Promise<{ items: unknown[]; styles: Record<string, { ascent?: number; descent?: number }> }>;
}
interface TextItem {
  str: string;
  transform: number[];
  width: number;
  fontName: string;
}

/** Text shorter than this (stripped) means the page has no text layer. */
export const SCANNED_MAX_CHARS = 25;
const ROW_TOL = 3; // pt, rows by bottom edge (as the reference reader)
const GLUE_GAP = 0.12; // x font size: a smaller gap between two items continues the word
const BASELINE_TOL = 0.5; // pt

/** A word before row grouping: text + box (PDF points, top-left origin). */
export interface PdfWord {
  s: string;
  x0: number;
  y0: number;
  x1: number;
  y1: number;
}

const round = (v: number, nd: number): number => {
  const f = 10 ** nd;
  return Math.round(v * f) / f;
};

function isTextItem(it: unknown): it is TextItem {
  return typeof (it as TextItem)?.str === "string" && Array.isArray((it as TextItem).transform);
}

/** Words of one page, in content order, glued across item breaks inside a word. */
function pageWords(
  items: unknown[],
  styles: Record<string, { ascent?: number; descent?: number }>,
  vp: { convertToViewportPoint(x: number, y: number): number[] },
): PdfWord[] {
  const words: PdfWord[] = [];
  let prev: { word: PdfWord; base: number; size: number; endsWithSpace: boolean } | null = null;
  for (const it of items) {
    if (!isTextItem(it) || it.str.length === 0) continue;
    const [a = 1, b = 0, , , e = 0, f = 0] = it.transform;
    const size = Math.hypot(a, b) || 1;
    const st = styles[it.fontName] ?? {};
    const ascent = typeof st.ascent === "number" && st.ascent > 0 ? st.ascent : 0.8;
    const descent = typeof st.descent === "number" && st.descent < 0 ? st.descent : -0.2;
    const [px = e, base = 0] = vp.convertToViewportPoint(e, f);
    const perChar = it.str.length ? it.width / it.str.length : 0;
    const re = /\S+/g;
    let m: RegExpExecArray | null;
    let first = true;
    while ((m = re.exec(it.str))) {
      const x0 = px + perChar * m.index;
      const x1 = px + perChar * (m.index + m[0].length);
      const w: PdfWord = { s: m[0], x0, x1, y0: base - ascent * size, y1: base - descent * size };
      const glue =
        first && m.index === 0 && prev && !prev.endsWithSpace &&
        Math.abs(prev.base - base) <= BASELINE_TOL &&
        x0 - prev.word.x1 <= GLUE_GAP * Math.max(size, prev.size) && x0 - prev.word.x1 >= -GLUE_GAP * size;
      if (glue && prev) {
        prev.word.s += w.s;
        prev.word.x1 = Math.max(prev.word.x1, w.x1);
        prev.word.y0 = Math.min(prev.word.y0, w.y0);
        prev.word.y1 = Math.max(prev.word.y1, w.y1);
      } else {
        words.push(w);
        prev = { word: w, base, size, endsWithSpace: false };
      }
      first = false;
    }
    if (prev) prev.endsWithSpace = /\s$/.test(it.str) || (first && /\s/.test(it.str));
  }
  return words;
}

/** Page text + word boxes from words (the reference reader's row rebuild). `docSha256`: sha256 of the PDF's bytes. */
export function buildPage(n: number, words: PdfWord[], width: number, height: number, docSha256: string): CalcPage {
  const rows: { y: number; items: PdfWord[] }[] = [];
  const order = [...words].sort((p, q) => round(p.y1, 1) - round(q.y1, 1) || p.x0 - q.x0);
  for (const w of order) {
    let row = rows.find((r) => Math.abs(r.y - w.y1) < ROW_TOL);
    if (!row) {
      row = { y: w.y1, items: [] };
      rows.push(row);
    }
    row.items.push(w);
  }
  rows.sort((p, q) => p.y - q.y);
  let text = "";
  const boxes: WordBox[] = [];
  for (const r of rows) {
    const items = [...r.items].sort((p, q) => p.x0 - q.x0);
    const lineStart = text.length;
    items.forEach((w, k) => {
      if (k) text += " ";
      boxes.push([round(w.x0, 2), round(w.y0, 2), round(w.x1, 2), round(w.y1, 2), text.length, text.length + w.s.length]);
      text += w.s;
    });
    if (text.length > lineStart) text += "\n";
  }
  text = text.replace(/\n+$/, "");
  return { n, text, words: boxes, width, height, scanned: text.trim().length < SCANNED_MAX_CHARS, doc_sha256: docSha256 };
}

let defaultPdfjs: Promise<PdfjsLike> | null = null;

/** Extract every page. `pdfjs` defaults to `import("pdfjs-dist")` (browser build). */
export async function extractPdf(data: Uint8Array, opts: { pdfjs?: PdfjsLike } = {}): Promise<PdfText> {
  const pdfjs = opts.pdfjs ?? (await (defaultPdfjs ??= import("pdfjs-dist") as unknown as Promise<PdfjsLike>));
  const docSha256 = await sha256(data);
  // pdf.js may transfer (detach) the buffer it is given: hand it a copy
  const doc = await pdfjs.getDocument({ data: data.slice(), verbosity: 0, isEvalSupported: false }).promise;
  try {
    const pages: CalcPage[] = [];
    for (let n = 1; n <= doc.numPages; n++) {
      const page = await doc.getPage(n);
      const vp = page.getViewport({ scale: 1 });
      const tc = await page.getTextContent();
      pages.push(buildPage(n, pageWords(tc.items, tc.styles, vp), vp.width, vp.height, docSha256));
    }
    const info = ((await doc.getMetadata().catch(() => ({ info: {} }))).info ?? {}) as { Title?: unknown };
    return {
      pages, meta: { page_count: doc.numPages, title: typeof info.Title === "string" ? info.Title : "", sha256: docSha256 },
    };
  } finally {
    await doc.destroy();
  }
}

/** Boxes of the words overlapping [start, end) of the page text, merged per line. */
export function rectsForSpan(page: Pick<CalcPage, "words">, start: number, end: number): Rect[] {
  const out: Rect[] = [];
  for (const [x0, y0, x1, y1, s, e] of page.words) {
    if (s < end && e > start) {
      const last = out[out.length - 1];
      if (last && Math.abs(last[3] - y1) < 2 && x0 - last[2] < 12) {
        last[2] = Math.max(last[2], x1);
        last[1] = Math.min(last[1], y0);
      } else {
        out.push(sheetRect(x0, y0, x1, y1));
      }
    }
  }
  return out;
}
