import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { buildGraph, type ModelInput } from '@unloaded/element-graph';
import { parseIfc } from '@unloaded/ifc-parser';
import { elementGraphToBim } from './elementGraphToBim';
import {
  computeLoadPathTrace,
  getDirectConnectivityNeighbors,
  isColumnStackNode,
  isElementTypeNode,
  isInstanceNode,
  isProjectNode,
} from '../utils/graphEngine';

const root = new URL('../../', import.meta.url);
const simpleFrame = JSON.parse(readFileSync(new URL('data/simple-frame.json', root), 'utf8')) as ModelInput;

describe('elementGraphToBim on simple-frame', () => {
  const { graph: eg } = buildGraph(simpleFrame);
  const { graph, rawLinks } = elementGraphToBim(eg);
  const byId = new Map(graph.nodes.map((n) => [n.id, n]));

  it('builds the Project -> Category -> Instance hierarchy the UI expects', () => {
    expect(graph.nodes.filter(isProjectNode)).toHaveLength(1);
    expect(graph.projectName).toBe('Simple frame fixture');
    const cats = graph.nodes.filter(isElementTypeNode).map((n) => n.id).sort();
    expect(cats).toEqual(['cat-beam', 'cat-col', 'cat-conn', 'cat-footing', 'cat-slab']);
    expect(graph.nodes.filter(isInstanceNode)).toHaveLength(simpleFrame.elements.length);
  });

  it('maps marks, levels and categories onto instance nodes', () => {
    const b1 = byId.get('B1')!;
    expect(b1.label).toBe('B101');
    expect(b1.parent).toBe('cat-beam');
    expect(b1.floor).toBe('Level 1');
    expect(b1.floorNum).toBe(2);
    expect(byId.get('K1')!.shape3d).toBe('joint');
  });

  it('converts bbox to feet, Y-up, base at zero', () => {
    const f1 = byId.get('F1')!;
    expect(f1.size3d![0]).toBeCloseTo(1.5 * 3.28084, 3);
    expect(f1.size3d![1]).toBeCloseTo(0.6 * 3.28084, 3); // depth becomes the Y (up) extent
    const minY = Math.min(...graph.nodes.filter((n) => n.pos3d && n.size3d).map((n) => n.pos3d![1] - n.size3d![1] / 2));
    expect(minY).toBeCloseTo(0, 6);
  });

  it('emits directed load-path links (source supported by target)', () => {
    expect(rawLinks).toContainEqual({ source: 'S1', target: 'B1', relation: 'load-path' });
    expect(rawLinks).toContainEqual({ source: 'B1', target: 'K1', relation: 'load-path' });
  });

  it('traces the real load path down from the slab to the footings', () => {
    const { chainNodeIds } = computeLoadPathTrace(graph.nodes, rawLinks, ['S1'], 'down', 16);
    expect([...chainNodeIds].sort()).toEqual(['B1', 'C1', 'C2', 'F1', 'F2', 'K1', 'K2', 'S1']);
    const up = computeLoadPathTrace(graph.nodes, rawLinks, ['C1'], 'up', 16).chainNodeIds;
    expect(up.has('S1')).toBe(true);
    expect(up.has('F1')).toBe(false);
  });

  it('exposes beam <-> connection <-> column connectivity', () => {
    const k1 = getDirectConnectivityNeighbors('K1', graph.nodes, rawLinks).map((n) => n.id).sort();
    expect(k1).toEqual(['B1', 'C1']);
  });
});

describe('elementGraphToBim on the IFC sample (end to end)', async () => {
  const bytes = new Uint8Array(
    readFileSync(new URL('data/Building-Structural-IFC4.ifc', root))
  );
  const input = await parseIfc(bytes, { fileName: 'Building-Structural-IFC4.ifc' });
  const { graph: eg } = buildGraph(input);
  const { graph, rawLinks } = elementGraphToBim(eg);

  it('produces a laid-out graph with 3D boxes for every element with geometry', () => {
    const instances = graph.nodes.filter(isInstanceNode);
    expect(instances).toHaveLength(eg.nodeCount);
    const withGeom = eg.nodes().filter((n) => n.geometry).length;
    expect(instances.filter((n) => n.pos3d && n.size3d)).toHaveLength(withGeom);
    expect(graph.nodes.every((n) => Number.isFinite(n.x) && Number.isFinite(n.y))).toBe(true);
  });

  it('every link endpoint exists and every stack holds columns', () => {
    const ids = new Set(graph.nodes.map((n) => n.id));
    for (const l of rawLinks) {
      expect(ids.has(l.source), l.source).toBe(true);
      expect(ids.has(l.target), l.target).toBe(true);
    }
    for (const s of graph.nodes.filter(isColumnStackNode)) {
      const kids = graph.nodes.filter((n) => n.parent === s.id);
      expect(kids.length).toBeGreaterThan(0);
      expect(kids.every((k) => k.categoryParent === 'cat-col')).toBe(true);
    }
  });
});
