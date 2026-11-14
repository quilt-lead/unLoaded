import type { SerializedElementGraph } from "../model/graph-types.ts";
import { ElementGraph } from "./ElementGraph.ts";

/** Plain-JSON snapshot of a graph (format "unloaded.element-graph", version 1). */
export function serializeGraph(graph: ElementGraph): SerializedElementGraph {
  return graph.serialize();
}

/** Inverse of serializeGraph. Accepts the object or its JSON string. */
export function deserializeGraph(data: SerializedElementGraph | string): ElementGraph {
  return ElementGraph.deserialize(data);
}

export function graphToJSON(graph: ElementGraph, space?: number): string {
  return JSON.stringify(graph.serialize(), null, space);
}
