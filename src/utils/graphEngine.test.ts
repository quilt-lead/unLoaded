import { describe, expect, it } from 'vitest';
import type { BimNode, LoadPathEdge } from '../types/bim';
import { computeLoadPathTrace, computeRadialLayout, getCalcBubbleLayout } from './graphEngine';

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

describe('calc graph bubble layout', () => {
  it('wraps long labels and gives them enough radius', () => {
    const short = getCalcBubbleLayout('S-501');
    const label = 'S-102 Pile Cap & Caisson';
    const long = getCalcBubbleLayout(label);

    expect(long.lines.join(' ')).toBe(label);
    expect(Math.max(...long.lines.map((line) => line.length))).toBeLessThanOrEqual(12);
    const widestLine = Math.max(...long.lines.map((line) => line.length * long.fontSize * 0.6));
    const halfHeight = ((long.lines.length - 1) * long.lineHeight) / 2 + long.fontSize / 2;
    expect(Math.hypot(widestLine / 2, halfHeight)).toBeLessThanOrEqual(long.radius);
    expect(long.radius).toBeGreaterThan(short.radius);
  });

  it('spaces enlarged calculation bubbles without collisions', () => {
    const categoryLabel = 'Beam calcs';
    const nodes: BimNode[] = [
      { id: 'root', label: 'Calc package', kind: 'calc-root', level: 0, r: 36, x: 0, y: 0 },
      {
        id: 'beam-calcs',
        label: categoryLabel,
        kind: 'calc-category',
        level: 1,
        parent: 'root',
        r: Math.max(26, getCalcBubbleLayout(categoryLabel).radius),
        x: 0,
        y: 0,
      },
      ...Array.from({ length: 30 }, (_, index) => {
        const label = `S-${300 + index} L0${(index % 5) + 1} Grid Line ${index + 1} Girder`;
        return {
          id: `calc-${index}`,
          label,
          kind: 'calc' as const,
          level: 2,
          parent: 'beam-calcs',
          r: getCalcBubbleLayout(label).radius,
          x: 0,
          y: 0,
        };
      }),
    ];

    const laidOut = computeRadialLayout(nodes).filter((node) => node.kind === 'calc');
    for (let i = 0; i < laidOut.length; i++) {
      for (let j = i + 1; j < laidOut.length; j++) {
        const a = laidOut[i];
        const b = laidOut[j];
        expect(Math.hypot(a.x - b.x, a.y - b.y)).toBeGreaterThanOrEqual(a.r + b.r);
      }
    }
  });
});
