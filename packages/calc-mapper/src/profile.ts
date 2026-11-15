/**
 * Section designations: ONE normaliser for both sides of every size comparison (calc text and
 * element profiles). Ported verbatim from packages/ifc-parser/src/profile.ts `normaliseProfile`
 * (that module also reads IFC geometry through web-ifc, so it is not imported into the browser
 * engine); test/profile.test.ts pins the two to the same outputs.
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
