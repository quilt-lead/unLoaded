import { describe, expect, it } from "vitest";
import {
  addDecision, applyDecisions, buildExport, connectivity, diffGraphs, effectiveDecisions, graphElements, GraphFormatError,
  loadPath, parseGraph, propagate, ruleProvenance, segmentCalcs, mapCalcs, type Decision, type Link,
} from "../src/index.ts";
import { DOC_SHA, GRAPH_SHA, graph, node, page } from "./helpers.ts";

describe("serialized element graph -> element rows", () => {
  it("maps nodes the way the reference engine did", () => {
    const els = new Map(graphElements(graph()).map((e) => [e.global_id, e]));
    const b = els.get("B1")!;
    expect([b.ifc_type, b.cat, b.mark, b.profile, b.storey, b.type_name]).toEqual(["IfcBeam", "Beam", "2B1", "W18X35", "Level 2", "W18X35"]);
    expect(b.geom).toEqual({ min: [0, 0, 4], max: [6, 0.2, 4.4], p1: [0, 0.1, 4.2], p2: [6, 0.1, 4.2] });
    expect(els.get("K1")!.cat).toBe("Connection");
    expect(els.get("F1")!.cat).toBe("Connection");
    expect(els.get("X1")!.cat).toBe("Other");
    expect(els.get("C1")!.storey).toBe("");
    expect([...els.keys()]).toEqual(["B1", "C1", "F1", "K1", "X1"]);
  });

  it("load path = supports edges; connectivity = connects edges", () => {
    expect(loadPath(graph()).map((e) => [e.src, e.dst, e.rule, e.gap_m])).toEqual([
      ["B1", "K1", "connection contact", 0.004], ["K1", "C1", "connection contact", 0]]);
    expect(connectivity(graph())).toEqual([{ a: "B1", b: "C1", rule: "IfcRelConnectsElements", explicit: true }]);
  });

  it.each([
    ["not json", "not valid JSON"],
    ["[1]", "JSON object"],
    [JSON.stringify(graph({ format: "x" as never })), "format must be"],
    [JSON.stringify(graph({ version: 2 as never })), "version 2 is not supported"],
    [JSON.stringify({ ...graph(), nodes: "x" }), "graph.nodes must be a list"],
    [JSON.stringify(graph({ nodes: [node("A", "beam"), node("A", "beam")], edges: [] })), "duplicate node id"],
    [JSON.stringify(graph({ edges: [{ id: "e", kind: "supports", a: "B1", b: "ZZ", directed: true, evidence: [] }] })), "not in graph.nodes"],
  ])("rejects what is not a serialized graph: %#", (bad, msg) => {
    expect(() => parseGraph(bad)).toThrow(GraphFormatError);
    expect(() => parseGraph(bad)).toThrow(msg);
  });
});

describe("impact", () => {
  it("waves pass through connection nodes (the package's loadPathDown depth)", () => {
    const els = new Map(graphElements(graph()).map((e) => [e.global_id, e]));
    const im = propagate("B1", "change", loadPath(graph()), [], [], els, [GRAPH_SHA]);
    expect(im.hit).toEqual({ B1: 0, K1: 1, C1: 1 });
    expect(im.waves).toBe(1);
  });

  it("removing the column re-frames what it carried and drops the connection that only served it", () => {
    const els = new Map(graphElements(graph()).map((e) => [e.global_id, e]));
    const im = propagate("C1", "remove", loadPath(graph()), [], [], els, [GRAPH_SHA]);
    expect(im.removed).toEqual(["C1", "K1"]);
    expect(Object.keys(im.hit)).toEqual(["B1"]);
  });
});

describe("diff", () => {
  it("reports removed, changed (per field) and load-path edges", () => {
    const b = graph();
    b.nodes = b.nodes.filter((n) => n.id !== "X1").map((n) => (n.id === "B1" ? { ...n, profile: "W18X40", params: { ...n.params, "Pset.Span": 6.2 } } : n));
    const d = diffGraphs(graph(), b, { a: 1, b: 2 });
    expect(d.removed).toEqual([{ global_id: "X1", mark: "", cat: "Other" }]);
    expect(d.added).toEqual([]);
    expect(d.changed).toEqual([{ global_id: "B1", mark: "2B1", fields: { "Pset.Span": [6.1, 6.2], profile: ["W18X35", "W18X40"] } }]);
    expect(diffGraphs(graph(), graph()).changed).toEqual([]);
  });
});

