/**
 * End-to-end parity check: launch the real CLI over stdio with the official MCP client, call EVERY
 * tool, and compare each result with what @unloaded/ifc-parser, @unloaded/element-graph,
 * @unloaded/calc-mapper, @unloaded/project-file and @unloaded/move-impact return when called
 * DIRECTLY here (independently of the server's own code). Decision writes go to a temp decisions
 * file; the inputs are never modified.
 *
 *   node packages/mcp-server/scripts/mcp-parity.ts                 # synthetic package: model rev 1 + rev 2 (current), calc_package.pdf
 *   node packages/mcp-server/scripts/mcp-parity.ts --two-pdf       # the same + calc_supplement.pdf as a second calc PDF
 *   node packages/mcp-server/scripts/mcp-parity.ts --model a.ifc [--model b.ifc] --calcs x.pdf [--calcs y.pdf ...]
 *   node packages/mcp-server/scripts/mcp-parity.ts project.calcgraph.json    # a project file (make-project-file.ts)
 *
 * The synthetic package is generated, never committed: `cd tools/calcgraph-reference && uv run python
 * -m synth.generate`. Exit 1 on any mismatch. One line per check.
 */
import { createHash } from "node:crypto";
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { basename, dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { isDeepStrictEqual, parseArgs } from "node:util";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";
import * as pdfjs from "pdfjs-dist/legacy/build/pdf.mjs";
import { parseIfc, hasStepHeader } from "@unloaded/ifc-parser";
import { buildGraph, ElementGraph, type SerializedElementGraph } from "@unloaded/element-graph";
import {
  ENGINE_VERSION, buildExport, buildState, diffGraphs, extractPdf, graphElements, impactOf, inferCalcEdges, loadPath, mapCalcs,
  parseGraph, propagate, rectsForSpan, segmentCalcs, sha256Json, statusOf,
  type Calc, type CalcEdge, type CalcPackage, type DecisionFields, type ElementStatus, type Finding, type GroupLink, type Link,
  type MappingRun, type PdfjsLike, type ProjectState,
} from "@unloaded/calc-mapper";
import { decodeBase64, headOf, parseProjectFile, storedExtractionFor } from "@unloaded/project-file";
import { impact as moveImpact } from "@unloaded/move-impact";

// web-ifc's wasm logs one "[WEB-IFC]" line per entity it cannot fully parse (harmless, often hundreds)
const consoleLog = console.log.bind(console);
console.log = (...a: unknown[]) => (typeof a[0] === "string" && a[0].startsWith("[WEB-IFC]") ? undefined : consoleLog(...a));

const here = dirname(fileURLToPath(import.meta.url));
const synthetic = (n: string) => resolve(here, "../../../tools/calcgraph-reference/data/synthetic", n);

const { values, positionals } = parseArgs({
  allowPositionals: true,
  options: { model: { type: "string", multiple: true }, calcs: { type: "string", multiple: true }, "two-pdf": { type: "boolean" }, keep: { type: "boolean" } },
});
const tmp = mkdtempSync(join(tmpdir(), "unloaded-mcp-parity-"));
const projectPath = positionals[0] ? resolve(positionals[0]) : null;
const modelPaths = (values.model ?? (projectPath ? [] : [synthetic("model_rev1.ifc"), synthetic("model_rev2.ifc")])).map((p) => resolve(p));
const calcPaths = (values.calcs ?? (projectPath ? [] : [synthetic("calc_package.pdf"), ...(values["two-pdf"] ? [synthetic("calc_supplement.pdf")] : [])])).map((p) => resolve(p));
for (const f of [...modelPaths, ...calcPaths, ...(projectPath ? [projectPath] : [])]) {
  if (!existsSync(f)) {
    console.error(`missing input ${f}${f.includes("calcgraph-reference") ? "\n(generate it: cd tools/calcgraph-reference && uv run python -m synth.generate)" : ""}`);
    process.exit(2);
  }
}
const decisionsPath = join(tmp, "decisions.json");
const projectSha0 = projectPath ? createHash("sha256").update(readFileSync(projectPath)).digest("hex") : null;
const ACTOR = "parity-check";
const sha = (b: Uint8Array | string) => createHash("sha256").update(b).digest("hex");
const plain = <T>(v: T): T => JSON.parse(JSON.stringify(v)) as T;
const pdfjsLike = pdfjs as unknown as PdfjsLike;

// ------------------------------------------------------------------ direct: the engine packages
interface Rev { revision: number; name: string; sha: string; graph: SerializedElementGraph }
const revs: Rev[] = [];
interface Doc { name: string; sha: string; prefix: string; bytes: Uint8Array; pkg: CalcPackage; run: MappingRun; offset: number; calcRev: number | null }
const docs: Doc[] = [];
let baseLog: DecisionFields[] = [];
const slug = (f: string) => basename(f).replace(/\.[^.]+$/, "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "") || "pdf";
const prefixPkg = (pkg: CalcPackage, prefix: string): CalcPackage => (prefix ? { ...pkg, calcs: pkg.calcs.map((c) => ({ ...c, key: prefix + c.key })) } : pkg);

async function graphOf(bytes: Uint8Array, name: string): Promise<SerializedElementGraph> {
  if (hasStepHeader(bytes.subarray(0, 1024))) return parseGraph(buildGraph(await parseIfc(bytes, { fileName: name })).graph.serialize());
  const data = JSON.parse(new TextDecoder().decode(bytes));
  return parseGraph(data.format === "unloaded.element-graph" ? ElementGraph.deserialize(data).serialize() : buildGraph(data).graph.serialize());
}

let pdfSources: { name: string; bytes: Uint8Array; stored?: unknown; calcRev: number | null }[] = [];
if (projectPath) {
  const file = parseProjectFile(JSON.parse(readFileSync(projectPath, "utf8")));
  for (const r of [...file.revisions].sort((a, b) => a.id - b.id).filter((r) => r.kind === "model")) {
    revs.push({ revision: r.id, name: r.sourceName, sha: sha(decodeBase64(r.blob)), graph: parseGraph(r.graph) });
  }
  const head = headOf(file.revisions, "calcs")!;
  pdfSources = [{ name: head.sourceName, bytes: decodeBase64(head.blob), stored: head.extraction, calcRev: head.id }];
  baseLog = file.decisions.map((d, i) => ({ id: i + 1, global_id: d.globalId, calc_key: d.calcKey, action: d.action, actor: d.actor, note: d.note, at: d.at, model_rev: d.modelRev, calc_rev: d.calcRev }));
} else {
  for (const [i, p] of modelPaths.entries()) {
    const bytes = new Uint8Array(readFileSync(p));
    revs.push({ revision: i + 1, name: basename(p), sha: sha(bytes), graph: await graphOf(bytes, basename(p)) });
  }
  pdfSources = calcPaths.map((p) => ({ name: basename(p), bytes: new Uint8Array(readFileSync(p)), calcRev: null }));
}
const cur = revs.at(-1)!;
const graph = cur.graph;
const eg = ElementGraph.deserialize(graph);
const graphSha = await sha256Json(graph);
const els = graphElements(graph);
const elById = new Map(els.map((e) => [e.global_id, e]));
const loadEdges = loadPath(graph);
let offset = 0;
for (const [i, s] of pdfSources.entries()) {
  const stored = s.stored !== undefined ? storedExtractionFor(s.stored, sha(s.bytes)) : null;
  const raw = stored?.pkg ?? segmentCalcs((await extractPdf(s.bytes, { pdfjs: pdfjsLike })).pages, s.name);
  const prefix = i === 0 ? "" : `${slug(s.name)}/`;
  const pkg = prefixPkg(raw, prefix);
  docs.push({ name: s.name, sha: sha(s.bytes), prefix, bytes: s.bytes, pkg, run: await mapCalcs(graph, pkg), offset, calcRev: s.calcRev });
  offset += pkg.pages.length;
}
const calcs: Calc[] = docs.flatMap((d) => d.pkg.calcs);
const docOf = new Map(docs.flatMap((d) => d.pkg.calcs.map((c) => [c.key, d] as const)));
const groups = docs[0]!.run.groups;
const single = docs.length === 1;

interface State {
  file: DecisionFields[]; log: DecisionFields[]; states: ProjectState[]; links: Link[]; byElement: Map<string, ElementStatus>;
  counts: Record<ElementStatus, number>; edges: Array<CalcEdge & { cross_pdf: boolean }>; findings: Finding[]; groupLinks: GroupLink[];
}
function direct(): State {
  const file: DecisionFields[] = existsSync(decisionsPath) ? JSON.parse(readFileSync(decisionsPath, "utf8")) : [];
  const log = [...baseLog, ...file.map((d) => ({ ...d, id: d.id + baseLog.length }))];
  const states = docs.map((d) => buildState(graph, d.pkg, d.run, log));
  const links = states.flatMap((s) => s.links);
  const byElement = new Map<string, ElementStatus>();
  const counts: Record<ElementStatus, number> = { confirmed: 0, review: 0, unmapped: 0 };
  for (const e of els) {
    const s = statusOf(links.filter((l) => l.global_id === e.global_id));
    byElement.set(e.global_id, s);
    counts[s] += 1;
  }
  const edges: State["edges"] = states.flatMap((s) => s.calc_edges.map((e) => ({ ...e, cross_pdf: false })));
  if (docs.length > 1) {
    const pages = docs.flatMap((d) => d.pkg.pages.map((p) => ({ ...p, n: p.n + d.offset })));
    const ls = links.map((l) => (l.page === null ? l : { ...l, page: l.page + docOf.get(l.calc_key)!.offset }));
    for (const e of inferCalcEdges(calcs.map((c) => ({ ...c, pages: [], spans: [] })), pages, ls)) {
      if (docOf.get(e.src) === docOf.get(e.dst)) continue;
      edges.push({ ...e, cross_pdf: true, evidence: e.evidence.map((v) => ({ ...v, page: v.page - docOf.get(v.calc)!.offset })) });
    }
  }
  return { file, log, states, links, byElement, counts, edges, findings: states.flatMap((s) => s.findings), groupLinks: states.flatMap((s) => s.group_links) };
}

// ------------------------------------------------------------------ via MCP: the real CLI
const bin = join(here, "..", "bin", "unloaded-mcp-server.mjs");
const inputArgs = projectPath ? ["--project", projectPath] : [...modelPaths.flatMap((p) => ["--model", p]), ...calcPaths.flatMap((p) => ["--calcs", p])];
async function connect(extra: string[]) {
  const client = new Client({ name: "mcp-parity", version: "0.0.0" });
  await client.connect(new StdioClientTransport({ command: process.execPath, args: [bin, ...inputArgs, ...extra], stderr: "ignore" }));
  return client;
}
const client = await connect(["--decisions", decisionsPath, "--actor", ACTOR]);

type Content = { type: string; text?: string; data?: string; mimeType?: string };
async function raw(c: Client, name: string, args: Record<string, unknown> = {}) {
  const r = await c.callTool({ name, arguments: args });
  return { isError: r.isError === true, content: r.content as Content[] };
}
async function call(name: string, args: Record<string, unknown> = {}) {
  const r = await raw(client, name, args);
  if (r.isError) throw new Error(`${name} ${JSON.stringify(args)}: ${r.content[0]?.text}`);
  return { json: JSON.parse(r.content.find((c) => c.type === "text")!.text!), content: r.content };
}

const results: { check: string; ok: boolean; detail?: string }[] = [];
const called = new Set<string>();
function check(name: string, got: unknown, want: unknown) {
  const ok = isDeepStrictEqual(plain(got), plain(want));
  results.push({ check: name, ok, ...(ok ? {} : { detail: `got ${JSON.stringify(got)?.slice(0, 400)}\n     want ${JSON.stringify(want)?.slice(0, 400)}` }) });
  console.log(`${ok ? "ok  " : "FAIL"} ${name}${ok ? "" : `\n     ${results.at(-1)!.detail}`}`);
}
const track = <T>(name: string, v: T) => (called.add(name), v);

let S = direct();
console.log(
  `# ${projectPath ? `${basename(projectPath)}: ` : ""}${revs.map((r) => r.name).join(" -> ")} + ${docs.map((d) => d.name).join(", ")}  ` +
    `(${els.length} elements, ${calcs.length} calcs, ${S.links.length} links, ${S.edges.length} calc edges, ${S.findings.length} findings)`,
);

// sanity: with no decisions, per-PDF edges equal mapCalcs' own edges
if (!baseLog.length) {
  check("direct: buildState calc edges (no decisions) == mapCalcs edges, per PDF",
    S.edges.filter((e) => !e.cross_pdf).map(({ cross_pdf: _, ...e }) => e), docs.flatMap((d) => d.run.calc_edges));
}

// tools listed + annotations
const listed = (await client.listTools()).tools;
const EXPECTED = ["calc_dependencies", "compare_revisions", "export_mapping", "get_calc", "get_element", "get_page_image", "impact_of_change",
  "list_calcs", "list_findings", "list_typical_groups", "move_column", "project_summary", "record_decision", "record_decisions", "review_status",
  "search_calc_text", "search_elements", "trace_load_path"];
check("tools listed", listed.map((t) => t.name).sort(), EXPECTED);
check("read tools annotated readOnlyHint true", listed.filter((t) => !t.name.startsWith("record_")).every((t) => t.annotations?.readOnlyHint === true), true);
check("write tools annotated readOnlyHint false, idempotentHint false",
  listed.filter((t) => t.name.startsWith("record_")).map((t) => [t.annotations?.readOnlyHint, t.annotations?.idempotentHint]), [[false, false], [false, false]]);

// project_summary
const sum = track("project_summary", (await call("project_summary")).json);
check("summary: elements", sum.model.elements, els.length);
check("summary: nodes by kind", sum.model.nodes_by_kind, eg.stats().nodesByKind);
check("summary: supports edges", sum.model.supports_edges, loadEdges.length);
check("summary: model revisions (revision, file, sha256, graph sha256)", sum.model_revisions.map((r: Record<string, unknown>) => [r.revision, r.file, r.sha256, r.graph_sha256]),
  await Promise.all(revs.map(async (r) => [r.revision, r.name, r.sha, await sha256Json(r.graph)])));
check("summary: calcs", sum.calcs.map((c: { key: string }) => c.key), calcs.map((c) => c.key));
check("summary: calc PDFs (name, sha256, prefix, pages)", sum.calc_pdfs.map((d: Record<string, unknown>) => [d.file, d.sha256, d.key_prefix, d.pages]),
  docs.map((d) => [d.name, d.sha, d.prefix, d.pkg.pages.length]));
check("summary: links", sum.links.total, S.links.length);
check("summary: status counts (statusOf over every PDF's links)", sum.element_status, S.counts);
if (single) check("summary: status counts == buildState counts (one PDF)", sum.element_status, S.states[0]!.counts);
check("summary: calc edges (total, cross)", [sum.calc_edges.total, sum.calc_edges.cross_pdf], [S.edges.length, S.edges.filter((e) => e.cross_pdf).length]);
check("summary: typical groups / group links / findings", [sum.typical_groups.total, sum.typical_groups.group_links, sum.findings.total], [groups.length, S.groupLinks.length, S.findings.length]);
check("summary: source (model sha, graph sha, engine)", [sum.source.model.sha256, sum.source.model.graph_sha256, sum.source.engine], [cur.sha, graphSha, ENGINE_VERSION]);
if (projectPath) check("summary: source names the project file + sha256", sum.source.project_file, { file: basename(projectPath), sha256: projectSha0 });

// search_elements
const cnt = async (a: Record<string, unknown>) => (await call("search_elements", { ...a, limit: 1 })).json.total;
track("search_elements", 0);
check("search_elements: category Column", await cnt({ category: "Column" }), els.filter((e) => e.cat === "Column").length);
check("search_elements: kind beam", await cnt({ kind: "beam" }), eg.nodesByKind("beam").length);
check("search_elements: status review", await cnt({ status: "review" }), S.counts.review);
check("search_elements: status unmapped", await cnt({ status: "unmapped" }), S.counts.unmapped);
const aProfile = els.find((e) => e.cat === "Beam" && e.profile)!.profile;
check(`search_elements: profile ${aProfile}`, await cnt({ profile: aProfile }), els.filter((e) => e.profile.toUpperCase().replace(/\s+/g, "").includes(aProfile.toUpperCase().replace(/\s+/g, ""))).length);
const page2 = (await call("search_elements", { category: "Connection", offset: 10, limit: 5 })).json;
check("search_elements: pagination", [page2.offset, page2.returned, page2.next_offset], [10, 5, 15]);

// get_element: every element's links (every engine field) and status
const linkKey = (l: Record<string, unknown>) => ({
  calc_key: l.calc_key, tier: l.tier, conf: l.conf, band: l.band, role: l.role, rule: l.rule, page: l.page, token: l.token, span: l.span,
  rects: l.rects, status: l.status ?? "auto", reasons: l.reasons ?? l.evidence, caveats: l.caveats, via_group: l.via_group ?? null,
  provenance: l.provenance, review_provenance: l.review_provenance ?? null,
});
const byConf = (a: Link, b: Link) => b.conf - a.conf || (a.calc_key < b.calc_key ? -1 : a.calc_key > b.calc_key ? 1 : 0);
async function checkElement(gid: string, label: string) {
  const ge = (await call("get_element", { id: gid })).json;
  const want = S.links.filter((l) => l.global_id === gid).sort(byConf).map((l) => linkKey(l as unknown as Record<string, unknown>));
  return isDeepStrictEqual(plain(ge.links.map(linkKey)), plain(want)) && ge.status === S.byElement.get(gid) ? null : `${label} ${gid}`;
}
track("get_element", 0);
const bad: string[] = [];
for (const e of els) {
  const r = await checkElement(e.global_id, e.mark);
  if (r) bad.push(r);
}
check(`get_element: links (tier, conf, band, role, reasons, caveats, provenance, rects, status...) + status for all ${els.length} elements`, bad, []);
const beam = els.find((e) => e.cat === "Beam" && eg.supportsOf(e.global_id).length && e.mark && els.filter((x) => x.mark === e.mark).length === 1)!;
const gb = (await call("get_element", { id: beam.mark })).json;
check(`get_element ${beam.mark} by mark resolves`, gb.element.global_id, beam.global_id);
check(`get_element ${beam.mark}: bears_on / carries`, [gb.connectivity.bears_on.map((x: { global_id: string }) => x.global_id), gb.connectivity.carries.map((x: { global_id: string }) => x.global_id)],
  [eg.supportsOf(beam.global_id), eg.supportedBy(beam.global_id)]);
check(`get_element ${beam.mark}: connections`, gb.connectivity.connections.map((x: { global_id: string }) => x.global_id).sort(), eg.connectionsOf(beam.global_id).sort());
check(`get_element ${beam.mark}: one-hop load path down`, gb.load_path.down.map((x: { global_id: string; depth: number }) => [x.global_id, x.depth]).sort(),
  [...eg.loadPathDown(beam.global_id)].filter(([id, d]) => id !== beam.global_id && d <= 1).sort());
const grouped = groups.find((g) => S.groupLinks.some((l) => l.group === g.id)) ?? groups[0]!;
const gm = (await call("get_element", { id: grouped.members[0]! })).json;
check("get_element: typical groups + group links of a grouped element", [gm.typical_groups.map((g: { id: string }) => g.id), gm.group_links],
  [groups.filter((g) => g.members.includes(grouped.members[0]!)).map((g) => g.id), S.groupLinks.filter((l) => groups.some((g) => g.id === l.group && g.members.includes(grouped.members[0]!)))]);
if (S.findings.length) {
  const f0 = S.findings[0]!;
  check("get_element: findings of an element with a finding", (await call("get_element", { id: f0.global_id })).json.findings, S.findings.filter((f) => f.global_id === f0.global_id));
}

// list_calcs + get_calc for every calc
const lcs = track("list_calcs", (await call("list_calcs", { limit: 500 })).json);
check("list_calcs: keys in order", lcs.items.map((c: { key: string }) => c.key), calcs.map((c) => c.key));
if (docs.length > 1) {
  const l2 = (await call("list_calcs", { pdf: docs[1]!.name, limit: 500 })).json;
  check("list_calcs: pdf filter", l2.items.map((c: { key: string }) => c.key), docs[1]!.pkg.calcs.map((c) => c.key));
}
track("get_calc", 0);
const badCalc: string[] = [];
for (const c of calcs) {
  const g = (await call("get_calc", { key: c.key, element_limit: 1000 })).json;
  const ls = S.links.filter((l) => l.calc_key === c.key);
  const ok = g.calc.pages.join() === c.pages.join() && g.calc.pdf.file === docOf.get(c.key)!.name &&
    isDeepStrictEqual(plain(g.calc.provenance), plain(c.provenance)) && isDeepStrictEqual(plain(g.calc.spans), plain(c.spans)) &&
    g.linked_elements.total === ls.length &&
    isDeepStrictEqual(plain(g.group_links), plain(S.groupLinks.filter((l) => l.calc_key === c.key))) &&
    isDeepStrictEqual(plain(g.findings), plain(S.findings.filter((f) => f.calc_key === c.key))) &&
    isDeepStrictEqual(g.calc_edges.feeds.map((e: { dst: string }) => e.dst), S.edges.filter((e) => e.src === c.key).map((e) => e.dst)) &&
    isDeepStrictEqual(g.calc_edges.fed_by.map((e: { src: string }) => e.src), S.edges.filter((e) => e.dst === c.key).map((e) => e.src));
  if (!ok) badCalc.push(c.key);
}
check(`get_calc: pages, spans, provenance, PDF, linked elements, group links, findings, feeds / fed_by for all ${calcs.length} calcs`, badCalc, []);
const textCalc = calcs.find((c) => c.pages.length > 1 && !c.scanned)!;
const gt = (await call("get_calc", { key: textCalc.key, include_text: true, page_limit: 1, page_offset: 1 })).json;
check(`get_calc ${textCalc.key}: include_text page 2 equals the PDF page text`, [gt.text.items[0].page, gt.text.items[0].text],
  [textCalc.pages[1], docOf.get(textCalc.key)!.pkg.pages.find((p) => p.n === textCalc.pages[1])!.text]);

// search_calc_text
const q = aProfile;
const st = track("search_calc_text", (await call("search_calc_text", { query: q, limit: 500 })).json);
let want = 0;
for (const d of docs) for (const p of d.pkg.pages) for (let i = p.text.toLowerCase().indexOf(q.toLowerCase()); i >= 0; i = p.text.toLowerCase().indexOf(q.toLowerCase(), i + q.length)) want++;
check(`search_calc_text "${q}": hit count`, st.total, want);
const h0 = st.items[0];
const hp = docs.find((d) => d.name === h0.pdf)!.pkg.pages.find((p) => p.n === h0.page)!;
check("search_calc_text: first hit span text + rects (rectsForSpan)", [hp.text.slice(h0.span[0], h0.span[1]), h0.rects], [h0.snippet.match, rectsForSpan(hp, h0.span[0], h0.span[1])]);

// trace_load_path
const slab = els.find((e) => e.cat === "Slab")!;
const tr = track("trace_load_path", (await call("trace_load_path", { id: slab.global_id, direction: "both" })).json);
check(`trace_load_path ${slab.mark || slab.global_id} down == loadPathDown`, tr.down.elements.map((x: { global_id: string; depth: number }) => [x.global_id, x.depth]).sort(),
  [...eg.loadPathDown(slab.global_id)].filter(([id]) => id !== slab.global_id).sort());
const footing = els.find((e) => e.cat === "Footing")!;
const tu = (await call("trace_load_path", { id: footing.global_id, direction: "up", max_depth: 2 })).json;
check("trace_load_path footing up max_depth 2 == loadPathUp (depth <= 2)", tu.up.elements.map((x: { global_id: string; depth: number }) => [x.global_id, x.depth]).sort(),
  [...eg.loadPathUp(footing.global_id)].filter(([id, d]) => id !== footing.global_id && d <= 2).sort());

// calc_dependencies
const edgeK = (e: { src: string; dst: string; rules: string[]; cross_pdf: boolean; evidence: unknown[]; provenance: unknown }) =>
  ({ src: e.src, dst: e.dst, rules: e.rules, cross_pdf: e.cross_pdf, provenance: e.provenance, evidence: (e.evidence as Array<Record<string, unknown>>).map(({ pdf: _p, ...v }) => v) });
const cd = track("calc_dependencies", (await call("calc_dependencies", { limit: 500 })).json);
check("calc_dependencies: whole graph (src, dst, rules, evidence, provenance, cross_pdf)", cd.items.map(edgeK), S.edges.map(edgeK));
const hub = S.edges[0]!.src;
const cdk = (await call("calc_dependencies", { key: hub })).json;
check(`calc_dependencies ${hub} depth 1`, cdk.items.map((e: { src: string; dst: string }) => `${e.src}>${e.dst}`).sort(),
  S.edges.filter((e) => e.src === hub || e.dst === hub).map((e) => `${e.src}>${e.dst}`).sort());
if (docs.length > 1) {
  const cross = S.edges.filter((e) => e.cross_pdf);
  check("two PDFs: cross-PDF edges only carry the cross-reference rule", cross.every((e) => e.rules.every((r) => r.startsWith("cross-reference"))), true);
  check("two PDFs: cross-PDF evidence pages lie within their own PDF", cross.every((e) => e.evidence.every((v) => v.page >= 1 && v.page <= docOf.get(v.calc)!.pkg.pages.length)), true);
  check("two PDFs: no page-reference edge spans two PDFs", S.edges.filter((e) => e.rules.some((r) => r.startsWith("page reference"))).every((e) => docOf.get(e.src) === docOf.get(e.dst)), true);
  check("two PDFs: every link's page lies within its own PDF", S.links.every((l) => l.page === null || l.page <= docOf.get(l.calc_key)!.pkg.pages.length), true);
}

// impact_of_change
const col = els.find((e) => e.cat === "Column" && eg.supportedBy(e.global_id).length)!;
track("impact_of_change", 0);
for (const mode of ["change", "remove"] as const) {
  const r = (await call("impact_of_change", { id: col.global_id, mode })).json;
  check(`impact_of_change ${col.mark} ${mode} == propagate (every PDF's links + calc edges)`, r.impact,
    propagate(col.global_id, mode, loadEdges, S.links, S.edges, elById, [graphSha, ...docs.map((d) => d.sha)]));
  if (single) check(`impact_of_change ${col.mark} ${mode} == impactOf (one PDF)`, r.impact, await impactOf(graph, docs[0]!.pkg, docs[0]!.run, S.log, col.global_id, mode));
}

// review_status
const rs = track("review_status", (await call("review_status", { limit: 500 })).json);
check("review_status: counts / needs_review / unmapped / low-confidence totals",
  [rs.counts, rs.needs_review.total, rs.unmapped.total, rs.low_confidence_links.total],
  [S.counts, S.counts.review, S.counts.unmapped, S.links.filter((l) => l.status !== "rejected" && (l.status ?? "auto") === "auto" && l.conf < 0.75).length]);

// list_findings / list_typical_groups
const lf = track("list_findings", (await call("list_findings", { limit: 500 })).json);
check("list_findings == buildState findings (every PDF)", lf.items.map(({ element: _e, calc_title: _t, pdf: _p, ...f }: Record<string, unknown>) => f), S.findings);
const lg = track("list_typical_groups", (await call("list_typical_groups", { limit: 500 })).json);
check("list_typical_groups: groups == mapCalcs groups", lg.items.map(({ member_marks: _m, group_links: _g, ...g }: Record<string, unknown>) => g), groups);
check("list_typical_groups: group links == buildState group links",
  lg.items.flatMap((g: { group_links: Array<Record<string, unknown>> }) => g.group_links.map(({ calc_title: _t, pdf: _p, ...l }) => l)),
  groups.flatMap((g) => S.groupLinks.filter((l) => l.group === g.id)));

// compare_revisions
track("compare_revisions", 0);
if (revs.length > 1) {
  const a = revs.at(-2)!;
  const cr = (await call("compare_revisions", {})).json;
  check(`compare_revisions ${a.name} -> ${cur.name} (default) == diffGraphs`, cr.compare,
    diffGraphs(a.graph, cur.graph, projectPath ? { a: a.revision, b: cur.revision } : { a: a.name, b: cur.name }));
  const rev = (await call("compare_revisions", { a: cur.revision, b: a.name })).json;
  check("compare_revisions reversed (by revision number and file name) == diffGraphs", rev.compare,
    diffGraphs(cur.graph, a.graph, projectPath ? { a: cur.revision, b: a.revision } : { a: cur.name, b: a.name }));
} else {
  const e = await raw(client, "compare_revisions", {});
  check("compare_revisions with one model revision explains how to add one", [e.isError, /repeat --model/.test(e.content[0]!.text!)], [true, true]);
}

// move_column
track("move_column", 0);
for (const move of [{ column: col.global_id, dx: 1.5, dy: 0 }, { column: col.global_id, remove: true as const }]) {
  const r = (await call("move_column", move)).json;
  check(`move_column ${col.mark} ${"remove" in move ? "remove" : "dx 1.5"} == move-impact impact`, r.result, moveImpact({ graph, graphSha256: graphSha, move, links: S.links }));
}

// export_mapping
const exportDirect = () => docs.map((d) => buildExport(graph, d.pkg, d.run, S.log, {
  model: cur.name, model_revision: cur.revision, calc_package: d.name, calc_revision: d.calcRev,
}));
const ex = track("export_mapping", (await call("export_mapping")).json);
check("export_mapping == buildExport per calc PDF", ex.packages.map((x: { report: unknown }) => x.report), exportDirect());

// get_page_image: a link, a span, a calc edge's evidence, a full page
track("get_page_image", 0);
const pngOk = (c: Content[]) => {
  const img = c.find((x) => x.type === "image")!;
  const b = Buffer.from(img.data!, "base64");
  return [img.mimeType, b.subarray(1, 4).toString(), b.readUInt32BE(16)];
};
const lk = S.links.find((l) => l.rects.length && l.tier === "exact" && docOf.get(l.calc_key)!.prefix === docs.at(-1)!.prefix)!;
const im = await call("get_page_image", { global_id: lk.global_id, calc_key: lk.calc_key, width: 800 });
check("get_page_image link: PNG (width == meta.pixels), page, PDF, highlight == link rects",
  [pngOk(im.content), im.json.page, im.json.pdf, im.json.highlight], [["image/png", "PNG", im.json.pixels[0]], lk.page, docOf.get(lk.calc_key)!.name, lk.rects]);
const sp = await call("get_page_image", { pdf: h0.pdf, page: h0.page, span: h0.span });
check("get_page_image span: highlight == rectsForSpan", sp.json.highlight, rectsForSpan(hp, h0.span[0], h0.span[1]));
const ev = S.edges.find((e) => e.evidence[0]?.rects?.length)!;
const ei = await call("get_page_image", { edge_src: ev.src, edge_dst: ev.dst });
check("get_page_image calc edge: page + highlight == evidence", [ei.json.page, ei.json.highlight], [ev.evidence[0]!.page, ev.evidence[0]!.rects]);
const fp = await call("get_page_image", { page: 1, pdf: docs.at(-1)!.name });
check("get_page_image full page: area == page size", fp.json.area_pt, [0, 0, docs.at(-1)!.pkg.pages[0]!.width, docs.at(-1)!.pkg.pages[0]!.height].map((v) => Math.round(v * 100) / 100));
check("get_page_image: source names the PDF + sha256", im.json.source.calc_pdfs, [{ file: docOf.get(lk.calc_key)!.name, sha256: docOf.get(lk.calc_key)!.sha, key_prefix: docOf.get(lk.calc_key)!.prefix }]);

// ------------------------------------------------------------------ writes
const reviewEl = els.find((e) => S.byElement.get(e.global_id) === "review")!;
const reviewLink = S.links.filter((l) => l.global_id === reviewEl.global_id && l.role === "design" && l.status !== "rejected").sort(byConf)[0]!;
const rd = track("record_decision", (await call("record_decision", { global_id: reviewEl.global_id, calc_key: reviewLink.calc_key, action: "confirm", note: "checked" })).json);
S = direct();
const rdoc = docOf.get(reviewLink.calc_key)!;
check("record_decision confirm: the file holds one calc-mapper Decision (id, fields, revisions)",
  S.file.map((d) => [d.id, d.global_id, d.calc_key, d.action, d.actor, d.note, d.model_rev, d.calc_rev]),
  [[1, reviewEl.global_id, reviewLink.calc_key, "confirm", ACTOR, "checked", projectPath ? cur.revision : cur.name, rdoc.calcRev ?? rdoc.name]]);
check("record_decision confirm: human provenance (rule, actor, at, inputs = graph + PDF)",
  [S.file[0]!.provenance?.method, S.file[0]!.provenance?.rule, S.file[0]!.provenance?.actor, S.file[0]!.provenance?.at, S.file[0]!.provenance?.inputs],
  ["human", "decision.confirm", ACTOR, S.file[0]!.at, [graphSha, rdoc.sha]]);
check("record_decision confirm: status review -> confirmed (== statusOf)", [rd.recorded[0].status_before, rd.recorded[0].status_after, S.byElement.get(reviewEl.global_id)], ["review", "confirmed", "confirmed"]);
check("record_decision confirm: get_element reflects it", await checkElement(reviewEl.global_id, "after confirm"), null);
check("record_decision: summary counts == direct", (await call("project_summary")).json.element_status, S.counts);

// batch: one invalid -> nothing written
const before = readFileSync(decisionsPath, "utf8");
const r1 = await raw(client, "record_decisions", { decisions: [
  { global_id: reviewEl.global_id, calc_key: reviewLink.calc_key, action: "undo" },
  { global_id: "NOT-A-GUID", calc_key: reviewLink.calc_key, action: "confirm" },
] });
check("record_decisions with an invalid entry: error, file unchanged", [r1.isError, readFileSync(decisionsPath, "utf8") === before, /nothing was written/.test(r1.content[0]!.text!)], [true, true, true]);

// batch: reject + manual + undo
const rej = S.links.find((l) => l.tier === "exact" && l.global_id !== reviewEl.global_id)!;
const unm = els.find((e) => S.byElement.get(e.global_id) === "unmapped") ?? els.find((e) => !S.links.some((l) => l.global_id === e.global_id))!;
const manualCalc = calcs.find((c) => !c.front && !c.scanned && !S.links.some((l) => l.global_id === unm.global_id && l.calc_key === c.key))!;
const rb = track("record_decisions", (await call("record_decisions", { decisions: [
  { global_id: rej.global_id, calc_key: rej.calc_key, action: "reject", note: "wrong calc" },
  { global_id: unm.global_id, calc_key: manualCalc.key, action: "manual" },
  { global_id: reviewEl.global_id, calc_key: reviewLink.calc_key, action: "undo" },
] })).json);
S = direct();
check("record_decisions: 3 appended with ids 2, 3, 4", [rb.recorded.length, S.file.map((d) => d.id)], [3, [1, 2, 3, 4]]);
check("record_decisions: reject / manual / undo reflected (get_element == buildState links)",
  [await checkElement(rej.global_id, "reject"), await checkElement(unm.global_id, "manual"), await checkElement(reviewEl.global_id, "undo")], [null, null, null]);
check("record_decisions: manual link has tier manual, role design", [S.links.find((l) => l.global_id === unm.global_id && l.calc_key === manualCalc.key)?.tier, S.byElement.get(unm.global_id)], ["manual", "confirmed"]);
check("after writes: calc edges == buildState on the decision log", (await call("calc_dependencies", { limit: 500 })).json.items.map(edgeK), S.edges.map(edgeK));
check("after writes: export_mapping == buildExport", (await call("export_mapping")).json.packages.map((x: { report: unknown }) => x.report), exportDirect());
check("after writes: findings == buildState findings", (await call("list_findings", { limit: 500 })).json.total, S.findings.length);

// someone else appends to the file: the server picks it up, and the next write keeps it
const ext: DecisionFields = { id: 5, global_id: rej.global_id, calc_key: rej.calc_key, action: "confirm", at: new Date(Date.now() + 1000).toISOString(), actor: "someone else", note: null };
writeFileSync(decisionsPath, JSON.stringify([...S.file, ext], null, 2));
S = direct();
check("external edit: get_element reflects a decision written by someone else", await checkElement(rej.global_id, "external"), null);
const rx = (await call("record_decision", { global_id: unm.global_id, calc_key: manualCalc.key, action: "undo" })).json;
S = direct();
check("external edit: next write keeps it (6 entries, external one intact, next id 6)", [S.file.length, S.file[4]!.actor, S.file[5]!.id, rx.reloaded_external_changes], [6, "someone else", 6, false]);
check("external edit: entries 1-5 byte-identical after the append", S.file.slice(0, 5), [...JSON.parse(before).slice(0, 1), ...S.file.slice(1, 4), ext]);

// errors
const e1 = await raw(client, "get_element", { id: "does-not-exist" });
check("error: unknown element is a tool error", [e1.isError, /no element/.test(e1.content[0]!.text!)], [true, true]);
const e2 = await raw(client, "record_decision", { global_id: els[0]!.global_id, calc_key: "no-such-calc", action: "confirm" });
check("error: unknown calc key on write", [e2.isError, /no calc "no-such-calc"/.test(e2.content[0]!.text!)], [true, true]);
const noLink = els.find((e) => !S.links.some((l) => l.global_id === e.global_id && l.calc_key === manualCalc.key))!;
const e3 = await raw(client, "record_decision", { global_id: noLink.global_id, calc_key: manualCalc.key, action: "confirm" });
check("error: confirm with no automatic link", [e3.isError, /no automatic link/.test(e3.content[0]!.text!)], [true, true]);
const e4 = await raw(client, "get_page_image", { pdf: docs[0]!.name, page: 999 });
check("error: page out of range names the PDF", [e4.isError, /page 999 is not in/.test(e4.content[0]!.text!)], [true, true]);
const beamEl = els.find((e) => e.cat === "Beam")!;
const e5 = await raw(client, "move_column", { column: beamEl.global_id, dx: 1 });
check("error: move_column on a beam", [e5.isError, /not a column/.test(e5.content[0]!.text!)], [true, true]);
await client.close();

const ro = await connect([]);
const e6 = await raw(ro, "record_decision", { global_id: reviewEl.global_id, calc_key: reviewLink.calc_key, action: "confirm" });
check("error: without --decisions the write tools explain how to enable them", [e6.isError, /--decisions/.test(e6.content[0]!.text!)], [true, true]);
await ro.close();

check("every tool was called", EXPECTED.filter((t) => !called.has(t)), []);
check("inputs untouched (models, PDFs, project file: sha256)",
  [...modelPaths, ...calcPaths, ...(projectPath ? [projectPath] : [])].map((p) => sha(new Uint8Array(readFileSync(p)))),
  projectPath ? [projectSha0] : [...revs.map((r) => r.sha), ...docs.map((d) => d.sha)]);

if (!values.keep) rmSync(tmp, { recursive: true, force: true });
else console.log(`kept ${tmp}`);
const failed = results.filter((r) => !r.ok);
console.log(`\n${results.length - failed.length}/${results.length} checks passed`);
process.exit(failed.length ? 1 : 0);
