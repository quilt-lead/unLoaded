import { describe, expect, it } from "vitest";
import { buildGraph, ElementGraph } from "../src/index.ts";
import { loadSimpleFrame } from "./helpers.ts";

describe("buildGraph on simple-frame fixture", () => {
  const input = loadSimpleFrame();
  const { graph, warnings } = buildGraph(input);

  it("creates all nodes and levels", () => {
    expect(graph.nodeCount).toBe(input.elements.length);
    expect(graph.levels().map((l) => l.id)).toEqual(["L0", "L1"]);
    expect(graph.getNode("B1")?.mark).toBe("B101");
    expect(graph.getNode("B1")?.tags).toEqual({});
    expect(graph.getNode("B1")?.links).toEqual([]);
  });

  it("produces every expected supports edge with correct direction", () => {
    for (const [a, b] of input._expected.supports) {
      const e = graph.findEdge("supports", a, b);
      expect(e, `supports ${a} -> ${b}`).toBeDefined();
      expect(e!.directed).toBe(true);
      expect(e!.a).toBe(a);
      expect(e!.b).toBe(b);
      expect(graph.findEdge("supports", b, a), `reverse ${b} -> ${a}`).toBeUndefined();
    }
  });

  it("does not produce the forbidden supports edges", () => {
    for (const [a, b] of input._expected.notSupports) {
      expect(graph.findEdge("supports", a, b), `supports ${a} -> ${b}`).toBeUndefined();
    }
  });

  it("has a connects edge for each support", () => {
    for (const [a, b] of input._expected.supports) {
      expect(graph.findEdge("connects", a, b), `connects ${a}|${b}`).toBeDefined();
      expect(graph.findEdge("connects", b, a)).toBe(graph.findEdge("connects", a, b));
    }
  });

  it("keeps explicit evidence first on the merged B1-K1 connects edge", () => {
    const e = graph.findEdge("connects", "B1", "K1")!;
    expect(e.id).toBe("connects:B1|K1");
    expect(e.directed).toBe(false);
    expect(e.evidence[0]).toMatchObject({ source: "explicit", rule: "IfcRelConnectsWithRealizingElements" });
    expect(e.evidence.some((ev) => ev.source === "inferred")).toBe(true);
  });

  it("tags inferred evidence with rule and gap", () => {
    const e = graph.findEdge("supports", "S1", "B1")!;
    expect(e.evidence[0]).toMatchObject({ source: "inferred", rule: "slab bears on support top" });
    expect(typeof e.evidence[0]!.detail?.gap_m).toBe("number");
  });

  it("supports queries and load paths", () => {
    expect(graph.connectionsOf("B1").sort()).toEqual(["K1", "K2"]);
    expect(graph.membersOf("K1").sort()).toEqual(["B1", "C1"]);
    expect(graph.supportsOf("B1").sort()).toEqual(["K1", "K2"]);
    expect(graph.supportedBy("C1")).toEqual(["K1"]);

    const down = graph.loadPathDown("S1");
    expect(down.get("S1")).toBe(0);
    expect(down.get("B1")).toBe(1);
    expect(down.get("K1")).toBe(2);
    expect(down.get("C1")).toBe(2); // connection is pass-through
    expect(down.get("F1")).toBe(3);
    expect(down.get("F2")).toBe(3);

    const up = graph.loadPathUp("F1");
    expect([...up.keys()].sort()).toEqual(["B1", "C1", "F1", "K1", "S1"]);
  });

  it("has no warnings and no cycles", () => {
    expect(warnings).toEqual([]);
    expect(graph.findCycles()).toEqual([]);
  });

  it("round-trips through serialize / deserialize losslessly", () => {
    const json = JSON.stringify(graph.serialize());
    const back = ElementGraph.deserialize(json);
    expect(back.serialize()).toEqual(graph.serialize());
    expect(JSON.stringify(back.serialize())).toBe(json);
    expect(back.loadPathDown("S1")).toEqual(graph.loadPathDown("S1"));
  });

  it("reports stats by kind and rule", () => {
    const s = graph.stats();
    expect(s.nodesByKind).toMatchObject({ footing: 2, column: 2, beam: 1, connection: 2, slab: 1 });
    expect(s.edgesByKind.supports).toBe(7);
    expect(s.edgesByRule["connection contact"]).toBeGreaterThan(0);
    expect(s.explicitEdges).toBe(1);
  });

  it("can disable inference", () => {
    const { graph: g } = buildGraph(input, { infer: false });
    expect(g.edgeCount).toBe(1);
    const { graph: g2 } = buildGraph(input, { infer: { bboxContact: false, slabBearing: false } });
    expect(g2.findEdge("supports", "S1", "B1")).toBeUndefined();
    expect(g2.findEdge("supports", "C1", "F1")).toBeDefined();
  });

  it("warns and skips relations with unknown endpoints", () => {
    const bad = { ...input, relations: [...input.relations, { a: "B1", b: "NOPE", kind: "connects", evidence: { rule: "x", source: "explicit" as const } }] };
    const r = buildGraph(bad);
    expect(r.warnings.some((w) => w.includes("NOPE"))).toBe(true);
  });

  it("does not let inference override an explicit supports direction", () => {
    const flipped = {
      ...input,
      relations: [{ a: "B1", b: "S1", kind: "supports", evidence: { rule: "manual", source: "explicit" as const } }],
    };
    const r = buildGraph(flipped);
    expect(r.graph.findEdge("supports", "B1", "S1")).toBeDefined();
    expect(r.graph.findEdge("supports", "S1", "B1")).toBeUndefined();
    expect(r.warnings.some((w) => w.includes("conflicts with explicit"))).toBe(true);
  });
});
