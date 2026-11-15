/**
 * Split a calc package into calcs. Port of the reference segment() (itself a port of the
 * mockup's segment() / titleOf()); rules unchanged:
 *
 * - a page with < 25 characters of text has no text layer (scanned / handwritten):
 *   consecutive such pages form one "scanned" calc that is never mapped. "Scanned" describes
 *   exactly those pages and nothing else.
 * - a page with front-matter evidence is front matter and is never mapped: >= 3 dot-leader
 *   entries ("Title ...... 12"), or a contents / index / cover heading line among its first lines
 *   (`FRONT_HEADING`: "Contents", "Table of Contents", "Index", "Cover Sheet" ...). Having no
 *   title is NOT front-matter evidence.
 * - a page whose first lines carry a calc-like title starts a new calc unless the
 *   title (ignoring "(cont.)" and punctuation) equals the current calc's title, or an earlier
 *   calc's title (that calc continues, after a gap) - also right after a scanned run or front matter
 * - a page (part) with text but no title continues the most recent calc that has text (not a
 *   scanned run, not front matter), after a gap as a new span: a calc's untitled pages after a
 *   scanned sketch or an inserted contents page stay in that calc. With no such calc yet (a cover
 *   with no title keyword, say) it starts an untitled calc ("Untitled (from page N)", rule
 *   `segment.untitled-start`), which is mapped like any other.
 * - software and element type come from keyword tables
 * - calc keys are unique by construction (`uniqueKeys`): links, decisions and export rows are keyed
 *   by (global_id, calc key), so two calcs must never share one
 *
 * Two deliberate changes from the mockup: software named in the title wins over software the
 * body cites, and the element type falls back to the line directly UNDER the title line (the
 * mockup took the page's second line, which is the title itself once a page has a running header).
 *
 * Every calc carries provenance: the segmentation rule that made it (a scanned run, front matter, or
 * a calc title) and the sha256 of the PDF its pages come from (each page's `doc_sha256`).
 */
import { sheetRect } from "./frames.ts";
import { rectsForSpan } from "./pdf.ts";
import { sha1Json } from "./hash.ts";
import { RULES, inputList, ruleProvenance } from "./provenance.ts";
import { SEGMENTER_VERSION, type Calc, type CalcPackage, type CalcPage, type CalcRegion, type CalcSpan, type ElementCategory, type TitleBox } from "./types.ts";

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
/** A heading line that marks a contents / index / cover page (the whole line, ignoring case and trailing ":"). */
export const FRONT_HEADING = /^(?:table\s+of\s+contents|contents|index(?:\s+of\s+(?:calculations|calcs|sheets|drawings))?|cover(?:\s+(?:sheet|page))?|title\s+sheet)\s*:?$/i;

