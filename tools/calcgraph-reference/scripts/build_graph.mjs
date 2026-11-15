// IFC -> serialized element graph (format "unloaded.element-graph" v1), with the SAME code the UI
// runs: packages/ifc-parser (parseIfc) then packages/element-graph (buildGraph, ElementGraph.serialize).
//
//   node tools/calcgraph-reference/scripts/build_graph.mjs model.ifc model.graph.json [more.ifc more.graph.json ...]
//
// Node >= 22.18 (runs the packages' .ts sources through Node's type stripping, like
// packages/ifc-parser/scripts/dump.ts and scripts/smoke.ts). The @unloaded/* workspace names are
// resolved straight to packages/*/src, so this works whether or not `npm install` has linked the
// workspaces; web-ifc comes from the repo root node_modules (`npm ci`).
// Output is deterministic (parser sorts elements / relations; graph ids are deterministic) and is
// written as pretty JSON so a diff of two builds is readable.
import { readFileSync, writeFileSync } from "node:fs";
import { register } from "node:module";
import { basename, dirname, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const repo = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..", "..");
const targets = {
  "@unloaded/element-graph": "packages/element-graph/src/index.ts",
  "@unloaded/element-graph/input": "packages/element-graph/src/model/input.ts",
  "@unloaded/ifc-parser": "packages/ifc-parser/src/index.ts",
};
const map = Object.fromEntries(Object.entries(targets).map(([k, v]) => [k, pathToFileURL(resolve(repo, v)).href]));
const hooks = `const MAP = ${JSON.stringify(map)};
export async function resolve(spec, ctx, next) {
  return MAP[spec] ? { url: MAP[spec], shortCircuit: true } : next(spec, ctx);
}`;
register(`data:text/javascript,${encodeURIComponent(hooks)}`);

const args = process.argv.slice(2);
if (args.length === 0 || args.length % 2) {
  console.error("usage: node tools/calcgraph-reference/scripts/build_graph.mjs in.ifc out.graph.json [in2.ifc out2.graph.json ...]");
  process.exit(2);
}
const { parseIfc } = await import(map["@unloaded/ifc-parser"]);
const { buildGraph } = await import(map["@unloaded/element-graph"]);
for (let i = 0; i < args.length; i += 2) {
  const [src, out] = [args[i], args[i + 1]];
  const input = await parseIfc(new Uint8Array(readFileSync(src)), { fileName: basename(src) });
  const { graph, warnings } = buildGraph(input);
  writeFileSync(out, JSON.stringify(graph.serialize(), null, 1) + "\n");
  const s = graph.stats();
  console.log(`${basename(src)} -> ${out}: ${s.nodes} nodes ${JSON.stringify(s.nodesByKind)}, ${s.edges} edges ` +
    `${JSON.stringify(s.edgesByKind)}; parser warnings ${input.warnings.length}, graph warnings ${warnings.length}`);
  for (const w of [...input.warnings, ...warnings].slice(0, 8)) console.log(`  - ${w}`);
}
