import { describe, expect, it } from "vitest";
import {
  designerOf, diffGraphs, GraphFormatError, inferCalcEdges, mapElements, pageReferences, parseGraph, ruleProvenance, runMapping,
  segment, uniqueKeys, foldText, type Link,
} from "../src/index.ts";
import { DOC_SHA, GRAPH_SHA, el, graph, page } from "./helpers.ts";

describe("calc keys are unique by construction", () => {
  const body = (mark: string) => `beam ${mark} W18X35 ok, stress ratio 0.81 fine`;
  const pages = [
    page(1, `BEAM DESIGN 2\n${body("2B1")}`), page(2, `BEAM DESIGN\n${body("2B2")}`), page(3, ""),
    page(4, `BEAM DESIGN\n${body("2B3")}`), page(5, body("2B4")),
  ];

  it("no two calcs share a key, and a titled page after a scanned run continues the earlier calc of that title", () => {
    // rejects: beam-design-2 [1], beam-design [2], scanned-1 [3], beam-design-2 [4, 5] (two calcs, one key)
    const calcs = segment(pages);
    expect(calcs.map((c) => [c.key, c.pages])).toEqual([["beam-design-2", [1]], ["beam-design", [2, 4, 5]], ["scanned-1", [3]]]);
    expect(new Set(calcs.map((c) => c.key)).size).toBe(calcs.length);
  });

  it("a suffix never takes a key another calc's own slug has", () => {
    // rejects the old "<base>-<count>" rule, which gave the second beam-design the key beam-design-2 a calc already had
    expect(uniqueKeys(["beam-design-2", "beam-design", "beam-design"])).toEqual(["beam-design-2", "beam-design", "beam-design-3"]);
    expect(uniqueKeys(["beam-design", "beam-design", "beam-design-2"])).toEqual(["beam-design", "beam-design-3", "beam-design-2"]);
    expect(uniqueKeys(["a", "a", "a"])).toEqual(["a", "a-2", "a-3"]);
  });
});

describe("continuations of a scanned run or front matter inherit their flags", () => {
  it("an untitled page after a contents page is front matter, not a mappable calc", () => {
    // rejects: a second calc "Front matter / contents (cont.)" with front: false that maps 2B1
    const pages = [page(1, "Design criteria .... 2\nBeams .... 3\nColumns .... 4"), page(2, "beam 2B1 W18X35 ok, stress ratio fine")];
    const calcs = segment(pages);
    expect(calcs.map((c) => [c.title, c.front, c.pages])).toEqual([["Front matter / contents", true, [1, 2]]]);
    expect(runMapping([el("a", "Beam", "2B1")], calcs, pages, GRAPH_SHA)).toEqual([]);
  });

  it("an untitled text page after a scanned run stays in that scanned calc", () => {
    // rejects: "Scanned page(s) - no text layer (cont.)" as a separate, mapped calc
    const pages = [page(1, ""), page(2, "beam 2B1 W18X35 ok, stress ratio fine")];
    const calcs = segment(pages);
    expect(calcs.map((c) => [c.key, c.scanned, c.pages])).toEqual([["scanned-1", true, [1, 2]]]);
    expect(runMapping([el("a", "Beam", "2B1")], calcs, pages, GRAPH_SHA)).toEqual([]);
  });

  it("a title-less cover is front matter", () => {
    // rejects: "Front matter" with front: false (mapped)
    const pages = [page(1, "Sample Office Building, job 2611, issued for permit")];
    expect(segment(pages).map((c) => [c.title, c.front])).toEqual([["Front matter", true]]);
  });
});

const link = (gid: string, calc: string, tier: Link["tier"], conf: number, role: Link["role"], extra: Partial<Link> = {}): Link => ({
  global_id: gid, calc_key: calc, conf, tier, rule: "r", page: null, token: "", span: null, snippet: null, rects: [], status: "auto",
  role, band: "high", evidence: [{ kind: "tier", weight: conf, note: tier, page: null, rects: [] }], caveats: [],
  provenance: ruleProvenance("matcher", `matcher.tier.${tier}`, [GRAPH_SHA, DOC_SHA]), ...extra,
});

