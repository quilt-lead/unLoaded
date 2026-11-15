/**
 * Tools on the fixture project (one model, one calc PDF), compared with calc-mapper / element-graph /
 * move-impact called directly: the same check the parity script makes over stdio, here in-process
 * so CI runs it.
 */
import { readFileSync } from "node:fs";
import { beforeAll, describe, expect, it } from "vitest";
import * as pdfjs from "pdfjs-dist/legacy/build/pdf.mjs";
import { ElementGraph, type SerializedElementGraph } from "@unloaded/element-graph";
import {
  ENGINE_VERSION, buildExport, buildState, diffGraphs, extractPdf, impactOf, mapCalcs, parseGraph, segmentCalcs, sha256Json,
  type CalcPackage, type MappingRun, type PdfjsLike, type ProjectState,
} from "@unloaded/calc-mapper";
import { impact as moveImpact } from "@unloaded/move-impact";
import type { Project } from "../src/project.ts";
import * as tools from "../src/tools.ts";
import { MODEL, MODEL_REV2, PDF, inputs, loadProject, plain } from "./helpers.ts";

let p: Project;
let graph: SerializedElementGraph;
let eg: ElementGraph;
let pkg: CalcPackage;
let run: MappingRun;
let state: ProjectState;

/** A graph JSON file as the server (and the app) reads it: ElementGraph.deserialize -> serialize -> parseGraph. */
const graphOf = (path: string) => parseGraph(ElementGraph.deserialize(JSON.parse(readFileSync(path, "utf8"))).serialize());

beforeAll(async () => {
  p = await loadProject(inputs());
  graph = graphOf(MODEL);
  eg = ElementGraph.deserialize(graph);
  pkg = segmentCalcs((await extractPdf(new Uint8Array(readFileSync(PDF)), { pdfjs: pdfjs as unknown as PdfjsLike })).pages, "test_calcs.pdf");
  run = await mapCalcs(graph, pkg);
  state = buildState(graph, pkg, run, []);
}, 120_000);