/** Front-matter evidence on a text page: dot-leader contents entries, or a contents / index / cover heading line. */
export function isFrontMatter(text: string): boolean {
  if ((text.match(TOC) ?? []).length >= 3) return true;
  const lines = text.split("\n").map((s) => s.trim()).filter(Boolean).slice(0, 6);
  return lines.some((l) => FRONT_HEADING.test(l));
}
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
    page: page.n, rects: [sheetRect(0, 0, round2(page.width), round2(page.height))], span: null, rule: TITLE_BOX_RULE, note,
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
  /** Started by an untitled text page with no calc to continue (rule segment.untitled-start). */
  untitled: boolean;
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
  return { page: page.n, rect: sheetRect(0, full ? 0 : top, round2(page.width), full ? round2(page.height) : bottom), start, end };
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
    const c: Building = { title, software: "", cat: "", parts: [], scanned, front: false, untitled: false, text: "" };
    calcs.push(c);
    return c;
  };
  /** A calc with text (not a scanned run, not front matter): the only kind a title or an untitled page continues. */
  const textCalc = (c: Building): boolean => !c.scanned && !c.front;
  /** The most recent text calc that took a part: where an untitled text page belongs. */
  let lastText: Building | null = null;
  for (const pg of pages) {
    const whole = pg.text.trim();
    if (whole.length < 25) {
      if (!cur || !cur.scanned) cur = push("Scanned page(s) - no text layer", true);
      cur.parts.push({ page: pg, start: 0, end: pg.text.length, text: pg.text });
      continue;
    }
    if (isFrontMatter(whole)) {
      cur = push("Front matter / contents");
      cur.front = true;
      cur.parts.push({ page: pg, start: 0, end: pg.text.length, text: pg.text });
      cur.text += "\n" + whole;
      continue;
    }
    for (const part of pageParts(pg)) {
      const t = part.text.trim();
      const title = titleOf(t);
      if (title) {
        if (!cur || !textCalc(cur) || norm(title) !== norm(cur.title)) {
          // titled like an earlier calc: that calc continues here (a gap -> a new span); else a new calc
          cur = calcs.find((c) => textCalc(c) && norm(c.title) === norm(title)) ?? push(title);
        }
      } else {
        // no title: the most recent calc with text continues (a gap after a scanned run or a contents
        // page -> a new span); with none yet, an untitled calc starts - having no title is not front matter
        if (!lastText) {
          lastText = push(`Untitled (from page ${pg.n})`);
          lastText.untitled = true;
        }
        cur = lastText;
      }
      lastText = cur;
      cur.parts.push(part);
      cur.text += "\n" + t;
    }
  }

  let nScanned = 0;
  const keys = uniqueKeys(calcs.map((c) => (c.scanned ? `scanned-${++nScanned}` : slug(c.title))));
  return calcs.map((c, ord) => {
    const key = keys[ord]!;
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
    const rule = c.scanned ? RULES.segment.scanned : c.front ? RULES.segment.front : c.untitled ? RULES.segment.untitled : RULES.segment.calc;
    return {
      key, ord, title: c.title, software: c.software, cat: c.cat, pages: [...new Set(c.parts.map((p) => p.page.n))],
      scanned: c.scanned, front: c.front, title_box: titleBox(first.page, c.title, c.scanned, c.front, first.start),
      content_hash: sha1Json([c.title, c.text]), spans: spansOf(c.parts),
      provenance: ruleProvenance("segment", rule, c.parts.map((p) => p.page.doc_sha256)),
    };
  });
}

/**
 * Calc keys from base slugs, unique by construction: the first calc with a base gets the base, a later
 * one the first `<base>-<n>` (n = 2, 3, ...) that no calc has taken - including a calc whose own title
 * slugs to that form ("Beam Design 2" -> beam-design-2 is never given to a second "Beam Design").
 */
export function uniqueKeys(bases: readonly string[]): string[] {
  const taken = new Set(bases.filter((b, i) => bases.indexOf(b) === i));
  const used = new Set<string>();
  return bases.map((base) => {
    let key = base;
    for (let n = 2; used.has(key) || (key !== base && taken.has(key)); n++) key = `${base}-${n}`;
    used.add(key);
    return key;
  });
}

/** The page regions of a calc in reading order (whole pages for a calc stored without spans). */
export function calcRegions(calc: Pick<Calc, "pages"> & { spans?: CalcSpan[] }, pages: CalcPage[]): CalcRegion[] {
  if (calc.spans?.length) return calc.spans.flatMap((s) => s.regions);
  const byN = new Map(pages.map((p) => [p.n, p]));
  return calc.pages.flatMap((n) => {
    const p = byN.get(n);
    return p ? [{ page: n, rect: sheetRect(0, 0, p.width, p.height), start: 0, end: p.text.length }] : [];
  });
}

/**
 * The one document a calc package's pages come from: their shared `doc_sha256`. Throws when pages
 * carry none (not from extractPdf) or come from more than one PDF.
 */
export function packageSha256(pages: Pick<CalcPage, "doc_sha256">[]): string {
  if (!pages.length || pages.some((p) => !p.doc_sha256)) {
    throw new Error("calc pages carry no document hash (doc_sha256): extract them with extractPdf");
  }
  const docs = inputList(pages.map((p) => p.doc_sha256));
  if (docs.length !== 1) throw new Error(`a calc package is one PDF, but its pages come from ${docs.length} documents`);
  return docs[0]!;
}

/** Segment extracted pages into a calc package. */
export function segmentCalcs(pages: CalcPage[], sourceName: string | null = null): CalcPackage {
  return { source_name: sourceName, source_sha256: packageSha256(pages), segmenter: SEGMENTER_VERSION, pages, calcs: segment(pages) };
}

/** Each calc's text (its regions joined, as the matcher reads it). */
export function calcText(pkg: Pick<CalcPackage, "pages">, calc: Pick<Calc, "pages"> & { spans?: CalcSpan[] }): string {
  const byN = new Map(pkg.pages.map((p) => [p.n, p.text]));
  return calcRegions(calc, pkg.pages).map((r) => (byN.get(r.page) ?? "").slice(r.start, r.end)).join("\n");
}