describe("decision log", () => {
  it("is append-only, latest wins, undo clears, and carries across runs while both keys exist", () => {
    let log: Decision[] = [];
    log = addDecision(log, { global_id: "B1", calc_key: "k", action: "reject" }, { at: "t1" });
    log = addDecision(log, { global_id: "B1", calc_key: "k", action: "confirm" }, { at: "t2" });
    log = addDecision(log, { global_id: "C1", calc_key: "k", action: "manual", actor: "issy" }, { at: "t3" });
    log = addDecision(log, { global_id: "X1", calc_key: "k", action: "confirm" }, { at: "t4" });
    log = addDecision(log, { global_id: "X1", calc_key: "k", action: "undo" }, { at: "t5" });
    expect(log.map((d) => d.id)).toEqual([1, 2, 3, 4, 5]);
    expect([...effectiveDecisions(log).values()].map((d) => [d.global_id, d.action])).toEqual([["B1", "confirm"], ["C1", "manual"]]);
    const auto: Link[] = [{ global_id: "B1", calc_key: "k", conf: 0.62, tier: "size", rule: "r", page: 1, token: "W", span: [0, 1], snippet: null, rects: [], status: "auto",
      role: "design", band: "medium", evidence: [], caveats: [], provenance: ruleProvenance("matcher", "matcher.tier.size", [GRAPH_SHA, DOC_SHA]) }];
    const out = applyDecisions(auto, log, new Set(["B1", "C1"]), new Set(["k"]));
    expect(out.map((l) => [l.global_id, l.status, l.tier, l.decided_at])).toEqual([["B1", "confirmed", "size", "t2"], ["C1", "manual", "manual", "t3"]]);
    expect(auto[0]!.status).toBe("auto"); // the run is not mutated
    expect(applyDecisions(auto, log, new Set(["B1"]), new Set(["other"]))[0]!.status).toBe("auto");
    expect(() => addDecision(log, { global_id: "a", calc_key: "b", action: "nope" as never })).toThrow();
  });
});

describe("export", () => {
  it("has the backend's /export shape plus connectivity", async () => {
    const pages = [page(1, "BEAM DESIGN - RAM STEEL\nbeam 2B1 W18X35 at Level 2"), page(2, "COLUMN DESIGN\ncolumn C1, see page 1")];
    const pkg = segmentCalcs(pages, "calcs.pdf");
    const g = graph();
    const ex = buildExport(g, pkg, await mapCalcs(g, pkg), [], { model_revision: "rev1" });
    expect(Object.keys(ex).sort()).toEqual(["calc_edges", "calc_package", "calc_revision", "calcs", "connectivity", "elements",
      "engine", "findings", "group_links", "groups", "load_path", "model", "model_revision", "producers"]);
    expect(ex.calc_package).toBe("calcs.pdf");
    const b1 = ex.elements.find((e) => e.global_id === "B1")!;
    // exact (0.97) + the line names B1's storey (+0.05) and size (+0.05), clamped to 1
    expect(b1.calcs[0]).toMatchObject({ calc: "beam-design-ram-steel", tier: "exact", confidence: 1, matched_text: "2B1", review: "auto",
      role: "design", band: "high" });
    expect(b1.calcs[0]!.reasons.map((r) => r.kind)).toEqual(["tier", "storey-match", "size-match"]);
    expect(ex.calcs[0]!.spans).toEqual([{ regions: [{ page: 1, rect: [0, 0, 612, 792], start: 0, end: pages[0]!.text.length }] }]);
    expect(b1.status).toBe("confirmed");
    expect(ex.calc_edges.map((e) => [e.src, e.dst, e.rules])).toEqual([["beam-design-ram-steel", "column-design", ["page reference (input from)"]]]);
    expect(ex.load_path).toEqual([{ src: "B1", dst: "K1", rule: "connection contact" }, { src: "K1", dst: "C1", rule: "connection contact" }]);
  });
});
