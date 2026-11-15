// A revision change within a project keeps what still exists; diff revisions are checked against the
// project before diff mode is entered.
import { describe, expect, it } from 'vitest';
import type { BimNode, CalcPackage, RevisionInfo } from '../types/bim';
import { diffRevisionsError, keepWhatExists, type PointerState } from './viewState';

const node = (id: string, kind: BimNode['kind'] = 'element') => ({ id, kind }) as BimNode;
const calc = (key: string) => ({ key }) as CalcPackage;
const view = (elements: string[], calcKeys: string[] = []) => ({
  elementNodes: [node('project', 'project'), ...elements.map((id) => node(id))],
  calcNodes: calcKeys.map((k) => node(`calc:${k}`, 'calc')),
  calcs: calcKeys.map(calc),
});
const pointers = (p: Partial<PointerState> = {}): PointerState => ({
  selectedNodeId: null,
  selectedNodeIds: new Set(),
  selectedCalcNodeId: null,
  selectedCalcNodeIds: new Set(),
  calcAnchorKey: null,
  impactReq: null,
  pdfTarget: null,
  ...p,
});

describe('keepWhatExists: the revision on screen changed', () => {
  // the old App reset selection, impact and PDF target on every revision change (entering a diff,
  // each swap, leaving it); a reset returns empty pointers, which every case below rejects
  it('keeps every pointer whose target is in the new view, as the same object', () => {
    const s = pointers({
      selectedNodeId: 'C1',
      selectedNodeIds: new Set(['C1', 'B2']),
      selectedCalcNodeId: 'calc:k1',
      selectedCalcNodeIds: new Set(['calc:k1']),
      calcAnchorKey: 'k1',
      impactReq: { gid: 'C1', mode: 'remove' },
      pdfTarget: { calcKey: 'k1', page: 2, rects: [] },
    });
    expect(keepWhatExists(s, view(['C1', 'B2', 'C8'], ['k1']))).toBe(s);
  });

  it('drops only what the new revision does not have', () => {
    const s = pointers({
      selectedNodeId: 'C8',
      selectedNodeIds: new Set(['C1', 'C8']),
      impactReq: { gid: 'C8', mode: 'change' },
      pdfTarget: { calcKey: 'gone', page: 1, rects: [] },
      calcAnchorKey: 'k1',
      selectedCalcNodeId: 'map:k1:C8',
      selectedCalcNodeIds: new Set(['map:k1:C8', 'calc:k1']),
    });
    const next = keepWhatExists(s, view(['C1'], ['k1']));
    expect(next.selectedNodeId).toBe('C1');
    expect([...next.selectedNodeIds]).toEqual(['C1']);
    expect(next.impactReq).toBeNull();
    expect(next.pdfTarget).toBeNull();
    expect(next.calcAnchorKey).toBe('k1');
    expect(next.selectedCalcNodeId).toBeNull(); // satellite of an element B does not have
    expect([...next.selectedCalcNodeIds]).toEqual(['calc:k1']);
  });

  it('a satellite of a kept anchor and a kept element stays; one of a dropped anchor does not', () => {
    const s = pointers({ calcAnchorKey: 'k1', selectedCalcNodeId: 'map:k1:C1', selectedCalcNodeIds: new Set(['map:k1:C1']) });
    expect(keepWhatExists(s, view(['C1'], ['k1']))).toBe(s);
    const next = keepWhatExists(s, view(['C1'], ['k2']));
    expect([next.calcAnchorKey, next.selectedCalcNodeId, next.selectedCalcNodeIds.size]).toEqual([null, null, 0]);
  });
});

const rev = (id: number, kind: 'model' | 'calcs') => ({ id, kind }) as RevisionInfo;

describe('diffRevisionsError: the one check before diff mode', () => {
  const revs = [rev(1, 'model'), rev(2, 'calcs'), rev(3, 'model')];
  it('accepts two model revisions of the project', () => {
    expect(diffRevisionsError(revs, 1, 3)).toBeNull();
    expect(diffRevisionsError(revs, 3, 1)).toBeNull();
  });
  // the old deep link entered diff mode on any two finite numbers: B from another browser's store,
  // or a calc revision, failed B's view and left a blank workspace with no way out
  it.each([
    [1, 99, /#99 is not a revision of this project/],
    [1, 2, /#2 is a calc package/],
    [3, 3, /same revision/],
    [1, 1.5, /whole numbers/],
  ])('refuses (%s, %s)', (a, b, why) => {
    expect(diffRevisionsError(revs, a, b)).toMatch(why);
  });
  it('refuses while the revisions are unknown', () => {
    expect(diffRevisionsError(null, 1, 3)).toMatch(/not loaded/);
  });
});
