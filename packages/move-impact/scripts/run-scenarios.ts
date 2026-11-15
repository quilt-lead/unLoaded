/**
 * Node CLI: the move-impact screen over a list of move scenarios, written as JSON - the input the
 * offline scorer (tools/calcgraph-reference/scripts/evaluate_move.py) grades against the v2 answer key.
 *
 *   node packages/move-impact/scripts/run-scenarios.ts --graph model.graph.json --scenarios move_scenarios.json \
 *     --out move_results.json [--facts move_facts.json] [--links links.json] [--sections move_sections.json]
 *
 * Node >= 22.18 (type stripping). The graph comes from tools/calcgraph-reference/scripts/build_graph.mjs
 * (packages/ifc-parser + packages/element-graph: what the UI builds). Scenarios: {scenarios: [{id, move}]}
 * with the move in metres and the column as a GlobalId. Facts: {facts: CalcFact[]} or a bare array.
 * Links: calc-mapper `Link[]` (or a run-pipeline.ts output's run.links). Sections: {sections: {profile: SectionProps}}.
 * Output: {engine, results: [{id, label, seconds, result: ImpactResult}]}.
 */
import { readFileSync, writeFileSync } from "node:fs";
import { register } from "node:module";
import { dirname, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { parseArgs } from "node:util";
import type { CalcFact, CalcLink, Move, SectionProps, SerializedElementGraph } from "../src/index.ts";

// resolve the @unloaded/* workspace names straight to packages/*/src (as build_graph.mjs does), so the
// CLI works whether or not `npm install` has linked the workspaces
const repo = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..", "..");
const targets: Record<string, string> = {
  "@unloaded/element-graph": "packages/element-graph/src/index.ts",
  "@unloaded/calc-mapper": "packages/calc-mapper/src/index.ts",
  "@unloaded/calc-mapper/types": "packages/calc-mapper/src/types.ts",
};
const map = Object.fromEntries(Object.entries(targets).map(([k, v]) => [k, pathToFileURL(resolve(repo, v)).href]));
register(
  `data:text/javascript,${encodeURIComponent(`const MAP = ${JSON.stringify(map)};
export async function resolve(spec, ctx, next) { return MAP[spec] ? { url: MAP[spec], shortCircuit: true } : next(spec, ctx); }`)}`,
);
const { ENGINE_VERSION, impact } = await import("../src/index.ts");
const { sha256Json } = await import(map["@unloaded/calc-mapper"]!);

const { values } = parseArgs({
  options: { graph: { type: "string" }, scenarios: { type: "string" }, out: { type: "string" }, facts: { type: "string" }, links: { type: "string" }, sections: { type: "string" } },
});
if (!values.graph || !values.scenarios || !values.out) {
  console.error("usage: run-scenarios.ts --graph g.json --scenarios s.json --out out.json [--facts facts.json] [--links links.json] [--sections s.json]");
  process.exit(2);
}
const read = (p: string) => JSON.parse(readFileSync(p, "utf8"));
const graph = read(values.graph) as SerializedElementGraph;
const scen = read(values.scenarios) as { scenarios: { id: string; label?: string; move: Move }[] };
const facts: CalcFact[] | undefined = values.facts ? (((f) => (Array.isArray(f) ? f : f.facts))(read(values.facts)) as CalcFact[]) : undefined;
const links: CalcLink[] | undefined = values.links
  ? (((l) => (Array.isArray(l) ? l : (l.links ?? l.run?.links)))(read(values.links)) as CalcLink[])
  : undefined;

const graphSha256: string = await sha256Json(graph);
const sections = values.sections ? (((x) => x.sections ?? x)(read(values.sections)) as Record<string, SectionProps>) : undefined;

const results = [];
for (const s of scen.scenarios) {
  const t = performance.now();
  const result = impact({ graph, graphSha256, move: s.move, ...(facts ? { facts } : {}), ...(links ? { links } : {}), ...(sections ? { sections } : {}) });
  const seconds = Math.round(performance.now() - t) / 1000;
  results.push({ id: s.id, label: s.label ?? null, seconds, result });
  const h = result.health ? ` band ${result.health.band}` : "";
  console.log(
    `${s.id} topo ${result.topological.length} screened ${result.screened.length}` +
      (result.staleRows ? ` rows ${result.staleRows.length}/${result.staleRows.filter((r) => r.screened).length}` : "") +
      `${h} (${seconds}s)  ${s.label ?? ""}`,
  );
}
writeFileSync(values.out, JSON.stringify({ engine: ENGINE_VERSION, graphSha256, facts: facts ? facts.length : null, results }, null, 1) + "\n");
console.log(`${results.length} scenarios -> ${values.out}`);
