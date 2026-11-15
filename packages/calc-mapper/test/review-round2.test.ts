/**
 * Review round 2. Most round-2 findings were defects the round-1 fixes introduced and that the
 * synthetic package never exercises, so each test here is a realistic input the OLD rule handled
 * and the round-1 rule broke (or a false positive the round-1 rule added). Expected values were
 * checked by running the production modules on these exact inputs.
 */
import { describe, expect, it } from "vitest";
import {
  ENGINE_VERSION, GraphFormatError, MAPPER_VERSION, SEGMENTER_VERSION, calcPackageProblem, findSections, foldText, graphElements,
  inferCalcEdges, mapElements, parseGraph, runMapping, runningLines, segment, segmentCalcs, sha1Json,
} from "../src/index.ts";
import { GRAPH_SHA, el, graph, page } from "./helpers.ts";

describe("an untitled text page continues the most recent calc with text", () => {
  it("a cover with no title keyword does not swallow the calc after it", () => {
    // rejects round 1: the cover became front matter and took page 2 with it, so 2B1 was never mapped
    const pages = [page(1, "Sample Office Building\nJob 2611 issued for permit 2026"), page(2, "Steel Beam B-series\nbeam 2B1 W18X35 ok, stress ratio 0.81")];
    const calcs = segment(pages);
    expect(calcs.map((c) => [c.key, c.front, c.pages])).toEqual([["untitled-from-page-1", false, [1, 2]]]);
    const links = runMapping([el("b1", "Beam", "2B1", "W18X35")], calcs, pages, GRAPH_SHA);
    expect(links.map((l) => [l.global_id, l.calc_key, l.tier])).toEqual([["b1", "untitled-from-page-1", "exact"]]);
  });

  it("a calc's untitled page after a scanned sketch stays in that calc (a new span)", () => {
    // rejects round 1: page 3 joined scanned-1, so 2B2 was never mapped
    const pages = [page(1, "BEAM DESIGN\nbeam 2B1 W18X35 ok, stress ratio 0.81"), page(2, ""), page(3, "beam 2B2 W18X35 ok, stress ratio 0.77 fine")];
    const calcs = segment(pages);
    expect(calcs.map((c) => [c.key, c.scanned, c.pages, c.spans.length])).toEqual([["beam-design", false, [1, 3], 2], ["scanned-1", true, [2], 1]]);
    const links = runMapping([el("b2", "Beam", "2B2", "W18X35")], calcs, pages, GRAPH_SHA);
    expect(links.map((l) => [l.calc_key, l.tier])).toEqual([["beam-design", "exact"]]);
  });

  it("after a titled return to an earlier calc, an untitled page continues that calc", () => {
    const pages = [
      page(1, "BEAM DESIGN\nbeam 2B1 W18X35 ok, ratio 0.81 fine"), page(2, "COLUMN DESIGN\ncolumn C1 W12X53 ok ratio 0.5"),
      page(3, "BEAM DESIGN (cont.)\nbeam 2B2 W18X35 ok fine"), page(4, "beam 2B3 W18X35 ok, ratio 0.7 fine here"),
    ];
    expect(segment(pages).map((c) => [c.key, c.pages])).toEqual([["beam-design", [1, 3, 4]], ["column-design", [2]]]);
  });
});

describe("calc text reads only complete designations as section sizes", () => {
  const B = [el("b1", "Beam", "2B1", "W18X35")];
  const linkOf = (line: string, els = B) => {
    const pages = [page(1, `BEAM DESIGN\n${line}`)];
    const r = mapElements(els, segment(pages), pages, GRAPH_SHA);
    return { conf: r.links.find((l) => l.global_id === "b1")?.conf, findings: r.findings.map((f) => f.calc_size) };
  };

  it.each([
    "beam 2B1 MU = 45 X 12 = 540 in-k", "beam 2B1 tributary 10 x 20 ft", "beam 2B1 end post HD12 holdown", "beam 2B1 HL93 live load HP1 CHS1",
    "beam 2B1 at GRID 12 X 14", "beam 2B1 over footing 48 X 48 X 18 IN", "beam 2B1 with HD 2 BOLTS", "beam 2B1 S 2 X 4 blocking",
    "beam 2B1 W 1.2 X 0.5 kPa",
  ])("arithmetic, grids and tags are not sizes: %s", (line) => {
    // rejects round 1: 2B1 dropped 0.97 -> 0.77 with a false size-mismatch finding ("45X12", "HD12", "S2X4" ...)
    expect(linkOf(line)).toEqual({ conf: 0.97, findings: [] });
  });

  it("a comma never joins a designation", () => {
    expect(findSections(foldText("IPE300 BEAM, HEA200,240")).map((h) => h.profile)).toEqual(["IPE300"]);
  });

  it.each([
    ["IPE 300", "IPE300"], ["HEA 200", "HEA200"], ["457X191X67 UB", "457X191X67UB"], ["533X210X92UB", "533X210X92UB"],
    ["310UB40.4", "310UB40.4"], ["C10X15.3", "C10X15.3"], ["L4X4X1/2", "L4X4X1/2"], ["HSS6X6X.375", "HSS6X6X.375"], ["W12X53", "W12X53"],
  ])("still finds %s (with no model profile to lean on)", (txt, norm) => {
    expect(findSections(foldText(`beam 2B1 ${txt} ok`)).map((h) => h.profile)).toEqual([norm]);
    expect(linkOf(`beam 2B1 ${txt} ok`, [el("b1", "Beam", "2B1", "W99X999")]).findings).toEqual([norm]);
  });

  it("a plain-word model profile is neither a size in the calc nor the model's size", () => {
    // rejects round 1 (every BEAM read as a size) and the older engine (a size-mismatch against "BEAM")
    const els = [el("b1", "Beam", "2B1", "Beam")];
    expect(linkOf("beam 2B1 W18X35 ok", els)).toEqual({ conf: 0.97, findings: [] });
    expect(findSections(foldText("typical beam checks"), { known: new Set(["BEAM"]) })).toEqual([]);
  });

  it("a dimensionless tag the model carries exactly is a size", () => {
    expect(linkOf("post 2B1 HD12 ok", [el("b1", "Beam", "2B1", "HD12")]).conf).toBe(1);
  });
});

