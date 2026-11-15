/**
 * End-to-end parity check: launch the real CLI over stdio with the official MCP client, call EVERY
 * tool, and compare each result with what @unloaded/ifc-parser, @unloaded/element-graph and
 * @unloaded/calc-parser return when called DIRECTLY here (independently of the server's own code).
 * Decision writes go to a temp decisions file; the inputs are never modified.
 *
 *   node packages/mcp-server/scripts/mcp-parity.ts                      # the calc-parser fixture
 *   node packages/mcp-server/scripts/mcp-parity.ts --model m.ifc --calcs a.pdf [--calcs b.pdf ...]
 *   node packages/mcp-server/scripts/mcp-parity.ts --two-pdf            # the fixture PDF twice, under two temp names
 *
 * Exit 1 on any mismatch. One line per check.
 */
import { createHash } from "node:crypto";
import { copyFileSync, existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { basename, dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { isDeepStrictEqual, parseArgs } from "node:util";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";
import * as pdfjs from "pdfjs-dist/legacy/build/pdf.mjs";
import { parseIfc } from "@unloaded/ifc-parser";
import { buildGraph } from "@unloaded/element-graph";
import {
  ENGINE_VERSION,
  effectiveLinks,
  exportMapping,
  inferCalcDeps,
  mapCalcs,
  mappingStatuses,
  propagateImpact,
  readPdf,
  rectsForSpan,
  toCalcElements,
  type Calc,
  type CalcEdge,
  type CalcLink,
  type CalcPage,
  type Decision,
  type PdfjsLike,
} from "@unloaded/calc-parser";

const here = dirname(fileURLToPath(import.meta.url));
const fixture = (n: string) => resolve(here, "../../calc-parser/test/fixtures", n);

const { values } = parseArgs({
  options: { model: { type: "string" }, calcs: { type: "string", multiple: true }, "two-pdf": { type: "boolean" }, keep: { type: "boolean" } },
});
const tmp = mkdtempSync(join(tmpdir(), "unloaded-mcp-parity-"));
const modelPath = resolve(values.model ?? fixture("model_rev1.ifc"));
let calcPaths = (values.calcs ?? [fixture("calc_package.pdf")]).map((p) => resolve(p));
if (values["two-pdf"]) {
  const a = join(tmp, "main-package.pdf");
  const b = join(tmp, "Supplement A.pdf");
  copyFileSync(calcPaths[0]!, a);
  copyFileSync(calcPaths[0]!, b);
  calcPaths = [a, b];
}
const decisionsPath = join(tmp, "decisions.json");
const ACTOR = "parity-check";
const sha = (b: Uint8Array | string) => createHash("sha256").update(b).digest("hex");
const plain = <T>(v: T): T => JSON.parse(JSON.stringify(v)) as T;

// ------------------------------------------------------------------ direct: the engine packages
const modelBytes = new Uint8Array(readFileSync(modelPath));
const modelInput = await parseIfc(modelBytes, { fileName: basename(modelPath) });
const { graph } = buildGraph(modelInput);
const els = toCalcElements(graph.nodes(), new Map(graph.levels().map((l) => [l.id, l.name])));
const gids = new Set(els.map((e) => e.global_id));
const elById = new Map(els.map((e) => [e.global_id, e]));
const loadEdges = graph.edges().filter((e) => e.kind === "supports").map((e) => ({ src: e.a, dst: e.b, rule: e.evidence[0]?.rule ?? "" }));

const slug = (f: string) => basename(f).replace(/\.[^.]+$/, "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "") || "pdf";
interface Doc { name: string; sha: string; prefix: string; pages: CalcPage[]; calcs: Calc[]; links: CalcLink[]; edges0: CalcEdge[]; offset: number }
const docs: Doc[] = [];
let offset = 0;
for (const [i, p] of calcPaths.entries()) {
  const bytes = new Uint8Array(readFileSync(p));
  const pkg = await readPdf(bytes, pdfjs as unknown as PdfjsLike);
  const m = mapCalcs(els, pkg.pages);
  const prefix = i === 0 ? "" : `${slug(p)}/`;
  const pre = (k: string) => prefix + k;
  docs.push({
    name: basename(p), sha: sha(bytes), prefix, pages: pkg.pages,
    calcs: m.calcs.map((c) => ({ ...c, key: pre(c.key) })),
    links: m.links.map((l) => ({ ...l, calc_key: pre(l.calc_key) })),
    edges0: m.calcEdges.map((e) => ({ ...e, src: pre(e.src), dst: pre(e.dst), evidence: e.evidence.map((v) => ({ ...v, calc: pre(v.calc) })) })),
    offset,
  });
  offset += pkg.pages.length;
}
const calcs = docs.flatMap((d) => d.calcs);
const calcKeys = new Set(calcs.map((c) => c.key));
const docOf = new Map(docs.flatMap((d) => d.calcs.map((c) => [c.key, d] as const)));
const rawLinks = docs.flatMap((d) => d.links);

interface State { log: Decision[]; links: CalcLink[]; byElement: Map<string, string>; counts: Record<string, number>; edges: Array<CalcEdge & { cross_pdf: boolean }> }
function direct(): State {
  const log: Decision[] = existsSync(decisionsPath) ? JSON.parse(readFileSync(decisionsPath, "utf8")) : [];
  const links = effectiveLinks(rawLinks, log, gids, calcKeys);
  const st = mappingStatuses(els, links);
  const edges: State["edges"] = [];
  for (const d of docs) {
    const own = new Set(d.calcs.map((c) => c.key));
    for (const e of inferCalcDeps(d.calcs, d.pages, links.filter((l) => own.has(l.calc_key)))) edges.push({ ...e, cross_pdf: false });
  }
  if (docs.length > 1) {
    const pages = docs.flatMap((d) => d.pages.map((p) => ({ ...p, n: p.n + d.offset })));
    const ls = links.map((l) => (l.page === null ? l : { ...l, page: l.page + docOf.get(l.calc_key)!.offset }));
    const noPages = calcs.map((c) => ({ ...c, pages: [] as number[] }));
    for (const e of inferCalcDeps(noPages, pages, ls)) {
      if (docOf.get(e.src) === docOf.get(e.dst)) continue;
      edges.push({ ...e, cross_pdf: true, evidence: e.evidence.map((v) => ({ ...v, page: v.page === null ? null : v.page - docOf.get(v.calc)!.offset })) });
    }
  }
  return { log, links, byElement: st.byElement, counts: st.counts, edges };
}

// ------------------------------------------------------------------ via MCP: the real CLI
const bin = join(here, "..", "bin", "unloaded-mcp-server.mjs");
const calcArgs = calcPaths.flatMap((p) => ["--calcs", p]);
async function connect(extra: string[]) {
  const client = new Client({ name: "mcp-parity", version: "0.0.0" });
  await client.connect(
    new StdioClientTransport({ command: process.execPath, args: [bin, "--model", modelPath, ...calcArgs, ...extra], stderr: "ignore" }),
  );
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
console.log(`# ${basename(modelPath)} + ${docs.map((d) => d.name).join(", ")}  (${els.length} elements, ${calcs.length} calcs, ${rawLinks.length} links, ${S.edges.length} calc edges)`);

// sanity: with no decisions, per-PDF edges equal mapCalcs' own edges
check("direct: per-PDF inferCalcDeps on effective links == mapCalcs edges (no decisions)",
  S.edges.filter((e) => !e.cross_pdf).map(({ cross_pdf: _, ...e }) => e), docs.flatMap((d) => d.edges0));

// tools listed + annotations
const listed = (await client.listTools()).tools;
const EXPECTED = ["calc_dependencies", "export_mapping", "get_calc", "get_element", "get_page_image", "impact_of_change", "list_calcs",
  "project_summary", "record_decision", "record_decisions", "review_status", "search_calc_text", "search_elements", "trace_load_path"];
check("tools listed", listed.map((t) => t.name).sort(), EXPECTED);
check("read tools annotated readOnlyHint true", listed.filter((t) => !t.name.startsWith("record_")).every((t) => t.annotations?.readOnlyHint === true), true);
check("write tools annotated readOnlyHint false, idempotentHint false",
  listed.filter((t) => t.name.startsWith("record_")).map((t) => [t.annotations?.readOnlyHint, t.annotations?.idempotentHint]), [[false, false], [false, false]]);

// project_summary
const sum = track("project_summary", (await call("project_summary")).json);
check("summary: elements", sum.model.elements, els.length);
check("summary: nodes by kind", sum.model.nodes_by_kind, graph.stats().nodesByKind);
check("summary: supports edges", sum.model.supports_edges, loadEdges.length);
check("summary: calcs", sum.calcs.map((c: { key: string }) => c.key), calcs.map((c) => c.key));
check("summary: calc PDFs (name, sha256, prefix, pages)", sum.calc_pdfs.map((d: Record<string, unknown>) => [d.file, d.sha256, d.key_prefix, d.pages]),
  docs.map((d) => [d.name, d.sha, d.prefix, d.pages.length]));
check("summary: links", sum.links.total, S.links.length);
check("summary: status counts", sum.element_status, S.counts);
check("summary: calc edges (total, cross)", [sum.calc_edges.total, sum.calc_edges.cross_pdf], [S.edges.length, S.edges.filter((e) => e.cross_pdf).length]);
check("summary: source (model sha, engine)", [sum.source.model.sha256, sum.source.engine], [sha(modelBytes), ENGINE_VERSION]);

// search_elements
const cnt = async (a: Record<string, unknown>) => (await call("search_elements", { ...a, limit: 1 })).json.total;
track("search_elements", 0);
check("search_elements: category Column", await cnt({ category: "Column" }), els.filter((e) => e.cat === "Column").length);
check("search_elements: kind beam", await cnt({ kind: "beam" }), graph.nodesByKind("beam").length);
check("search_elements: status review", await cnt({ status: "review" }), S.counts.review);
check("search_elements: status unmapped", await cnt({ status: "unmapped" }), S.counts.unmapped);
const aProfile = els.find((e) => e.cat === "Beam" && e.profile)!.profile;
check(`search_elements: profile ${aProfile}`, await cnt({ profile: aProfile }), els.filter((e) => e.profile.includes(aProfile)).length);
const page2 = (await call("search_elements", { category: "Connection", offset: 10, limit: 5 })).json;
check("search_elements: pagination", [page2.offset, page2.returned, page2.next_offset], [10, 5, 15]);

// get_element: every element's links and status
const linkKey = (l: { calc_key: string; tier: string; conf: number; rule: string; page: number | null; token: string; span: unknown; rects: unknown; status?: string }) =>
  ({ calc_key: l.calc_key, tier: l.tier, conf: l.conf, rule: l.rule, page: l.page, token: l.token, span: l.span, rects: l.rects, status: l.status ?? "auto" });
const byConf = (a: CalcLink, b: CalcLink) => b.conf - a.conf || (a.calc_key < b.calc_key ? -1 : a.calc_key > b.calc_key ? 1 : 0);
async function checkElement(gid: string, label: string) {
  const ge = (await call("get_element", { id: gid })).json;
  const want = S.links.filter((l) => l.global_id === gid).sort(byConf).map(linkKey);
  return isDeepStrictEqual(plain(ge.links.map(linkKey)), plain(want)) && ge.status === S.byElement.get(gid) ? null : `${label} ${gid}`;
}
track("get_element", 0);
const bad: string[] = [];
for (const e of els) {
  const r = await checkElement(e.global_id, e.mark);
  if (r) bad.push(r);
}
check(`get_element: links (tier, conf, rule, page, token, span, rects, status) + status for all ${els.length} elements`, bad, []);
const beam = els.find((e) => e.cat === "Beam" && graph.supportsOf(e.global_id).length && e.mark)!;
const gb = (await call("get_element", { id: beam.mark })).json;
check(`get_element ${beam.mark} by mark resolves`, gb.element.global_id, beam.global_id);
check(`get_element ${beam.mark}: bears_on / carries`, [gb.connectivity.bears_on.map((x: { global_id: string }) => x.global_id), gb.connectivity.carries.map((x: { global_id: string }) => x.global_id)],
  [graph.supportsOf(beam.global_id), graph.supportedBy(beam.global_id)]);
check(`get_element ${beam.mark}: connections`, gb.connectivity.connections.map((x: { global_id: string }) => x.global_id).sort(), graph.connectionsOf(beam.global_id).sort());
check(`get_element ${beam.mark}: one-hop load path down`, gb.load_path.down.map((x: { global_id: string; depth: number }) => [x.global_id, x.depth]).sort(),
  [...graph.loadPathDown(beam.global_id)].filter(([id, d]) => id !== beam.global_id && d <= 1).sort());

// list_calcs + get_calc for every calc
const lc = track("list_calcs", (await call("list_calcs", { limit: 500 })).json);
check("list_calcs: keys in order", lc.items.map((c: { key: string }) => c.key), calcs.map((c) => c.key));
if (docs.length > 1) {
  const l2 = (await call("list_calcs", { pdf: docs[1]!.name, limit: 500 })).json;
  check("list_calcs: pdf filter", l2.items.map((c: { key: string }) => c.key), docs[1]!.calcs.map((c) => c.key));
}
track("get_calc", 0);
const badCalc: string[] = [];
for (const c of calcs) {
  const g = (await call("get_calc", { key: c.key, element_limit: 1000 })).json;
  const ls = S.links.filter((l) => l.calc_key === c.key);
  const ok = g.calc.pages.join() === c.pages.join() && g.calc.pdf.file === docOf.get(c.key)!.name &&
    g.linked_elements.total === ls.length &&
    isDeepStrictEqual(g.calc_edges.feeds.map((e: { dst: string }) => e.dst), S.edges.filter((e) => e.src === c.key).map((e) => e.dst)) &&
    isDeepStrictEqual(g.calc_edges.fed_by.map((e: { src: string }) => e.src), S.edges.filter((e) => e.dst === c.key).map((e) => e.src));
  if (!ok) badCalc.push(c.key);
}
check(`get_calc: pages, PDF, linked elements, feeds / fed_by for all ${calcs.length} calcs`, badCalc, []);
const textCalc = calcs.find((c) => c.pages.length > 1 && !c.scanned)!;
const gt = (await call("get_calc", { key: textCalc.key, include_text: true, page_limit: 1, page_offset: 1 })).json;
check(`get_calc ${textCalc.key}: include_text page 2 equals the PDF page text`, gt.text.items[0], {
  page: textCalc.pages[1], text: docOf.get(textCalc.key)!.pages.find((p) => p.n === textCalc.pages[1])!.text,
});

// search_calc_text
const q = aProfile;
const st = track("search_calc_text", (await call("search_calc_text", { query: q, limit: 500 })).json);
let want = 0;
for (const d of docs) for (const p of d.pages) for (let i = p.text.toLowerCase().indexOf(q.toLowerCase()); i >= 0; i = p.text.toLowerCase().indexOf(q.toLowerCase(), i + q.length)) want++;
check(`search_calc_text "${q}": hit count`, st.total, want);
const h0 = st.items[0];
const hp = docs.find((d) => d.name === h0.pdf)!.pages.find((p) => p.n === h0.page)!;
check("search_calc_text: first hit span text + rects (rectsForSpan)", [hp.text.slice(h0.span[0], h0.span[1]), h0.rects], [h0.snippet.match, rectsForSpan(hp, h0.span[0], h0.span[1])]);

// trace_load_path
const slab = els.find((e) => e.cat === "Slab")!;
const tr = track("trace_load_path", (await call("trace_load_path", { id: slab.global_id, direction: "both" })).json);
check(`trace_load_path ${slab.mark || slab.global_id} down == loadPathDown`, tr.down.elements.map((x: { global_id: string; depth: number }) => [x.global_id, x.depth]).sort(),
  [...graph.loadPathDown(slab.global_id)].filter(([id]) => id !== slab.global_id).sort());
const footing = els.find((e) => e.cat === "Footing")!;
const tu = (await call("trace_load_path", { id: footing.global_id, direction: "up", max_depth: 2 })).json;
check(`trace_load_path footing up max_depth 2 == loadPathUp (depth <= 2)`, tu.up.elements.map((x: { global_id: string; depth: number }) => [x.global_id, x.depth]).sort(),
  [...graph.loadPathUp(footing.global_id)].filter(([id, d]) => id !== footing.global_id && d <= 2).sort());

// calc_dependencies
const edgeK = (e: { src: string; dst: string; rules: string[]; cross_pdf: boolean; evidence: unknown[] }) => ({ src: e.src, dst: e.dst, rules: e.rules, cross_pdf: e.cross_pdf, evidence: (e.evidence as Array<Record<string, unknown>>).map(({ pdf: _p, ...v }) => v) });
const cd = track("calc_dependencies", (await call("calc_dependencies", { limit: 500 })).json);
check("calc_dependencies: whole graph (src, dst, rules, evidence, cross_pdf)", cd.items.map(edgeK), S.edges.map(edgeK));
const hub = S.edges[0]!.src;
const cdk = (await call("calc_dependencies", { key: hub })).json;
check(`calc_dependencies ${hub} depth 1`, cdk.items.map((e: { src: string; dst: string }) => `${e.src}>${e.dst}`).sort(),
  S.edges.filter((e) => e.src === hub || e.dst === hub).map((e) => `${e.src}>${e.dst}`).sort());
if (docs.length > 1) {
  const cross = S.edges.filter((e) => e.cross_pdf);
  check("two PDFs: cross-PDF edges only carry the cross-reference rule", cross.every((e) => e.rules.every((r) => r.startsWith("cross-reference"))), true);
  check("two PDFs: cross-PDF evidence pages lie within their own PDF", cross.every((e) => e.evidence.every((v) => v.page !== null && v.page >= 1 && v.page <= docOf.get(v.calc)!.pages.length)), true);
  check("two PDFs: no page-reference edge spans two PDFs", S.edges.filter((e) => e.rules.some((r) => r.startsWith("page reference"))).every((e) => docOf.get(e.src) === docOf.get(e.dst)), true);
}

// impact_of_change
const col = els.find((e) => e.cat === "Column" && graph.supportedBy(e.global_id).length)!;
track("impact_of_change", 0);
for (const mode of ["change", "remove"] as const) {
  const r = (await call("impact_of_change", { id: col.global_id, mode })).json;
  check(`impact_of_change ${col.mark} ${mode} == propagateImpact`, r.impact, propagateImpact(col.global_id, mode, loadEdges, S.links, S.edges, elById));
}

// review_status
const rs = track("review_status", (await call("review_status", { limit: 500 })).json);
check("review_status: counts / needs_review / unmapped / low-confidence totals",
  [rs.counts, rs.needs_review.total, rs.unmapped.total, rs.low_confidence_links.total],
  [S.counts, S.counts.review, S.counts.unmapped, S.links.filter((l) => l.status !== "rejected" && (l.status ?? "auto") === "auto" && l.conf < 0.8).length]);

// export_mapping
const exportDirect = () => exportMapping({
  model: basename(modelPath), modelRevision: sha(modelBytes).slice(0, 12),
  calcPackage: docs.map((d) => d.name).join(" + "), calcRevision: docs.map((d) => d.sha.slice(0, 12)).join(" + "),
  engine: ENGINE_VERSION, elements: els.map((e) => ({ ...e, ifc_type: graph.getNode(e.global_id)?.source?.nativeType ?? "" })),
  calcs, links: S.links, calcEdges: S.edges, loadPath: loadEdges,
});
const ex = track("export_mapping", (await call("export_mapping")).json);
check("export_mapping == exportMapping", ex.report, exportDirect());

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
const ev = S.edges.find((e) => e.evidence[0]?.rects.length)!;
const ei = await call("get_page_image", { edge_src: ev.src, edge_dst: ev.dst });
check("get_page_image calc edge: page + highlight == evidence", [ei.json.page, ei.json.highlight], [ev.evidence[0]!.page, ev.evidence[0]!.rects]);
const fp = await call("get_page_image", { page: 1, pdf: docs.at(-1)!.name });
check("get_page_image full page: area == page size", fp.json.area_pt, [0, 0, docs.at(-1)!.pages[0]!.width, docs.at(-1)!.pages[0]!.height].map((v) => Math.round(v * 100) / 100));
check("get_page_image: source names the PDF + sha256", im.json.source.calc_pdfs, [{ file: docOf.get(lk.calc_key)!.name, sha256: docOf.get(lk.calc_key)!.sha, key_prefix: docOf.get(lk.calc_key)!.prefix }]);

// ------------------------------------------------------------------ writes
const reviewEl = els.find((e) => S.byElement.get(e.global_id) === "review")!;
const reviewLink = S.links.filter((l) => l.global_id === reviewEl.global_id).sort(byConf)[0]!;
const rd = track("record_decision", (await call("record_decision", { global_id: reviewEl.global_id, calc_key: reviewLink.calc_key, action: "confirm", note: "checked" })).json);
S = direct();
check("record_decision confirm: file has the decision", S.log.map((d) => [d.global_id, d.calc_key, d.action, d.actor, d.note]), [[reviewEl.global_id, reviewLink.calc_key, "confirm", ACTOR, "checked"]]);
check("record_decision confirm: status review -> confirmed (== mappingStatuses)", [rd.recorded[0].status_before, rd.recorded[0].status_after, S.byElement.get(reviewEl.global_id)], ["review", "confirmed", "confirmed"]);
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
const unm = els.find((e) => S.byElement.get(e.global_id) === "unmapped") ?? els.find((e) => !S.links.some((l) => l.global_id === e.global_id && l.calc_key === calcs.find((c) => !c.front)!.key))!;
const manualCalc = calcs.find((c) => !c.front && !c.scanned && !S.links.some((l) => l.global_id === unm.global_id && l.calc_key === c.key))!;
const rb = track("record_decisions", (await call("record_decisions", { decisions: [
  { global_id: rej.global_id, calc_key: rej.calc_key, action: "reject", note: "wrong calc" },
  { global_id: unm.global_id, calc_key: manualCalc.key, action: "manual" },
  { global_id: reviewEl.global_id, calc_key: reviewLink.calc_key, action: "undo" },
] })).json);
S = direct();
check("record_decisions: 3 appended, file has 4 entries", [rb.recorded.length, S.log.length], [3, 4]);
check("record_decisions: reject / manual / undo reflected (get_element == effectiveLinks)",
  [await checkElement(rej.global_id, "reject"), await checkElement(unm.global_id, "manual"), await checkElement(reviewEl.global_id, "undo")], [null, null, null]);
check("record_decisions: manual link has tier manual", S.links.find((l) => l.global_id === unm.global_id && l.calc_key === manualCalc.key)?.tier, "manual");
check("after writes: calc edges == inferCalcDeps on effective links", (await call("calc_dependencies", { limit: 500 })).json.items.map(edgeK), S.edges.map(edgeK));
check("after writes: export_mapping == exportMapping", (await call("export_mapping")).json.report, exportDirect());

// someone else appends to the file: the server picks it up, and the next write keeps it
const ext: Decision = { global_id: rej.global_id, calc_key: rej.calc_key, action: "confirm", at: new Date(Date.now() + 1000).toISOString(), actor: "someone else", note: null };
writeFileSync(decisionsPath, JSON.stringify([...S.log, ext], null, 2));
S = direct();
check("external edit: get_element reflects a decision written by someone else", await checkElement(rej.global_id, "external"), null);
const rx = (await call("record_decision", { global_id: unm.global_id, calc_key: manualCalc.key, action: "undo" })).json;
S = direct();
check("external edit: next write keeps it (6 entries, external one intact)", [S.log.length, S.log[4]!.actor, rx.reloaded_external_changes], [6, "someone else", false]);

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
await client.close();

const ro = await connect([]);
const e5 = await raw(ro, "record_decision", { global_id: reviewEl.global_id, calc_key: reviewLink.calc_key, action: "confirm" });
check("error: without --decisions the write tools explain how to enable them", [e5.isError, /--decisions/.test(e5.content[0]!.text!)], [true, true]);
await ro.close();

check("every tool was called", EXPECTED.filter((t) => !called.has(t)), []);
check("inputs untouched (model + PDFs sha256)", [sha(new Uint8Array(readFileSync(modelPath))), ...calcPaths.map((p) => sha(new Uint8Array(readFileSync(p))))], [sha(modelBytes), ...docs.map((d) => d.sha)]);

if (!values.keep) rmSync(tmp, { recursive: true, force: true });
else console.log(`kept ${tmp}`);
const failed = results.filter((r) => !r.ok);
console.log(`\n${results.length - failed.length}/${results.length} checks passed`);
process.exit(failed.length ? 1 : 0);
