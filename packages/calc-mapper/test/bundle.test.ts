/**
 * The model bundle (bundle.ts): one file with an element graph and its calc graph. Validation names the
 * field at fault; a demo calc graph and a PDF one both become the export the view reads; a mapped
 * project's export becomes a bundle and back without losing links, review state or evidence.
 */
import { describe, expect, it } from "vitest";
import {
  BUNDLE_FORMAT, BundleFormatError, buildExport, bundleExport, exportToCalcGraph, isBundle, makeBundle, mapCalcs, parseBundle, segmentCalcs,
  type BundleCalcGraph, type DecisionFields,
} from "../src/index.ts";
import { DOC_SHA, graph, page } from "./helpers.ts";

const demo = (): BundleCalcGraph => ({
  source: { kind: "demo" },
  calcs: [
    { key: "doc-b1", title: "S-201 Beam 2B1 Design", cat: "Beam", code: "AISC 360-22", rev: "Rev A", summary: "Flexure and shear" },
    { key: "doc-c1", title: "S-301 Column C1 Design", cat: "Column" },
  ],
  edges: [{ src: "doc-b1", dst: "doc-c1", rules: ["reaction"] }],
  links: [
    { element: "B1", calc: "doc-b1", role: "design", review: "auto", note: "Beam 2B1 flexure" },
    { element: "C1", calc: "doc-c1", role: "design", review: "confirmed", decided_by: "noah" },
    { element: "K1", calc: "doc-b1", role: "loads", review: "manual" },
  ],
});

const json = (cg: BundleCalcGraph | null = demo()) => JSON.parse(JSON.stringify(makeBundle(graph(), cg, { project: "T", demo: true })));

describe("parseBundle", () => {
  it("accepts a bundle, as text or as parsed JSON, and keeps the element graph as serialized", () => {
    const b = json();
    expect(isBundle(b)).toBe(true);
    const p = parseBundle(JSON.stringify(b));
    expect(p.format).toBe(BUNDLE_FORMAT);
    expect(p.elementGraph).toEqual(graph());
    expect(p.calcGraph?.calcs).toHaveLength(2);
    expect(parseBundle(json(null)).calcGraph).toBeNull();
  });

  it.each([
    ["wrong version", (b: any) => { b.version = 2; }, /version 2 is not supported/],
    ["bad element graph", (b: any) => { b.elementGraph.nodes[0].id = ""; }, /^elementGraph: graph.nodes\[0\]/],
    ["duplicate calc key", (b: any) => { b.calcGraph.calcs[1].key = "doc-b1"; }, /duplicate calc key "doc-b1"/],
    ["unknown category", (b: any) => { b.calcGraph.calcs[0].cat = "Girder"; }, /calcs\[0\]\.cat/],
    ["edge to an unknown calc", (b: any) => { b.calcGraph.edges[0].dst = "nope"; }, /edges\[0\]/],
    ["link to an unknown element", (b: any) => { b.calcGraph.links[0].element = "B9"; }, /links\[0\]\.element "B9" is not a node/],
    ["link to an unknown calc", (b: any) => { b.calcGraph.links[0].calc = "nope"; }, /links\[0\]\.calc "nope"/],
    ["the same pair twice", (b: any) => { b.calcGraph.links.push({ ...b.calcGraph.links[0] }); }, /linked to calc "doc-b1" twice/],
    ["bad review", (b: any) => { b.calcGraph.links[0].review = "rejected"; }, /review must be/],
    ["conf out of range", (b: any) => { b.calcGraph.links[0].conf = 1.5; }, /conf must be a number from 0 to 1/],
    ["pdf source without a sha", (b: any) => { b.calcGraph.source = { kind: "pdf", documents: [{ sha256: "x", pages: 1, page_offset: 0 }] }; }, /sha256/],
  ])("refuses %s", (_name, mutate, msg) => {
    const b = json();
    mutate(b);
    expect(() => parseBundle(b)).toThrow(BundleFormatError);
    expect(() => parseBundle(b)).toThrow(msg);
  });
});

