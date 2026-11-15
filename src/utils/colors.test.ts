import { describe, expect, it } from 'vitest';
import { NO_DATA_COLOR, getEffectiveNodeColor, getHeatmapColor } from './colors';
import type { BimNode } from '../types/bim';

describe('utilization heatmap', () => {
  it.each([undefined, NaN, Infinity, -Infinity])('shows unknown utilization (%s) in the neutral no-data colour', (utilization) => {
    expect(getHeatmapColor(utilization)).toBe(NO_DATA_COLOR);
  });

  it('keeps reported zero and overload values on the utilization scale', () => {
    expect(getHeatmapColor(0)).toBe('#06b6d4');
    expect(getHeatmapColor(1.25)).toBe('#ef4444');
    expect(getHeatmapColor(0.5)).not.toBe(getHeatmapColor(undefined));
  });

  it('uses the no-data colour for imported elements without utilization while retaining diff colors', () => {
    const node: BimNode = { id: 'beam-1', label: 'B101', kind: 'element', ifcType: 'IfcBeam', level: 2, x: 0, y: 0, r: 10 };
    expect(getEffectiveNodeColor(node, 'utilisation')).toBe(NO_DATA_COLOR);
    expect(getEffectiveNodeColor({ ...node, utilization: NaN }, 'utilisation')).toBe(NO_DATA_COLOR);
    expect(getEffectiveNodeColor({ ...node, diffStatus: 'removed' }, 'utilisation', true)).toBe('#ef4444');
  });
});
