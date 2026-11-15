// applyModelDiff lays the diff A -> B over revision B's view: ghosts are A-only elements, placed in a
// family of their own kind.
import { describe, expect, it } from 'vitest';
import type { BimNode, ElementTopology, ModelDiff } from '../types/bim';
import { PROJECT_NODE_ID } from '../loaders/elementGraphToBim';
import { applyModelDiff, mergeProject } from './mergeProject';

const node = (n: Partial<BimNode> & Pick<BimNode, 'id' | 'kind'>): BimNode => ({ label: n.id, level: 0, r: 8, x: 0, y: 0, ...n }) as BimNode;

/** Revision B (id 2): beam family B with B1, brace category with no family. */
function viewOfB(modelRevisionId: number) {
  const topology: ElementTopology = {
    projectName: 'P',
    elementNodes: [
      node({ id: PROJECT_NODE_ID, kind: 'project' }),
      node({ id: 'cat-beam', kind: 'category', parent: PROJECT_NODE_ID }),
      node({ id: 'cat-brace', kind: 'category', parent: PROJECT_NODE_ID }),
      node({ id: 'fam:beam:B', kind: 'family', label: 'B', elementKind: 'beam', parent: 'cat-beam', categoryParent: 'cat-beam' }),
      node({ id: 'B1', kind: 'element', label: 'B1', mark: 'B1', elementKind: 'beam', parent: 'fam:beam:B', categoryParent: 'cat-beam' }),
    ],
    hierarchyLinks: [],
    loadPath: [],
    connectivity: [],
  };
  return { ...mergeProject(topology, null, { source: 'project', projectId: 'p', modelFileUrl: null }), modelRevisionId };
}

const diff: ModelDiff = {
  a: 1,
  b: 2,
  meta: new Map([
    ['BR3', { status: 'removed', changes: [] }],
    ['B2', { status: 'removed', changes: [] }],
  ]),
  onlyInA: [
    { elementId: 'BR3', mark: 'B3', category: 'brace' },
    { elementId: 'B2', mark: 'B2', category: 'beam' },
  ],
  onlyInB: [],
  edgesAdded: 0,
  edgesRemoved: 0,
};

describe('applyModelDiff', () => {
  // the old version laid the diff over the head view whatever the pair, so with head != B every status was wrong
  it("refuses a view that is not revision B's", () => {
    expect(applyModelDiff(viewOfB(3), diff, { base: 'A', compare: 'B' })).toBeNull();
  });

  // the old version matched a ghost's family by label only: removed brace "B3" landed under beam family "B"
  it('places A-only elements as ghosts in a family of their own kind, drawn from A', () => {
    const r = applyModelDiff(viewOfB(2), diff, { base: 'A', compare: 'B' })!;
    const by = new Map(r.view.elementNodes.map((n) => [n.id, n]));
    expect(by.get('BR3')).toMatchObject({ parent: 'cat-brace', elementKind: 'brace', isGhost: true, diffStatus: 'removed' });
    expect(by.get('B2')).toMatchObject({ parent: 'fam:beam:B', elementKind: 'beam', isGhost: true });
    expect(by.get('B1')).toMatchObject({ diffStatus: 'unchanged' });
    expect(r.ghosts).toEqual([{ revisionId: 1, elementIds: ['BR3', 'B2'] }]);
    expect([r.summary.removedCount, r.summary.addedCount]).toEqual([2, 0]);
  });
});