describe("bundleExport (demo calc graph)", () => {
  it("gives the export the view reads: calcs, edges, links per element, review state, demo provenance", async () => {
    const b = parseBundle(json());
    const exp = await bundleExport(b.elementGraph, b.calcGraph!);
    expect(exp.calc_source).toEqual({ kind: "demo" });
    expect(exp.calcs.map((c) => [c.key, c.element_type, c.pages])).toEqual([["doc-b1", "Beam", []], ["doc-c1", "Column", []]]);
    expect(exp.calcs[0]!.meta).toEqual({ code: "AISC 360-22", rev: "Rev A", summary: "Flexure and shear" });
    expect(exp.calcs[1]!.meta).toBeUndefined();
    expect(exp.calc_edges).toHaveLength(1);
    const byEl = new Map(exp.elements.map((e) => [e.global_id, e]));
    const b1 = byEl.get("B1")!.calcs[0]!;
    expect(b1.review).toBe("auto");
    expect(b1.reasons.some((r) => r.note === "Beam 2B1 flexure")).toBe(true);
    expect(b1.caveats.join(" ")).toMatch(/Demo data/);
    expect(b1.provenance).toMatchObject({ rule: "bundle.demo", method: "estimate" });
    expect(b1.provenance.inputs).toHaveLength(1); // the element graph's sha256
    expect(byEl.get("C1")!.calcs[0]!.review).toBe("confirmed");
    expect(byEl.get("K1")!.calcs[0]).toMatchObject({ review: "manual", role: "design" });
    expect(byEl.get("B1")!.status).toBe("confirmed"); // conf 1 design link
    expect(byEl.get("F1")!.status).toBe("unmapped");
    expect(exp.connectivity.length).toBeGreaterThan(0);
    expect(exp.load_path.length).toBe(2);
  });

  it("applies the project's decisions after the bundle's own review state", async () => {
    const b = parseBundle(json());
    const log: DecisionFields[] = [
      { id: 1, global_id: "C1", calc_key: "doc-c1", action: "reject", actor: "rev", note: null, at: "2026-11-15T00:00:00Z" },
      { id: 2, global_id: "B1", calc_key: "doc-b1", action: "confirm", actor: "rev", note: null, at: "2026-11-15T00:00:01Z" },
    ];
    const exp = await bundleExport(b.elementGraph, b.calcGraph!, log);
    const byEl = new Map(exp.elements.map((e) => [e.global_id, e]));
    expect(byEl.get("C1")!.calcs[0]!.review).toBe("rejected");
    expect(byEl.get("C1")!.status).toBe("unmapped");
    expect(byEl.get("B1")!.calcs[0]!.review).toBe("confirmed");
  });
});

describe("export -> bundle -> export (a demo)", () => {
  it("stays a demo: same calcs, links, notes and review state, no doubled caveats", async () => {
    const b = parseBundle(json());
    const exp = await bundleExport(b.elementGraph, b.calcGraph!);
    const cg = exportToCalcGraph(exp);
    expect(cg.source).toEqual({ kind: "demo" });
    expect(cg.calcs[0]).toMatchObject({ key: "doc-b1", code: "AISC 360-22", summary: "Flexure and shear" });
    const exp2 = await bundleExport(b.elementGraph, parseBundle(JSON.parse(JSON.stringify(makeBundle(b.elementGraph, cg)))).calcGraph!);
    const pick = (x: typeof exp) => x.elements.flatMap((e) => e.calcs.map((l) => [e.global_id, l.calc, l.review, l.caveats, l.reasons.map((r) => r.note)]));
    expect(pick(exp2)).toEqual(pick(exp));
  });
});

describe("export -> bundle -> export (a mapped project)", () => {
  it("keeps calcs, edges, links, evidence and review state; names the PDF by sha256; drops rejected links", async () => {
    const g = graph();
    const pkg = segmentCalcs([page(1, "BEAM DESIGN\nbeam 2B1 W18X35 OK"), page(2, "COLUMN DESIGN\ncolumn C1 design, see page 1")], "calcs.pdf");
    const run = await mapCalcs(g, pkg);
    const beamKey = pkg.calcs.find((c) => /beam/i.test(c.title))!.key;
    const decisions: DecisionFields[] = [{ id: 1, global_id: "B1", calc_key: beamKey, action: "confirm", actor: "rev", note: null, at: "2026-11-15T00:00:00Z" }];
    const exp = buildExport(g, pkg, run, decisions);
    const cg = exportToCalcGraph(exp);
    expect(cg.source).toEqual({ kind: "pdf", documents: [{ doc_id: null, name: "calcs.pdf", revision: null, sha256: DOC_SHA, pages: 2, page_offset: 0 }] });

    const back = parseBundle(JSON.parse(JSON.stringify(makeBundle(g, cg))));
    const exp2 = await bundleExport(back.elementGraph, back.calcGraph!);
    expect(exp2.calcs.map((c) => [c.key, c.pages, c.spans])).toEqual(exp.calcs.map((c) => [c.key, c.pages, c.spans]));
    expect(exp2.calc_edges.map((e) => [e.src, e.dst])).toEqual(exp.calc_edges.map((e) => [e.src, e.dst]));
    const pick = (x: typeof exp) => x.elements.flatMap((e) => e.calcs.filter((l) => l.review !== "rejected").map((l) => [e.global_id, l.calc, l.review, l.page, l.evidence.rects.length]));
    expect(pick(exp2)).toEqual(pick(exp));
    const link = exp2.elements.find((e) => e.global_id === "B1")!.calcs.find((l) => l.calc === beamKey)!;
    expect(link.review).toBe("confirmed");
    expect(link.provenance.inputs).toContain(DOC_SHA); // the run's own provenance is kept
  });
});
