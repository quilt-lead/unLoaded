import { describe, expect, it } from 'vitest';
import type { LoadPathEdge } from '../types/bim';
import { computeLoadPathTrace } from './graphEngine';

const stackedColumnPath: LoadPathEdge[] = [
  { source: 'column-upper', target: 'column-lower', rule: 'column-on-column support' },
  { source: 'column-lower', target: 'footing-a', rule: 'column bears on footing' },
];

describe('computeLoadPathTrace', () => {
  it('traces down a stacked column to its footing and up through the stack', () => {
    const down = computeLoadPathTrace(stackedColumnPath, ['column-upper'], 'down', 16);
    expect(down.chainNodeIds).toEqual(new Set(['column-upper', 'column-lower', 'footing-a']));
    expect(down.chainLinkKeys).toEqual(new Set(['column-upper->column-lower', 'column-lower->footing-a']));

    const up = computeLoadPathTrace(stackedColumnPath, ['footing-a'], 'up', 16);
    expect(up.chainNodeIds).toEqual(new Set(['footing-a', 'column-lower', 'column-upper']));
  });

  it('respects the configured trace depth', () => {
    const trace = computeLoadPathTrace(stackedColumnPath, ['column-upper'], 'down', 1);
    expect(trace.chainNodeIds).toEqual(new Set(['column-upper', 'column-lower']));
    expect(trace.chainLinkKeys).toEqual(new Set(['column-upper->column-lower']));
  });
});
