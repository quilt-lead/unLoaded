/**
 * End-to-end parity check: launch the real CLI over stdio with the official MCP client, call every
 * tool, and compare each tool's numbers / records with what @unloaded/calc-mapper (and
 * @unloaded/move-impact) return when called DIRECTLY on the same project file - decoded here
 * independently of the server's own loader.
 *
 *   node packages/mcp-server/scripts/mcp-parity.ts path/to/project.calcgraph.json [--out report.json]
 *
 * Exit code 1 on any mismatch. Prints one line per check.
 */
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { parseArgs } from "node:util";
import { isDeepStrictEqual } from "node:util";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";
import {
  buildCalcSet, buildExport, buildState, diffGraphs, impactOf, mapCalcs, parseGraph, sha256Json,
  type CalcPackage, type DecisionFields, type SerializedElementGraph,
} from "@unloaded/calc-mapper";
import { impact as moveImpact } from "@unloaded/move-impact";

const { values, positionals } = parseArgs({ allowPositionals: true, options: { out: { type: "string" } } });
const file = positionals[0];
if (!file) {
  console.error("usage: mcp-parity.ts project.calcgraph.json [--out report.json]");
  process.exit(2);
}

// ------------------------------------------------------------ direct: calc-mapper on the same file
interface Rev { id: number; kind: "model" | "calcs"; sourceName: string; graph?: unknown; extraction?: CalcPackage; docId?: string }
const pf = JSON.parse(readFileSync(file, "utf8")) as {
  documents: { docId: string; name: string; removed: boolean }[];
  revisions: Rev[];
  decisions: { globalId: string; calcKey: string; action: DecisionFields["action"]; actor: string | null; note: string | null; at: string; modelRev: number | null; calcRev: number | null }[];
};
const head = (k: Rev["kind"]) => pf.revisions.filter((r) => r.kind === k).sort((a, b) => b.id - a.id)[0]!;
const mRev = head("model");
// the calc set: each live calc document's head revision, in document order (what the app and the server map)
const cRevs = pf.documents.filter((d) => !d.removed)
  .map((d) => pf.revisions.filter((r) => r.kind === "calcs" && r.docId === d.docId).sort((a, b) => b.id - a.id)[0]!);
const cRev = cRevs.length === 1 ? cRevs[0]! : null;
const graph = parseGraph(mRev.graph) as SerializedElementGraph;
const pkg = buildCalcSet(cRevs.map((r) => ({ doc_id: r.docId!, name: pf.documents.find((d) => d.docId === r.docId)!.name, revision: r.id, package: r.extraction! })));
const decisions: DecisionFields[] = pf.decisions.map((d, i) => ({
  id: i + 1, global_id: d.globalId, calc_key: d.calcKey, action: d.action, actor: d.actor, note: d.note, at: d.at,
  model_rev: d.modelRev, calc_rev: d.calcRev,
}));
const run = await mapCalcs(graph, pkg);
const state = buildState(graph, pkg, run, decisions);
const exp = buildExport(graph, pkg, run, decisions, {
  model: mRev.sourceName, model_revision: mRev.id,
  calc_package: cRev ? cRev.sourceName : `${cRevs.length} calc documents`, calc_revision: cRev ? cRev.id : null,
});

// ------------------------------------------------------------ via MCP: the real CLI over stdio
const bin = join(dirname(fileURLToPath(import.meta.url)), "..", "bin", "unloaded-mcp-server.mjs");
const client = new Client({ name: "mcp-parity", version: "0.0.0" });
await client.connect(new StdioClientTransport({ command: process.execPath, args: [bin, file], stderr: "ignore" }));

async function call(name: string, args: Record<string, unknown> = {}) {
  const r = await client.callTool({ name, arguments: args });
  const content = r.content as { type: string; text?: string; data?: string; mimeType?: string }[];
  if (r.isError) throw new Error(`${name}: ${content[0]?.text}`);
  return { json: JSON.parse(content.find((c) => c.type === "text")!.text!), content };
}

