import { describe, expect, it } from 'vitest';
import { getEffectiveNodeColor, getHeatmapColor } from './colors';
import type { BimNode } from '../types/bim';

describe('utilization heatmap', () => {
  it.each([undefined, NaN, Infinity, -Infinity])('shows unknown utilization (%s) in neutral gray', (utilization) => {
    expect(getHeatmapColor(utilization)).toBe('#71717a');
  });

  it('keeps reported zero and overload values on the utilization scale', () => {
    expect(getHeatmapColor(0)).toBe('#06b6d4');
    expect(getHeatmapColor(1.25)).toBe('#ef4444');
    expect(getHeatmapColor(0.5)).not.toBe(getHeatmapColor(undefined));
  });

  it('uses neutral gray for imported elements without utilization while retaining diff colors', () => {
    const node: BimNode = { id: 'beam-1', label: 'B101', type: 'IfcBeam', level: 2, x: 0, y: 0, r: 10 };
    expect(getEffectiveNodeColor(node, true)).toBe('#71717a');
    expect(getEffectiveNodeColor({ ...node, diffStatus: 'added' }, true, true)).toBe('#14AE5C');
    expect(getEffectiveNodeColor({ ...node, diffStatus: 'removed' }, true, true)).toBe('#ef4444');
  });
});
