/**
 * Tools on the fixture, compared with the engine packages called directly (the same check the parity
 * script makes over stdio, here in-process so CI can run it).
 */
import { readFileSync } from "node:fs";
import { beforeAll, describe, expect, it } from "vitest";
import * as pdfjs from "pdfjs-dist/legacy/build/pdf.mjs";
import { parseIfc } from "@unloaded/ifc-parser";
import { buildGraph, type ElementGraph } from "@unloaded/element-graph";
import {
  ENGINE_VERSION, effectiveLinks, exportMapping, mapCalcs, mappingStatuses, propagateImpact, readPdf, toCalcElements,
  type CalcElement, type CalcMapping, type PdfjsLike,
} from "@unloaded/calc-parser";
import type { Project } from "../src/project.ts";
import * as tools from "../src/tools.ts";
import { MODEL, PDF, inputs, loadProject } from "./helpers.ts";

let p: Project;
let graph: ElementGraph;
let els: CalcElement[];
let m: CalcMapping;

beforeAll(async () => {
  p = await loadProject(inputs());
  ({ graph } = buildGraph(await parseIfc(new Uint8Array(readFileSync(MODEL)), { fileName: "model_rev1.ifc" })));
  els = toCalcElements(graph.nodes(), new Map(graph.levels().map((l) => [l.id, l.name])));
  m = mapCalcs(els, (await readPdf(new Uint8Array(readFileSync(PDF)), pdfjs as unknown as PdfjsLike)).pages);
}, 120_000);

describe("single PDF: the engine's output, unchanged", () => {
  it("keeps calc-parser's plain calc keys, links and calc edges", () => {
    expect(p.calcs.map((c) => c.key)).toEqual(m.calcs.map((c) => c.key));
    expect(p.rawLinks).toEqual(m.links);
    expect(p.calcEdges.map(({ cross_pdf, ...e }) => (expect(cross_pdf).toBe(false), e))).toEqual(m.calcEdges);
  });

  it("project_summary counts match the engine", () => {
    const s = tools.projectSummary(p);
    const eff = effectiveLinks(m.links, [], new Set(els.map((e) => e.global_id)), new Set(m.calcs.map((c) => c.key)));
    expect(s.element_status).toEqual(mappingStatuses(els, eff).counts);
    expect(s.model.elements).toBe(graph.nodes().length);
    expect(s.model.supports_edges).toBe(graph.edges().filter((e) => e.kind === "supports").length);
    expect(s.source).toMatchObject({ model: { file: "model_rev1.ifc" }, engine: ENGINE_VERSION });
    expect(s.calc_pdfs[0]).toMatchObject({ file: "calc_package.pdf", key_prefix: "", main: true, no_text_pages: [9] });
  });

  it("get_element resolves a mark and returns links sorted by confidence with connectivity", () => {
    const beam = els.find((e) => e.cat === "Beam" && e.mark && graph.supportsOf(e.global_id).length)!;
    const r = tools.getElement(p, { id: beam.mark });
    expect(r.element.global_id).toBe(beam.global_id);
    const confs = r.links.map((l) => l.conf);
    expect(confs).toEqual([...confs].sort((a, b) => b - a));
    expect(r.links.map((l) => l.calc_key).sort()).toEqual(m.links.filter((l) => l.global_id === beam.global_id).map((l) => l.calc_key).sort());
    expect(r.connectivity.bears_on.map((x) => x.global_id)).toEqual(graph.supportsOf(beam.global_id));
    expect(r.connectivity.bears_on[0]!.edges[0]!.evidence.length).toBeGreaterThan(0);
  });

  it("impact_of_change is propagateImpact on the supports edges", () => {
    const col = els.find((e) => e.cat === "Column")!;
    const edges = graph.edges().filter((e) => e.kind === "supports").map((e) => ({ src: e.a, dst: e.b }));
    for (const mode of ["change", "remove"] as const) {
      const want = propagateImpact(col.global_id, mode, edges, p.links, m.calcEdges, new Map(els.map((e) => [e.global_id, e])));
      expect(tools.impactOfChange(p, { id: col.global_id, mode }).impact).toEqual(want);
    }
  });

  it("export_mapping is exportMapping", () => {
    const r = tools.exportMappingTool(p, {}) as { report: ReturnType<typeof exportMapping> };
    expect(r.report).toEqual(exportMapping(tools.exportInput(p)));
    expect(r.report.elements.length).toBe(els.length);
  });

  it("trace_load_path follows loadPathDown / loadPathUp with max_depth", () => {
    const slab = els.find((e) => e.cat === "Slab")!;
    const r = tools.traceLoadPath(p, { id: slab.global_id, direction: "down", max_depth: 2 });
    expect(r.down!.elements.map((x) => [x.global_id, x.depth]).sort()).toEqual(
      [...graph.loadPathDown(slab.global_id)].filter(([id, d]) => id !== slab.global_id && d <= 2).sort(),
    );
    expect(r.down!.truncated).toBe(true);
  });

  it("search_calc_text finds text with rects, scoped by calc", () => {
    const r = tools.searchCalcText(p, { query: "c5", limit: 500 });
    expect(r.total).toBeGreaterThan(0);
    for (const h of r.items) expect(h.snippet.match.toLowerCase()).toBe("c5");
    const scoped = tools.searchCalcText(p, { query: "c5", calc: "column-design-ram-structural-system" });
    expect(scoped.items.every((h) => h.calc_key === "column-design-ram-structural-system")).toBe(true);
  });

  it("get_page_image highlights a link's rects and crops around them", async () => {
    const l = p.links.find((x) => x.tier === "exact" && x.rects.length)!;
    const { image, meta } = await tools.getPageImage(p, { global_id: l.global_id, calc_key: l.calc_key });
    expect(Buffer.from(image.png).subarray(1, 4).toString()).toBe("PNG");
    expect(meta.highlight).toEqual(l.rects);
    expect(meta.page).toBe(l.page);
    expect((meta.area_pt as number[])[3]! - (meta.area_pt as number[])[1]!).toBeLessThan(image.page.height);
  });

  it("bad references are actionable errors", () => {
    expect(() => tools.getElement(p, { id: "nope" })).toThrow(/no element with GlobalId or mark "nope"/);
    expect(() => tools.getCalc(p, { key: "column-desig" })).toThrow(/Did you mean: column-design-ram-structural-system/);
    expect(() => tools.listCalcs(p, { pdf: "other.pdf" })).toThrow(/no calc PDF "other.pdf"/);
  });
});
