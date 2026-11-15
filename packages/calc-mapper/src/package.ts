/**
 * The shape check for a calc package read back from a store or a file (a stored extraction). It checks
 * exactly the fields the engine and its readers dereference (segment.ts `calcRegions` / `calcText`,
 * matcher.ts, calcdeps.ts, project.ts, pdf.ts `rectsForSpan`), so a package that passes never makes
 * them throw a TypeError, and one that fails is re-extracted by the caller instead
 * (project-file `storedExtractionFor`). It does not judge WHICH segmenter made the package or WHICH
 * PDF it came from: the caller compares `segmenter` and the hashes.
 */
import type { CalcPackage } from "./types.ts";

const isObj = (v: unknown): v is Record<string, unknown> => !!v && typeof v === "object" && !Array.isArray(v);
const isNum = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);
const isInt = (v: unknown): v is number => Number.isInteger(v);
const nums = (v: unknown, n: number): boolean => Array.isArray(v) && v.length === n && v.every(isNum);
const isStr = (v: unknown): v is string => typeof v === "string";

/**
 * What is wrong with a stored calc package, or null when it has the shape the engine reads:
 *   source_name a string or null; source_sha256 and segmenter strings
 *   pages[]  non-empty; n a positive integer, unique; text a string; words a list of
 *            [x0, y0, x1, y1, start, end] numbers; width / height numbers; scanned a boolean;
 *            doc_sha256 a string
 *   calcs[]  key a non-empty string, unique; ord an integer; title / software / cat / content_hash
 *            strings; pages a list of page numbers in the package; scanned / front booleans;
 *            title_box { page, rects[4 numbers], span null or [start, end], rule, note };
 *            spans[] of { regions[] of { page in the package, rect 4 numbers, start / end integers } };
 *            provenance { producer, rule, method strings, inputs strings }
 */
export function calcPackageProblem(x: unknown): string | null {
  if (!isObj(x)) return "not an object";
  if (x.source_name !== null && !isStr(x.source_name)) return "source_name must be a string or null";
  if (!isStr(x.source_sha256)) return "source_sha256 must be a string";
  if (!isStr(x.segmenter)) return "segmenter must be a string";
  if (!Array.isArray(x.pages) || !x.pages.length) return "pages must be a non-empty list";
  const pageNs = new Set<number>();
  for (const [i, pg] of x.pages.entries()) {
    const at = `pages[${i}]`;
    if (!isObj(pg)) return `${at} must be an object`;
    if (!isInt(pg.n) || pg.n < 1) return `${at}.n must be a positive integer`;
    if (pageNs.has(pg.n)) return `${at}: duplicate page number ${pg.n}`;
    pageNs.add(pg.n);
    if (!isStr(pg.text)) return `${at}.text must be a string`;
    if (!Array.isArray(pg.words) || !pg.words.every((w) => nums(w, 6))) return `${at}.words must be a list of [x0, y0, x1, y1, start, end]`;
    if (!isNum(pg.width) || !isNum(pg.height)) return `${at}.width / height must be numbers`;
    if (typeof pg.scanned !== "boolean") return `${at}.scanned must be a boolean`;
    if (!isStr(pg.doc_sha256)) return `${at}.doc_sha256 must be a string`;
  }
  if (!Array.isArray(x.calcs)) return "calcs must be a list";
  const keys = new Set<string>();
  for (const [i, c] of x.calcs.entries()) {
    const at = `calcs[${i}]`;
    if (!isObj(c)) return `${at} must be an object`;
    if (!isStr(c.key) || !c.key) return `${at}.key must be a non-empty string`;
    if (keys.has(c.key)) return `${at}: duplicate calc key ${JSON.stringify(c.key)}`;
    keys.add(c.key);
    if (!isInt(c.ord)) return `${at}.ord must be an integer`;
    for (const k of ["title", "software", "cat", "content_hash"] as const) if (!isStr(c[k])) return `${at}.${k} must be a string`;
    if (!Array.isArray(c.pages) || !c.pages.every((n) => pageNs.has(n as number))) return `${at}.pages must list pages of the package`;
    if (typeof c.scanned !== "boolean" || typeof c.front !== "boolean") return `${at}.scanned / front must be booleans`;
    const tb = c.title_box;
    if (!isObj(tb) || !isInt(tb.page) || !Array.isArray(tb.rects) || !tb.rects.every((r) => nums(r, 4))
      || !(tb.span === null || nums(tb.span, 2)) || !isStr(tb.rule) || !isStr(tb.note)) {
      return `${at}.title_box must be { page, rects, span, rule, note }`;
    }
    if (!Array.isArray(c.spans) || !c.spans.every((s) => isObj(s) && Array.isArray(s.regions) && s.regions.every((r) =>
      isObj(r) && pageNs.has(r.page as number) && nums(r.rect, 4) && isInt(r.start) && isInt(r.end)))) {
      return `${at}.spans must be a list of { regions: [{ page, rect, start, end }] } on pages of the package`;
    }
    const pv = c.provenance;
    if (!isObj(pv) || !isStr(pv.producer) || !isStr(pv.rule) || !isStr(pv.method) || !Array.isArray(pv.inputs) || !pv.inputs.every(isStr)) {
      return `${at}.provenance must be { producer, rule, method, inputs }`;
    }
  }
  return null;
}

/** Type guard over `calcPackageProblem`. */
export const isCalcPackage = (x: unknown): x is CalcPackage => calcPackageProblem(x) === null;
