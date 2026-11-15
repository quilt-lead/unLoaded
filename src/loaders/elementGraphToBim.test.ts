import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { buildGraph, type ModelInput } from '@unloaded/element-graph';
import { parseIfc } from '@unloaded/ifc-parser';
import { elementGraphToBim, markFamily, PROJECT_NODE_ID } from './elementGraphToBim';
import { mergeProject } from '../data/mergeProject';
import { computeLoadPathTrace, getConnectivityNeighbors, isElementNode, isElementTypeNode, isFamilyNode, isProjectNode } from '../utils/graphEngine';
import type { CalcData, CalcLink } from '../types/bim';

const root = new URL('../../', import.meta.url);
const simpleFrame = JSON.parse(readFileSync(new URL('data/simple-frame.json', root), 'utf8')) as ModelInput;

describe('elementGraphToBim on simple-frame', () => {
  const { graph: eg } = buildGraph(simpleFrame);
  const topo = elementGraphToBim(eg);
  const byId = new Map(topo.elementNodes.map((n) => [n.id, n]));

  it('builds project -> kind category -> family -> element', () => {
    expect(topo.elementNodes.filter(isProjectNode)).toHaveLength(1);
    expect(topo.projectName).toBe('Simple frame fixture');
    const cats = topo.elementNodes.filter(isElementTypeNode).map((n) => n.id).sort();
    expect(cats).toEqual(['cat-beam', 'cat-col', 'cat-conn', 'cat-footing', 'cat-slab']);
    expect(topo.elementNodes.filter(isElementNode)).toHaveLength(simpleFrame.elements.length);
    // every element hangs off a family (a column stack or a mark family), every family off a category
    for (const el of topo.elementNodes.filter(isElementNode)) {
      const fam = byId.get(el.parent!);
      expect(fam && isFamilyNode(fam), el.id).toBe(true);
      expect(byId.get(fam!.parent!)?.kind).toBe('category');
      expect(el.categoryParent).toBe(fam!.parent);
    }
    const ids = new Set(topo.elementNodes.map((n) => n.id));
    for (const l of topo.hierarchyLinks) {
      expect(ids.has(l.source) && ids.has(l.target)).toBe(true);
    }
    expect(topo.hierarchyLinks.filter((l) => l.source === PROJECT_NODE_ID)).toHaveLength(cats.length);
  });

  it('maps marks, kinds and storeys onto element nodes', () => {
    const b1 = byId.get('B1')!;
    expect(b1.label).toBe('B101');
    expect(b1.elementKind).toBe('beam');
    expect(b1.categoryParent).toBe('cat-beam');
    expect(b1.storey).toBe('Level 1');
    expect(b1.storeyOrder).toBe(2);
    expect(byId.get('K1')!.elementKind).toBe('connection');
    expect(markFamily('2B13')).toBe('B');
    expect(markFamily('ST-1')).toBe('ST');
    expect(markFamily('')).toBeNull();
  });

  it('carries element-graph boxes for the 3D fallback', () => {
    expect(byId.get('F1')!.bbox).toBeDefined();
  });

  it('lays out every node', () => {
    expect(topo.elementNodes.every((n) => Number.isFinite(n.x) && Number.isFinite(n.y))).toBe(true);
  });

  it('emits directed load-path edges (source supported by target)', () => {
    const pairs = topo.loadPath.map((e) => `${e.source}->${e.target}`);
    expect(pairs).toContain('S1->B1');
    expect(pairs).toContain('B1->K1');
    expect(topo.loadPath.every((e) => e.rule.length > 0)).toBe(true);
  });

  it('traces the real load path down from the slab to the footings', () => {
    const { chainNodeIds } = computeLoadPathTrace(topo.loadPath, ['S1'], 'down', 16);
    expect([...chainNodeIds].sort()).toEqual(['B1', 'C1', 'C2', 'F1', 'F2', 'K1', 'K2', 'S1']);
    const up = computeLoadPathTrace(topo.loadPath, ['C1'], 'up', 16).chainNodeIds;
    expect(up.has('S1')).toBe(true);
    expect(up.has('F1')).toBe(false);
  });

  it('traces down a stacked column to its lower segment and footing', () => {
    const stacked: ModelInput = {
      meta: { version: 1, project: 'Stacked columns', units: 'm', source: { format: 'fixture', file: 'stacked-columns.json' } },
      levels: [
        { id: 'L0', name: 'Foundation', elevation: 0 },
        { id: 'L1', name: 'Level 1', elevation: 3.5 },
        { id: 'L2', name: 'Level 2', elevation: 7 },
      ],
      elements: [
        {
          id: 'F1',
          kind: 'footing',
          mark: 'F1',
          levelId: 'L0',
          params: {},
          geometry: { bbox: { min: [-0.75, -0.75, -0.6], max: [0.75, 0.75, 0] } },
          source: { format: 'fixture', nativeType: 'IfcFooting' },
        },
        {
          id: 'C1-L1',
          kind: 'column',
          mark: 'C1',
          levelId: 'L1',
          params: {},
          geometry: { bbox: { min: [-0.13, -0.13, 0], max: [0.13, 0.13, 3.5] } },
          source: { format: 'fixture', nativeType: 'IfcColumn' },
        },
        {
          id: 'C1-L2',
          kind: 'column',
          mark: 'C1',
          levelId: 'L2',
          params: {},
          geometry: { bbox: { min: [-0.13, -0.13, 3.5], max: [0.13, 0.13, 7] } },
          source: { format: 'fixture', nativeType: 'IfcColumn' },
        },
      ],
      relations: [
        { a: 'C1-L2', b: 'C1-L1', kind: 'supports', evidence: { rule: 'column-on-column support', source: 'explicit' } },
        { a: 'C1-L1', b: 'F1', kind: 'supports', evidence: { rule: 'column bears on footing', source: 'explicit' } },
      ],
      warnings: [],
    };
    const topology = elementGraphToBim(buildGraph(stacked, { infer: false }).graph);
    const trace = computeLoadPathTrace(topology.loadPath, ['C1-L2'], 'down', 16);

    expect(topology.elementNodes.some((n) => n.kind === 'family' && n.id.startsWith('stack-'))).toBe(true);
    expect(trace.chainNodeIds).toEqual(new Set(['C1-L2', 'C1-L1', 'F1']));
  });

  it('exposes beam <-> connection <-> column connectivity', () => {
    expect(getConnectivityNeighbors('K1', topo.connectivity).sort()).toEqual(['B1', 'C1']);
  });

  it('merges calc data onto elements by GlobalId', () => {
    const link: CalcLink = {
      elementId: 'B1',
      calcKey: 'beam-calc',
      confidence: 0.97,
      tier: 'exact',
      rule: 'Mark "B101" named in calc',
      matchedText: 'B101',
      review: 'auto',
      evidence: { page: 3, rects: [[1, 2, 3, 4]], snippet: null },
      role: 'design',
      band: 'high',
      reasons: [{ kind: 'tier', weight: 0.97, note: 'Mark named in calc', page: 3, rects: [[1, 2, 3, 4]] }],
      caveats: [],
      provenance: { producer: 'calc-mapper@0.1.0/matcher', rule: 'matcher.tier.exact', method: 'rule', inputs: [], actor: null, at: null },
      reviewProvenance: null,
    };
    const calc: CalcData = {
      projectName: null,
      modelName: 'frame.ifc',
      modelRevisionId: 1,
      calcPackageName: 'calcs.pdf',
      calcRevisionId: 2,
      engine: 'test',
      calcs: [
        {
          key: 'beam-calc',
          docId: null,
          docName: null,
          title: 'BEAM DESIGN',
          software: '',
          elementType: 'Beam',
          pages: [3],
          scanned: false,
          frontMatter: false,
          titleBox: null,
          color: '#4e79a7',
          regions: [{ page: 3, rect: [0, 0, 612, 792] }],
        },
      ],
      calcDependencies: [],
      calcNodes: [],
      calcLinks: [],
      calcToElementIds: new Map([['beam-calc', ['B1']]]),
      linksByElement: new Map([['B1', [link]]]),
      statusByElement: new Map([['B1', 'confirmed']]),
      groups: [],
      findings: [],
      producers: null,
      calcOrigin: 'pdf',
    };
    const view = mergeProject(topo, calc, { source: 'project', projectId: 'p1', modelFileUrl: null });
    const b1 = view.elementNodes.find((n) => n.id === 'B1')!;
    expect(b1.calcLinks).toEqual([link]);
    expect(b1.mappingStatus).toBe('confirmed');
    // a calc package is loaded, so an element the engine has no row for is unmapped
    expect(view.elementNodes.find((n) => n.id === 'C1')!.mappingStatus).toBe('unmapped');
    expect(view.counts.confirmed).toBe(1);
    expect(view.counts.unmapped).toBe(simpleFrame.elements.length - 1);
    // without calc data there is no mapping status at all
    const local = mergeProject(topo, null, { source: 'project', projectId: 'p1', modelFileUrl: null });
    expect(local.elementNodes.find((n) => n.id === 'B1')!.mappingStatus).toBeUndefined();
  });
});

