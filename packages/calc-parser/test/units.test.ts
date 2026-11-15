/** Hand-built cases: ports of backend/tests/test_matcher_units.py plus the review and impact rules. */
import { describe, expect, it } from 'vitest';
import {
  effectiveLinks,
  inferCalcDeps,
  propagateImpact,
  runMapping,
  segment,
  statusOf,
  toCalcElements,
  type CalcElement,
  type CalcLink,
  type CalcPage,
  type Decision,
} from '../src/index.ts';
import { pyRe } from '../src/pyre.ts';

function page(n: number, text: string): CalcPage {
  const words: CalcPage['words'] = [];
  let pos = 0;
  for (const line of text.split('\n')) {
    for (const w of line.split(' ')) {
      words.push([0, 0, 1, 1, pos, pos + w.length]);
      pos += w.length + 1;
    }
  }
  return { n, text, words, width: 612, height: 792, images: 0 };
}

const el = (gid: string, cat: string, mark: string, profile = '', storey = 'Level 2'): CalcElement => ({
  global_id: gid,
  cat,
  mark,
  profile,
  storey,
});

describe('matcher tiers', () => {
  it('finds range, exact, xref, partial and size links', () => {
    const pages = [page(1, 'HEADER LINE\nBEAM DESIGN - RAM STEEL\nbeams 2B1 - 2B3 and SL2\n2B9 W18X35\nCB1 see hand calc')];
    const calcs = segment(pages);
    const els = [
      el('a', 'Beam', '2B1'),
      el('b', 'Beam', '2B2'),
      el('c', 'Beam', '2B9'),
      el('s', 'Slab', 'SL-2'),
      el('k', 'Beam', '2CB1'),
      el('u', 'Beam', '', 'W18X35'),
    ];
    const got = new Set(runMapping(els, calcs, pages).map((l) => `${l.global_id}:${l.tier}`));
    // test_matcher_units.py expects "a:range", but 2B1 is also named outright, so exact (0.97) beats
    // range (0.90). The Python matcher gives a:exact too; that test only ran in CI and was wrong.
    for (const want of ['a:exact', 'b:range', 'c:exact', 's:xref', 'k:partial', 'u:size']) expect(got).toContain(want);
    expect(calcs[0]!.software).toBe('RAM Structural System');
    expect(calcs[0]!.cat).toBe('Beam');
  });

  it('never maps scanned pages or front matter', () => {
    const pages = [page(1, 'Design criteria .... 2\nBeams .... 3\nColumns .... 4'), page(2, '')];
    const calcs = segment(pages);
    expect(calcs[0]!.front).toBe(true);
    expect(calcs[1]!.scanned).toBe(true);
    expect(calcs[1]!.software).toBe('Needs OCR');
    expect(runMapping([el('a', 'Beam', 'B1')], calcs, pages)).toEqual([]);
  });

  it('falls back to element type when a calc names no marks or sizes', () => {
    const pages = [page(1, 'COLUMN DESIGN CHECK\nAll columns are checked for axial load and buckling.')];
    const links = runMapping([el('c1', 'Column', 'C1'), el('b1', 'Beam', 'B1')], segment(pages), pages);
    expect(links.map((l) => [l.global_id, l.tier, l.conf])).toEqual([['c1', 'type', 0.3]]);
  });

  it('uses Unicode-aware word boundaries, like Python', () => {
    expect(/\bWALL\b/i.test('ÉWALL')).toBe(true); // plain JS: É is not a word character
    expect(pyRe(String.raw`\bWALL\b`, 'i').test('ÉWALL')).toBe(false);
    expect(pyRe(String.raw`\bWALL\b`, 'i').test('shear WALL design')).toBe(true);
  });
});

