/**
 * Section designations: ONE grammar and ONE normaliser for both sides of every size comparison.
 *
 * - `normaliseProfile` and `PROFILE_PATTERNS` / `profileFromText` are ported verbatim from
 *   packages/ifc-parser/src/profile.ts, which is how the MODEL side gets an element's profile (the
 *   designation read out of Name / ObjectType text, normalised). That module also reads IFC geometry
 *   through web-ifc, so it is not imported into the browser engine; test/profile.test.ts (grammar)
 *   and test/features.test.ts (normaliser) pin the ported functions to the parser's outputs.
 * - `findSections` is how the CALC side finds designations in calc text. It does NOT reuse the
 *   parser's patterns: those read a Name / ObjectType field that is known to hold a profile, so they
 *   are deliberately loose ("45 X 12", "HD12", "S 2 X 4" are profiles there). Calc text is mostly
 *   arithmetic, grids, loads and tags, so a calc-side designation must be COMPLETE
 *   (`CALC_SECTION_PATTERNS`): a family prefix with every dimension that family needs, written
 *   without the spaces and commas that make it read as arithmetic; or exactly a profile the model
 *   carries that is itself a designation (`isDesignation`: a digit and a letter, so a ProfileName
 *   such as "Beam" is never a size). A dimensionless tag ("HD12", "HP1", "HL93") is a size only when
 *   the model carries exactly that profile.
 */

/** Upper case, no whitespace, 'x' / '×' / '*' between numbers -> 'X'. */
export function normaliseProfile(s: string): string {
  return s
    .trim()
    .toUpperCase()
    .replace(/×/g, "X")
    .replace(/(\d)\s*[X*]\s*(?=\d)/g, "$1X")
    .replace(/\s+/g, "");
}

const NUM = String.raw`\d+(?:[.,]\d+)?`;
const FRAC = String.raw`(?:\d+\s*-\s*)?\d+\/\d+|\d+(?:[.,]\d+)?`;
const X = String.raw`\s*[xX×*]\s*`;

/** Ordered: specific steel shapes first, generic WxD last (packages/ifc-parser's PROFILE_PATTERNS, verbatim). */
export const PROFILE_PATTERNS: readonly RegExp[] = [
  new RegExp(String.raw`\bHSS\s*(?:${FRAC})(?:${X}(?:${FRAC})){1,2}`, "i"),
  new RegExp(String.raw`\b(?:W|M|S|HP|C|MC|WT|MT|ST)\s?${NUM}${X}${NUM}\b`, "i"),
  new RegExp(String.raw`\bL\s?(?:${FRAC})${X}(?:${FRAC})${X}(?:${FRAC})`, "i"),
  new RegExp(String.raw`\b(?:IPE|IPN|UPN|UPE|PFC|HEA|HEB|HEM|HE\s?\d+\s?[ABM]|HD|HL|HP|CHS|SHS|RHS)\s?${NUM}(?:${X}${NUM}){0,2}\b`, "i"),
  new RegExp(String.raw`\b${NUM}${X}${NUM}${X}${NUM}\s*(?:UB|UC|UBP|PFC)\b`, "i"),
  new RegExp(String.raw`\b(?:UB|UC|UBP)\s*${NUM}${X}${NUM}${X}${NUM}\b`, "i"),
  new RegExp(String.raw`\b\d{2,4}${X}\d{2,4}(?:${X}\d{1,4})?\b`),
];

/** The first designation in the texts, by pattern priority (packages/ifc-parser's profileFromText, verbatim). */
export function profileFromText(texts: Array<string | undefined>): string | undefined {
  for (const re of PROFILE_PATTERNS) {
    for (const t of texts) {
      if (!t) continue;
      const m = re.exec(t);
      if (m) return normaliseProfile(m[0]);
    }
  }
  return undefined;
}

/** One section designation found in a text: [index, index + length) of the text, and its normalised form. */
export interface SectionHit {
  index: number;
  length: number;
  profile: string;
}

/**
 * A normalised profile that can be a section designation: it has a digit and a letter. A plain word
 * (an IFC ProfileName "Beam", "Default") or a bare number is not one, so it is never matched in calc
 * text and never compared as the model's size.
 */
export const isDesignation = (normalised: string): boolean => /\d/.test(normalised) && /[A-Z]/i.test(normalised);

const D = String.raw`(?:\d+-\d+\/\d+|\d+\/\d+|\d+(?:\.\d+)?|\.\d+)`; // a dimension: 6, 15.3, 1/2, 1-1/2, .375
const N = String.raw`\d+(?:\.\d+)?`;
const SX = String.raw`\s?[X×*]\s?`; // between dimensions, after a multi-letter family prefix
const TX = String.raw`[X×*]`; // tight: single-letter prefixes and the generic form take no spaces
/** Not continued: no word character, and no ",<digit>" / ".<digit>" (a list or a decimal comma) right after. */
const END = String.raw`(?![\w.,]?\d)(?!\w)`;

/** A calc-side section pattern; `depth` (the first number) must fall in a family's real range when given. */
export interface CalcPattern {
  re: RegExp;
  depth?: [number, number];
}

