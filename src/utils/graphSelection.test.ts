import { describe, expect, it } from 'vitest';
import { selectNodesInBox } from './graphSelection';

const nodes = [
  { id: 'inside', x: 5, y: 5, r: 2 },
  { id: 'touching', x: 12, y: 5, r: 3 },
  { id: 'outside', x: 20, y: 5, r: 2 },
];

describe('graph box selection', () => {
  it('selects only fully enclosed nodes when dragging left to right', () => {
    expect(selectNodesInBox(nodes, { x: 0, y: 0 }, { x: 10, y: 10 })).toEqual(['inside']);
  });

  it('selects nodes touched by the box when dragging right to left', () => {
    expect(selectNodesInBox(nodes, { x: 15, y: 10 }, { x: 0, y: 0 })).toEqual(['inside', 'touching']);
  });

  it('uses the same direction rule when dragging upward', () => {
    expect(selectNodesInBox(nodes, { x: 15, y: 10 }, { x: 0, y: 0 })).toEqual(['inside', 'touching']);
    expect(selectNodesInBox(nodes, { x: 0, y: 10 }, { x: 14, y: 0 })).toEqual(['inside']);
  });
});
