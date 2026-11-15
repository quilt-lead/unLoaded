import { describe, expect, it } from 'vitest';
import { legacyToElementGraph, type LegacyBimJson } from '../loaders/legacyBimJson';
import { elementGraphToBim } from '../loaders/elementGraphToBim';
import { mergeProject } from '../data/mergeProject';

// Ported from prod. Prod's version tested `getNodeDocuments`, `getAllDocumentsFlattened` and
// `buildCalculationGraph` in graphEngine.ts; this branch deleted all three with `BimNode.documents`
// (D6): calc documents and calc mappings come only from a calc package (packages/calc-mapper ->
// src/data/loadProject.ts), and a legacy demo JSON's documents enter once, through
// legacyToElementGraph -> elementGraphToBim, as `demoDocuments` labelled demo data (D19).
// What is tested here is the same promise on that one path: nothing is invented - no documents, no
// revision histories, no calc mappings - and supplied documents keep their metadata and every element
// they are attached to.
// Not ported: "null filter vs empty match set" for getAllDocumentsFlattened. There is no flattened
// document list filtered by the workspace match set on this branch; the PDF view lists the calc
// package's calcs, and its search is covered in src/components/DocumentBrowser.test.tsx.
const doc = {
  id: 'beam-package',
  title: 'Beam calculations',
  type: 'Calculation (PDF)',
  code: 'B-01',
  rev: 'Rev C',
  pages: 8,
  date: '2026-11-14',
  summary: 'Beam design checks',
};

const beam = (id: string, x: number, documents?: Record<string, unknown>[]) => ({
  id,
  label: id,
  type: 'Instance',
  level: 2,
  parent: 'cat-beam',
  floor: 'L2',
  floorNum: 2,
  pos3d: [x, 20, 0],
  size3d: [20, 1.5, 1],
  documents,
});

const model = (nodes: ReturnType<typeof beam>[]): LegacyBimJson => ({
  projectName: 'Docs test',
  nodes: [{ id: 'cat-beam', label: 'IfcBeam', type: 'Category', level: 1 }, ...nodes],
});

const view = (json: LegacyBimJson) => {
  const { graph } = legacyToElementGraph(json, 'docs-test.json');
  const topo = elementGraphToBim(graph);
  return mergeProject(topo, null, { source: 'project', projectId: 'p', modelFileUrl: null });
};

describe('documents on the one model path', () => {
  it('does not invent documents or calculation mappings for an unmapped model', () => {
    const v = view(model([beam('B1', 0), beam('B2', 40, [])]));
    const els = v.elementNodes.filter((n) => n.kind === 'element');
    expect(els).toHaveLength(2);
    expect(els.every((n) => n.demoDocuments === undefined)).toBe(true);
    expect(els.every((n) => (n.calcLinks ?? []).length === 0 && n.mappingStatus === undefined)).toBe(true);
    expect(v.calcs).toEqual([]);
    expect(v.calcNodes).toEqual([]);
    expect(v.calcToElementIds.size).toBe(0);
    expect(v.hasDemoData).toBe(false);
  });

  it('uses a neutral root label when no project name is available', () => {
    const graph = buildCalculationGraph([], '');

    expect(graph.calcNodes.find((node) => node.id === 'calc-root')?.label).toBe('Calculation Graph');
  });

  it('preserves supplied document metadata without inventing revision history', () => {
    const withHistory = { ...doc, id: 'other-package', revisions: [{ rev: 'Rev A', date: '2026-10-01', pages: 3 }] };
    const v = view(model([beam('B1', 0, [doc]), beam('B2', 40, [withHistory])]));
    const b1 = v.elementNodes.find((n) => n.id === 'B1')!;
    expect(b1.demoDocuments).toEqual([doc]);
    const b2 = v.elementNodes.find((n) => n.id === 'B2')!;
    expect(b2.demoDocuments).toHaveLength(1);
    expect(b2.demoDocuments![0]).not.toHaveProperty('revisions');
    expect(b2.demoDocuments![0].rev).toBe('Rev C');
    // demo documents are labelled demo data and are never calc links
    expect(v.hasDemoData).toBe(true);
    expect(v.calcToElementIds.size).toBe(0);
    expect((b1.calcLinks ?? []).length).toBe(0);
  });

  it('keeps a shared package on every element it is attached to', () => {
    const v = view(model([beam('B1', 0, [doc]), beam('B2', 40, [doc]), beam('B3', 80, [{ ...doc, id: 'other-package' }])]));
    const holders = v.elementNodes.filter((n) => n.demoDocuments?.some((d) => d.id === 'beam-package')).map((n) => n.id);
    expect(holders.sort()).toEqual(['B1', 'B2']);
  });
});
