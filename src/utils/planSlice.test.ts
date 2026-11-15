import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { buildGraph, ElementGraph, type ModelInput } from '@unloaded/element-graph';
import { parseBundle } from '@unloaded/calc-mapper';
import { elementGraphToBim } from '../loaders/elementGraphToBim';
import type { BimNode } from '../types/bim';
import { buildLevelPlan, buildPlanIndex, formatElevation, levelForElement, planLevels, stepLevel } from './planSlice';

const root = new URL('../../', import.meta.url);
const read = (f: string) => readFileSync(new URL(f, root), 'utf8');

const simple = (() => {
  const topo = elementGraphToBim(buildGraph(JSON.parse(read('data/simple-frame.json')) as ModelInput).graph);
  return { nodes: topo.elementNodes, levels: topo.levels ?? [] };
})();

const harborview = (() => {
  const b = parseBundle(read('data/harborview/harborview-tower-rev1-base.bundle.json'));
  const topo = elementGraphToBim(ElementGraph.deserialize(b.elementGraph));
  return { nodes: topo.elementNodes, levels: topo.levels ?? [] };
})();

const roles = (items: { role: string }[]) => items.reduce<Record<string, number>>((m, i) => ((m[i.role] = (m[i.role] ?? 0) + 1), m), {});

describe('planSlice on simple-frame', () => {
  const index = buildPlanIndex(simple.nodes, simple.levels);

  it('levels are the storeys with something on them, lowest first; the slab marks its storey', () => {
    expect(index.levels.map((l) => [l.name, l.elevation, l.hasSlab])).toEqual([
      ['Foundation', 0, false],
      ['Level 1', 3.5, true],
    ]);
  });

  it('draws Level 1 as a framing plan: slab, beam centreline, the columns below, the connections', () => {
    const plan = index.plans.get('L1')!;
    expect(roles(plan.items)).toEqual({ slab: 1, beam: 1, column: 2, connection: 2 });
    const beam = plan.items.find((i) => i.role === 'beam')!;
    expect(beam.node.mark).toBe('B101');
    expect(beam.shape).toEqual({ type: 'line', a: [0.14, 0], b: [5.86, 0], width: 0.14 });
    // slabs first, connections last: the draw order
    expect(plan.items[0]!.role).toBe('slab');
    expect(plan.items.at(-1)!.role).toBe('connection');
  });

  it('draws the ground floor with its footings and the columns that start there', () => {
    expect(roles(index.plans.get('L0')!.items)).toEqual({ foundation: 2, 'column-start': 2 });
  });

  it('finds an element its level and steps between levels', () => {
    const col = simple.nodes.find((n) => n.mark === 'C2')!;
    expect(levelForElement(index, col.id, null)).toBe('L0');
    expect(levelForElement(index, col.id, 'L1')).toBe('L1');
    expect(levelForElement(index, 'nope', 'L1')).toBeNull();
    expect(stepLevel(index, 'L0', 1)).toBe('L1');
    expect(stepLevel(index, 'L1', 1)).toBeNull();
    expect(stepLevel(index, 'L0', -1)).toBeNull();
    expect(stepLevel(index, null, 1)).toBe('L0');
  });
});

describe('planSlice on the Harborview tower', () => {
  const index = buildPlanIndex(harborview.nodes, harborview.levels);

  it('puts a storey\'s ceiling framing on the level above it (the IFC convention)', () => {
    // "L03" girders and slab sit at the L04 elevation
    const l04 = index.plans.get('floor:L04')!;
    const marks = l04.items.map((i) => i.node.mark ?? '');
    expect(marks).toContain('G-D4E4-L03');
    expect(marks).toContain('Slab L03');
    expect(l04.level.hasSlab).toBe(true);
    // the L03 columns carry L04; the L04 columns stand on them and are not repeated
    expect(l04.items.filter((i) => i.role === 'column').every((i) => i.node.mark!.endsWith('-L03'))).toBe(true);
    expect(l04.items.some((i) => i.role === 'column-start')).toBe(false);
  });

  it('draws every element of a typical floor exactly once', () => {
    const l04 = index.plans.get('floor:L04')!;
    const ids = l04.items.map((i) => i.id);
    expect(new Set(ids).size).toBe(ids.length);
    const r = roles(l04.items);
    expect(r.slab).toBe(1);
    expect(r.beam).toBeGreaterThan(20);
    expect(r.column).toBe(20);
    expect(r.connection).toBeGreaterThan(10);
    expect(r.wall).toBeGreaterThan(0);
    expect(r.brace).toBeGreaterThan(0);
  });

  it('every beam, column and connection is on some level', () => {
    for (const n of harborview.nodes.filter((n) => n.kind === 'element' && ['beam', 'column', 'connection'].includes(n.elementKind!))) {
      expect(index.levelsOf.has(n.id), `${n.mark}`).toBe(true);
    }
  });
});

describe('planSlice edge cases', () => {
  const el = (id: string, kind: string, min: [number, number, number], max: [number, number, number], extra: Partial<BimNode> = {}): BimNode => ({
    id,
    label: id,
    kind: 'element',
    level: 2,
    elementKind: kind,
    r: 8,
    x: 0,
    y: 0,
    bbox: { min, max },
    ...extra,
  });

  it('has no levels without geometry, and makes a level from a slab no storey sits on', () => {
    expect(buildPlanIndex([{ ...el('a', 'beam', [0, 0, 0], [1, 0, 0]), bbox: undefined }], []).levels).toEqual([]);
    const slab = el('s', 'slab', [0, 0, 2.8], [4, 4, 3]);
    expect(planLevels([slab], [])).toEqual([{ id: 'slab:3.000', name: 's', elevation: 3, hasSlab: true }]);
  });

  it('draws a beam without an axis along its bbox, and a sloped beam by its axis', () => {
    const level = { id: 'x', name: 'X', elevation: 3, hasSlab: false };
    const flat = el('b', 'beam', [0, -0.1, 2.6], [5, 0.1, 3]);
    expect(buildLevelPlan([flat], level).items[0]!.shape).toEqual({ type: 'line', a: [0, 0], b: [5, 0], width: 0.2 });
    const sloped = el('r', 'beam', [0, 0, 2.2], [3, 4, 3.1], { axis: { start: [0, 0, 2.4], end: [3, 4, 2.9] }, section: { width: 0.15 } });
    expect(buildLevelPlan([sloped], level).items[0]!.shape).toEqual({ type: 'line', a: [0, 0], b: [3, 4], width: 0.15 });
  });

  it('formats elevations as a datum', () => {
    expect(formatElevation(11.5824)).toBe('+11.582 m');
    expect(formatElevation(-7.1628)).toBe('−7.163 m');
    expect(formatElevation(0.0001)).toBe('±0.000 m');
  });
});
