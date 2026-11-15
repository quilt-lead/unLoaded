/**
 * Split a calc package into calcs. Port of segment.py (itself a port of the
 * mockup's segment() / titleOf()).
 *
 * Rules (deterministic):
 * - a page with < 25 characters of text has no text layer (scanned / handwritten):
 *   consecutive such pages form one "scanned" calc that is never mapped
 * - a page with >= 3 dot-leader entries ("Title ...... 12") is front matter / contents
 *   and is never mapped
 * - a page whose first lines carry a calc-like title starts a new calc unless the
 *   title (ignoring "(cont.)" and punctuation) equals the current calc's title
 * - software and element type come from keyword tables
 *
 * Software named in the title wins over software the body cites, and the element
 * type falls back to the line directly UNDER the title line.
 */
import { pyRe, pyStrip } from './pyre.ts';
import type { Calc, CalcCat, CalcPage } from './types.ts';

export const SOFTWARE: ReadonlyArray<readonly [RegExp, string]> = [
  [/RAM\s*CONCEPT/i, 'RAM Concept'],
  [/RAM\s*(STRUCTURAL|STEEL|FRAME|ELEMENTS)/i, 'RAM Structural System'],
  [pyRe(String.raw`\bETABS\b`, 'i'), 'ETABS'],
  [pyRe(String.raw`\bSAFE\b`), 'SAFE'], // case-sensitive: "safe" is an ordinary word
  [/SAP\s?2000/i, 'SAP2000'],
  [/MATHCAD/i, 'MathCAD'],
  [/TEKLA\s+STRUCTURAL\s+DESIGNER/i, 'Tekla Structural Designer'],
  [/RISA/i, 'RISA'],
  [/IDEA\s*STATICA/i, 'IDEA StatiCa'],
  [/PROFIS/i, 'Hilti PROFIS'],
  [pyRe(String.raw`\bVBA\b|\.XLSM`, 'i'), 'VBA / Excel'],
  [pyRe(String.raw`\bEXCEL\b|\.XLSX`, 'i'), 'Excel'],
  [/HAND\s*CALC/i, 'Hand calc'],
  [/PROKON/i, 'Prokon'],
  [/SPACEGASS|SPACE\s*GASS/i, 'SpaceGass'],
  [/ROBOT/i, 'Robot'],
  [/SCIA/i, 'SCIA'],
  [/MIDAS/i, 'MIDAS'],
  [/STAAD/i, 'STAAD'],
  [/ENERCALC/i, 'Enercalc'],
];

/** Element-type keywords, in priority order. Non-global: safe to `.test` / `.exec` repeatedly. */
export const CAT_WORDS: ReadonlyArray<readonly [Exclude<CalcCat, ''>, RegExp]> = [
  ['Connection', pyRe(String.raw`\b(connection|shear tab|fin plate|end plate|base plate|bolt group|cleat|moment conn)`, 'i')],
  ['Footing', pyRe(String.raw`\b(footing|foundation|pad|raft|pile cap)`, 'i')],
  ['Pile', pyRe(String.raw`\bpiles?\b`, 'i')],
  ['Brace', pyRe(String.raw`\b(brac(e|ing)|x-brace)`, 'i')],
  ['Column', pyRe(String.raw`\bcolumns?\b`, 'i')],
  ['Slab', pyRe(String.raw`\b(slab|deck|pt slab|post-tension)`, 'i')],
  ['Wall', pyRe(String.raw`\b(wall|core)\b`, 'i')],
  ['Beam', pyRe(String.raw`\b(beams?|girders?|joists?|lintels?|transfer)\b`, 'i')],
];

const TITLE_KW = /(design|calc|calculation|check|analysis|criteria|framing|report|schedule|connection|footing|bracing)/i;
const TOC = /\.{4,}\s*\d+/g;

export function catOfText(s: string): CalcCat {
  return CAT_WORDS.find(([, rx]) => rx.test(s))?.[0] ?? '';
}

/** Python `[s.strip() for s in text.split('\n') if s.strip()]`. */
function nonEmptyLines(text: string): string[] {
  return text
    .split('\n')
    .map((s) => pyStrip(s))
    .filter((s) => s.length > 0);
}

export function titleOf(text: string): string | null {
  for (const line of nonEmptyLines(text).slice(0, 6)) {
    if (line.length > 4 && line.length < 90 && TITLE_KW.test(line) && !/\.{4,}/.test(line)) {
      return pyStrip(line.replace(/\s*\((cont\.?|continued)\)\s*$/i, ''));
    }
  }
  return null;
}

function norm(s: string | null | undefined): string {
  return (s ?? '').toUpperCase().replace(/[^A-Z0-9]/g, '');
}

function slug(s: string): string {
  const out = s
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/-+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 60);
  return out || 'calc';
}

export function segment(pages: ReadonlyArray<Pick<CalcPage, 'n' | 'text'>>): Calc[] {
  const calcs: Calc[] = [];
  let cur: Calc | null = null;

  const push = (title: string, scanned = false): Calc => {
    const c: Calc = { key: '', title, software: '', cat: '', pages: [], scanned, front: false, text: '' };
    calcs.push(c);
    return c;
  };

  for (const pg of pages) {
    const t = pyStrip(pg.text);
    if (t.length < 25) {
      if (!(cur && cur.scanned)) cur = push('Scanned page(s) - no text layer', true);
      cur.pages.push(pg.n);
      continue;
    }
    if ((t.match(TOC) ?? []).length >= 3) {
      cur = push('Front matter / contents');
      cur.front = true;
      cur.pages.push(pg.n);
      cur.text += '\n' + t;
      continue;
    }
    const title = titleOf(t);
    if (!cur || cur.scanned || cur.front || (title && norm(title) !== norm(cur.title))) {
      cur = push(title || (cur ? cur.title + ' (cont.)' : 'Front matter'));
    }
    cur.pages.push(pg.n);
    cur.text += '\n' + t;
  }

  const seen = new Map<string, number>();
  let nScanned = 0;
  for (const c of calcs) {
    let base: string;
    if (c.scanned) {
      nScanned += 1;
      base = `scanned-${nScanned}`;
    } else {
      base = slug(c.title);
    }
    const k = (seen.get(base) ?? 0) + 1;
    seen.set(base, k);
    c.key = k === 1 ? base : `${base}-${k}`;
    if (c.front) continue;
    // software named in the title wins over software the body merely cites
    const sw =
      SOFTWARE.find(([rx]) => rx.test(c.title))?.[1] || SOFTWARE.find(([rx]) => rx.test(c.text))?.[1] || '';
    c.software = sw || (c.scanned ? 'Needs OCR' : '');
    const lines = nonEmptyLines(c.text);
    let under = '';
    for (let i = 0; i < lines.length; i++) {
      if (norm(titleOf(lines[i]!) ?? '') === norm(c.title) && norm(c.title)) {
        under = i + 1 < lines.length ? lines[i + 1]! : '';
        break;
      }
    }
    c.cat = catOfText(c.title) || catOfText(under);
  }
  return calcs;
}
