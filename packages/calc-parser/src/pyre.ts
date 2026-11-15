/**
 * Python `re` compatibility for the ported rules.
 *
 * JavaScript's `\b` only knows ASCII word characters; Python 3's `\b` is Unicode
 * aware. Calc text can contain accented letters next to marks ("ÉB1"), so a
 * literal `\b` would split words Python keeps whole. `pyRe` rewrites `\b` into
 * Unicode-aware lookarounds and adds the `u` flag.
 */
const W = '[\\p{L}\\p{N}\\p{M}_]';
const WORD_BOUNDARY = `(?:(?<=${W})(?!${W})|(?<!${W})(?=${W}))`;

export function pyRe(source: string, flags = ''): RegExp {
  return new RegExp(source.replace(/\\b/g, WORD_BOUNDARY), flags.includes('u') ? flags : flags + 'u');
}

/** Python's `str.strip()`. */
export function pyStrip(s: string): string {
  return s.replace(/^\s+|\s+$/g, '');
}

/** Start of the line holding `idx`: Python's `s.rfind("\n", 0, idx) + 1`. */
export function lineStart(s: string, idx: number): number {
  return idx > 0 ? s.lastIndexOf('\n', idx - 1) + 1 : 0;
}

/** Code-point string order, as Python compares `str`. */
export function cmpStr(a: string, b: string): number {
  return a < b ? -1 : a > b ? 1 : 0;
}
