/**
 * Node CLI: the calc engine on one model revision + calc package, written as JSON - the input the
 * offline scorer (tools/calcgraph-reference/scripts/evaluate.py) grades against ground truth.
 *
 *   node packages/calc-mapper/scripts/run-pipeline.ts --graph rev1.graph.json --pdf calcs.pdf --out result.json \
 *     [--decisions decisions.json] [--compare-to rev2.graph.json] [--impact <GlobalId>:remove|change ...]
 *
 * Node >= 22.18 (type stripping). The graph comes from tools/calcgraph-reference/scripts/build_graph.mjs
 * (packages/ifc-parser + packages/element-graph, i.e. what the UI builds). pdf.js runs from its legacy
 * build, as pdf.js documents for Node. Output:
 *   { export, run: {links, calc_edges}, pdf: {pages: [{n, text, scanned}]}, compare?, impacts: {"gid:mode": Impact} }
 */
import { readFileSync, writeFileSync } from "node:fs";
import { basename } from "node:path";
import { parseArgs } from "node:util";
import {
  buildExport, decisionFrom, diffGraphs, extractPdf, impactOf, mapCalcs, parseGraph, segmentCalcs,
  type DecisionFields, type ImpactMode, type PdfjsLike,
} from "../src/index.ts";

const { values } = parseArgs({
  options: {
    graph: { type: "string" }, pdf: { type: "string" }, out: { type: "string" }, decisions: { type: "string" },
    "compare-to": { type: "string" }, impact: { type: "string", multiple: true },
  },
});
if (!values.graph || !values.pdf || !values.out) {
  console.error("usage: run-pipeline.ts --graph g.json --pdf calcs.pdf --out out.json [--decisions d.json] [--compare-to g2.json] [--impact gid:mode ...]");
  process.exit(2);
}
const graph = parseGraph(readFileSync(values.graph, "utf8"));
const pdfjs = (await import("pdfjs-dist/legacy/build/pdf.mjs")) as unknown as PdfjsLike;
const text = await extractPdf(new Uint8Array(readFileSync(values.pdf)), { pdfjs });
const pkg = segmentCalcs(text.pages, basename(values.pdf));
const run = await mapCalcs(graph, pkg);
// a decision-log file may predate provenance: decisionFrom keeps a decision's provenance or states it from its own fields
const decisions = values.decisions
  ? (JSON.parse(readFileSync(values.decisions, "utf8")) as DecisionFields[]).map((d) => decisionFrom(d))
  : [];
const out: Record<string, unknown> = {
  export: buildExport(graph, pkg, run, decisions, { model: basename(values.graph) }),
  run,
  pdf: { meta: text.meta, pages: text.pages.map((p) => ({ n: p.n, text: p.text, scanned: p.scanned })) },
  impacts: Object.fromEntries(await Promise.all((values.impact ?? []).map(async (spec) => {
    const i = spec.lastIndexOf(":");
    const gid = spec.slice(0, i), mode = spec.slice(i + 1) as ImpactMode;
    return [spec, await impactOf(graph, pkg, run, decisions, gid, mode)] as const;
  }))),
};
if (values["compare-to"]) {
  out.compare = diffGraphs(graph, parseGraph(readFileSync(values["compare-to"], "utf8")), {
    a: basename(values.graph), b: basename(values["compare-to"]),
  });
}
writeFileSync(values.out, JSON.stringify(out));
const e = out.export as ReturnType<typeof buildExport>;
console.log(`${values.out}: ${e.elements.length} elements, ${e.elements.reduce((n, x) => n + x.calcs.length, 0)} links, ` +
  `${e.calcs.length} calcs, ${e.calc_edges.length} calc edges, ${e.load_path.length} load-path edges`);
