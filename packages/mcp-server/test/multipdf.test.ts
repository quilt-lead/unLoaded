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
import { extractPdf, mapCalcs, parseGraph, segmentCalcs, statusOf, type PdfjsLike } from "@unloaded/calc-mapper";
import type { Project } from "../src/project.ts";
import { stemSlug } from "../src/project.ts";
import * as tools from "../src/tools.ts";
import { MODEL, PDF, SUPPLEMENT, inputs, loadProject, plain, tempDir } from "./helpers.ts";

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
    // page references never resolve into another PDF
    for (const e of p.calcEdges.filter((x) => x.rules.some((r) => r.startsWith("page reference")))) {
      expect(p.pdfOfCalc.get(e.src)).toBe(p.pdfOfCalc.get(e.dst));
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