describe("running headers and footers are detected per document", () => {
  const P1 = page(1, "BEAM DESIGN\nbeam 2B1 W18X35 at level 2 ok");
  const P2 = page(2, "GIRDER DESIGN\ngirder 2G1 W24X55 at level 2 ok");
  const edges = (pages: ReturnType<typeof page>[]) => inferCalcEdges(segment(pages), pages, []).map((e) => [e.src, e.dst]);

  it("a recurring footer with a cue word, and a recurring header, are not references", () => {
    // rejects round 1: "Designed per ..." (cue PER) and "Page 4   Project: ..." (not at line end) drew edges
    expect(edges([P1, P2,
      page(3, "COLUMN DESIGN\ncolumn C1 W12X53 ok\nDesigned per AISC 360-16    Page 1"),
      page(4, "COLUMN DESIGN (cont.)\ncolumn C2 W12X53 ok\nDesigned per AISC 360-16    Page 2")])).toEqual([]);
    expect(edges([P1, P2,
      page(3, "Page 1   Project: Office Tower\nCOLUMN DESIGN\ncolumn C1 W12X53 ok"),
      page(4, "Page 2   Project: Office Tower\nCOLUMN DESIGN (cont.)\ncolumn C2 W12X53 ok")])).toEqual([]);
  });

  it("a page mention that does not recur stays a reference, cue word or not", () => {
    // rejects round 1, which dropped a bare line-end "page 7" as a footer
    expect(edges([P1, P2, page(3, "COLUMN DESIGN\ncolumn C1 W12X53 ok\naxial ratio 0.6 ok\nmax end reaction: page 1")]))
      .toEqual([["beam-design", "column-design"]]);
  });

  it("finds the running lines by band, on short pages too", () => {
    const pages = [page(1, "beam 2B5 ok fine here\nRISA-3D Version 19 Page 1"), page(2, "BEAM DESIGN\nbody\nmore\nRISA-3D Version 19 Page 2")];
    const r = runningLines(pages);
    expect([...(r.get(1) ?? [])]).toEqual([pages[0]!.text.indexOf("RISA")]);
    expect([...(r.get(2) ?? [])]).toEqual([pages[1]!.text.indexOf("RISA")]);
  });
});

describe("parseGraph is exactly as strict as what the engine reads", () => {
  const withB1 = (patch: Record<string, unknown>) => graph({ nodes: graph().nodes.map((n) => (n.id === "B1" ? { ...n, ...patch } : n)) as never });

  it.each([
    ["a numeric mark", withB1({ mark: 101 })],
    ["a numeric level id and name", { ...withB1({ levelId: 2 }), levels: [{ id: 2, name: 2 }] as never }],
    ["2-component coordinates", withB1({ geometry: { bbox: { min: [0, 0], max: [6, 0.2] } } })],
    ["a NaN coordinate serialized as null", withB1({ geometry: { bbox: { min: [null, 0, 4], max: [6, 0.2, 4.4] } } })],
    ["meta that is not an object", { ...graph(), meta: "x" as never }],
    ["evidence detail that is not an object", graph({ edges: graph().edges.map((e) => ({ ...e, evidence: [{ rule: "r", source: "inferred", detail: 5 }] })) as never })],
  ])("accepts what the app can save: %s", (_name, g) => {
    // rejects round 1, which refused these, so a saved project failed to reopen
    expect(() => parseGraph(JSON.stringify(g))).not.toThrow();
  });

  it("reads numbers in text fields as their text", () => {
    const rows = graphElements(parseGraph(JSON.stringify({ ...withB1({ mark: 101, levelId: 2 }), levels: [{ id: 2, name: 2 }] })));
    expect(rows.find((r) => r.global_id === "B1")).toMatchObject({ mark: "101", storey: "2" });
  });

  it.each([
    [withB1({ profile: { a: 1 } }), "profile must be a string or number"],
    [withB1({ geometry: { bbox: { min: "abc", max: [1, 1, 1] } } }), "geometry.bbox needs min and max"],
    [graph({ edges: [{ id: "e", kind: "supports", a: "B1", b: "C1", directed: true, evidence: [null] }] as never }), "evidence must be a list of objects"],
  ])("still refuses a shape the engine would throw on or misread: %#", (g, msg) => {
    expect(() => parseGraph(JSON.stringify(g))).toThrow(GraphFormatError);
    expect(() => parseGraph(JSON.stringify(g))).toThrow(msg);
  });
});