describe('calc dependencies', () => {
  it('reads page references and their direction', () => {
    const pages = [
      page(1, 'BEAM DESIGN CALC\nreactions carried to page 2'),
      page(2, 'COLUMN DESIGN CALC\nloads per page 3'),
      page(3, 'FOOTING DESIGN CALC\nbearing check'),
    ];
    const calcs = segment(pages);
    const edges = inferCalcDeps(calcs, pages, []);
    expect(edges.map((e) => [e.src, e.dst, e.rules[0]])).toEqual([
      ['beam-design-calc', 'column-design-calc', 'page reference (output to)'],
      ['footing-design-calc', 'column-design-calc', 'page reference (input from)'],
    ]);
  });
});

describe('review decisions', () => {
  const base: CalcLink = {
    global_id: 'a',
    calc_key: 'k',
    conf: 0.62,
    tier: 'size',
    rule: '',
    page: 1,
    span: [0, 1],
    token: 'x',
    snippet: null,
    rects: [],
  };
  const d = (action: Decision['action'], gid = 'a', calc = 'k'): Decision => ({
    global_id: gid,
    calc_key: calc,
    action,
    at: '2026-11-14T12:00:00',
    actor: 'eng',
  });

  it('applies confirm / reject / manual / undo and drops decisions for vanished elements', () => {
    const gids = new Set(['a', 'b']);
    const keys = new Set(['k']);
    expect(statusOf(effectiveLinks([base], [], gids, keys))).toBe('review');
    expect(statusOf(effectiveLinks([base], [d('confirm')], gids, keys))).toBe('confirmed');
    expect(statusOf(effectiveLinks([base], [d('reject')], gids, keys))).toBe('unmapped');
    expect(statusOf(effectiveLinks([base], [d('reject'), d('undo')], gids, keys))).toBe('review');
    const manual = effectiveLinks([base], [d('manual', 'b')], gids, keys);
    expect(manual.find((l) => l.global_id === 'b')).toMatchObject({ tier: 'manual', status: 'manual', conf: 1 });
    expect(effectiveLinks([base], [d('manual', 'gone')], gids, keys)).toHaveLength(1);
    expect(base.status).toBeUndefined(); // inputs are not mutated
  });
});

describe('impact', () => {
  // slab -> beam -> plate -> column -> footing
  const edges = [
    { src: 's', dst: 'b' },
    { src: 'b', dst: 'p' },
    { src: 'p', dst: 'c' },
    { src: 'c', dst: 'f' },
  ];
  const els = {
    s: { cat: 'Slab', mark: 'S1' },
    b: { cat: 'Beam', mark: 'B1' },
    p: { cat: 'Connection', mark: '' },
    c: { cat: 'Column', mark: 'C1' },
    f: { cat: 'Footing', mark: 'F1' },
  };
  const links = [
    { global_id: 'c', calc_key: 'col' },
    { global_id: 'f', calc_key: 'ftg' },
  ];

  it('removing a column orphans its footing, re-frames the beam via the plate, and stales calcs downstream', () => {
    const r = propagateImpact('c', 'remove', edges, links, [{ src: 'ftg', dst: 'report' }], els);
    expect(r.removed).toEqual(['c', 'f', 'p']);
    expect(r.hit).toEqual({ b: 0 });
    expect(r.stale).toEqual({ col: 'covers C1', ftg: 'covers F1', report: 'input from ftg' });
  });
});

describe('element adapter', () => {
  it('maps ModelInput elements to matcher records', () => {
    const got = toCalcElements(
      [
        { id: 'g1', kind: 'beam', mark: 'B1', profile: 'w12x26', levelId: 'L2', source: { nativeType: 'IfcBeam' } },
        { id: 'g2', kind: 'connection', mark: 'n/a', source: { nativeType: 'IfcPlate' } },
        { id: 'g3', kind: 'brace', mark: 'N.A.' },
      ],
      new Map([['L2', 'Level 2']]),
    );
    expect(got).toEqual([
      { global_id: 'g1', cat: 'Beam', mark: 'B1', profile: 'W12X26', storey: 'Level 2', name: '' },
      { global_id: 'g2', cat: 'Connection', mark: 'n/a', profile: '', storey: '', name: '' },
      { global_id: 'g3', cat: 'Brace', mark: '', profile: '', storey: '', name: '' },
    ]);
  });
});