const results: { check: string; ok: boolean; detail?: string }[] = [];
function check(name: string, got: unknown, want: unknown) {
  const ok = isDeepStrictEqual(got, want);
  results.push({ check: name, ok, ...(ok ? {} : { detail: `got ${JSON.stringify(got)?.slice(0, 300)} want ${JSON.stringify(want)?.slice(0, 300)}` }) });
  console.log(`${ok ? "ok  " : "FAIL"} ${name}${ok ? "" : `\n     ${results.at(-1)!.detail}`}`);
}

const listed = (await client.listTools()).tools;
check("tools listed", listed.map((t) => t.name).sort(), [
  "compare_revisions", "get_calc", "get_element", "get_page_image", "impact_of_change", "list_findings", "list_revisions",
  "list_typical_groups", "move_column", "project_summary", "search_elements",
]);
check("every tool is annotated read-only", listed.every((t) => t.annotations?.readOnlyHint === true && t.annotations?.destructiveHint === false), true);

// project_summary
const sum = (await call("project_summary")).json;
check("summary: element count", sum.counts.elements, state.elements.length);
check("summary: element status counts", sum.counts.element_status, state.counts);
check("summary: calcs", sum.counts.calcs, exp.calcs.length);
check("summary: links", sum.counts.links, state.links.length);
check("summary: calc edges", sum.counts.calc_edges, exp.calc_edges.length);
check("summary: load-path edges", sum.counts.load_path_edges, exp.load_path.length);
check("summary: connectivity edges", sum.counts.connectivity_edges, exp.connectivity.length);
check("summary: typical groups / group links", [sum.counts.typical_groups, sum.counts.group_links], [exp.groups.length, exp.group_links.length]);
check("summary: findings", sum.counts.findings, exp.findings.length);
check("summary: decisions", sum.counts.decisions, decisions.length);
check("summary: producers", sum.source.producers, JSON.parse(JSON.stringify(exp.producers)));
check("summary: graph sha256", sum.source.model_revision.graph_sha256, await sha256Json(graph));

// search_elements
const cols = (await call("search_elements", { kind: "Column", limit: 500 })).json;
check("search: columns", cols.count, state.elements.filter((e) => e.cat === "Column").length);
const w18 = (await call("search_elements", { size: "w18 x35", limit: 500 })).json;
check("search: size W18X35", w18.count, state.elements.filter((e) => e.profile.toUpperCase() === "W18X35" || e.profile.toUpperCase().includes("W18X35")).length);
const unm = (await call("search_elements", { status: "unmapped", limit: 500 })).json;
check("search: unmapped", unm.count, state.counts.unmapped);

// get_element: a beam with a design link, and the element of the first finding
const beam = exp.elements.find((e) => e.ifc_type === "IfcBeam" && e.calcs.some((l) => l.role === "design"))!;
const ge = (await call("get_element", { id: beam.mark })).json;
check(`get_element ${beam.mark}: links (role/band/caveats/reasons/provenance) equal the export`, ge.calcs, JSON.parse(JSON.stringify(beam.calcs)));
check(`get_element ${beam.mark}: load path`, [ge.load_path.bears_on.length, ge.load_path.carries.length],
  [state.edges.filter((x) => x.src === beam.global_id).length, state.edges.filter((x) => x.dst === beam.global_id).length]);
check(`get_element ${beam.mark}: connectivity`, ge.connectivity.length, exp.connectivity.filter((c) => c.a === beam.global_id || c.b === beam.global_id).length);
if (exp.findings[0]) {
  const f = exp.findings[0];
  const gf = (await call("get_element", { id: f.global_id })).json;
  check(`get_element ${f.global_id}: findings`, gf.findings, JSON.parse(JSON.stringify(exp.findings.filter((x) => x.global_id === f.global_id))));
}

// get_calc: every calc
let calcOk = 0;
for (const c of exp.calcs) {
  const g = (await call("get_calc", { key: c.key })).json;
  const linked = exp.elements.reduce((n, e) => n + e.calcs.filter((l) => l.calc === c.key).length, 0);
  const same = isDeepStrictEqual(g.calc, JSON.parse(JSON.stringify(c))) && g.linked_elements.length === linked &&
    g.calc_edges.feeds.length === exp.calc_edges.filter((x) => x.src === c.key).length &&
    g.calc_edges.fed_by.length === exp.calc_edges.filter((x) => x.dst === c.key).length &&
    g.findings.length === exp.findings.filter((x) => x.calc_key === c.key).length;
  if (same) calcOk += 1;
}
check(`get_calc: calc record, linked elements, edges, findings for all ${exp.calcs.length} calcs`, calcOk, exp.calcs.length);
const withText = (await call("get_calc", { key: exp.calcs.find((c) => !c.front_matter && !c.scanned)!.key, include_text: true })).json;
check("get_calc: include_text returns text", typeof withText.text?.text === "string" && withText.text.text.length > 0, true);