/**
 * The calc-text grammar: complete designations only (see the module comment). Calc text is folded
 * (upper case) before it is read. In priority order, as the parser orders its patterns.
 */
export const CALC_SECTION_PATTERNS: readonly CalcPattern[] = [
  // HSS6X6X3/8, HSS6X6X.375, HSS 8.625X.322
  { re: new RegExp(String.raw`\bHSS\s?${D}(?:${SX}${D}){1,2}${END}`, "g") },
  // W18X35, W 18X35, C10X15.3, S8X18.4, HP12X53 (no spaces around the X; the depth is a real one:
  // "S2X4" is lumber, "W1.2X0.5" a load)
  { re: new RegExp(String.raw`\b(?:W|M|S|C|HP|MC)\s?(\d{1,2})${TX}${N}${END}`, "g"), depth: [3, 44] },
  { re: new RegExp(String.raw`\b(?:WT|MT|ST)\s?(\d{1,2}(?:\.\d)?)${TX}${N}${END}`, "g"), depth: [2, 22] },
  // L4X4X1/2, L3-1/2X3X1/4 (three dimensions)
  { re: new RegExp(String.raw`\bL${D}${TX}${D}${TX}${D}${END}`, "g") },
  // IPE 300, HEA200, UPN 120 (the family name is the designation: one size, two digits or more)
  { re: new RegExp(String.raw`\b(?:IPE|IPN|UPN|UPE|PFC|HEA|HEB|HEM)\s?\d{2,4}(?:${SX}${N}){0,2}${END}`, "g") },
  { re: new RegExp(String.raw`\bHE\s?\d{2,4}\s?[ABM]${END}`, "g") },
  // families that need their dimensions: CHS 168.3X7.1, SHS 100X100X6, RHS 200X100X8, HD 400X1086, HL 1000X443
  { re: new RegExp(String.raw`\b(?:CHS|SHS|RHS|HD|HL|HP)\s?${N}(?:${SX}${N}){1,2}${END}`, "g") },
  // 457X191X67 UB, 533X210X92UB, UB 457X191X67
  { re: new RegExp(String.raw`\b\d{2,4}${SX}\d{2,4}${SX}${N}\s?(?:UB|UC|UBP|PFC)${END}`, "g") },
  { re: new RegExp(String.raw`\b(?:UB|UC|UBP)\s?\d{2,4}${SX}\d{2,4}${SX}${N}${END}`, "g") },
  // 310UB40.4, 250PFC, 200UC46.2
  { re: new RegExp(String.raw`\b\d{2,3}(?:UB|UC|PFC|WB|WC)(?:${N})?${END}`, "g") },
  // generic 600X300 / 1200X1200X600: three- or four-digit sides, written tight ("45 X 12" is arithmetic)
  { re: new RegExp(String.raw`\b\d{3,4}${TX}\d{3,4}(?:${TX}\d{1,4})?${END}`, "g") },
];

/** A whole token (as the matcher tokenises marks): a known designation must be one, not part of one. */
const TOKEN = /[A-Z0-9]+(?:[-./][A-Z0-9]+)*/gi;

/**
 * Every section designation in (folded) calc `text`, left to right, non-overlapping. Candidates are
 * the matches of CALC_SECTION_PATTERNS and, when given, whole tokens whose normalised form is one of
 * the `known` designations (the model's profiles; any that is not `isDesignation` is ignored). Where
 * candidates overlap, the earliest start wins; at the same start a known designation wins, then the
 * longer match, then pattern priority. A candidate that is one of the model's `marks` (normalised by
 * the caller's mark normaliser `markOf`) is a mark, not a size, and is dropped.
 */
export function findSections(
  text: string, opts: { known?: ReadonlySet<string>; marks?: ReadonlySet<string>; markOf?: (s: string) => string } = {},
): SectionHit[] {
  const cands: { index: number; length: number; rank: number }[] = [];
  CALC_SECTION_PATTERNS.forEach(({ re, depth }, rank) => {
    for (const m of text.matchAll(re)) {
      if (!m[0].length) continue;
      if (depth && m[1] !== undefined && (Number(m[1]) < depth[0] || Number(m[1]) > depth[1])) continue;
      cands.push({ index: m.index, length: m[0].length, rank: rank + 1 });
    }
  });
  const known = [...(opts.known ?? [])].filter(isDesignation);
  if (known.length) {
    const set = new Set(known);
    for (const m of text.matchAll(TOKEN)) if (set.has(normaliseProfile(m[0]))) cands.push({ index: m.index, length: m[0].length, rank: 0 });
  }
  cands.sort((p, q) => p.index - q.index || (p.rank === 0 ? 0 : 1) - (q.rank === 0 ? 0 : 1) || q.length - p.length || p.rank - q.rank);
  const out: SectionHit[] = [];
  let end = 0;
  for (const c of cands) {
    if (c.index < end) continue;
    const s = text.slice(c.index, c.index + c.length);
    if (opts.marks?.size && opts.markOf && opts.marks.has(opts.markOf(s))) continue;
    out.push({ index: c.index, length: c.length, profile: normaliseProfile(s) });
    end = c.index + c.length;
  }
  return out;
}
