/**
 * Section designations: ONE grammar and ONE normaliser for both sides of every size comparison.
 *
 * - `normaliseProfile` and `PROFILE_PATTERNS` / `profileFromText` are ported verbatim from
 *   packages/ifc-parser/src/profile.ts, which is how the MODEL side gets an element's profile (the
 *   designation read out of Name / ObjectType text, normalised). That module also reads IFC geometry
 *   through web-ifc, so it is not imported into the browser engine; test/profile.test.ts (grammar)
 *   and test/features.test.ts (normaliser) pin the ported functions to the parser's outputs.
 * - `findSections` is how the CALC side finds designations in calc text: the same patterns, every
 *   occurrence with its offset, plus any designation the model actually carries (an element's profile
 *   can come straight from an IFC ProfileName such as "310UB40.4" or "HSS6X6X.375", which no text
 *   pattern describes). So any designation the model can carry can be found in a calc.
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

const GLOBAL_PATTERNS = PROFILE_PATTERNS.map((re) => new RegExp(re.source, re.flags + "g"));
/** A whole token (as the matcher tokenises marks): a known designation must be one, not part of one. */
const TOKEN = /[A-Z0-9]+(?:[-./][A-Z0-9]+)*/gi;

/**
 * Every section designation in `text`, left to right, non-overlapping. Candidates are the matches of
 * PROFILE_PATTERNS and, when given, whole tokens whose normalised form is one of the `known`
 * designations (the model's profiles). Where candidates overlap, the earliest start wins; at the same
 * start a known designation wins, then the longer match, then pattern priority (as a single
 * alternation of the patterns would). A candidate that is one of the model's `marks` (normalised by
 * the caller's mark normaliser `markOf`) is a mark, not a size, and is dropped.
 */
export function findSections(
  text: string, opts: { known?: ReadonlySet<string>; marks?: ReadonlySet<string>; markOf?: (s: string) => string } = {},
): SectionHit[] {
  const cands: { index: number; length: number; rank: number }[] = [];
  GLOBAL_PATTERNS.forEach((re, rank) => {
    for (const m of text.matchAll(re)) if (m[0].length) cands.push({ index: m.index, length: m[0].length, rank: rank + 1 });
  });
  if (opts.known?.size) {
    for (const m of text.matchAll(TOKEN)) if (opts.known.has(normaliseProfile(m[0]))) cands.push({ index: m.index, length: m[0].length, rank: 0 });
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
