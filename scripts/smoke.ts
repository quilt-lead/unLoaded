// End-to-end smoke test: IFC file -> parseIfc -> buildGraph -> summary.
// Usage: node scripts/smoke.ts [file.ifc]
import { readFileSync } from "node:fs";
import { basename } from "node:path";
import { parseIfc } from "@unloaded/ifc-parser";
import { buildGraph } from "@unloaded/element-graph";

const file = process.argv[2] ?? "data/Building-Structural-IFC4.ifc";
const input = await parseIfc(new Uint8Array(readFileSync(file)), { fileName: basename(file) });
const { graph, warnings } = buildGraph(input);
console.log(`file: ${file}`);
console.log(`parser warnings: ${input.warnings.length}`, input.warnings);
console.log(`graph warnings: ${warnings.length}`, warnings);
console.log("stats:", JSON.stringify(graph.stats(), null, 2));
for (const n of graph.nodesByKind("beam").slice(0, 2)) {
  console.log(`\n${n.kind} ${n.mark ?? n.name ?? n.id}`);
  for (const e of graph.edgesOf(n.id)) {
    const other = e.a === n.id ? e.b : e.a;
    const o = graph.getNode(other);
    console.log(`  ${e.kind} ${e.a === n.id ? "->" : "<-"} ${o?.kind} ${o?.name ?? other}  [${e.evidence.map((v) => v.rule).join("; ")}]`);
  }
}
