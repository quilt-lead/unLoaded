import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { diffGraphs } from '@unloaded/calc-mapper';
import { isLegacyBimJson, legacyToElementGraph } from './legacyBimJson';
import { elementGraphToBim } from './elementGraphToBim';

const root = new URL('../../', import.meta.url);
const read = (f: string) => JSON.parse(readFileSync(new URL(f, root), 'utf8')) as unknown;

describe("Noah's legacy demo JSON through the element graph and the one diff", () => {
  const a = read('sample-data/harborview-tower-rev1-base.json');
  const b = read('sample-data/harborview-tower-rev2-compare.json');

  it('is recognised as legacy BIM JSON', () => {
    expect(isLegacyBimJson(a)).toBe(true);
    expect(isLegacyBimJson({ format: 'unloaded.element-graph', nodes: [] })).toBe(false);
  });

  it('becomes an element graph with inferred topology and labelled demo documents', () => {
    if (!isLegacyBimJson(a)) throw new Error('not legacy');
    const { graph } = legacyToElementGraph(a, 'rev1.json');
    expect(graph.nodeCount).toBeGreaterThan(400);
    const topo = elementGraphToBim(graph);
    expect(topo.loadPath.length).toBeGreaterThan(0);
    expect(topo.elementNodes.some((n) => n.demoDocuments && n.demoDocuments.length > 0)).toBe(true);
    // invented engineering numbers are not carried
    expect(topo.elementNodes.every((n) => n.utilization === undefined)).toBe(true);
  });

  it('diffs rev 1 against rev 2 with diffGraphs', () => {
    if (!isLegacyBimJson(a) || !isLegacyBimJson(b)) throw new Error('not legacy');
    const ga = legacyToElementGraph(a, 'rev1.json').graph.serialize();
    const gb = legacyToElementGraph(b, 'rev2.json').graph.serialize();
    const cmp = diffGraphs(ga, gb, { a: 1, b: 2 });
    expect(cmp.added.length).toBeGreaterThan(0);
    expect(diffGraphs(ga, ga).added.length + diffGraphs(ga, ga).removed.length + diffGraphs(ga, ga).changed.length).toBe(0);
  });
});