describe("single PDF: the engine's output, unchanged", () => {
  it("keeps calc-mapper's plain calc keys, links, calc edges, statuses, groups and findings", async () => {
    expect(p.graph.graphSha256).toBe(await sha256Json(graph));
    expect(p.calcs.map((c) => c.key)).toEqual(pkg.calcs.map((c) => c.key));
    expect(plain(p.rawLinks)).toEqual(plain(run.links));
    expect(plain(p.links)).toEqual(plain(state.links));
    expect(p.calcEdges.map(({ cross_pdf, ...e }) => (expect(cross_pdf).toBe(false), plain(e)))).toEqual(plain(state.calc_edges));
    expect(p.counts).toEqual(state.counts);
    expect(plain(p.findings)).toEqual(plain(state.findings));
    expect(plain(p.groups)).toEqual(plain(run.groups));
  });

  it("project_summary counts match the engine and name the sources", () => {
    const s = tools.projectSummary(p);
    expect(s.element_status).toEqual(state.counts);
    expect(s.model.elements).toBe(graph.nodes.length);
    expect(s.model.supports_edges).toBe(graph.edges.filter((e) => e.kind === "supports").length);
    expect(s.findings.total).toBe(state.findings.length);
    expect(s.source).toMatchObject({ model: { file: "test_rev1.graph.json", graph_sha256: p.graph.graphSha256 }, engine: ENGINE_VERSION });
    expect(s.calc_pdfs[0]).toMatchObject({ file: "test_calcs.pdf", key_prefix: "", main: true, extraction: "extracted" });
    expect(s.model_revisions).toHaveLength(1);
  });

  it("get_element resolves a mark and returns every engine field of its links, with connectivity", () => {
    const r = tools.getElement(p, { id: "B-101" });
    expect(r.element.global_id).toBe("B1");
    const want = state.links.filter((l) => l.global_id === "B1");
    expect(r.links.map((l) => [l.calc_key, l.tier, l.conf, l.role, l.band])).toEqual(want.map((l) => [l.calc_key, l.tier, l.conf, l.role, l.band]));
    expect(plain(r.links[0]!.reasons)).toEqual(plain(want[0]!.evidence));
    expect(plain(r.links[0]!.provenance)).toEqual(plain(want[0]!.provenance));
    expect(r.connectivity.bears_on.map((x) => x.global_id)).toEqual(eg.supportsOf("B1"));
    expect(r.connectivity.bears_on[0]!.edges[0]!.evidence.length).toBeGreaterThan(0);
  });

  it("list_findings is the engine's size-mismatch finding (calc W12X40, model W12X53)", () => {
    const r = tools.listFindings(p, {});
    expect(plain(r.items.map(({ element: _e, calc_title: _t, pdf: _p, ...f }) => f))).toEqual(plain(state.findings));
    expect(r.items).toHaveLength(1);
    expect(r.items[0]).toMatchObject({ kind: "size-mismatch", global_id: "C2", calc_key: "column-design-check" });
    expect(r.items[0]!.model_size).toMatch(/W12X53/);
    expect(r.items[0]!.calc_size).toMatch(/W12X40/);
    expect(tools.getElement(p, { id: "C-2" }).findings).toHaveLength(1);
  });

  it("list_typical_groups is mapCalcs' typical groups", () => {
    const r = tools.listTypicalGroups(p, { limit: 500 });
    expect(plain(r.items.map(({ member_marks: _m, group_links: _g, ...g }) => g))).toEqual(plain(run.groups));
  });

  it("impact_of_change is the engine's impactOf", async () => {
    for (const mode of ["change", "remove"] as const) {
      expect(plain(tools.impactOfChange(p, { id: "C-1", mode }).impact)).toEqual(plain(await impactOf(graph, pkg, run, [], "C1", mode)));
    }
  });

  it("export_mapping is buildExport", () => {
    const r = tools.exportMappingTool(p, {});
    expect(r.packages).toHaveLength(1);
    expect(plain(r.packages[0]!.report)).toEqual(
      plain(buildExport(graph, pkg, run, [], { model: "test_rev1.graph.json", model_revision: 1, calc_package: "test_calcs.pdf", calc_revision: null })),
    );
  });

  it("move_column is move-impact on the graph and the reviewed links, and refuses a beam", () => {
    for (const move of [{ column: "C1", dx: 1, dy: 0 }, { column: "C1", remove: true as const }]) {
      const r = tools.moveColumn(p, { column: "C-1", ...("remove" in move ? { remove: true } : { dx: 1 }) });
      expect(plain(r.result)).toEqual(plain(moveImpact({ graph, graphSha256: p.graph.graphSha256, move, links: state.links })));
    }
    expect(() => tools.moveColumn(p, { column: "B-101", dx: 1 })).toThrow(/not a column/);
    expect(() => tools.moveColumn(p, { column: "C-1" })).toThrow(/give dx and\/or dy/);
  });

  it("compare_revisions needs a second model revision", () => {
    expect(() => tools.compareRevisions(p, {})).toThrow(/repeat --model/);
  });

  it("trace_load_path follows loadPathDown / loadPathUp with max_depth", () => {
    const r = tools.traceLoadPath(p, { id: "B1", direction: "down", max_depth: 1 });
    expect(r.down!.elements.map((x) => [x.global_id, x.depth]).sort()).toEqual(
      [...eg.loadPathDown("B1")].filter(([id, d]) => id !== "B1" && d <= 1).sort(),
    );
    expect(r.down!.truncated).toBe(true);
  });

  it("search_calc_text finds text with rects, scoped by calc", () => {
    const r = tools.searchCalcText(p, { query: "b-101", limit: 500 });
    expect(r.total).toBe(2);
    for (const h of r.items) expect(h.snippet.match.toLowerCase()).toBe("b-101");
    const scoped = tools.searchCalcText(p, { query: "b-101", calc: "column-design-check" });
    expect(scoped.items.map((h) => h.calc_key)).toEqual(["column-design-check"]);
  });

  it("get_page_image highlights a link's rects and crops around them", async () => {
    const l = p.links.find((x) => x.global_id === "B1" && x.tier === "exact")!;
    const { image, meta } = await tools.getPageImage(p, { global_id: "B1", calc_key: l.calc_key });
    expect(Buffer.from(image.png).subarray(1, 4).toString()).toBe("PNG");
    expect(meta.highlight).toEqual(l.rects);
    expect(meta.page).toBe(l.page);
    expect((meta.area_pt as number[])[3]! - (meta.area_pt as number[])[1]!).toBeLessThan(image.page.height);
  });

  it("bad references are actionable errors", () => {
    expect(() => tools.getElement(p, { id: "nope" })).toThrow(/no element with GlobalId or mark "nope"/);
    expect(() => tools.getCalc(p, { key: "column-desig" })).toThrow(/Did you mean: column-design-check/);
    expect(() => tools.listCalcs(p, { pdf: "other.pdf" })).toThrow(/no calc PDF "other.pdf"/);
  });
});

describe("two model revisions", () => {
  it("maps the calcs onto the LAST --model, and compare_revisions is diffGraphs", async () => {
    const p2 = await loadProject(inputs({ models: [MODEL, MODEL_REV2] }));
    expect(p2.current.name).toBe("test_rev2.graph.json");
    expect(p2.elements.map((e) => e.global_id)).not.toContain("F2");
    const r = tools.compareRevisions(p2, {});
    const want = diffGraphs(graphOf(MODEL), graphOf(MODEL_REV2), { a: "test_rev1.graph.json", b: "test_rev2.graph.json" });
    expect(plain(r.compare)).toEqual(plain(want));
    expect(r.compare.removed.map((x) => x.global_id)).toEqual(["F2"]);
    expect(r.compare.changed.map((x) => x.global_id)).toEqual(["C2"]);
    expect(r.calcs_linked_to_diff!.map((x) => x.calc_key)).toContain("column-design-check");
    expect(plain(tools.compareRevisions(p2, { a: 2, b: "test_rev1.graph.json" }).compare)).toEqual(
      plain(diffGraphs(graphOf(MODEL_REV2), graphOf(MODEL), { a: "test_rev2.graph.json", b: "test_rev1.graph.json" })),
    );
    expect(() => tools.compareRevisions(p2, { a: 9 })).toThrow(/no model revision "9"/);
  }, 120_000);
});
