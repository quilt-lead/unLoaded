/**
 * Calc package PDF -> pages of text with word boxes (pdf.js). Port of pdf_ingest.py.
 *
 * pdf.js returns text runs, not words. Runs are split on whitespace into words
 * (x positions interpolated by character), runs that touch with no gap are
 * joined back into one word (what MuPDF does), then the page text is rebuilt line
 * by line from words grouped by baseline. Every word keeps its character span in
 * the page text and its box in PDF points (top-left origin), so any match the
 * mapper makes can be turned back into highlight rectangles on the page.
 */
import type { CalcPackage, CalcPage, Rect, WordBox } from './types.ts';

/** The parts of the pdf.js module this reader uses (pass `pdfjs-dist` or its legacy build). */
export interface PdfjsLike {
  getDocument(src: { data: Uint8Array; [k: string]: unknown }): { promise: Promise<PdfDocLike> };
  Util: { transform(m1: number[], m2: number[]): number[] };
  OPS: Record<string, number>;
}
interface PdfDocLike {
  numPages: number;
  getPage(n: number): Promise<PdfPageLike>;
  getMetadata(): Promise<{ info?: unknown }>;
  destroy(): Promise<void>;
}
interface PdfPageLike {
  rotate: number;
  getViewport(o: { scale: number; rotation?: number }): { width: number; height: number; transform: number[] };
  getTextContent(): Promise<{ items: unknown[]; styles?: Record<string, { fontFamily?: string }> }>;
  getOperatorList(): Promise<{ fnArray: number[]; argsArray: unknown[][] }>;
  cleanup(): void;
}
interface TextItemLike {
  str: string;
  transform: number[];
  width: number;
  height: number;
}

export interface ReadPdfOptions {
  /** Count images per page (walks each page's operator list; slower on scanned packages). Default true. */
  countImages?: boolean;
  /** Called after each page. */
  onPage?: (n: number, total: number) => void;
}

/** A word before row assembly. */
interface Frag {
  s: string;
  x0: number;
  y0: number;
  x1: number;
  y1: number;
  /** Font size, to judge whether two touching runs are one word. */
  size: number;
}

/**
 * Ascent / descent as a fraction of the font size. MuPDF uses each font's own
 * metrics; these are the medians measured against it on the synthetic package.
 */
const ASCENT = 0.93;
const DESCENT = 0.31;
const round2 = (v: number) => Math.round(v * 100) / 100;
const round1 = (v: number) => Math.round(v * 10) / 10;

function isTextItem(it: unknown): it is TextItemLike {
  return typeof it === 'object' && it !== null && typeof (it as TextItemLike).str === 'string' && Array.isArray((it as TextItemLike).transform);
}

/**
 * Helvetica advance widths (AFM, 1/1000 em) for ASCII 32..126. pdf.js gives a run's
 * total width but not per-glyph positions; weighting characters by a proportional
 * font's widths places word edges far closer than an even split. Monospace runs
 * are split evenly. Other characters weigh 556.
 */
const HELV = [
  278, 278, 355, 556, 556, 889, 667, 191, 333, 333, 389, 584, 278, 333, 278, 278, 556, 556, 556, 556, 556, 556, 556, 556,
  556, 556, 278, 278, 584, 584, 584, 556, 1015, 667, 667, 722, 722, 667, 611, 778, 722, 278, 500, 667, 556, 833, 722, 778,
  667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 278, 278, 278, 469, 556, 333, 556, 556, 500, 556, 556, 278, 556,
  556, 222, 222, 500, 222, 833, 556, 556, 556, 556, 333, 500, 278, 556, 500, 722, 500, 500, 500, 334, 260, 334, 584,
];
const charWeight = (ch: string, mono: boolean) => {
  if (mono) return 1;
  const c = ch.charCodeAt(0);
  return c >= 32 && c <= 126 ? HELV[c - 32]! : 556;
};

/** Text runs -> words with boxes in top-left page coordinates. */
function wordsOf(
  items: unknown[],
  styles: Record<string, { fontFamily?: string }>,
  viewportTransform: number[],
  util: PdfjsLike['Util'],
): Frag[] {
  const frags: Frag[] = [];
  for (const it of items) {
    if (!isTextItem(it) || !it.str) continue;
    const fontName = (it as { fontName?: string }).fontName;
    const mono = /mono|courier/i.test(`${fontName ? (styles[fontName]?.fontFamily ?? '') : ''} ${fontName ?? ''}`);
    const t = util.transform(viewportTransform, it.transform);
    const size = Math.hypot(t[2]!, t[3]!) || Math.abs(it.height) || 1;
    // run direction in device space (handles rotated pages / text)
    const scaleX = Math.hypot(t[0]!, t[1]!) || 1;
    const ux = t[0]! / scaleX;
    const uy = t[1]! / scaleX;
    const baseX = t[4]!;
    const baseY = t[5]!;
    // it.width is in text space scaled by the item's own matrix -> device units via the viewport scale
    const vpScale = Math.hypot(viewportTransform[0]!, viewportTransform[1]!) || 1;
    const runW = it.width * vpScale;
    // cumulative character weights -> x offset of each character boundary
    const cum = [0];
    for (const ch of it.str) {
      const w = charWeight(ch, mono);
      // surrogate pairs take two code units: keep `cum` indexed by code unit
      for (let u = 0; u < ch.length; u++) cum.push(cum[cum.length - 1]! + (u === 0 ? w : 0));
    }
    const total = cum[cum.length - 1]! || 1;
    for (const m of it.str.matchAll(/\S+/g)) {
      const a = (cum[m.index]! / total) * runW;
      const b = (cum[m.index + m[0].length]! / total) * runW;
      const xa = baseX + ux * a;
      const xb = baseX + ux * b;
      const ya = baseY + uy * a;
      const yb = baseY + uy * b;
      frags.push({
        s: m[0],
        x0: Math.min(xa, xb),
        x1: Math.max(xa, xb),
        y0: Math.min(ya, yb) - size * ASCENT,
        y1: Math.max(ya, yb) + size * DESCENT,
        size,
      });
    }
  }
  return frags;
}

