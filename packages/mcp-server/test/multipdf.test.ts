/**
 * Several calc PDFs: calc-mapper maps one PDF per run, so the server runs it per PDF. The main PDF keeps
 * plain keys, the others get "<stem>/" prefixes, page numbers never cross PDFs, element status is the
 * engine's statusOf over every PDF's links, and cross-PDF edges come only from the cross-reference rule.
 * Fixture: the main package designs beam B-101 and the columns; "Supplement A.pdf" designs the shear
 * tabs and takes B-101's end reactions (a cross-reference into the main package).
 */
import { copyFileSync, mkdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { beforeAll, describe, expect, it } from "vitest";
import * as pdfjs from "pdfjs-dist/legacy/build/pdf.mjs";
import { ElementGraph } from "@unloaded/element-graph";
import { buildState, designerOf, extractPdf, mapCalcs, parseGraph, segmentCalcs, statusOf, type PdfjsLike } from "@unloaded/calc-mapper";
import type { Project } from "../src/project.ts";
import { stemSlug } from "../src/project.ts";
import * as tools from "../src/tools.ts";
import { CROSS_MAIN, CROSS_SUPPLEMENT, MODEL, PDF, SUPPLEMENT, inputs, loadProject, plain, tempDir } from "./helpers.ts";

let single: Project;
let p: Project;

beforeAll(async () => {
  single = await loadProject(inputs());
  p = await loadProject(inputs({ calcs: [PDF, SUPPLEMENT] }));
}, 120_000);

describe("two calc PDFs", () => {
  it("keeps the main PDF's keys plain and prefixes the supplement's with its file-stem slug", () => {
    expect(stemSlug("Supplement A.pdf")).toBe("supplement-a");
    expect(p.pdfs[0]!.calcs.map((c) => c.key)).toEqual(single.calcs.map((c) => c.key));
    expect(p.pdfs[1]!.calcs.map((c) => c.key)).toEqual(["supplement-a/connection-design-check"]);
    expect(new Set(p.calcs.map((c) => c.key)).size).toBe(p.calcs.length);
  });

  it("maps each PDF on its own (mapCalcs on the prefixed package), pages within that PDF", async () => {
    const graph = parseGraph(ElementGraph.deserialize(JSON.parse(readFileSync(MODEL, "utf8"))).serialize());
    const pkg = segmentCalcs((await extractPdf(new Uint8Array(readFileSync(SUPPLEMENT)), { pdfjs: pdfjs as unknown as PdfjsLike })).pages, "Supplement A.pdf");
    const run = await mapCalcs(graph, { ...pkg, calcs: pkg.calcs.map((c) => ({ ...c, key: `supplement-a/${c.key}` })) });
    expect(plain(p.pdfs[1]!.run.links)).toEqual(plain(run.links));
    expect(plain(p.pdfs[0]!.run.links)).toEqual(plain(single.rawLinks));
    for (const pdf of p.pdfs) for (const l of pdf.run.links) expect(l.page! <= pdf.pages.length).toBe(true);
  });

  it("element status is statusOf over every PDF's links (the shear tabs are designed only in the supplement)", () => {
    expect(single.status.get("K1")).toBe("unmapped");
    expect(p.status.get("K1")).toBe("confirmed");
    for (const e of p.elements) expect(p.status.get(e.global_id)).toBe(statusOf(p.linksByElement.get(e.global_id) ?? []));
  });

  it("keeps every same-PDF edge and adds only cross-reference edges across PDFs", () => {
    const within = p.calcEdges.filter((e) => !e.cross_pdf);
    expect(plain(within.filter((e) => !e.src.includes("/") && !e.dst.includes("/")))).toEqual(plain(single.calcEdges));
    const cross = p.calcEdges.filter((e) => e.cross_pdf);
    expect(cross.map((e) => [e.src, e.dst])).toEqual([["beam-design-check", "supplement-a/connection-design-check"]]);
    for (const e of cross) {
      expect(e.rules.every((r) => r.startsWith("cross-reference"))).toBe(true);
      for (const ev of e.evidence) {
        expect(ev.calc).toBe("supplement-a/connection-design-check");
        expect(ev.page).toBe(1); // page 1 of the supplement, not of the combined view
        expect(ev.global_id).toBe("B1");
      }
    }
  });

  it("impact crosses PDFs through the calc graph", () => {
    const r = tools.impactOfChange(p, { id: "B-101", mode: "change" });
    expect(Object.keys(r.impact.stale)).toContain("supplement-a/connection-design-check");
    expect(r.impact.provenance.inputs).toEqual(expect.arrayContaining(p.pdfs.map((d) => d.sha256)));
  });

  it("tools name the PDF of every calc and resolve pages per PDF", async () => {
    const r = tools.getCalc(p, { key: "supplement-a/connection-design-check" }) as { calc: { pdf: { file: string }; pages: number[] } };
    expect(r.calc.pdf.file).toBe("Supplement A.pdf");
    expect(r.calc.pages).toEqual([1]);
    const img = await tools.getPageImage(p, { pdf: "supplement-a", page: 1 });
    expect(img.meta).toMatchObject({ pdf: "Supplement A.pdf", page: 1, calc_key: "supplement-a/connection-design-check" });
    await expect(tools.getPageImage(p, { pdf: "supplement-a", page: 2 })).rejects.toThrow(/page 2 is not in Supplement A.pdf/);
    expect(tools.searchCalcText(p, { query: "B-101", pdf: "Supplement A.pdf" }).items.every((h) => h.pdf === "Supplement A.pdf")).toBe(true);
    const ex = tools.exportMappingTool(p, {});
    expect(ex.packages.map((x) => x.pdf.file)).toEqual(["test_calcs.pdf", "Supplement A.pdf"]);
  });

  it("refuses two PDFs with the same calc-key prefix", async () => {
    const dir = join(tempDir(), "other");
    mkdirSync(dir);
    const twin = join(dir, "Supplement A.pdf");
    copyFileSync(SUPPLEMENT, twin);
    await expect(loadProject(inputs({ calcs: [PDF, SUPPLEMENT, twin] }))).rejects.toThrow(/same calc-key prefix "supplement-a\/"/);
  });
});

/**
 * The cross-PDF pair (fixtures.ts CROSS_*): B-101 designed in both PDFs, a "see page 2" in the
 * supplement, and a "carried to shear tab ST-2" in the main PDF naming a connection the supplement
 * designs on ITS page 2. Every expectation below fails if one of the cross-PDF rules breaks.
 */
describe("cross-PDF rules", () => {
  let x: Project;
  const MAIN_BEAM = "beam-design-check";
  const SUP_BEAM = "supplement-b/beam-design-check";
  const SUP_CONN = "supplement-b/connection-design-check";
  const COLUMN = "column-design-check";
  const edge = (src: string, dst: string) => x.calcEdges.find((e) => e.src === src && e.dst === dst);
  beforeAll(async () => {
    x = await loadProject(inputs({ calcs: [CROSS_MAIN, CROSS_SUPPLEMENT] }));
  }, 120_000);

  it("the fixture designs B-101 in both PDFs with the same tier and confidence", () => {
    const design = x.links.filter((l) => l.global_id === "B1" && l.role === "design" && l.status !== "rejected");
    expect(design.map((l) => [l.calc_key, l.tier, l.conf]).sort()).toEqual([[MAIN_BEAM, "exact", 1], [SUP_BEAM, "exact", 1]]);
  });

  it("gives every element ONE designer across all PDFs (designerOf over every PDF's links)", () => {
    const designer = designerOf(x.links);
    expect(designer.get("B1")!.calc_key).toBe(MAIN_BEAM); // tie on role and tier: the smaller calc key
    const seen = new Map<string, Set<string>>();
    let crossRefs = 0;
    for (const e of x.calcEdges) {
      for (const ev of e.evidence) {
        if (!ev.global_id) continue; // page-reference evidence names no element
        crossRefs += 1;
        const other = ev.calc === e.src ? e.dst : e.src;
        expect(other, `${e.src} -> ${e.dst} via ${ev.global_id}`).toBe(designer.get(ev.global_id)!.calc_key);
        (seen.get(ev.global_id) ?? seen.set(ev.global_id, new Set()).get(ev.global_id)!).add(other);
      }
    }
    expect(crossRefs).toBeGreaterThan(0);
    for (const [gid, ds] of seen) expect([...ds], gid).toHaveLength(1);
    // the supplement's own B-101 calc is not a second designer of its neighbour's mention
    expect(edge(SUP_BEAM, SUP_CONN)).toBeUndefined();
    expect(edge(MAIN_BEAM, SUP_CONN)).toMatchObject({ cross_pdf: true, rules: [expect.stringMatching(/^cross-reference/)] });
  });

  it("resolves a page reference inside its own PDF only (the combined view's page-reference rule is off)", () => {
    // positive control: the supplement's "see page 2" is its own page 2 (the connection calc)
    expect(edge(SUP_CONN, SUP_BEAM)).toMatchObject({ cross_pdf: false, rules: ["page reference (input from)"] });
    expect(edge(SUP_CONN, SUP_BEAM)!.evidence.map((ev) => [ev.calc, ev.page])).toEqual([[SUP_BEAM, 1]]);
    // in the combined view "page 2" would be the MAIN PDF's page 2, the column calc
    expect(x.calcEdges.filter((e) => [e.src, e.dst].includes(COLUMN) && [e.src, e.dst].includes(SUP_BEAM))).toEqual([]);
    const pageRefs = x.calcEdges.filter((e) => e.rules.some((r) => r.startsWith("page reference")));
    expect(pageRefs.length).toBeGreaterThanOrEqual(2); // one in each PDF
    for (const e of pageRefs) expect(x.pdfOfCalc.get(e.src)).toBe(x.pdfOfCalc.get(e.dst));
  });

  it("reads a cross-PDF mention's cue word on its own PDF's page (page numbers offset in the combined view)", () => {
    // "Column C-2 reactions carried to shear tab ST-2": "to" before the mention = the column calc feeds the connection calc
    const e = edge(COLUMN, SUP_CONN);
    expect(e).toMatchObject({ cross_pdf: true });
    expect(e!.evidence.map((ev) => [ev.calc, ev.page, ev.global_id])).toEqual([[COLUMN, 2, "K2"]]);
    expect(edge(SUP_CONN, COLUMN)).toBeUndefined();
    for (const c of x.calcEdges.filter((y) => y.cross_pdf)) {
      for (const ev of c.evidence) expect(ev.page).toBeLessThanOrEqual(x.pdfOfCalc.get(ev.calc)!.pages.length);
    }
  });

  it("with one PDF the calc edges are exactly buildState's", async () => {
    const one = await loadProject(inputs({ calcs: [CROSS_MAIN] }));
    const st = buildState(one.graph.graph, one.pdfs[0]!.pkg, one.pdfs[0]!.run, []);
    expect(plain(one.calcEdges.map(({ cross_pdf: _c, ...e }) => e))).toEqual(plain(st.calc_edges));
  }, 120_000);

  it("every tool's source block names the PDF of every calc its result mentions, and of every sha256 its provenance cites", async () => {
    const reads: [string, () => unknown][] = [
      ["project_summary", () => tools.projectSummary(x)],
      ["search_elements", () => tools.searchElements(x, { limit: 500 })],
      ["get_element B1", () => tools.getElement(x, { id: "B1" })],
      ["get_element K2", () => tools.getElement(x, { id: "K2" })],
      ["list_calcs", () => tools.listCalcs(x, {})],
      ["get_calc", () => tools.getCalc(x, { key: SUP_CONN, include_text: true })],
      ["search_calc_text", () => tools.searchCalcText(x, { query: "B-101", limit: 500 })],
      ["trace_load_path", () => tools.traceLoadPath(x, { id: "B1", direction: "both" })],
      ["calc_dependencies", () => tools.calcDependencies(x, {})],
      ["calc_dependencies key", () => tools.calcDependencies(x, { key: COLUMN, depth: 3 })],
      ["impact_of_change", () => tools.impactOfChange(x, { id: "C-1", mode: "remove" })],
      ["impact_of_change B1", () => tools.impactOfChange(x, { id: "B1", mode: "change" })],
      ["review_status", () => tools.reviewStatus(x, { limit: 500 })],
      ["list_findings", () => tools.listFindings(x, {})],
      ["list_typical_groups", () => tools.listTypicalGroups(x, {})],
      ["move_column", () => tools.moveColumn(x, { column: "C-2", remove: true })],
      ["export_mapping", () => tools.exportMappingTool(x, {})],
    ];
    const CALC_FIELDS = new Set(["calc_key", "calc", "src", "dst", "key", "calcKey", "center"]);
    const shaToPdf = new Map(x.pdfs.map((d) => [d.sha256, d.name]));
    for (const [name, fn] of reads) {
      const r = plain(fn()) as { source: { calc_pdfs: { file: string }[] } };
      const listed = new Set(r.source.calc_pdfs.map((d) => d.file));
      const need = new Set<string>();
      const walk = (v: unknown, k: string | null): void => {
        if (Array.isArray(v)) v.forEach((y) => walk(y, k));
        else if (v && typeof v === "object") {
          for (const [kk, vv] of Object.entries(v)) if (kk !== "source") walk(vv, kk);
        }
        else if (typeof v === "string") {
          if (k !== null && CALC_FIELDS.has(k) && x.pdfOfCalc.has(v)) need.add(x.pdfOfCalc.get(v)!.name);
          if (shaToPdf.has(v)) need.add(shaToPdf.get(v)!);
        }
      };
      walk(r, null);
      expect([...need].filter((f) => !listed.has(f)), name).toEqual([]);
    }
    // trace_load_path names the PDFs of the best calcs it returns (it used to name none)
    expect((tools.traceLoadPath(x, { id: "B1", direction: "both" }).source as { calc_pdfs: unknown[] }).calc_pdfs.length).toBeGreaterThan(0);
  });
});
