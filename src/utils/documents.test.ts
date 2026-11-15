import { describe, expect, it } from 'vitest';
import { BimDocument, BimNode } from '../types/bim';
import { buildCalculationGraph, getAllDocumentsFlattened, getNodeDocuments } from './graphEngine';

const document: BimDocument = {
  id: 'beam-package',
  title: 'Beam calculations',
  type: 'Calculation (PDF)',
  code: 'B-01',
  rev: 'Rev C',
  pages: 8,
  date: '2026-11-14',
  summary: 'Beam design checks',
};

const element = (id: string, documents?: BimDocument[]): BimNode => ({
  id,
  label: id,
  type: 'IfcBeam',
  level: 2,
  r: 10,
  x: 0,
  y: 0,
  documents,
});

describe('mapped calculation documents', () => {
  it('does not invent documents or calculation mappings for an unmapped model', () => {
    const nodes = [element('B1'), element('B2', [])];
    expect(getNodeDocuments(null)).toEqual([]);
    expect(getAllDocumentsFlattened(nodes, null, false)).toEqual([]);

    const graph = buildCalculationGraph(nodes, 'Imported model');
    expect(graph.docToElementIds.size).toBe(0);
    expect(graph.calcNodes.filter((node) => node.id.startsWith('calc-doc-'))).toEqual([]);
  });

  it('preserves supplied document metadata without inventing revision history', () => {
    expect(getNodeDocuments(element('B1', [document]))).toEqual([document]);
    const withHistory = {
      ...document,
      revisions: [{ rev: 'Rev A', date: '2026-10-01', pages: 3, summary: 'Original checks' }],
    };
    expect(getNodeDocuments(element('B2', [withHistory]))).toEqual([withHistory]);
  });

  it('distinguishes no filter from a filter that matches no elements', () => {
    const nodes = [
      element('B1', [document]),
      { ...element('project', [{ ...document, id: 'project-package' }]), type: 'Project', level: 0 },
    ];
    expect(getAllDocumentsFlattened(nodes, null, false)).toHaveLength(2);
    expect(getAllDocumentsFlattened(nodes, new Set(), false)).toEqual([]);
  });

  it('keeps all mappings of a shared package when only one element matches', () => {
    const nodes = [
      element('B1', [document]),
      element('B2', [document]),
      element('B3', [{ ...document, id: 'other-package' }]),
    ];
    const filtered = getAllDocumentsFlattened(nodes, new Set(['B2']), false);
    expect(filtered).toHaveLength(1);
    expect(filtered[0].id).toBe('beam-package');
    expect(filtered[0].mappedElementIds).toEqual(['B1', 'B2']);
    expect(nodes[0].documents).toEqual([document]);
  });
});
