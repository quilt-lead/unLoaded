// The drawing-set import path below the PDF: a drawing parser ModelInput -> element graph -> view nodes. The
// drawing params (Drawing.Occurrences above all) must survive to the BimNode, where the drawing evidence reads them.
import { describe, expect, it } from 'vitest';
import { parseDrawingPages } from '@unloaded/drawing-parser';
import { details, framingPlan, schedule } from '../../packages/drawing-parser/test/helpers';
import { importDrawingModel } from './parsers';
import { elementGraphToBim } from './elementGraphToBim';
import { readOccurrences } from '../data/drawingOccurrences';

describe('importDrawingModel', () => {
  const input = parseDrawingPages([framingPlan(), schedule(), details()]);

  it('builds an element graph with format "drawing", named after the file', async () => {
    const res = await importDrawingModel(input, 'S-sheets.pdf');
    expect(res.kind).toBe('model');
    expect(res.format).toBe('drawing');
    expect(res.projectName).toBe(input.meta.project || 'S-sheets');
    expect(res.elementGraph.nodeCount).toBe(input.elements.length);
  });

  it('keeps every Drawing.* param on the view nodes, and each element\'s occurrences read back as typed targets', async () => {
    const res = await importDrawingModel(input, 'S-sheets.pdf');
    const nodes = elementGraphToBim(res.elementGraph).elementNodes.filter((n) => n.kind === 'element');
    expect(nodes).toHaveLength(input.elements.length);
    const byId = new Map(nodes.map((n) => [n.id, n]));
    for (const el of input.elements) {
      const n = byId.get(el.id)!;
      for (const [k, v] of Object.entries(el.params)) {
        // (the adapter drops empty / null params, for every format)
        if (k.startsWith('Drawing.') && v !== '' && v !== null) expect(n.params?.[k], `${el.id} ${k}`).toBe(String(v));
      }
      const occ = readOccurrences(n.params);
      expect(occ.length, el.id).toBe(Number(el.params['Drawing.OccurrenceCount']));
      expect(occ[0]).toMatchObject({ sheet: el.params['Drawing.Sheet'], page: el.params['Drawing.Page'] });
      for (const o of occ) expect(o.file).toBe('set.pdf'); // the page builder's file name
    }
    // a schedule-only element (the column) still has its schedule row as evidence
    const col = nodes.find((n) => n.id === 'column:1/A:level-1..level-2')!;
    expect(readOccurrences(col.params).map((o) => o.how)).toEqual(['schedule_row']);
  });
});
