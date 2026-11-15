/**
 * @unloaded/calc-parser - calc package PDF -> calcs -> element <-> calc links ->
 * calc dependency graph -> change impact. Runs in the browser (pdf.js) and in Node.
 *
 * TypeScript port of prototyping/calc-graph/backend/calcgraph (pdf_ingest, segment,
 * matcher, calcdeps, impact, and the review parts of pipeline/store). The IFC side
 * comes from @unloaded/ifc-parser; `toCalcElements` adapts its elements.
 */
import { inferCalcDeps } from './calcdeps.ts';
import { runMapping } from './matcher.ts';
import { segment } from './segment.ts';
import type { Calc, CalcEdge, CalcElement, CalcLink, CalcPage } from './types.ts';

export * from './types.ts';
export { readPdf, rectsForSpan, assemblePage, type PdfjsLike, type ReadPdfOptions } from './pdf.ts';
export { segment, titleOf, catOfText, SOFTWARE, CAT_WORDS } from './segment.ts';
export { runMapping, normMark, dashless, CONF } from './matcher.ts';
export { inferCalcDeps } from './calcdeps.ts';
export { propagateImpact } from './impact.ts';
export { catOf, profileFrom, normProfile, toCalcElements, type ModelElementLike } from './elements.ts';
export {
  effectiveDecisions,
  effectiveLinks,
  statusOf,
  mappingStatuses,
  exportMapping,
  CALC_PALETTE,
  calcColor,
  type MappingStatus,
  type ExportInput,
} from './review.ts';

/** Bumped whenever a rule changes, so stored runs can be told apart. */
export const ENGINE_VERSION = 'mapper-v1.0-ts';

export interface CalcMapping {
  calcs: Calc[];
  links: CalcLink[];
  calcEdges: CalcEdge[];
}

/** Segment the pages, map elements to calcs, infer calc dependencies. Pure and synchronous. */
export function mapCalcs(elements: readonly CalcElement[], pages: readonly CalcPage[]): CalcMapping {
  const calcs = segment(pages);
  const links = runMapping(elements, calcs, pages);
  const calcEdges = inferCalcDeps(calcs, pages, links);
  return { calcs, links, calcEdges };
}
