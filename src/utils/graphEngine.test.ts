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

  it('applies the selected step limit to upward and bidirectional traces', () => {
    const longPath = Array.from({ length: 20 }, (_, i) => ({
      source: `member-${i + 1}`,
      target: `member-${i}`,
      rule: 'supports',
    }));

    const limitedUp = computeLoadPathTrace(longPath, ['member-0'], 'up', 1);
    expect(limitedUp.chainNodeIds).toEqual(new Set(['member-0', 'member-1']));
    expect(limitedUp.chainLinkKeys).toEqual(new Set(['member-1->member-0']));

    const fullUp = computeLoadPathTrace(longPath, ['member-0'], 'up', 16);
    expect(fullUp.chainNodeIds.size).toBe(21);
    expect(fullUp.chainNodeIds.has('member-20')).toBe(true);
    expect(fullUp.chainLinkKeys.size).toBe(20);

    const both = computeLoadPathTrace(longPath, ['member-10'], 'both', 2);
    expect(both.chainNodeIds).toEqual(new Set(['member-8', 'member-9', 'member-10', 'member-11', 'member-12']));
  });
});