describe("the designer of an element", () => {
  const pg = page(1, "SHEAR TAB CONNECTION\nreaction of girder 2G5 at ST-1");
  const loads = link("g", "a-takeoff", "exact", 0.97, "loads");
  const design = link("g", "b-girder-design", "size", 0.62, "design");
  const xref = link("g", "c-shear-tab", "xref", 0.45, "loads", { page: 1, span: [40, 43], token: "2G5" });

  it("is the design-role calc, not a stronger loads-only mention", () => {
    // rejects: the loads-only exact link (0.97) chosen over the design link (0.62) by tier alone
    expect(designerOf([loads, design]).get("g")?.calc_key).toBe("b-girder-design");
    const edges = inferCalcEdges([], [pg], [loads, design, xref]);
    expect(edges.map((e) => [e.src, e.dst])).toEqual([["b-girder-design", "c-shear-tab"]]);
  });

  it("does not depend on the order of the links (ties go to the smaller calc key)", () => {
    const p = link("g", "p-calc", "exact", 0.97, "design"), q = link("g", "q-calc", "exact", 0.97, "design");
    expect(designerOf([q, p]).get("g")?.calc_key).toBe("p-calc");
    expect(designerOf([p, q]).get("g")?.calc_key).toBe("p-calc");
    expect(designerOf([design, loads]).get("g")?.calc_key).toBe("b-girder-design");
  });
});

describe("page numbers are not page references", () => {
  it("drops 'Page n of N', 'Page n/N' and a bare footer 'Page n'; keeps cued and parenthesised references", () => {
    const U = foldText([
      "RISA-3D Version 19.0.2 Page 1", "Page 2 of 40", "Page 3/5", "column reactions from page 1",
      "Ru := 32.8 kip (max end reaction, page 7)", "carried to ST-1 connection design (page 10).",
    ].join("\n"));
    expect(pageReferences(U).map((r) => [r.from, r.cue ?? null])).toEqual([[1, "FROM"], [7, null], [10, "TO"]]);
  });

  it("a calc whose software numbers its pages 1..n draws no edge to PDF page 1's calc", () => {
    // rejects: false edges beam-design -> footing-design from "Page 1 of 1" / "Page 1/1" / "RISA ... Page 1"
    const pages = [
      page(1, "BEAM DESIGN\nbeam 2B1 W18X35 at level 2"),
      page(2, "COLUMN DESIGN\ncolumn reactions from page 1"),
      page(3, "FOOTING DESIGN\nfooting F1 bearing ok\nPage 1 of 1\nPage 1/1\nRISA-3D Version 19.0.2 Page 1"),
    ];
    const edges = inferCalcEdges(segment(pages), pages, []);
    expect(edges.map((e) => [e.src, e.dst])).toEqual([["beam-design", "column-design"]]);
  });
});

describe("one storey test for the size rule and the evidence", () => {
  it("'roofing' does not name the Roof storey", () => {
    // rejects: the size rule's substring test reading ROOFING as Roof and dropping the Level 3 member
    const els = [el("r", "Beam", "", "W12X19", "Roof"), el("l3", "Beam", "", "W12X19", "Level 3")];
    const pages = [page(1, "BEAM DESIGN\nroofing support beams W12X19 ok")];
    const { links } = mapElements(els, segment(pages), pages, GRAPH_SHA);
    expect(links.map((l) => l.global_id).sort()).toEqual(["l3", "r"]);
    expect(links.every((l) => !/ on Roof/.test(l.rule))).toBe(true);
  });

  it("'Level 10' does not name Level 1", () => {
    const pages = [page(1, "BEAM DESIGN\nLevel 10 typical beams W18X35 ok")];
    const { links } = mapElements([el("a", "Beam", "", "W18X35", "Level 1")], segment(pages), pages, GRAPH_SHA);
    expect(links.map((l) => [l.global_id, l.rule])).toEqual([["a", "Size W18X35 + element type Beam (no mark given)"]]);
  });
});

