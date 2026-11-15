import { describe, expect, it } from 'vitest';
import {
  DIFF_PALETTE,
  GRAPH_NODE_PALETTE,
  KIND_PALETTE,
  NO_DATA_COLOR,
  PROJECT_COLOR,
  getContrastingTextStyle,
  getEffectiveNodeColor,
  getHeatmapColor,
} from './colors';
import type { BimNode } from '../types/bim';

describe('node colors', () => {
  it('keeps the supplied swatches and interpolated steps distinct', () => {
    expect(GRAPH_NODE_PALETTE.slice(0, 6)).toEqual([
      '#FF1493',
      '#A3D900',
      '#00AEEF',
      '#FF8A00',
      '#FF5E7E',
      '#FFAE42',
    ]);
    expect(new Set(GRAPH_NODE_PALETTE).size).toBe(GRAPH_NODE_PALETTE.length);
    expect(new Set(Object.values(KIND_PALETTE)).size).toBe(Object.keys(KIND_PALETTE).length);
  });

  it('reserves gray for both graph roots and uses the same kind color across node levels', () => {
    const root: BimNode = { id: 'project', label: 'Project', kind: 'project', level: 0, x: 0, y: 0, r: 36 };
    const category: BimNode = { id: 'cat-col', label: 'Columns', kind: 'category', elementKind: 'column', level: 1, x: 0, y: 0, r: 26 };
    const family: BimNode = { id: 'stack-01', label: 'C1', kind: 'family', elementKind: 'column', level: 1.5, x: 0, y: 0, r: 15 };
    const element: BimNode = { id: 'column-1', label: 'C1', kind: 'element', elementKind: 'column', level: 2, x: 0, y: 0, r: 8 };

    expect(getEffectiveNodeColor(root)).toBe(PROJECT_COLOR);
    expect(PROJECT_COLOR).toBe('#D8D3D8');
    expect(getEffectiveNodeColor({ ...root, kind: 'calc-root' }, 'utilisation', true)).toBe(PROJECT_COLOR);
    expect(getEffectiveNodeColor(category)).toBe(KIND_PALETTE.column);
    expect(getEffectiveNodeColor(family)).toBe(KIND_PALETTE.column);
    expect(getEffectiveNodeColor(element)).toBe(KIND_PALETTE.column);
    expect(getEffectiveNodeColor({ ...element, ifcType: 'IfcColumn', elementKind: undefined })).toBe(KIND_PALETTE.column);
  });

  it('maps calculation categories to their corresponding structural category', () => {
    const calcCategory = (label: string) =>
      getEffectiveNodeColor({ id: `calccat:${label}`, label, kind: 'calc-category', level: 1, x: 0, y: 0, r: 26 });

    expect(calcCategory('Beam calcs')).toBe(KIND_PALETTE.beam);
    expect(calcCategory('Column calcs')).toBe(KIND_PALETTE.column);
    expect(calcCategory('Connection & Fastener calcs')).toBe(KIND_PALETTE.connection);
    expect(calcCategory('Slab & Punching Shear calcs')).toBe(KIND_PALETTE.slab);
    expect(calcCategory('Shear Wall & Lateral calcs')).toBe(KIND_PALETTE.wall);
    expect(calcCategory('Foundation & Geotech calcs')).toBe(KIND_PALETTE.footing);
  });

  it('shows unmapped elements in red in review mode while keeping missing status distinct', () => {
    const element: BimNode = { id: 'beam-1', label: 'B101', kind: 'element', elementKind: 'beam', level: 2, x: 0, y: 0, r: 8 };

    expect(getEffectiveNodeColor({ ...element, mappingStatus: 'unmapped' }, 'review')).toBe('#ef4444');
    expect(getEffectiveNodeColor(element, 'review')).toBe(NO_DATA_COLOR);
  });
});

describe('utilization heatmap', () => {
  it.each([undefined, NaN, Infinity, -Infinity])('uses a distinct palette color for unknown utilization (%s)', (utilization) => {
    expect(getHeatmapColor(utilization)).toBe(NO_DATA_COLOR);
    expect(getHeatmapColor(utilization)).not.toBe(PROJECT_COLOR);
  });

  it('keeps reported zero and overload values on the utilization scale', () => {
    expect(getHeatmapColor(0)).toBe('#00AEEF');
    expect(getHeatmapColor(1.25)).toBe('#FF5E7E');
    expect(getHeatmapColor(0.5)).not.toBe(getHeatmapColor(undefined));
  });

  it('keeps diff-state colors distinct from the project root', () => {
    const node: BimNode = { id: 'beam-1', label: 'B101', kind: 'element', ifcType: 'IfcBeam', elementKind: 'beam', level: 2, x: 0, y: 0, r: 10 };
    expect(getEffectiveNodeColor(node, 'utilisation', true)).toBe(DIFF_PALETTE.unchanged);
    expect(getEffectiveNodeColor({ ...node, diffStatus: 'removed' }, 'utilisation', true)).toBe(DIFF_PALETTE.removed);
    expect(Object.values(DIFF_PALETTE)).not.toContain(PROJECT_COLOR);
  });

  it('chooses readable label text against both bright and dark fills', () => {
    expect(getContrastingTextStyle('#FF1493').fill).toBe('#090d16');
    expect(getContrastingTextStyle('#2F2F2F').fill).toBe('#ffffff');
  });
});
