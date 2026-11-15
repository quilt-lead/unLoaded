import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { ElementGraph } from '@unloaded/element-graph';
import { bundleExport, diffGraphs, parseBundle } from '@unloaded/calc-mapper';
import { importModel } from './parsers';
import { elementGraphToBim } from './elementGraphToBim';
import { toCalcData } from '../data/loadProject';
import { mergeProject } from '../data/mergeProject';

// The Harborview A/B demo as model bundles (scripts/convert-legacy-demo.ts made them from Noah's legacy
// JSON). The element counts and the A/B diff are the ones the legacy in-app loader gave, so the demo
// diff is unchanged by the conversion.
const root = new URL('../../', import.meta.url);
const bytes = (f: string) => new Uint8Array(readFileSync(new URL(f, root)));
const A = 'data/harborview/harborview-tower-rev1-base.bundle.json';
const B = 'data/harborview/harborview-tower-rev2-compare.bundle.json';
const bundle = (f: string) => parseBundle(new TextDecoder().decode(bytes(f)));

describe('Harborview demo model bundles', () => {
  it('are valid bundles: the element graph and a demo calc graph side by side', () => {
    const a = bundle(A);
    const b = bundle(B);
    expect(a.meta).toMatchObject({ project: 'Harborview Corporate Center', label: 'Rev 1 base', demo: true });
    expect(b.meta.label).toBe('Rev 2 compare');
    expect([a.elementGraph.nodes.length, b.elementGraph.nodes.length]).toEqual([420, 488]);
    expect([a.elementGraph.edges.length, b.elementGraph.edges.length]).toEqual([1773, 2118]);
    expect(a.calcGraph?.source).toEqual({ kind: 'demo' });
    expect([a.calcGraph!.calcs.length, b.calcGraph!.calcs.length]).toEqual([78, 85]);
    // every element of the demo has its one design link
    expect(a.calcGraph!.links.length).toBe(420);
  });

  it('diffs rev 1 against rev 2 as the legacy loader did (70 added, 2 removed, 29 modified)', () => {
    const cmp = diffGraphs(bundle(A).elementGraph, bundle(B).elementGraph, { a: 1, b: 2 });
    expect([cmp.added.length, cmp.removed.length, cmp.changed.length]).toEqual([70, 2, 29]);
  });

  it('opens as a model with its calc graph, and shows demo calcs in the calc graph labelled as demo data', async () => {
    const res = await importModel('harborview-tower-rev1-base.bundle.json', bytes(A), () => {});
    if (res.kind !== 'model') throw new Error('not a model');
    expect(res.format).toBe('bundle');
    expect(res.elementGraph.nodeCount).toBe(420);
    const exp = await bundleExport(res.elementGraph.serialize(), res.calcGraph!);
    const view = mergeProject(elementGraphToBim(ElementGraph.deserialize(res.elementGraph.serialize())), toCalcData(exp), {
      source: 'project',
      projectId: 'p',
      modelFileUrl: null,
    });
    expect(view.calcOrigin).toBe('bundle-demo');
    expect(view.hasDemoData).toBe(true);
    expect(view.calcs).toHaveLength(78);
    expect(view.calcNodes.find((n) => n.kind === 'calc-root')?.label).toBe('Demo calcs');
    const cap = view.elementNodes.find((n) => n.id === 'pcap-A1')!;
    expect(cap.calcLinks?.[0]).toMatchObject({ calcKey: 'doc-fdn-a1', role: 'design' });
    expect(view.calcToElementIds.get('doc-fdn-a1')?.sort()).toEqual(['pcap-A1', 'pile-A1']);
    expect(view.calcs.find((c) => c.key === 'doc-fdn-a1')?.meta?.code).toBe('ACI 318-19 Ch.13');
  });

  it('refuses the retired legacy format with a pointer to the converter', async () => {
    const legacy = new TextEncoder().encode(JSON.stringify({ projectName: 'x', nodes: [{ id: 'a' }], links: [] }));
    await expect(importModel('old.json', legacy, () => {})).rejects.toThrow(/convert-legacy-demo/);
  });
});
