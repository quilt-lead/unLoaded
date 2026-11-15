/**
 * Node CLI: drawing PDF(s) -> ModelInput JSON -> serialized element graph JSON.
 *
 *   node packages/drawing-parser/scripts/parse.ts --pdf drawings.pdf [--pdf more.pdf] \
 *     --out model.json [--graph graph.json]
 *
 * Node >= 22.18 (type stripping). pdf.js runs from its legacy build, as pdf.js documents for Node.
 * The graph is what the UI would build from this ModelInput (buildGraph with default inference).
 */
import { readFileSync, writeFileSync } from "node:fs";
import { basename } from "node:path";
import { parseArgs } from "node:util";
import type { PdfjsLike } from "@unloaded/calc-mapper";
import { buildGraph } from "@unloaded/element-graph";
import { parseDrawingSet } from "../src/index.ts";

const { values } = parseArgs({
  options: { pdf: { type: "string", multiple: true }, out: { type: "string" }, graph: { type: "string" } },
});
if (!values.pdf?.length || !values.out) {
  console.error("usage: parse.ts --pdf drawings.pdf [--pdf more.pdf] --out model.json [--graph graph.json]");
  process.exit(2);
}
const pdfjs = (await import("pdfjs-dist/legacy/build/pdf.mjs")) as unknown as PdfjsLike;
const files = values.pdf.map((p) => ({ name: basename(p), data: new Uint8Array(readFileSync(p)) }));
const model = await parseDrawingSet(files, { pdfjs });
writeFileSync(values.out, JSON.stringify(model, null, 1));
const byKind = new Map<string, number>();
for (const e of model.elements) byKind.set(e.kind, (byKind.get(e.kind) ?? 0) + 1);
console.log(`${values.out}: ${model.elements.length} elements (${[...byKind].map(([k, n]) => `${k} ${n}`).join(", ")}), ` +
  `${model.levels.length} levels, ${model.relations.length} relations, ${model.warnings.length} warnings`);
if (values.graph) {
  const { graph, warnings } = buildGraph(model);
  writeFileSync(values.graph, JSON.stringify(graph.serialize()));
  const st = graph.stats();
  console.log(`${values.graph}: ${st.nodes} nodes, ${st.edges} edges (${Object.entries(st.edgesByKind).map(([k, n]) => `${k} ${n}`).join(", ")}), ` +
    `${warnings.length} graph warnings`);
}
