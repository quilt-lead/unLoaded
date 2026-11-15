/**
 * Split a calc package into calcs. Port of the reference segment() (itself a port of the
 * mockup's segment() / titleOf()); rules unchanged:
 *
 * - a page with < 25 characters of text has no text layer (scanned / handwritten):
 *   consecutive such pages form one "scanned" calc that is never mapped
 * - a page with >= 3 dot-leader entries ("Title ...... 12") is front matter / contents
 *   and is never mapped
 * - a page whose first lines carry a calc-like title starts a new calc unless the
 *   title (ignoring "(cont.)" and punctuation) equals the current calc's title
 * - software and element type come from keyword tables
 *
 * Two deliberate changes from the mockup: software named in the title wins over software the
 * body cites, and the element type falls back to the line directly UNDER the title line (the
 * mockup took the page's second line, which is the title itself once a page has a running header).
 */
import { rectsForSpan } from "./pdf.ts";
import { sha1Json } from "./hash.ts";
import type { Calc, CalcPackage, CalcPage, CalcRegion, CalcSpan, ElementCategory, Rect, TitleBox } from "./types.ts";

const SOFTWARE: [RegExp, string][] = [
  [/RAM\s*CONCEPT/i, "RAM Concept"], [/RAM\s*(STRUCTURAL|STEEL|FRAME|ELEMENTS)/i, "RAM Structural System"],
  [/\bETABS\b/i, "ETABS"], [/\bSAFE\b/, "SAFE"], [/SAP\s?2000/i, "SAP2000"], [/MATHCAD/i, "MathCAD"],
  [/TEKLA\s+STRUCTURAL\s+DESIGNER/i, "Tekla Structural Designer"], [/RISA/i, "RISA"], [/IDEA\s*STATICA/i, "IDEA StatiCa"],
  [/PROFIS/i, "Hilti PROFIS"], [/\bVBA\b|\.XLSM/i, "VBA / Excel"], [/\bEXCEL\b|\.XLSX/i, "Excel"], [/HAND\s*CALC/i, "Hand calc"],
  [/PROKON/i, "Prokon"], [/SPACEGASS|SPACE\s*GASS/i, "SpaceGass"], [/ROBOT/i, "Robot"], [/SCIA/i, "SCIA"], [/MIDAS/i, "MIDAS"],
  [/STAAD/i, "STAAD"], [/ENERCALC/i, "Enercalc"],
];

/** Element category keywords, in priority order (first match wins). */
export const CAT_WORDS: [Exclude<ElementCategory, "Other">, RegExp][] = [
  ["Connection", /\b(connection|shear tab|fin plate|end plate|base plate|bolt group|cleat|moment conn)/i],
  ["Footing", /\b(footing|foundation|pad|raft|pile cap)/i],
  ["Pile", /\bpiles?\b/i],
  ["Brace", /\b(brac(e|ing)|x-brace)/i],
  ["Column", /\bcolumns?\b/i],
  ["Slab", /\b(slab|deck|pt slab|post-tension)/i],
  ["Wall", /\b(wall|core)\b/i],
  ["Beam", /\b(beams?|girders?|joists?|lintels?|transfer)\b/i],
];
const TITLE_KW = /(design|calc|calculation|check|analysis|criteria|framing|report|schedule|connection|footing|bracing)/i;
const TOC = /\.{4,}\s*\d+/g;
export const TITLE_BOX_RULE = "segment.title_box";

export function catOfText(s: string): ElementCategory | "" {
  return CAT_WORDS.find(([, rx]) => rx.test(s))?.[0] ?? "";
}

export function titleOf(text: string): string | null {
  const lines = text.split("\n").map((s) => s.trim()).filter(Boolean).slice(0, 6);
  for (const line of lines) {
    if (line.length > 4 && line.length < 90 && TITLE_KW.test(line) && !/\.{4,}/.test(line)) {
      return line.replace(/\s*\((cont\.?|continued)\)\s*$/i, "").trim();
    }
  }
  return null;
}

const norm = (s: string | null | undefined): string => (s ?? "").toUpperCase().replace(/[^A-Z0-9]/g, "");

function slug(s: string): string {
  const base = s.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/-+/g, "-").replace(/^-+|-+$/g, "");
  return base.slice(0, 60) || "calc";
}

/**
 * Where a calc's title sits on its first page (the title line's word boxes, or the whole page, saying
 * why). `from` = where the calc starts in the page text (0 = top of page; > 0 for a calc that starts mid-page).
 */
