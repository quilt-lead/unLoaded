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
import type { Calc, CalcPackage, CalcPage, ElementCategory, TitleBox } from "./types.ts";

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

/** Where a calc's title sits on its first page (the title line's word boxes, or the whole page, saying why). */
export function titleBox(page: CalcPage, title: string, scanned = false, front = false): TitleBox {
  const whole = (note: string): TitleBox => ({
    page: page.n, rects: [[0, 0, round2(page.width), round2(page.height)]], span: null, rule: TITLE_BOX_RULE, note,
  });
  if (scanned) return whole("scanned page, no text layer: located by the whole page");
  if (front) return whole("front matter / contents page: located by the whole page");
  const want = norm(title);
  let pos = 0;
  let seen = 0;
  for (const line of page.text.split("\n")) {
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

interface Building {
  title: string;
  software: string;
  cat: ElementCategory | "";
  pages: number[];
  scanned: boolean;
  front: boolean;
  text: string;
}

/** Segment pages (from extractPdf) into calcs. Returns the calcs with keys, software, category, title boxes. */
export function segment(pages: CalcPage[]): Calc[] {
  const calcs: Building[] = [];
  let cur: Building | null = null;
  const push = (title: string, scanned = false): Building => {
    const c: Building = { title, software: "", cat: "", pages: [], scanned, front: false, text: "" };
    calcs.push(c);
    return c;
  };
  for (const pg of pages) {
    const t = pg.text.trim();
    if (t.length < 25) {
      if (!cur || !cur.scanned) cur = push("Scanned page(s) - no text layer", true);
      cur.pages.push(pg.n);
      continue;
    }
    if ((t.match(TOC) ?? []).length >= 3) {
      cur = push("Front matter / contents");
      cur.front = true;
      cur.pages.push(pg.n);
      cur.text += "\n" + t;
      continue;
    }
    const title = titleOf(t);
    if (!cur || cur.scanned || cur.front || (title && norm(title) !== norm(cur.title))) {
      cur = push(title || (cur ? cur.title + " (cont.)" : "Front matter"));
    }
    cur.pages.push(pg.n);
    cur.text += "\n" + t;
  }

  const byN = new Map(pages.map((p) => [p.n, p]));
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
    const first = byN.get(c.pages[0]!)!;
    return {
      key, ord, title: c.title, software: c.software, cat: c.cat, pages: c.pages, scanned: c.scanned, front: c.front,
      title_box: titleBox(first, c.title, c.scanned, c.front), content_hash: sha1Json([c.title, c.text]),
    };
  });
}

/** Segment extracted pages into a calc package. */
export function segmentCalcs(pages: CalcPage[], sourceName: string | null = null): CalcPackage {
  return { source_name: sourceName, pages, calcs: segment(pages) };
}

/** Each calc's text (its pages joined, as the matcher reads it). */
export function calcText(pkg: Pick<CalcPackage, "pages">, calc: Pick<Calc, "pages">): string {
  const byN = new Map(pkg.pages.map((p) => [p.n, p.text]));
  return calc.pages.map((n) => byN.get(n) ?? "").join("\n");
}
