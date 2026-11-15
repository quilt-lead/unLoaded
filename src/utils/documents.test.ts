import { describe, expect, it } from 'vitest';
import { buildGraph, type ModelInput } from '@unloaded/element-graph';
import { bundleExport, makeBundle, parseBundle, type BundleCalcGraph } from '@unloaded/calc-mapper';
import { elementGraphToBim } from '../loaders/elementGraphToBim';
import { toCalcData } from '../data/loadProject';
import { mergeProject } from '../data/mergeProject';

// Ported from prod. Prod's version tested `getNodeDocuments`, `getAllDocumentsFlattened` and
// `buildCalculationGraph` in graphEngine.ts; this branch deleted all three with `BimNode.documents`
// (D6): calc documents and calc mappings come only from a calc package (packages/calc-mapper ->
// src/data/loadProject.ts) or from a model bundle's calc graph (bundle.ts). Demo documents used to be
// inspector-only notes from legacy JSON; they are now a bundle's demo calc graph, labelled demo data.
// What is tested here is the same promise on that one path: nothing is invented - no calcs, no
// revision histories, no calc mappings - and supplied calcs keep their metadata and every element
// they are linked to.
// Not ported: "null filter vs empty match set" for getAllDocumentsFlattened. There is no flattened
// document list filtered by the workspace match set on this branch; the PDF view lists the calcs,
// and its search is covered in src/components/DocumentBrowser.test.tsx.
const model = (): ModelInput => ({
  meta: { version: 1, project: 'Docs test', units: 'm', source: { format: 'test' } },
  levels: [{ id: 'L2', name: 'L2', elevation: 6 }],
  elements: ['B1', 'B2', 'B3'].map((id, i) => ({
    id,
    kind: 'beam',
    mark: id,
    levelId: 'L2',
    params: {},
    geometry: { bbox: { min: [i * 12, 0, 6], max: [i * 12 + 6, 0.3, 6.4] } },
    source: { format: 'test' },
  })),
  relations: [],
  warnings: [],
});

const beamCalc = { key: 'beam-package', title: 'Beam calculations', cat: 'Beam' as const, code: 'B-01', rev: 'Rev C', date: '2026-11-14', summary: 'Beam design checks' };

const view = async (calcGraph: BundleCalcGraph | null) => {
  const { graph } = buildGraph(model());
  const b = parseBundle(JSON.parse(JSON.stringify(makeBundle(graph.serialize(), calcGraph, { demo: true }))));
  const calc = b.calcGraph ? toCalcData(await bundleExport(b.elementGraph, b.calcGraph)) : null;
  return mergeProject(elementGraphToBim(graph), calc, { source: 'project', projectId: 'p', modelFileUrl: null });
};

describe('calcs on the one model path', () => {
  it('does not invent calcs or calculation mappings for a model without a calc graph', async () => {
    const v = await view(null);
    const els = v.elementNodes.filter((n) => n.kind === 'element');
    expect(els).toHaveLength(3);
    expect(els.every((n) => (n.calcLinks ?? []).length === 0 && n.mappingStatus === undefined)).toBe(true);
    expect(v.calcs).toEqual([]);
    expect(v.calcNodes).toEqual([]);
    expect(v.calcToElementIds.size).toBe(0);
    expect(v.calcOrigin).toBeNull();
    expect(v.hasDemoData).toBe(false);
  });

  it('keeps supplied calc metadata without inventing revision history, labelled as demo data', async () => {
    const v = await view({
      source: { kind: 'demo' },
      calcs: [beamCalc],
      edges: [],
      links: [{ element: 'B1', calc: 'beam-package', role: 'design', review: 'auto' }],
    });
    expect(v.calcs).toHaveLength(1);
    expect(v.calcs[0]).toMatchObject({ key: 'beam-package', title: 'Beam calculations', meta: { code: 'B-01', rev: 'Rev C', date: '2026-11-14' } });
    expect(v.calcs[0]).not.toHaveProperty('revisions');
    expect(v.calcs[0]!.pages).toEqual([]); // no PDF: no pages are invented
    expect(v.hasDemoData).toBe(true);
    // the other elements are unmapped, not given a calc
    expect(v.elementNodes.find((n) => n.id === 'B2')!.calcLinks).toEqual([]);
  });

  it('keeps a shared calc on every element it is linked to', async () => {
    const v = await view({
      source: { kind: 'demo' },
      calcs: [beamCalc, { key: 'other-package', title: 'Other', cat: 'Beam' }],
      edges: [],
      links: [
        { element: 'B1', calc: 'beam-package', role: 'design', review: 'auto' },
        { element: 'B2', calc: 'beam-package', role: 'design', review: 'auto' },
        { element: 'B3', calc: 'other-package', role: 'design', review: 'auto' },
      ],
    });
    expect(v.calcToElementIds.get('beam-package')?.sort()).toEqual(['B1', 'B2']);
    expect(v.calcToElementIds.get('other-package')).toEqual(['B3']);
  });
});