export function titleBox(page: CalcPage, title: string, scanned = false, front = false, from = 0): TitleBox {
  const whole = (note: string): TitleBox => ({
    page: page.n, rects: [[0, 0, round2(page.width), round2(page.height)]], span: null, rule: TITLE_BOX_RULE, note,
  });
  if (scanned) return whole("scanned page, no text layer: located by the whole page");
  if (front) return whole("front matter / contents page: located by the whole page");
  const want = norm(title);
  let pos = from;
  let seen = 0;
  for (const line of page.text.slice(from).split("\n")) {
    const start = pos;
    pos += line.length + 1;
    if (!line.trim()) continue;
    seen += 1;
    if (seen > 6) break;
    const t = titleOf(line);
    if (want && t && norm(t) === want) {
      const lead = line.length - line.replace(/^\s+/, "").length;
      const span: [number, number] = [start + lead, start + line.replace(/\s+$/, "").length];
      const rects = rectsForSpan(page, span[0], span[1]);
      if (rects.length) return { page: page.n, rects, span, rule: TITLE_BOX_RULE, note: "title line words" };
    }
  }
  return whole("title line not found on the first page (continuation or derived title): whole page");
}

const round2 = (v: number): number => Math.round(v * 100) / 100;

interface Part {
  page: CalcPage;
  start: number;
  end: number;
  text: string;
}

interface Building {
  title: string;
  software: string;
  cat: ElementCategory | "";
  parts: Part[];
  scanned: boolean;
  front: boolean;
  text: string;
}

/** Height of the tallest word on [start, end) of the page (a proxy for the line's font size). */
function lineHeight(page: CalcPage, start: number, end: number): number {
  let h = 0;
  for (const [, y0, , y1, s] of page.words) if (s >= start && s < end) h = Math.max(h, y1 - y0);
  return h;
}

/** A heading line this much taller than the page's typical line starts a new calc mid-page. */
export const HEADING_RATIO = 1.2;
/** ... and, when the page has a leading title, at least this fraction of that title's height. */
export const TITLE_HEIGHT_RATIO = 0.9;

/**
 * Cut a page into parts at mid-page calc titles: a line below the page's leading title that reads as
 * a calc title (titleOf) AND is set as a heading - taller than HEADING_RATIO x the page's median line
 * and, when the page has a leading title, set about as large as it (TITLE_HEIGHT_RATIO). A body line
 * that merely contains a title keyword ("design", "bracing") is not a heading. A page with no such
 * line is one part (the whole page).
 */
export function pageParts(page: CalcPage): Part[] {
  const lines: { start: number; end: number; text: string; h: number }[] = [];
  let pos = 0;
  for (const line of page.text.split("\n")) {
    if (line.trim()) lines.push({ start: pos, end: pos + line.length, text: line, h: lineHeight(page, pos, pos + line.length) });
    pos += line.length + 1;
  }
  const hs = lines.map((l) => l.h).filter((h) => h > 0).sort((p, q) => p - q);
  const median = hs.length ? hs[Math.floor((hs.length - 1) / 2)]! : 0;
  const lead = titleOf(page.text);
  const leadIdx = lead ? lines.slice(0, 6).findIndex((l) => norm(titleOf(l.text)) === norm(lead)) : -1;
  const leadH = leadIdx >= 0 ? lines[leadIdx]!.h : 0;
  const cuts: number[] = [];
  lines.forEach((l, i) => {
    if (i === 0 || i <= leadIdx || !median) return;
    if (l.h >= HEADING_RATIO * median && l.h >= TITLE_HEIGHT_RATIO * leadH && titleOf(l.text)) cuts.push(l.start);
  });
  const bounds = [0, ...cuts, page.text.length];
  const parts: Part[] = [];
  for (let i = 0; i + 1 < bounds.length; i++) {
    const start = bounds[i]!, end = bounds[i + 1]!;
    parts.push({ page, start, end, text: page.text.slice(start, end) });
  }
  return parts;
}

const round1 = (v: number): number => Math.round(v * 10) / 10;

function regionOf(p: Part): CalcRegion {
  const { page, start, end } = p;
  const full = start === 0 && end >= page.text.length;
  let y0 = Infinity, y1 = -Infinity;
  for (const [, wy0, , wy1, s] of page.words) {
    if (s >= start && s < end) {
      y0 = Math.min(y0, wy0);
      y1 = Math.max(y1, wy1);
    }
  }
  const top = start === 0 || !Number.isFinite(y0) ? 0 : Math.max(0, round1(y0 - 4));
  const bottom = end >= page.text.length || !Number.isFinite(y1) ? round2(page.height) : Math.min(round2(page.height), round1(y1 + 4));
  return { page: page.n, rect: [0, full ? 0 : top, round2(page.width), full ? round2(page.height) : bottom], start, end };
}

/** Regions in reading order -> spans: a region continues the span when it picks up exactly where the last one stopped. */
function spansOf(parts: Part[]): CalcSpan[] {
  const spans: CalcSpan[] = [];
  let prev: Part | null = null;
  for (const p of parts) {
    const continues = prev !== null && (
      (p.page.n === prev.page.n && p.start === prev.end) ||
      (p.page.n === prev.page.n + 1 && prev.end >= prev.page.text.length && p.start === 0));
    if (!continues) spans.push({ regions: [] });
    spans[spans.length - 1]!.regions.push(regionOf(p));
    prev = p;
  }
  return spans;
}

