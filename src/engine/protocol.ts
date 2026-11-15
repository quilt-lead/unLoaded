// Messages between the app and the calc engine worker (src/engine/engine.worker.ts).
// Everything crossing the boundary is plain JSON (plus transferable byte buffers), typed by
// @unloaded/calc-mapper's public types.
import type { CalcPackage, Compare, DecisionFields, Export, ExportInfo, Impact, ImpactMode, MappingRun, SerializedElementGraph } from '@unloaded/calc-mapper/types';

export interface EngineOps {
  /** calc package PDF -> pages (pdf.js, word boxes) + segmented calcs */
  extract: { args: { bytes: Uint8Array; sourceName: string }; result: CalcPackage };
  /** element graph x calc package -> auto links + calc dependencies */
  map: { args: { graph: SerializedElementGraph; pkg: CalcPackage }; result: MappingRun };
  /** the export of a (graph, package, run) with the decision log applied */
  export: { args: { graph: SerializedElementGraph; pkg: CalcPackage; run: MappingRun; decisions: DecisionFields[]; info: ExportInfo }; result: Export };
  /** what goes stale if an element changes / is removed */
  impact: { args: { graph: SerializedElementGraph; pkg: CalcPackage | null; run: MappingRun | null; decisions: DecisionFields[]; globalId: string; mode: ImpactMode }; result: Impact };
  /** the ONE revision diff: two element graphs */
  diff: { args: { a: SerializedElementGraph; b: SerializedElementGraph; labelA: number; labelB: number }; result: Compare };
}

export type EngineOp = keyof EngineOps;

export type EngineRequest = { [K in EngineOp]: { id: number; op: K; args: EngineOps[K]['args'] } }[EngineOp];

export type EngineResponse =
  | { id: number; type: 'progress'; message: string }
  | { id: number; type: 'result'; result: unknown }
  | { id: number; type: 'error'; error: string };