describe('elementGraphToBim on the IFC sample (end to end)', async () => {
  const bytes = new Uint8Array(readFileSync(new URL('data/Building-Structural-IFC4.ifc', root)));
  const input = await parseIfc(bytes, { fileName: 'Building-Structural-IFC4.ifc' });
  const { graph: eg } = buildGraph(input);
  const topo = elementGraphToBim(eg);

  it('produces a laid-out node for every graph element', () => {
    expect(topo.elementNodes.filter(isElementNode)).toHaveLength(eg.nodeCount);
    expect(topo.elementNodes.every((n) => Number.isFinite(n.x) && Number.isFinite(n.y))).toBe(true);
  });

  it('every edge endpoint exists and every column stack holds columns', () => {
    const ids = new Set(topo.elementNodes.map((n) => n.id));
    for (const e of [...topo.loadPath, ...topo.connectivity]) {
      expect(ids.has(e.source), e.source).toBe(true);
      expect(ids.has(e.target), e.target).toBe(true);
    }
    for (const s of topo.elementNodes.filter((n) => n.id.startsWith('stack-'))) {
      const kids = topo.elementNodes.filter((n) => n.parent === s.id);
      expect(kids.length).toBeGreaterThan(0);
      expect(kids.every((k) => k.categoryParent === 'cat-col')).toBe(true);
    }
  });
});