/**
 * Segment pages (from extractPdf) into calcs: keys, software, category, title boxes, and the calc's
 * spans of page regions. Rules of the reference segmenter, applied to page PARTS (a page cut at
 * mid-page calc titles; a page without one is one part), plus: a part titled like an EARLIER calc
 * (not the current one) continues that calc after a gap, as a new span.
 */
export function segment(pages: CalcPage[]): Calc[] {
  const calcs: Building[] = [];
  let cur: Building | null = null;
  const push = (title: string, scanned = false): Building => {
    const c: Building = { title, software: "", cat: "", parts: [], scanned, front: false, text: "" };
    calcs.push(c);
    return c;
  };
  for (const pg of pages) {
    const whole = pg.text.trim();
    if (whole.length < 25) {
      if (!cur || !cur.scanned) cur = push("Scanned page(s) - no text layer", true);
      cur.parts.push({ page: pg, start: 0, end: pg.text.length, text: pg.text });
      continue;
    }
    if ((whole.match(TOC) ?? []).length >= 3) {
      cur = push("Front matter / contents");
      cur.front = true;
      cur.parts.push({ page: pg, start: 0, end: pg.text.length, text: pg.text });
      cur.text += "\n" + whole;
      continue;
    }
    for (const part of pageParts(pg)) {
      const t = part.text.trim();
      const title = titleOf(t);
      if (cur && !cur.scanned && !cur.front && title && norm(title) !== norm(cur.title)) {
        // titled like an earlier calc: that calc continues here (a gap -> a new span)
        const earlier = calcs.find((c) => !c.scanned && !c.front && norm(c.title) === norm(title));
        if (earlier) cur = earlier;
      }
      if (!cur || cur.scanned || cur.front || (title && norm(title) !== norm(cur.title))) {
        cur = push(title || (cur ? cur.title + " (cont.)" : "Front matter"));
      }
      cur.parts.push(part);
      cur.text += "\n" + t;
    }
  }

  const seen = new Map<string, number>();
  let nScanned = 0;
  return calcs.map((c, ord) => {
    let base: string;
    if (c.scanned) {
      nScanned += 1;
      base = `scanned-${nScanned}`;
    } else {
      base = slug(c.title);
    }
    const k = (seen.get(base) ?? 0) + 1;
    seen.set(base, k);
    const key = k === 1 ? base : `${base}-${k}`;
    if (!c.front) {
      // software named in the title wins over software the body merely cites
      const sw = SOFTWARE.find(([rx]) => rx.test(c.title))?.[1] || SOFTWARE.find(([rx]) => rx.test(c.text))?.[1] || "";
      c.software = sw || (c.scanned ? "Needs OCR" : "");
      const lines = c.text.split("\n").map((s) => s.trim()).filter(Boolean);
      let under = "";
      for (let i = 0; i < lines.length; i++) {
        if (norm(c.title) && norm(titleOf(lines[i]!) ?? "") === norm(c.title)) {
          under = lines[i + 1] ?? "";
          break;
        }
      }
      c.cat = catOfText(c.title) || catOfText(under);
    }
    const first = c.parts[0]!;
    return {
      key, ord, title: c.title, software: c.software, cat: c.cat, pages: [...new Set(c.parts.map((p) => p.page.n))],
      scanned: c.scanned, front: c.front, title_box: titleBox(first.page, c.title, c.scanned, c.front, first.start),
      content_hash: sha1Json([c.title, c.text]), spans: spansOf(c.parts),
    };
  });
}

/** The page regions of a calc in reading order (whole pages for a calc stored without spans). */
export function calcRegions(calc: Pick<Calc, "pages"> & { spans?: CalcSpan[] }, pages: CalcPage[]): CalcRegion[] {
  if (calc.spans?.length) return calc.spans.flatMap((s) => s.regions);
  const byN = new Map(pages.map((p) => [p.n, p]));
  return calc.pages.flatMap((n) => {
    const p = byN.get(n);
    return p ? [{ page: n, rect: [0, 0, p.width, p.height] as Rect, start: 0, end: p.text.length }] : [];
  });
}

/** Segment extracted pages into a calc package. */
export function segmentCalcs(pages: CalcPage[], sourceName: string | null = null): CalcPackage {
  return { source_name: sourceName, pages, calcs: segment(pages) };
}

/** Each calc's text (its regions joined, as the matcher reads it). */
export function calcText(pkg: Pick<CalcPackage, "pages">, calc: Pick<Calc, "pages"> & { spans?: CalcSpan[] }): string {
  const byN = new Map(pkg.pages.map((p) => [p.n, p.text]));
  return calcRegions(calc, pkg.pages).map((r) => (byN.get(r.page) ?? "").slice(r.start, r.end)).join("\n");
}
