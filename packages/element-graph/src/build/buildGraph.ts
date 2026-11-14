import type { ModelInput } from "../model/input.ts";
import { ElementGraph, isDirectedKind } from "../graph/ElementGraph.ts";
import { inferConnectivity, type InferOptions } from "../infer/inferConnectivity.ts";

export type BuildOptions = InferOptions;

export interface BuildResult {
  graph: ElementGraph;
  /** Build-time issues (skipped relations, inference conflicts, supports cycles). Parser warnings stay on the input. */
  warnings: string[];
}

/**
 * Build an ElementGraph from a parser's ModelInput:
 * levels + nodes, explicit relations, geometric inference, then cycle check.
 * Never throws on bad data - issues are reported as warnings.
 */
export function buildGraph(input: ModelInput, opts: BuildOptions = {}): BuildResult {
  const warnings: string[] = [];
  const graph = new ElementGraph({ meta: input.meta, levels: input.levels });
  const levelIds = new Set(input.levels.map((l) => l.id));

  graph.batch(() => {
    for (const el of input.elements) {
      if (graph.hasNode(el.id)) {
        warnings.push(`duplicate element id "${el.id}" skipped`);
        continue;
      }
      if (el.levelId !== undefined && !levelIds.has(el.levelId)) {
        warnings.push(`element "${el.id}" references unknown level "${el.levelId}"`);
      }
      graph.addNode(el);
    }
    for (const r of input.relations) {
      if (!graph.hasNode(r.a) || !graph.hasNode(r.b)) {
        const missing = [r.a, r.b].filter((id) => !graph.hasNode(id)).join(", ");
        warnings.push(`relation ${r.kind} ${r.a} -> ${r.b} skipped: unknown endpoint ${missing}`);
        continue;
      }
      if (r.a === r.b) {
        warnings.push(`relation ${r.kind} on "${r.a}" skipped: self-relation`);
        continue;
      }
      graph.addEdge({ kind: r.kind, a: r.a, b: r.b, directed: isDirectedKind(r.kind), evidence: r.evidence });
    }
  });

  if (opts.infer !== false) {
    const inferred = inferConnectivity(graph, opts);
    warnings.push(...inferred.warnings);
  }

  for (const cycle of graph.findCycles("supports")) {
    warnings.push(`supports cycle: ${[...cycle, cycle[0]].join(" -> ")}`);
  }
  return { graph, warnings };
}
