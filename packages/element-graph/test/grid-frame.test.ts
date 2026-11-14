import { describe, expect, it } from "vitest";
import { buildGraph } from "../src/index.ts";
import { gridFrame } from "./helpers.ts";

describe("synthetic grid frame (10x10 bays, 3 storeys)", () => {
  const bx = 10, by = 10, storeys = 3;
  const input = gridFrame(bx, by, storeys);
  const t0 = performance.now();
  const { graph, warnings } = buildGraph(input);
  const ms = performance.now() - t0;

  const cols = (bx + 1) * (by + 1);
  const beamsPerStorey = bx * (by + 1) + by * (bx + 1);
  const conns = beamsPerStorey * 2 * storeys;
  const slabs = bx * by * storeys;

  it("builds quickly", () => {
    console.log(`grid frame: ${input.elements.length} elements, ${graph.edgeCount} edges, ${ms.toFixed(0)} ms`);
    expect(ms).toBeLessThan(1000);
  });

  it("has expected node counts", () => {
    expect(graph.nodesByKind("column")).toHaveLength(cols * storeys);
    expect(graph.nodesByKind("beam")).toHaveLength(beamsPerStorey * storeys);
    expect(graph.nodesByKind("connection")).toHaveLength(conns);
    expect(graph.nodesByKind("slab")).toHaveLength(slabs);
  });

  it("has expected supports edge counts per rule", () => {
    const rules = new Map<string, number>();
    for (const e of graph.edges()) {
      if (e.kind !== "supports") continue;
      const r = e.evidence[0]!.rule;
      rules.set(r, (rules.get(r) ?? 0) + 1);
    }
    expect(rules.get("connection contact")).toBe(conns * 2); // beam -> K, K -> column
    expect(rules.get("slab bears on support top")).toBe(slabs * 4);
    expect(rules.get("column bottom bears on support")).toBe(cols * storeys);
    expect(rules.get("beam end bears on column/wall")).toBeUndefined();
    expect(graph.stats().edgesByKind.supports).toBe(conns * 2 + slabs * 4 + cols * storeys);
  });

  it("has sensible load paths and no cycles", () => {
    expect(warnings).toEqual([]);
    const down = graph.loadPathDown("S_4_4_2");
    expect(down.has("F_4_4")).toBe(true);
    expect(down.get("C_4_4_0")).toBe(4); // slab, beam, (K) column top storey, column, column
    expect(graph.supportsOf("C_3_3_1")).toEqual(["C_3_3_0"]);
    expect(graph.supportsOf("C_3_3_0")).toEqual(["F_3_3"]);
    expect(graph.connectionsOf("BX_2_2_0").sort()).toEqual(["K_BX_2_2_0_0", "K_BX_2_2_0_1"]);
  });
});
