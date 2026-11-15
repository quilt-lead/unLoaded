// The calc engine operations the worker runs: thin calls into @unloaded/calc-mapper (the ONLY
// module in src/ that imports its functions). Kept free of worker plumbing so the same functions
// could run on the main thread (tests, a future non-worker fallback).
import { buildExport, diffGraphs, extractPdf, impactOf, mapCalcs, segmentCalcs, type PdfjsLike } from '@unloaded/calc-mapper';
import type { EngineOp, EngineOps } from './protocol';

type Op<K extends EngineOp> = (args: EngineOps[K]['args'], progress: (m: string) => void) => Promise<EngineOps[K]['result']>;

export function engineOps(pdfjs: unknown): { [K in EngineOp]: Op<K> } {
  return {
    extract: async ({ bytes, sourceName }, progress) => {
      progress(`Reading text from ${sourceName}`);
      const text = await extractPdf(bytes, { pdfjs: pdfjs as PdfjsLike });
      progress(`Finding the calcs in ${text.pages.length} pages`);
      return segmentCalcs(text.pages, sourceName);
    },
    map: async ({ graph, pkg }, progress) => {
      progress(`Matching ${pkg.calcs.length} calcs against ${graph.nodes.length} elements`);
      return mapCalcs(graph, pkg);
    },
    export: async ({ graph, pkg, run, decisions, info }) => buildExport(graph, pkg, run, decisions, info),
    impact: async ({ graph, pkg, run, decisions, globalId, mode }) => impactOf(graph, pkg, run, decisions, globalId, mode),
    diff: async ({ a, b, labelA, labelB }) => diffGraphs(a, b, { a: labelA, b: labelB }),
  };
}