// impact_of_change: a column, remove and change
const col = state.elements.find((e) => e.cat === "Column")!;
for (const mode of ["remove", "change"] as const) {
  const r = (await call("impact_of_change", { id: col.global_id, mode })).json;
  check(`impact_of_change ${col.mark} ${mode}: impact equals impactOf`, r.impact, JSON.parse(JSON.stringify(await impactOf(graph, pkg, run, decisions, col.global_id, mode))));
}

// revisions + compare
const revs = (await call("list_revisions")).json;
check("list_revisions: ids", [...revs.revisions.model, ...revs.revisions.calcs].map((r: { id: number }) => r.id).sort(), pf.revisions.map((r) => r.id).sort());
const models = pf.revisions.filter((r) => r.kind === "model").sort((a, b) => a.id - b.id);
if (models.length >= 2) {
  const [a, b] = [models[0]!, models.at(-1)!];
  const cmp = (await call("compare_revisions", { a: a.id, b: b.id })).json;
  check(`compare_revisions ${a.id} -> ${b.id}: equals diffGraphs`, cmp.compare,
    JSON.parse(JSON.stringify(diffGraphs(parseGraph(a.graph), parseGraph(b.graph), { a: a.id, b: b.id }))));
}

// findings + groups
const lf = (await call("list_findings", { limit: 500 })).json;
check("list_findings: equal the export's findings", lf.findings, JSON.parse(JSON.stringify(exp.findings)));
const lg = (await call("list_typical_groups", { limit: 500 })).json;
check("list_typical_groups: groups", lg.groups.map((g: { group: unknown }) => g.group), JSON.parse(JSON.stringify(exp.groups)));
check("list_typical_groups: group links", lg.groups.flatMap((g: { links: unknown[] }) => g.links).length, exp.group_links.length);

// get_page_image: a link's page, cropped to its first rect with the rect highlighted
const link = beam.calcs.find((l) => l.evidence.rects.length)!;
const r0 = link.evidence.rects[0]!;
const crop = [r0[0] - 60, r0[1] - 30, r0[2] + 60, r0[3] + 30];
const img = await call("get_page_image", { page: link.page, rect: crop, highlight: link.evidence.rects, width: 900 });
const png = img.content.find((c) => c.type === "image")!;
const bytes = Buffer.from(png.data!, "base64");
check("get_page_image: PNG image content", [png.mimeType, bytes.subarray(1, 4).toString()], ["image/png", "PNG"]);
check("get_page_image: crop width in pixels", bytes.readUInt32BE(16), img.json.pixels[0]);
check("get_page_image: pdf sha256 is the run's", img.json.source.pdf_sha256, run.producers.calc_package?.sha256);
const full = await call("get_page_image", { page: 1 });
check("get_page_image: full page", full.json.area_pt, [0, 0, pkg.combined.pages[0]!.width, pkg.combined.pages[0]!.height]);
if (values.out) writeFileSync(values.out.replace(/\.json$/, ".png"), bytes);

// move_column: equals move-impact called directly
const mc = (await call("move_column", { column: col.global_id, dx: 1.5, dy: 0 })).json;
const direct = moveImpact({ graph, graphSha256: await sha256Json(graph), move: { column: col.global_id, dx: 1.5, dy: 0 }, links: state.links });
check(`move_column ${col.mark} dx 1.5 m: equals move-impact`, mc.result, JSON.parse(JSON.stringify(direct)));

await client.close();
const failed = results.filter((r) => !r.ok);
console.log(`\n${results.length - failed.length}/${results.length} checks passed`);
if (values.out) writeFileSync(values.out, JSON.stringify({ file, results }, null, 2));
process.exit(failed.length ? 1 : 0);
