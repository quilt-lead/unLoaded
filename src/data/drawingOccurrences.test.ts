import { describe, expect, it } from 'vitest';
import { cropAround, HOW_LABEL, OCCURRENCES_PARAM, readOccurrences, shownOccurrences } from './drawingOccurrences';

const occ = (o: Record<string, unknown> = {}) => ({
  file: 'plans.pdf', sheet: 'S2.0.2', page: 55, rect: [1533.1, 1272.4, 1568.4, 1283], how: 'plan_tag', text: 'W16x26', ...o,
});
const params = (v: unknown) => ({ [OCCURRENCES_PARAM]: typeof v === 'string' ? v : JSON.stringify(v) });

describe('readOccurrences', () => {
  it('reads the parser JSON into typed targets, in order', () => {
    const out = readOccurrences(params([occ(), occ({ how: 'schedule_row', sheet: 'S2.0.1', page: 54, rect: [2328.1, 1879.3, 2616.2, 1889.8], text: 'F12 12\' - 0"' })]));
    expect(out).toEqual([
      { file: 'plans.pdf', sheet: 'S2.0.2', page: 55, rect: [1533.1, 1272.4, 1568.4, 1283], how: 'plan_tag', text: 'W16x26' },
      { file: 'plans.pdf', sheet: 'S2.0.1', page: 54, rect: [2328.1, 1879.3, 2616.2, 1889.8], how: 'schedule_row', text: 'F12 12\' - 0"' },
    ]);
    for (const o of out) expect(HOW_LABEL[o.how]).toBeTruthy();
  });

  it('gives nothing for a missing param, an IFC element, invalid JSON or a non-array', () => {
    expect(readOccurrences(undefined)).toEqual([]);
    expect(readOccurrences({})).toEqual([]);
    expect(readOccurrences({ 'Pset.Mark': 'B1' })).toEqual([]);
    expect(readOccurrences(params(''))).toEqual([]);
    expect(readOccurrences(params('[{"file":'))).toEqual([]);
    expect(readOccurrences(params({ file: 'x' }))).toEqual([]);
    expect(readOccurrences(params('null'))).toEqual([]);
  });

  it('drops malformed entries and keeps the valid ones', () => {
    const bad = [
      null, 'x', occ({ file: '' }), occ({ page: 0 }), occ({ page: 2.5 }), occ({ page: '55' }), occ({ how: 'section_cut' }),
      occ({ rect: [1, 2, 3] }), occ({ rect: [1, 2, 'a', 4] }), occ({ rect: [10, 10, 5, 20] }), occ({ rect: [0, 0, Infinity, 1] }),
    ];
    expect(readOccurrences(params([...bad, occ()]))).toHaveLength(1);
  });

  it('defaults a missing sheet or text to empty strings', () => {
    const [o] = readOccurrences(params([{ file: 'a.pdf', page: 1, rect: [0, 0, 1, 1], how: 'note' }]));
    expect(o).toMatchObject({ sheet: '', text: '' });
  });
});

describe('shownOccurrences', () => {
  const list = readOccurrences(params([occ(), occ({ file: 'other.pdf' })]));
  it('keeps the occurrences whose drawing PDF is loaded, with its URL', () => {
    expect(shownOccurrences(list, { 'plans.pdf': 'blob:1' })).toEqual([{ ...list[0], url: 'blob:1' }]);
  });
  it('shows nothing without drawing PDFs (an IFC model)', () => {
    expect(shownOccurrences(list, undefined)).toEqual([]);
    expect(shownOccurrences(list, {})).toEqual([]);
  });
});

describe('cropAround', () => {
  const centre = (r: number[]) => [(r[0]! + r[2]!) / 2, (r[1]! + r[3]!) / 2];
  it('centres a short tag in a crop of at least the minimum size, at the aspect ratio', () => {
    const tag = [1533.1, 1272.4, 1568.4, 1283];
    const c = cropAround(tag, { minW: 220, minH: 140, aspect: 1.5 });
    expect(centre(c)[0]).toBeCloseTo(centre(tag)[0]!);
    expect(centre(c)[1]).toBeCloseTo(centre(tag)[1]!);
    expect(c[2]! - c[0]!).toBeGreaterThanOrEqual(220);
    expect(c[3]! - c[1]!).toBeGreaterThanOrEqual(140);
    expect((c[2]! - c[0]!) / (c[3]! - c[1]!)).toBeCloseTo(1.5);
    // the tag is inside the crop
    expect(c[0]! <= tag[0]! && c[1]! <= tag[1]! && c[2]! >= tag[2]! && c[3]! >= tag[3]!).toBe(true);
  });
  it('shows a long schedule row whole, with padding', () => {
    const row = [2328.1, 1879.3, 2616.2, 1889.8];
    const c = cropAround(row, { pad: 24 });
    expect(c[0]).toBeLessThanOrEqual(row[0]! - 24);
    expect(c[2]).toBeGreaterThanOrEqual(row[2]! + 24);
  });
});
