import { describe, expect, it } from 'vitest';
import type { BimNode } from '../types/bim';
import { computeLoadPathTrace } from './graphEngine';

const stackNodes: BimNode[] = [
  {
    id: 'stack-a',
    label: 'Column Stack A',
    type: 'ColumnStack',
    level: 1.5,
    floorNum: 0,
    r: 15,
    x: 0,
    y: 0,
  },
  {
    id: 'column-lower',
    label: 'Column A L01',
    type: 'Column',
    level: 2,
    parent: 'stack-a',
    floorNum: 1,
    r: 11,
    x: 0,
    y: 0,
  },
  {
    id: 'column-upper',
    label: 'Column A L02',
    type: 'Column',
    level: 2,
    parent: 'stack-a',
    floorNum: 2,
    r: 11,
    x: 0,
    y: 0,
  },
  {
    id: 'footing-a',
    label: 'Footing A',
    type: 'Footing',
    level: 2,
    floorNum: 0,
    r: 11,
    x: 0,
    y: 0,
  },
];

describe('computeLoadPathTrace', () => {
  it('traces down a column stack to its footing and up through the stack', () => {
    const rawLinks = [{ source: 'column-lower', target: 'footing-a' }];

    const down = computeLoadPathTrace(stackNodes, rawLinks, ['column-upper'], 'down', 16);
    expect(down.chainNodeIds).toEqual(new Set(['column-upper', 'column-lower', 'footing-a']));

    const up = computeLoadPathTrace(stackNodes, rawLinks, ['footing-a'], 'up', 16);
    expect(up.chainNodeIds).toEqual(new Set(['footing-a', 'column-lower', 'column-upper']));
  });

  it('does not add a shortcut when the stack already has a support path', () => {
    const rawLinks = [
      { source: 'column-upper', target: 'column-lower', relation: 'load-path' as const },
      { source: 'column-lower', target: 'footing-a', relation: 'load-path' as const },
    ];

    const trace = computeLoadPathTrace(stackNodes, rawLinks, ['column-upper'], 'down', 16);
    expect(trace.chainLinkKeys).toEqual(
      new Set(['column-upper->column-lower', 'column-lower->footing-a'])
    );
  });
});