describe("calc text is folded once where the rules read it", () => {
  it("a Unicode hyphen in the calc matches the ASCII mark (token and range rules)", () => {
    // rejects: "SL‐2" tokenised as "SL" + "2" (no match; the slab calc fell to the type tier), and "2B1‑2B3" as no range
    const pages = [page(1, "SLAB DESIGN\nslab SL‐2 thickness 200 mm ok"), page(2, "BEAM DESIGN\nbeams 2B1‑2B3 W18X35 ok")];
    const els = [el("s", "Slab", "SL-2"), el("b2", "Beam", "2B2")];
    const links = runMapping(els, segment(pages), pages, GRAPH_SHA);
    const s = links.find((l) => l.global_id === "s")!;
    expect([s.tier, s.token]).toEqual(["exact", "SL‐2"]);
    expect(links.find((l) => l.global_id === "b2")?.tier).toBe("range");
  });

  it("offsets stay exact when upper-casing would lengthen a character", () => {
    // rejects: toUpperCase() turning "ß" into "SS", so every span after it pointed one character late
    const pages = [page(1, "BEAM DESIGN\nstraße beam 2B1 ok fine")];
    const [l] = runMapping([el("a", "Beam", "2B1")], segment(pages), pages, GRAPH_SHA);
    expect(l!.token).toBe("2B1");
    expect(pages[0]!.text.slice(l!.span![0], l!.span![1])).toBe("2B1");
  });
});

describe("the diff hash and the per-field comparison are one field list", () => {
  it("a rename lists the name (and an ifc_type change lists ifc_type)", () => {
    // rejects: changed with fields {} - the hash covered name / ifc_type, the field loop did not
    const b = graph();
    b.nodes = b.nodes.map((n) => (n.id === "B1" ? { ...n, name: "2B1 renamed" } : n.id === "C1" ? { ...n, source: { format: "ifc", nativeType: "IfcMember" } } : n));
    expect(diffGraphs(graph(), b).changed).toEqual([
      { global_id: "B1", mark: "2B1", fields: { name: ["2B1", "2B1 renamed"] } },
      { global_id: "C1", mark: "C1", fields: { ifc_type: ["IfcColumn", "IfcMember"] } },
    ]);
  });

  it("float noise below 1 mm and an axis-only change are not 'moved / resized'", () => {
    // rejects: geometry compared unrounded (with the axis) while the hash rounds the bbox to 1 mm
    const b = graph();
    b.nodes = b.nodes.map((n) => (n.id === "B1"
      ? { ...n, profile: "W18X40", geometry: { bbox: { min: [1e-7, 0, 4], max: [6, 0.2000001, 4.4] }, axis: { start: [0, 0.1, 4.2], end: [6, 0.1, 4.21] } } }
      : n));
    expect(diffGraphs(graph(), b).changed).toEqual([{ global_id: "B1", mark: "2B1", fields: { profile: ["W18X35", "W18X40"] } }]);
  });
});

describe("parseGraph validates every field the engine reads", () => {
  const withB1 = (geometry: unknown) => JSON.stringify(graph({ nodes: graph().nodes.map((n) => (n.id === "B1" ? { ...n, geometry } : n)) as never }));
  it.each([
    [withB1({ bbox: {} }), "geometry.bbox needs min and max"],
    [withB1({ bbox: { min: [0, 0], max: [1, 1, 1] } }), "geometry.bbox needs min and max"],
    [withB1({ bbox: { min: [0, 0, 0], max: [1, 1, 1] }, axis: { start: [0, 0, 0] } }), "geometry.axis needs start and end"],
    [JSON.stringify(graph({ levels: [{}] as never })), "graph.levels[0] needs a string id"],
    [JSON.stringify(graph({ levels: [null] as never })), "graph.levels[0] needs a string id"],
    [JSON.stringify(graph({ edges: [{ id: "e", kind: "supports", a: "B1", b: "C1", directed: true, evidence: {} }] as never })), "evidence must be a list"],
    [JSON.stringify(graph({ nodes: graph().nodes.map((n) => (n.id === "B1" ? { ...n, params: [] } : n)) as never })), "params must be an object"],
  ])("rejects a shape graphElements / loadPath would throw a TypeError on: %#", (bad, msg) => {
    // rejects: parseGraph accepting these, then graphElements failing with a TypeError past callers that catch GraphFormatError
    expect(() => parseGraph(bad)).toThrow(GraphFormatError);
    expect(() => parseGraph(bad)).toThrow(msg);
  });

  it("still accepts a well-formed graph", () => {
    expect(() => parseGraph(JSON.stringify(graph()))).not.toThrow();
  });
});
