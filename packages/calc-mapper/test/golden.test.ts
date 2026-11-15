/**
 * Golden regression on the synthetic calc package (12 calcs, 459 elements).
 *
 * fixtures/golden/ holds frozen inputs (page text + word boxes, element rows) and the expected
 * calcs, links and calc dependencies, trimmed to the fields that must not drift: segmentation,
 * which element links to which calc (tier, page, matched span) and the dependency edges.
 * Confidence is deliberately not pinned: it is the sum of the evidence weights and is tuned.
 * Carried over from the retired packages/calc-parser.
 */
import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { segmentCalcs } from '../src/index.ts';
import { mapElements } from '../src/matcher.ts';
import { inferCalcEdges } from '../src/calcdeps.ts';
import type { CalcPage, ElementRow, WordBox } from '../src/types.ts';

const golden = <T>(name: string): T => JSON.parse(readFileSync(new URL(`./fixtures/golden/${name}`, import.meta.url), 'utf8')) as T;

const SHA = 'a'.repeat(64);
type GoldenPage = { n: number; text: string; words: WordBox[]; width: number; height: number };
const pages: CalcPage[] = golden<{ pages: GoldenPage[] }>('pages.json').pages.map((p) => ({
  ...p,
  scanned: p.text.trim().length < 25,
  doc_sha256: SHA,
}));
const elements = golden<Omit<ElementRow, 'express_id' | 'type_name' | 'params' | 'geom' | 'content_hash'>[]>('elements.json').map(
  (e): ElementRow => ({ express_id: null, type_name: '', params: {}, geom: null, content_hash: '', ...e }),
);

describe('golden: synthetic calc package', () => {
  const pkg = segmentCalcs(pages, 'calc_package.pdf');
  const { links } = mapElements(elements, pkg.calcs, pages, SHA);

  it('splits the package into the same 12 calcs', () => {
    expect(pkg.calcs.map(({ key, title, cat, pages, front, scanned }) => ({ key, title, cat, pages, front, scanned }))).toEqual(
      golden('calcs.json'),
    );
  });

  it('links the same elements to the same calcs (tier, page, span)', () => {
    const got = links.map((l) => [l.global_id, l.calc_key, l.tier, l.page, l.span]);
    const want = golden<unknown[][]>('links.json');
    expect(got).toHaveLength(want.length);
    expect(new Set(got.map((x) => JSON.stringify(x)))).toEqual(new Set(want.map((x) => JSON.stringify(x))));
  });

  it('infers the same calc dependency edges', () => {
    const edges = inferCalcEdges(pkg.calcs, pages, links).map(({ src, dst, rules }) => ({ src, dst, rules }));
    expect(edges).toEqual(golden('calc_edges.json'));
  });
});
