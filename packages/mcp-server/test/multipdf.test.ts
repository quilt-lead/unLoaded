/**
 * Several calc PDFs: the server maps them as ONE calc set (calc-mapper buildCalcSet), as the app does.
 * Each PDF is a document (d1, d2, ... in --calcs order), calc keys are calc refs "<docId>#<key>", the
 * engine runs once on the set, and every page number the tools give is a page of the record's own PDF
 * (the engine's set page minus that PDF's page_offset). Fixture: the main package designs beam B-101
 * and the columns; "Supplement A.pdf" designs the shear tabs and takes B-101's end reactions (a
 * cross-reference into the main package).
 */
import { copyFileSync, mkdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { beforeAll, describe, expect, it } from "vitest";
import * as pdfjs from "pdfjs-dist/legacy/build/pdf.mjs";
import { ElementGraph } from "@unloaded/element-graph";
import {
  buildCalcSet, buildState, extractPdf, mapCalcs, parseGraph, segmentCalcs, statusOf, type CalcSet, type PdfjsLike, type ProjectState,
} from "@unloaded/calc-mapper";
import type { Project } from "../src/project.ts";
import * as tools from "../src/tools.ts";
import { CROSS_MAIN, CROSS_SUPPLEMENT, MODEL, PDF, SUPPLEMENT, inputs, loadProject, plain, tempDir } from "./helpers.ts";

let single: Project;
let p: Project;
let set: CalcSet;
let state: ProjectState;

const read = async (path: string, name: string) =>
  segmentCalcs((await extractPdf(new Uint8Array(readFileSync(path)), { pdfjs: pdfjs as unknown as PdfjsLike })).pages, name);

beforeAll(async () => {
  single = await loadProject(inputs());
  p = await loadProject(inputs({ calcs: [PDF, SUPPLEMENT] }));
  const graph = parseGraph(ElementGraph.deserialize(JSON.parse(readFileSync(MODEL, "utf8"))).serialize());
  set = buildCalcSet([
    { doc_id: "d1", name: "test_calcs", package: await read(PDF, "test_calcs.pdf") },
    { doc_id: "d2", name: "Supplement A", package: await read(SUPPLEMENT, "Supplement A.pdf") },
  ]);
  state = buildState(graph, set, await mapCalcs(graph, set), []);
}, 120_000);

const docPage = (key: string, n: number | null) => (n === null ? null : n - set.docs.find((d) => key.startsWith(`${d.doc_id}#`))!.page_offset);

describe("two calc PDFs", () => {
  it("makes each PDF a document of the set, with calc refs as keys", () => {
    expect(p.pdfs.map((d) => [d.docId, d.prefix, d.offset])).toEqual([["d1", "d1#", 0], ["d2", "d2#", set.docs[1]!.page_offset]]);
    expect(p.pdfs[0]!.calcs.map((c) => c.key)).toEqual(single.calcs.map((c) => c.key));
    expect(p.pdfs[1]!.calcs.map((c) => c.key)).toEqual(["d2#connection-design-check"]);
    expect(p.calcs.map((c) => c.key)).toEqual(set.combined.calcs.map((c) => c.key));
  });

  it("is the engine's run on the set, with every page number in its own PDF", () => {
    const local = (l: (typeof state.links)[number]) =>
      ({ ...l, page: docPage(l.calc_key, l.page), evidence: l.evidence.map((e) => ({ ...e, page: docPage(l.calc_key, e.page) })) });
    expect(plain(p.links)).toEqual(plain(state.links.map(local)));
    expect(p.counts).toEqual(state.counts);
    for (const l of p.links) if (l.page !== null) expect(l.page <= p.pdfOfCalc.get(l.calc_key)!.pages.length).toBe(true);
  });

  it("element status is the engine's over the whole set (the shear tabs are designed only in the supplement)", () => {
    expect(single.status.get("K1")).toBe("unmapped");
    expect(p.status.get("K1")).toBe("confirmed");
    for (const e of p.elements) expect(p.status.get(e.global_id)).toBe(statusOf(p.linksByElement.get(e.global_id) ?? []));
  });

  it("finds the cross-reference edge between the PDFs; page references stay inside a PDF", () => {
    const within = p.calcEdges.filter((e) => !e.cross_pdf);
    expect(plain(within)).toEqual(plain(single.calcEdges));
    const cross = p.calcEdges.filter((e) => e.cross_pdf);
    expect(cross.map((e) => [e.src, e.dst])).toEqual([["d1#beam-design-check", "d2#connection-design-check"]]);
    for (const e of cross) {
      expect(e.rules.every((r) => r.startsWith("cross-reference"))).toBe(true);
      for (const ev of e.evidence) {
        expect(ev.calc).toBe("d2#connection-design-check");
        expect(ev.page).toBe(1); // page 1 of the supplement, not the set page
        expect(ev.global_id).toBe("B1");
      }
    }
    for (const e of p.calcEdges.filter((x) => x.rules.some((r) => r.startsWith("page reference")))) {
      expect(p.pdfOfCalc.get(e.src)).toBe(p.pdfOfCalc.get(e.dst));
    }
  });

  it("impact crosses PDFs through the calc graph", () => {
    const r = tools.impactOfChange(p, { id: "B-101", mode: "change" });
    expect(Object.keys(r.impact.stale)).toContain("d2#connection-design-check");
    expect(r.impact.provenance.inputs).toEqual(expect.arrayContaining(p.pdfs.map((d) => d.sha256)));
  });

  it("tools name the PDF of every calc, take bare keys when unique, and resolve pages per PDF", async () => {
    const r = tools.getCalc(p, { key: "connection-design-check" }) as { calc: { key: string; pdf: { file: string }; pages: number[] } };
    expect(r.calc).toMatchObject({ key: "d2#connection-design-check", pdf: { file: "Supplement A.pdf" }, pages: [1] });
    const img = await tools.getPageImage(p, { pdf: "d2", page: 1 });
    expect(img.meta).toMatchObject({ pdf: "Supplement A.pdf", page: 1, calc_key: "d2#connection-design-check" });
    await expect(tools.getPageImage(p, { pdf: "d2", page: 2 })).rejects.toThrow(/page 2 is not in Supplement A.pdf/);
    expect(tools.searchCalcText(p, { query: "B-101", pdf: "Supplement A.pdf" }).items.every((h) => h.pdf === "Supplement A.pdf")).toBe(true);
    const ex = tools.exportMappingTool(p, {});
    expect(ex.calc_documents.map((d) => [d.doc_id, d.file, d.page_offset])).toEqual([["d1", "test_calcs.pdf", 0], ["d2", "Supplement A.pdf", set.docs[1]!.page_offset]]);
    expect(ex.report.calc_package).toBe("2 calc documents");
  });

  it("leaves out a second copy of the same PDF (a calc set holds a PDF once)", async () => {
    const dir = join(tempDir(), "other");
    mkdirSync(dir);
    const twin = join(dir, "Copy of Supplement.pdf");
    copyFileSync(SUPPLEMENT, twin);
    const t = await loadProject(inputs({ calcs: [PDF, SUPPLEMENT, twin] }));
    expect(t.pdfs.map((d) => d.name)).toEqual(["test_calcs.pdf", "Supplement A.pdf"]);
    expect(t.warnings.some((w) => /Copy of Supplement.pdf has the same content as Supplement A.pdf/.test(w))).toBe(true);
  });
});

/**
 * The cross-PDF pair (fixtures.ts CROSS_*) on the calc set: B-101 designed in both PDFs, a "see page 2"
 * in the supplement, and a "carried to shear tab ST-2" in the main PDF naming a connection the
 * supplement designs on ITS page 2. The engine resolves all three on the set; these pin that the
 * server's page translation (set page - page_offset) keeps every evidence page in its own PDF.
 */
describe("cross-PDF cases on the calc set", () => {
  let x: Project;
  const MAIN_BEAM = "d1#beam-design-check";
  const SUP_BEAM = "d2#beam-design-check";
  const SUP_CONN = "d2#connection-design-check";
  const COLUMN = "d1#column-design-check";
  const edge = (src: string, dst: string) => x.calcEdges.find((e) => e.src === src && e.dst === dst);
  beforeAll(async () => {
    x = await loadProject(inputs({ calcs: [CROSS_MAIN, CROSS_SUPPLEMENT] }));
  }, 120_000);

  it("one designer per element across the set; page references and cue words stay in their own PDF", () => {
    const design = x.links.filter((l) => l.global_id === "B1" && l.role === "design" && l.status !== "rejected");
    expect(design.map((l) => l.calc_key).sort()).toEqual([MAIN_BEAM, SUP_BEAM]);
    // the supplement's mention of B-101 is fed by ONE designer (the main beam calc), not by both
    expect(edge(SUP_BEAM, SUP_CONN)).toBeUndefined();
    expect(edge(MAIN_BEAM, SUP_CONN)).toMatchObject({ cross_pdf: true });
    // "see page 2" in the supplement is the supplement's own page 2
    expect(edge(SUP_CONN, SUP_BEAM)).toMatchObject({ cross_pdf: false, rules: ["page reference (input from)"] });
    expect(edge(SUP_CONN, SUP_BEAM)!.evidence.map((ev) => [ev.calc, ev.page])).toEqual([[SUP_BEAM, 1]]);
    // "carried to shear tab ST-2" is read on the main PDF's page 2: the column calc feeds the connection calc
    expect(edge(COLUMN, SUP_CONN)!.evidence.map((ev) => [ev.calc, ev.page, ev.global_id])).toEqual([[COLUMN, 2, "K2"]]);
    expect(edge(SUP_CONN, COLUMN)).toBeUndefined();
    for (const e of x.calcEdges) for (const ev of e.evidence) expect(ev.page).toBeLessThanOrEqual(x.pdfOfCalc.get(ev.calc)!.pages.length);
  });

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
