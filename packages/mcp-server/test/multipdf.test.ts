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
import { MODEL, PDF, SUPPLEMENT, inputs, loadProject, plain, tempDir } from "./helpers.ts";

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