/** Join runs that touch on the same baseline into one word (no whitespace between them in the PDF). */
function joinTouching(frags: Frag[]): Frag[] {
  const sorted = [...frags].sort((p, q) => round1(p.y1) - round1(q.y1) || p.x0 - q.x0);
  const out: Frag[] = [];
  for (const f of sorted) {
    const prev = out[out.length - 1];
    const gap = prev ? f.x0 - prev.x1 : Infinity;
    if (prev && Math.abs(prev.y1 - f.y1) < 1 && gap > -0.5 && gap < 0.1 * Math.min(prev.size, f.size)) {
      prev.s += f.s;
      prev.x1 = Math.max(prev.x1, f.x1);
      prev.y0 = Math.min(prev.y0, f.y0);
      prev.y1 = Math.max(prev.y1, f.y1);
    } else {
      out.push({ ...f });
    }
  }
  return out;
}

/** Words -> page text + word boxes. Same row grouping as pdf_ingest.read_pdf. */
export function assemblePage(words: ReadonlyArray<{ s: string; x0: number; y0: number; x1: number; y1: number }>): {
  text: string;
  words: WordBox[];
} {
  const rows: Array<{ y: number; items: typeof words[number][] }> = [];
  const order = [...words].sort((p, q) => round1(p.y1) - round1(q.y1) || p.x0 - q.x0);
  for (const w of order) {
    let row = rows.find((r) => Math.abs(r.y - w.y1) < 3);
    if (!row) {
      row = { y: w.y1, items: [] };
      rows.push(row);
    }
    row.items.push(w);
  }
  rows.sort((p, q) => p.y - q.y);
  const parts: string[] = [];
  const boxes: WordBox[] = [];
  let pos = 0;
  for (const r of rows) {
    const items = [...r.items].sort((p, q) => p.x0 - q.x0);
    const lineStart = pos;
    items.forEach((w, k) => {
      if (k) {
        parts.push(' ');
        pos += 1;
      }
      boxes.push([round2(w.x0), round2(w.y0), round2(w.x1), round2(w.y1), pos, pos + w.s.length]);
      parts.push(w.s);
      pos += w.s.length;
    });
    if (pos > lineStart) {
      parts.push('\n');
      pos += 1;
    }
  }
  return { text: parts.join('').replace(/\n+$/, ''), words: boxes };
}

const IMAGE_OPS = ['paintImageXObject', 'paintImageXObjectRepeat', 'paintInlineImageXObject', 'paintImageMaskXObject'];

async function imageCount(page: PdfPageLike, ops: PdfjsLike['OPS']): Promise<number> {
  const codes = new Set(IMAGE_OPS.map((k) => ops[k]).filter((v): v is number => v !== undefined));
  const list = await page.getOperatorList();
  const xobjects = new Set<unknown>();
  let inline = 0;
  list.fnArray.forEach((fn, i) => {
    if (!codes.has(fn)) return;
    const name = list.argsArray[i]?.[0];
    if (typeof name === 'string') xobjects.add(name);
    else inline += 1;
  });
  return xobjects.size + inline;
}

export async function readPdf(data: Uint8Array, pdfjs: PdfjsLike, opts: ReadPdfOptions = {}): Promise<CalcPackage> {
  // pdf.js transfers (detaches) the buffer it is given: hand it a copy.
  const doc = await pdfjs.getDocument({ data: data.slice(), isEvalSupported: false }).promise;
  try {
    const pages: CalcPage[] = [];
    for (let n = 1; n <= doc.numPages; n++) {
      const page = await doc.getPage(n);
      const vp = page.getViewport({ scale: 1 });
      const tc = await page.getTextContent();
      const { text, words } = assemblePage(joinTouching(wordsOf(tc.items, tc.styles ?? {}, vp.transform, pdfjs.Util)));
      const images = opts.countImages === false ? 0 : await imageCount(page, pdfjs.OPS);
      pages.push({ n, text, words, width: vp.width, height: vp.height, images });
      page.cleanup();
      opts.onPage?.(n, doc.numPages);
    }
    const meta = await doc.getMetadata().catch(() => ({ info: undefined }));
    const title = (meta.info as { Title?: unknown } | undefined)?.Title;
    return { pages, meta: { page_count: doc.numPages, title: typeof title === 'string' ? title : '' } };
  } finally {
    await doc.destroy();
  }
}

/** Boxes of the words overlapping [start, end) of the page text, merged per line. */
export function rectsForSpan(page: Pick<CalcPage, 'words'>, start: number, end: number): Rect[] {
  const out: Rect[] = [];
  for (const [x0, y0, x1, y1, s, e] of page.words) {
    if (s < end && e > start) {
      const last = out[out.length - 1];
      if (last && Math.abs(last[3] - y1) < 2 && x0 - last[2] < 12) {
        last[2] = Math.max(last[2], x1);
        last[1] = Math.min(last[1], y0);
      } else {
        out.push([x0, y0, x1, y1]);
      }
    }
  }
  return out;
}
