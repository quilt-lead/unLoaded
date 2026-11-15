// The calc engine operations the worker runs: thin calls into @unloaded/calc-mapper (the ONLY
// module in src/ that imports its functions), plus @unloaded/drawing-parser for drawing sets. Kept free of worker plumbing so the same functions
// could run on the main thread (tests, a future non-worker fallback).
//
// Calcs reach map / export / impact as a calc SET (the head revision of every calc document); the set
// is combined here, in the worker, so the main thread never copies the combined pages.
import {
  buildCalcSet, buildExport, bundleExport, diffCalcSets, diffGraphs, extractPdf, impactOf, mapCalcs, resolveRevisionTarget, segmentCalcs, type PdfjsLike,
} from '@unloaded/calc-mapper';
import type { EngineOp, EngineOps } from './protocol';

type Op<K extends EngineOp> = (args: EngineOps[K]['args'], progress: (m: string) => void) => Promise<EngineOps[K]['result']>;

export function engineOps(pdfjs: unknown): { [K in EngineOp]: Op<K> } {
  const extract: Op<'extract'> = async ({ bytes, sourceName }, progress) => {
    progress(`Reading text from ${sourceName}`);
    const text = await extractPdf(bytes, { pdfjs: pdfjs as PdfjsLike });
    progress(`Finding the calcs in ${text.pages.length} pages`);
    return segmentCalcs(text.pages, sourceName);
  };
  return {
    extract,
    extractPlaced: async ({ bytes, sourceName, known }, progress) => {
      const pkg = await extract({ bytes, sourceName }, progress);
      return { pkg, target: resolveRevisionTarget(known, pkg, sourceName) };
    },
    map: async ({ graph, docs }, progress) => {
      const set = buildCalcSet(docs);
      progress(`Matching ${set.combined.calcs.length} calcs in ${docs.length} PDF${docs.length === 1 ? '' : 's'} against ${graph.nodes.length} elements`);
      return mapCalcs(graph, set);
    },
    export: async ({ graph, docs, run, decisions, info }) => buildExport(graph, buildCalcSet(docs), run, decisions, info),
    bundleExport: async ({ graph, calcGraph, decisions, info }) => bundleExport(graph, calcGraph, decisions, info),
    impact: async ({ graph, docs, run, decisions, globalId, mode }) =>
      impactOf(graph, docs ? buildCalcSet(docs) : null, run, decisions, globalId, mode),
    diff: async ({ a, b, labelA, labelB }) => diffGraphs(a, b, { a: labelA, b: labelB }),
    calcDiff: async ({ before, after }) => diffCalcSets(before, after),
    parseDrawing: async ({ bytes, sourceName }, progress) => {
      // loaded on first use: the drawing parser pulls in ifc-parser (section names), which this worker otherwise never needs
      const { parseDrawingSet } = await import('@unloaded/drawing-parser');
      progress(`Reading the sheets of ${sourceName}`);
      return parseDrawingSet([{ name: sourceName, data: bytes }], { pdfjs: pdfjs as PdfjsLike });
    },
  };
}
