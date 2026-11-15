import { describe, expect, it } from "vitest";
import { buildGraph, type ElementInput, type ModelInput, type Vec3 } from "../src/index.ts";

const el = (id: string, kind: string, min: Vec3, max: Vec3, axis?: { start: Vec3; end: Vec3 }): ElementInput => ({
  id,
  kind,
  params: {},
  source: { format: "synthetic" },
  geometry: axis ? { bbox: { min, max }, axis } : { bbox: { min, max } },
});

const model = (elements: ElementInput[]): ModelInput => ({
  meta: { version: 1, units: "m", source: { format: "synthetic" } },
  levels: [],
  elements,
  relations: [],
  warnings: [],
});

// pile cap 2.7 m square, 1.07 m deep, top at 0; pile under it, head at the cap underside (Harborview layout)
const cap = el("CAP", "footing", [-1.35, -1.35, -1.07], [1.35, 1.35, 0]);
const pile = (id: string, x: number, top: number) =>
  el(id, "pile", [x - 0.26, -0.26, -7.16], [x + 0.26, 0.26, top], { start: [x, 0, top], end: [x, 0, -7.16] });

describe("footingOnPile", () => {
  it("a pile cap is supported by the pile under it", () => {
    const { graph } = buildGraph(model([cap, pile("P", 0, -1.07)]));
    const e = graph.findEdge("supports", "CAP", "P");
    expect(e?.evidence.map((v) => v.rule)).toContain("footing bears on pile");
    expect(graph.findEdge("supports", "P", "CAP")).toBeUndefined();
  });

  it("an embedded pile head also supports the cap; every pile of a group does", () => {
    const { graph } = buildGraph(model([cap, pile("P1", -0.8, -0.9), pile("P2", 0.8, -0.9)]));
    expect(graph.supportsOf("CAP").sort()).toEqual(["P1", "P2"]);
  });

  it("a pile only grazing the cap side in plan is not a support", () => {
    const { graph } = buildGraph(model([cap, pile("P", 1.6, -1.07)]));
    expect(graph.findEdge("supports", "CAP", "P")).toBeUndefined();
  });
});
