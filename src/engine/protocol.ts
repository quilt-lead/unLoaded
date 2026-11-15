// Messages between the app and the calc engine worker (src/engine/engine.worker.ts).
// Everything crossing the boundary is plain JSON (plus transferable byte buffers), typed by
// @unloaded/calc-mapper's public types.
import type {
  BundleCalcGraph, CalcPackage, CalcSetDiff, CalcSetDocument, Compare, DecisionFields, Export, ExportInfo, Impact, ImpactMode, KnownDocument, MappingRun,
  RevisionTarget, SerializedElementGraph,
} from '@unloaded/calc-mapper';

export interface EngineOps {
  /** calc package PDF -> pages (pdf.js, word boxes) + segmented calcs */
  extract: { args: { bytes: Uint8Array; sourceName: string }; result: CalcPackage };
  /** extract, then which calc document it is: already loaded, a new revision of one, or a new document (a suggestion) */
  extractPlaced: { args: { bytes: Uint8Array; sourceName: string; known: KnownDocument[] }; result: { pkg: CalcPackage; target: RevisionTarget } };
  /** element graph x calc set (every document's head) -> auto links + calc dependencies */
  map: { args: { graph: SerializedElementGraph; docs: CalcSetDocument[] }; result: MappingRun };
  /** the export of a (graph, calc set, run) with the decision log applied */
  export: { args: { graph: SerializedElementGraph; docs: CalcSetDocument[]; run: MappingRun; decisions: DecisionFields[]; info: ExportInfo }; result: Export };
  /** the export of a model bundle's calc graph against its element graph, with the decision log applied (no PDF, no mapping run) */
  bundleExport: { args: { graph: SerializedElementGraph; calcGraph: BundleCalcGraph; decisions: DecisionFields[]; info: ExportInfo }; result: Export };
  /** what goes stale if an element changes / is removed */
  impact: { args: { graph: SerializedElementGraph; docs: CalcSetDocument[] | null; run: MappingRun | null; decisions: DecisionFields[]; globalId: string; mode: ImpactMode }; result: Impact };
  /** the ONE revision diff: two element graphs */
  diff: { args: { a: SerializedElementGraph; b: SerializedElementGraph; labelA: number; labelB: number }; result: Compare };
  /** calc revision diff: two calc sets (documents in their own page numbers) */
  calcDiff: { args: { before: CalcSetDocument[]; after: CalcSetDocument[] }; result: CalcSetDiff };
}

export type EngineOp = keyof EngineOps;

export type EngineRequest = { [K in EngineOp]: { id: number; op: K; args: EngineOps[K]['args'] } }[EngineOp];

export type EngineResponse =
  | { id: number; type: 'progress'; message: string }
  | { id: number; type: 'result'; result: unknown }
  | { id: number; type: 'error'; error: string };
