import { describe, expect, it } from 'vitest';
import { getContrastingTextStyle, getEffectiveNodeColor, getGraphNodeColor, getHeatmapColor } from './colors';
import type { BimNode } from '../types/bim';

describe('utilization heatmap', () => {
  it.each([undefined, NaN, Infinity, -Infinity])('uses a distinct color for unknown utilization (%s)', (utilization) => {
    expect(getHeatmapColor(utilization)).toBe('#FF1493');
  });

  describe('graph center node', () => {
    it('stays gray in normal, heatmap, and diff views', () => {
      const project: BimNode = { id: 'proj-root', label: 'Project', type: 'Project', level: 0, x: 0, y: 0, r: 36 };

      expect(getGraphNodeColor(project, false)).toBe('#D8D3D8');
      expect(getGraphNodeColor(project, true, true)).toBe('#D8D3D8');
      expect(getEffectiveNodeColor(project, false)).toBe('#D8D3D8');
    });
  });

  it('assigns unique reference-inspired colors to graph categories only', () => {
    const categories = [
      'cat-slab', 'cat-col', 'cat-beam', 'cat-mframe', 'cat-brace', 'cat-conn', 'cat-wall',
      'cat-mat', 'cat-pcap', 'cat-pile', 'cat-footing', 'cat-stair', 'cat-roof', 'cat-curtain',
      'cat-window', 'cat-door', 'cat-railing', 'cat-covering', 'cat-rebar', 'cat-tendon', 'cat-proxy',
    ];
    const colors = categories.map((categoryParent) =>
      getGraphNodeColor(
        { id: categoryParent, label: categoryParent, type: 'Instance', level: 2, categoryParent, x: 0, y: 0, r: 10 },
        false
      )
    );

    expect(colors.slice(0, 6)).toEqual([
      '#FF1493',
      '#A3D900',
      '#00AEEF',
      '#FF8A00',
      '#FF5E7E',
      '#FFAE42',
    ]);
    expect(new Set(colors).size).toBe(categories.length);
    expect(colors).not.toContain('#D8D3D8');

    const column: BimNode = {
      id: 'column-1',
      label: 'C1',
      type: 'IfcColumn',
      ifcType: 'IFCCOLUMN',
      level: 2,
      categoryParent: 'cat-col',
      x: 0,
      y: 0,
      r: 10,
    };
    expect(getGraphNodeColor(column, false)).toBe('#A3D900');
    expect(getEffectiveNodeColor(column, false)).toBe('#A3D900');
  });

  it('uses the same accent for corresponding calculation and structural categories', () => {
    const categoryColor = (id: string) =>
      getGraphNodeColor({ id, label: id, type: 'Category', level: 1, x: 0, y: 0, r: 20 }, false);

    expect(categoryColor('calc-cat-beam')).toBe(categoryColor('cat-beam'));
    expect(categoryColor('calc-cat-col')).toBe(categoryColor('cat-col'));
    expect(categoryColor('calc-cat-conn')).toBe(categoryColor('cat-conn'));
    expect(categoryColor('calc-cat-slab')).toBe(categoryColor('cat-slab'));
    expect(categoryColor('calc-cat-wall')).toBe(categoryColor('cat-wall'));
    expect(categoryColor('calc-cat-fdn')).toBe(categoryColor('cat-footing'));
  });

  it('keeps reported zero and overload values on the utilization scale', () => {
    expect(getHeatmapColor(0)).toBe('#00AEEF');
    expect(getHeatmapColor(1.25)).toBe('#FF5E7E');
    expect(getHeatmapColor(0.5)).not.toBe(getHeatmapColor(undefined));
  });

  it('uses a distinct unknown-utilization color while retaining diff colors', () => {
    const node: BimNode = { id: 'beam-1', label: 'B101', type: 'IfcBeam', level: 2, x: 0, y: 0, r: 10 };
    expect(getEffectiveNodeColor(node, true)).toBe('#FF1493');
    expect(getEffectiveNodeColor({ ...node, diffStatus: 'added' }, true, true)).toBe('#A3D900');
    expect(getEffectiveNodeColor({ ...node, diffStatus: 'unchanged' }, true, true)).toBe('#00AEEF');
    expect(getEffectiveNodeColor({ ...node, diffStatus: 'removed' }, true, true)).toBe('#FF5E7E');
  });

  it('chooses readable label text against both dark and bright node fills', () => {
    expect(getContrastingTextStyle('#FF1493').fill).toBe('#090d16');
    expect(getContrastingTextStyle('#2F2F2F').fill).toBe('#ffffff');
  });
});
