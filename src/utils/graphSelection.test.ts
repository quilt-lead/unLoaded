import { describe, expect, it } from 'vitest';
import { selectNodesInBox, selectRectsInBox } from './graphSelection';

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

  it('uses horizontal drag direction when the box is drawn upward', () => {
    expect(selectNodesInBox(nodes, { x: 0, y: 10 }, { x: 14, y: 0 })).toEqual(['inside']);
    expect(selectNodesInBox(nodes, { x: 14, y: 0 }, { x: 0, y: 10 })).toEqual(['inside', 'touching']);
  });
});

describe('graph comment box selection', () => {
  const rects = [
    { id: 'inside', x: 1, y: 1, width: 4, height: 3 },
    { id: 'overlapping', x: 8, y: 2, width: 6, height: 3 },
    { id: 'outside', x: 20, y: 2, width: 4, height: 3 },
  ];

  it('selects only fully enclosed comments when dragging left to right', () => {
    expect(selectRectsInBox(rects, { x: 0, y: 0 }, { x: 10, y: 10 })).toEqual(['inside']);
  });

  it('selects comments touched by the box when dragging right to left', () => {
    expect(selectRectsInBox(rects, { x: 10, y: 10 }, { x: 0, y: 0 })).toEqual(['inside', 'overlapping']);
  });
});