describe("a stored calc package", () => {
  it("records the segmenter that made it, and the engine version names both versions", () => {
    const pkg = segmentCalcs([page(1, "BEAM DESIGN\nbeam 2B1 W18X35 ok")]);
    expect(pkg.segmenter).toBe(SEGMENTER_VERSION);
    expect(ENGINE_VERSION).toBe(`${MAPPER_VERSION}+${SEGMENTER_VERSION}`);
    expect(calcPackageProblem(JSON.parse(JSON.stringify(pkg)))).toBeNull();
  });

  it.each([
    ["no text on a page", (x: any) => delete x.pages[0].text, /pages\[0\]\.text/],
    ["words not a list", (x: any) => (x.pages[0].words = {}), /pages\[0\]\.words/],
    ["spans not a list", (x: any) => (x.calcs[0].spans = 5), /calcs\[0\]\.spans/],
    ["a duplicate calc key", (x: any) => x.calcs.push({ ...x.calcs[0], ord: 1 }), /duplicate calc key/],
    ["a region on a page the package does not have", (x: any) => (x.calcs[0].spans[0].regions[0].page = 9), /calcs\[0\]\.spans/],
  ])("names what is wrong: %s", (_n, mutate, why) => {
    const x = JSON.parse(JSON.stringify(segmentCalcs([page(1, "BEAM DESIGN\nbeam 2B1 W18X35 ok")])));
    mutate(x);
    expect(calcPackageProblem(x)).toMatch(why);
  });
});

/**
 * Version ratchet. Stored extractions are reused while `segmenter` === SEGMENTER_VERSION, and stored
 * mapping runs while their engine === ENGINE_VERSION, so a change to what segment / runMapping /
 * inferCalcEdges return that keeps the version reuses stale results in every existing project (round 2,
 * finding 3). This fixture exercises the rules realistic packages hit; if its fingerprint changes, bump
 * the version (types.ts) and re-pin BOTH the version and the fingerprint here.
 */
describe("version ratchet: a behaviour change must bump the version that keys stored results", () => {
  const RATCHET_PAGES = [
    page(1, "Sample Office Building\nJob 2611 issued for permit 2026"),
    page(2, "TABLE OF CONTENTS\nBeams 3\nColumns 5"),
    page(3, "BEAM DESIGN\nbeam 2B1 W18X35 at Level 2, MU = 45 X 12 = 540 in-k\nbeams 2B2-2B4 W18X35 ok\nRISA-3D Version 19 Page 1"),
    page(4, ""),
    page(5, "beam 2B5 tributary 10 x 20 ft, HD12 holdown at end\nRISA-3D Version 19 Page 2"),
    page(6, "COLUMN DESIGN\ncolumn C1 W12X53 reactions from page 3\nLevel 2 typical beams W18X35\nmax end reaction: page 5\nDesign loads per S-001"),
    page(7, "S-001 GRAVITY LOAD CRITERIA\nSuperimposed dead load 15 psf, live load 50 psf\nCarried to S-002"),
    page(8, "S-002 SEISMIC LOAD ANALYSIS\nSeismic weight from S-001; base shear V = 0.12 W"),
  ];
  const RATCHET_ELEMENTS = [
    el("b1", "Beam", "2B1", "W18X35"), el("b3", "Beam", "2B3", "W18X35"), el("b5", "Beam", "2B5", "W18X35"),
    el("b9", "Beam", "", "W18X35"), el("c1", "Column", "C1", "W12X53"), el("x", "Beam", "2B9", "Beam"),
  ];

  it("segmenter", () => {
    const fp = sha1Json(segment(RATCHET_PAGES).map((c) => [c.key, c.title, c.pages, c.scanned, c.front, c.cat, c.software, c.spans]));
    expect({ version: SEGMENTER_VERSION, fp }).toEqual({ version: "segment-v3", fp: "36d19b0cde0e583151850f28a5376169a0184720" });
  });

  it("matcher and calc edges", () => {
    const calcs = segment(RATCHET_PAGES);
    const links = runMapping(RATCHET_ELEMENTS, calcs, RATCHET_PAGES, GRAPH_SHA);
    const fp = sha1Json([
      links.map((l) => [l.global_id, l.calc_key, l.tier, l.conf, l.role, l.span]),
      inferCalcEdges(calcs, RATCHET_PAGES, links).map((e) => [e.src, e.dst, e.rules]),
    ]);
    expect({ version: MAPPER_VERSION, fp }).toEqual({ version: "mapper-v1.3", fp: "46cc6a4621703f3d228b8a63062618f505c7e9a1" });
  });
});
