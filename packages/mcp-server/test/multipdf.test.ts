/**
 * Several calc PDFs: mapCalcs runs per PDF, the main PDF keeps plain keys, the others get
 * "<stem>/" prefixes, page numbers never cross PDFs, and cross-PDF edges come only from the
 * cross-reference rule. No PDF tool is in the tree to build a second package, so the fixture is
 * passed twice under two names.
 */
import { beforeAll, describe, expect, it } from "vitest";
import type { Project } from "../src/project.ts";
import { stemSlug } from "../src/project.ts";
import * as tools from "../src/tools.ts";
import { inputs, loadProject, twoPdfs } from "./helpers.ts";

let single: Project;
let p: Project;

beforeAll(async () => {
  const t = twoPdfs();
  single = await loadProject(inputs());
  p = await loadProject(inputs({ calcs: [t.main, t.supplement] }));
}, 120_000);

describe("two calc PDFs", () => {
  it("keeps the main PDF's keys plain and prefixes the supplement's with its file-stem slug", () => {
    expect(stemSlug("Supplement A.pdf")).toBe("supplement-a");
    const keys = single.calcs.map((c) => c.key);
    expect(p.pdfs[0]!.calcs.map((c) => c.key)).toEqual(keys);
    expect(p.pdfs[1]!.calcs.map((c) => c.key)).toEqual(keys.map((k) => `supplement-a/${k}`));
    expect(new Set(p.calcs.map((c) => c.key)).size).toBe(p.calcs.length);
  });

  it("maps each PDF on its own: same links per PDF, pages within that PDF", () => {
    const strip = (k: string) => k.replace(/^supplement-a\//, "");
    expect(p.pdfs[1]!.links.map((l) => ({ ...l, calc_key: strip(l.calc_key) }))).toEqual(single.rawLinks);
    for (const pdf of p.pdfs) for (const l of pdf.links) expect(l.page! <= pdf.pages.length).toBe(true);
    expect(p.counts).toEqual(single.counts);
  });

  it("keeps every same-PDF edge and adds only cross-reference edges across PDFs", () => {
    const within = p.calcEdges.filter((e) => !e.cross_pdf);
    expect(within.length).toBe(single.calcEdges.length * 2);
    const cross = p.calcEdges.filter((e) => e.cross_pdf);
    expect(cross.length).toBeGreaterThan(0);
    for (const e of cross) {
      expect(p.pdfOfCalc.get(e.src)).not.toBe(p.pdfOfCalc.get(e.dst));
      expect(e.rules.every((r) => r.startsWith("cross-reference"))).toBe(true);
      for (const ev of e.evidence) expect(ev.page! >= 1 && ev.page! <= p.pdfOfCalc.get(ev.calc)!.pages.length).toBe(true);
    }
    // page references never resolve into another PDF
    for (const e of p.calcEdges.filter((x) => x.rules.some((r) => r.startsWith("page reference")))) {
      expect(p.pdfOfCalc.get(e.src)).toBe(p.pdfOfCalc.get(e.dst));
    }
  });

  it("tools name the PDF of every calc and resolve pages per PDF", async () => {
    const r = tools.getCalc(p, { key: "supplement-a/column-design-ram-structural-system" }) as { calc: { pdf: { file: string }; pages: number[] } };
    expect(r.calc.pdf.file).toBe("Supplement A.pdf");
    expect(r.calc.pages).toEqual([13, 14]);
    const img = await tools.getPageImage(p, { pdf: "supplement-a", page: 13 });
    expect(img.meta).toMatchObject({ pdf: "Supplement A.pdf", page: 13, calc_key: "supplement-a/column-design-ram-structural-system" });
    expect(tools.searchCalcText(p, { query: "C5", pdf: "Supplement A.pdf" }).items.every((h) => h.pdf === "Supplement A.pdf")).toBe(true);
  });

  it("refuses two PDFs with the same calc-key prefix", async () => {
    const a = twoPdfs();
    const b = twoPdfs();
    await expect(loadProject(inputs({ calcs: [a.main, a.supplement, b.supplement] }))).rejects.toThrow(/same calc-key prefix "supplement-a\/"/);
  });
});
