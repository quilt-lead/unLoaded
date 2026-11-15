/**
 * Render one page of a calc PDF to PNG in Node: pdf.js's legacy build (the same pdfjs-dist 4.10.38
 * the engine extracts text with) drawing onto @napi-rs/canvas - the canvas pdf.js itself uses in Node
 * (its NodeCanvasFactory loads @napi-rs/canvas, an optional dependency of pdfjs-dist), so there is
 * one canvas implementation in the tree, prebuilt per platform, with no system libraries to install.
 *
 * Coordinates are the engine's page frame: PDF points, origin top-left, y down - the frame of every
 * `rects` on links, calc-edge evidence and `rectsForSpan` - so they can be passed straight back as
 * `rect` (crop) or `highlight`. This is presentation only; it makes no engine call.
 */
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { createCanvas } from "@napi-rs/canvas";

type Rect = [number, number, number, number];

interface Viewport {
  width: number;
  height: number;
}
interface RenderPage {
  getViewport(o: { scale: number; offsetX?: number; offsetY?: number }): Viewport;
  render(o: { canvasContext: unknown; viewport: Viewport }): { promise: Promise<void> };
  cleanup(): void;
}
interface RenderDoc {
  numPages: number;
  getPage(n: number): Promise<RenderPage>;
  destroy(): Promise<void>;
}
interface PdfjsRender {
  getDocument(src: Record<string, unknown>): { promise: Promise<RenderDoc> };
}

const pdfjsDir = dirname(createRequire(import.meta.url).resolve("pdfjs-dist/package.json"));
/** pdf.js needs the standard 14 fonts' data to draw text a PDF does not embed (Node reads them from disk). */
const STANDARD_FONTS = join(pdfjsDir, "standard_fonts") + "/";
const CMAPS = join(pdfjsDir, "cmaps") + "/";

let pdfjs: Promise<PdfjsRender> | null = null;
const loadPdfjs = () => (pdfjs ??= import("pdfjs-dist/legacy/build/pdf.mjs") as unknown as Promise<PdfjsRender>);

export const DEFAULT_WIDTH = 1200;
export const MIN_WIDTH = 200;
export const MAX_WIDTH = 3000;
/** A crop is never rendered above this many pixels per PDF point (a tiny rect would otherwise blow up). */
export const MAX_SCALE = 8;

export interface PageImage {
  png: Uint8Array;
  width: number;
  height: number;
  /** Pixels per PDF point. */
  scale: number;
  page: { n: number; width: number; height: number; count: number };
  /** The rendered area in PDF points (sheet frame): the crop, clamped to the page, or the whole page. */
  area: Rect;
}

export class PageImageError extends Error {
  name = "PageImageError";
}

function checkRect(r: readonly number[], what: string): Rect {
  if (r.length !== 4 || r.some((v) => typeof v !== "number" || !Number.isFinite(v))) {
    throw new PageImageError(`${what} must be [x0, y0, x1, y1] in PDF points`);
  }
  const [a, b, c, d] = r as Rect;
  return [Math.min(a, c), Math.min(b, d), Math.max(a, c), Math.max(b, d)];
}

/**
 * Render page `n` (1-based) of a PDF. `rect` crops to that area (PDF points, top-left origin);
 * `highlight` outlines boxes in the same frame; `width` is the image width in pixels.
 */
export async function renderPage(
  pdf: Uint8Array,
  n: number,
  opts: { rect?: readonly number[] | null; highlight?: readonly (readonly number[])[] | null; width?: number | null } = {},
): Promise<PageImage> {
  const lib = await loadPdfjs();
  const doc = await lib.getDocument({
    data: pdf.slice(), verbosity: 0, isEvalSupported: false,
    standardFontDataUrl: STANDARD_FONTS, cMapUrl: CMAPS, cMapPacked: true,
  }).promise;
  try {
    if (!Number.isInteger(n) || n < 1 || n > doc.numPages) {
      throw new PageImageError(`page ${n} is not in this PDF (pages 1-${doc.numPages})`);
    }
    const page = await doc.getPage(n);
    const base = page.getViewport({ scale: 1 });
    let area: Rect = [0, 0, base.width, base.height];
    if (opts.rect) {
      const r = checkRect(opts.rect, "rect");
      area = [Math.max(0, r[0]), Math.max(0, r[1]), Math.min(base.width, r[2]), Math.min(base.height, r[3])];
      if (area[2] - area[0] < 1 || area[3] - area[1] < 1) {
        throw new PageImageError(`rect ${JSON.stringify(r)} is outside page ${n} (${base.width.toFixed(0)} x ${base.height.toFixed(0)} pt)`);
      }
    }
    const want = Math.round(Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, opts.width ?? DEFAULT_WIDTH)));
    const scale = Math.min(MAX_SCALE, want / (area[2] - area[0]));
    const w = Math.max(1, Math.round((area[2] - area[0]) * scale));
    const h = Math.max(1, Math.round((area[3] - area[1]) * scale));
    const canvas = createCanvas(w, h);
    const ctx = canvas.getContext("2d");
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, w, h);
    // the viewport's offset moves the crop's top-left corner to the canvas origin; the rest is clipped
    const viewport = page.getViewport({ scale, offsetX: -area[0] * scale, offsetY: -area[1] * scale });
    await page.render({ canvasContext: ctx, viewport }).promise;
    for (const raw of opts.highlight ?? []) {
      const r = checkRect(raw, "each highlight");
      const x = (r[0] - area[0]) * scale, y = (r[1] - area[1]) * scale;
      const rw = (r[2] - r[0]) * scale, rh = (r[3] - r[1]) * scale;
      ctx.fillStyle = "rgba(255, 196, 0, 0.28)";
      ctx.fillRect(x, y, rw, rh);
      ctx.strokeStyle = "rgba(214, 120, 0, 0.95)";
      ctx.lineWidth = Math.max(1.5, scale * 0.75);
      ctx.strokeRect(x, y, rw, rh);
    }
    page.cleanup();
    const png = await canvas.encode("png");
    return {
      png: new Uint8Array(png.buffer, png.byteOffset, png.byteLength), width: w, height: h,
      scale: Math.round(scale * 1000) / 1000,
      page: { n, width: base.width, height: base.height, count: doc.numPages },
      area: area.map((v) => Math.round(v * 100) / 100) as Rect,
    };
  } finally {
    await doc.destroy();
  }
}
