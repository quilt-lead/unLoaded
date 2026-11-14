// Public API of @unloaded/element-graph. Dependency-free and side-effect-free.

// Parser -> graph contract.
export type * from "./model/input.ts";
export { MODEL_INPUT_VERSION, KNOWN_ELEMENT_KINDS, KNOWN_RELATION_KINDS } from "./model/input.ts";

// Graph types.
export type * from "./model/graph-types.ts";
export { ELEMENT_GRAPH_FORMAT, ELEMENT_GRAPH_FORMAT_VERSION } from "./model/graph-types.ts";

// Graph.
export { ElementGraph, CONNECTION_KIND, edgeId, isDirectedKind } from "./graph/ElementGraph.ts";
export type { ElementGraphOptions } from "./graph/ElementGraph.ts";
export { serializeGraph, deserializeGraph, graphToJSON } from "./graph/serialize.ts";

// Build + inference.
export { buildGraph } from "./build/buildGraph.ts";
export type { BuildOptions, BuildResult } from "./build/buildGraph.ts";
export { inferConnectivity, RULE_NAMES, RULE_LABELS, resolveRules } from "./infer/inferConnectivity.ts";
export type { InferOptions, InferResult, RuleName } from "./infer/inferConnectivity.ts";
export { findContactPairs, autoCellSize } from "./infer/spatial-index.ts";
export type { ContactPair } from "./infer/spatial-index.ts";

// Tolerances + geometry helpers.
export { DEFAULT_TOLERANCES, resolveTolerances } from "./tolerances.ts";
export type { Tolerances } from "./tolerances.ts";
export {
  bboxGap,
  pointBoxDist,
  planPointBoxDist,
  planOverlapArea,
  bboxCenter,
  memberAxis,
  axisAngleDeg,
} from "./geometry.ts";
export type { Axis } from "./geometry.ts";
