/**
 * Regression tests for the round-2 review of move-impact (2026-11-14): transfer-member changes reach
 * columns only through statics, one factoring rule per column (no borrowed combination), column support
 * cycles, walls and two-path footings, and the footing clash basis. Each test names the wrong behaviour
 * it rejects.
 */
import { describe, expect, it } from "vitest";
import type { ElementNode, GraphEdge, SerializedElementGraph } from "@unloaded/element-graph";
import { impact, type CalcFact, type ImpactResult } from "../src/index.ts";

const GRAPH_SHA = "a".repeat(64);
const DOC_SHA = "b".repeat(64);
const FT = 0.3048;
type V3 = [number, number, number];

function node(id: string, kind: string, extra: Partial<ElementNode> = {}): ElementNode {
  return { id, kind, name: id, params: {}, source: { format: "test" }, tags: {}, links: [], ...extra };
}
function line(id: string, kind: string, a: V3, b: V3, levelId: string): ElementNode {
  const min = [0, 1, 2].map((k) => Math.min(a[k]!, b[k]!) - 0.05) as V3;
  const max = [0, 1, 2].map((k) => Math.max(a[k]!, b[k]!) + 0.05) as V3;
  return node(id, kind, { levelId, geometry: { bbox: { min, max }, axis: { start: a, end: b } } });
}
function box(id: string, kind: string, c: V3, h: V3, levelId = "L0"): ElementNode {
  return node(id, kind, { levelId, geometry: { bbox: { min: [c[0] - h[0], c[1] - h[1], c[2] - h[2]], max: [c[0] + h[0], c[1] + h[1], c[2] + h[2]] } } });
}
const sup = (a: string, b: string): GraphEdge => ({ id: `supports:${a}->${b}`, kind: "supports", a, b, directed: true, evidence: [] });
const graphOf = (levels: SerializedElementGraph["levels"], nodes: ElementNode[], edges: GraphEdge[]): SerializedElementGraph =>
  ({ format: "unloaded.element-graph", version: 1, meta: null, levels, nodes, edges });
/** A beam with a connection node at each end, supported (through it) by si / sj. */
function beam(nodes: ElementNode[], edges: GraphEdge[], id: string, a: V3, b: V3, si: string, sj: string, lv: string) {
  nodes.push(line(id, "beam", a, b, lv));
  for (const [end, p, s] of [["i", a, si], ["j", b, sj]] as const) {
    const k = `K-${id}-${end}`;
    nodes.push(box(k, "connection", p, [0.05, 0.05, 0.05], lv));
    edges.push(sup(id, k), sup(k, s));
  }
}
const src = (calcKey: string) => ({ calcKey, page: 1, rects: [], documentSha256: DOC_SHA });
const kip = (value: number) => ({ value, unit: "kip" });
const klf = (value: number) => ({ value, unit: "klf" });
const changesOf = (r: ImpactResult, e: string, quantity: string) =>
  (r.screened.find((x) => x.element === e)?.changes ?? []).filter((c) => c.quantity === quantity);
const delta = (r: ImpactResult, e: string, quantity: string) => {
  const c = changesOf(r, e, quantity);
  expect(c).toHaveLength(1);
  return c[0]!.after.value - c[0]!.before.value;
};

describe("removal: a transfer member's change reaches columns only through statics (finding 1)", () => {
  // C2 at (10, 4) carries E1 (from girder GL on line x = 0) and E3 (to girder GR on x = 20); removing it
  // makes E1 + E3 one 20 m transfer member whose far supports are the two GIRDERS, not columns
  const graph = () => {
    const nodes: ElementNode[] = [];
    const edges: GraphEdge[] = [];
    for (const [c, x, y] of [["C1", 0, 0], ["C3", 0, 8], ["C4", 20, 0], ["C6", 20, 8], ["C2", 10, 4]] as const) {
      nodes.push(line(c, "column", [x, y, 0], [x, y, 3], "L0"), box(`F${c.slice(1)}`, "footing", [x, y, -0.3], [0.5, 0.5, 0.3]));
      edges.push(sup(c, `F${c.slice(1)}`));
    }
    beam(nodes, edges, "GL", [0, 0.1, 3], [0, 7.9, 3], "C1", "C3", "L1");
    beam(nodes, edges, "GR", [20, 0.1, 3], [20, 7.9, 3], "C4", "C6", "L1");
    beam(nodes, edges, "E1", [0.1, 4, 3], [9.9, 4, 3], "GL", "C2", "L1");
    beam(nodes, edges, "E3", [10.1, 4, 3], [19.9, 4, 3], "C2", "GR", "L1");
    beam(nodes, edges, "E2", [0.1, 8, 3], [19.9, 8, 3], "C3", "C6", "L1");
    return graphOf([{ id: "L0", name: "Ground", elevation: 0 }, { id: "L1", name: "Level 1", elevation: 3 }], nodes, edges);
  };
  const r = impact({ graph: graph(), graphSha256: GRAPH_SHA, move: { column: "C2", remove: true } });

  it("the girder is re-solved with the change as a point load; it is not given a column load", () => {
    // rejects: GL treated as a column (a column_load change on a beam) and copied to everything below it
    expect(changesOf(r, "GL", "column_load")).toHaveLength(0);
    expect(delta(r, "GL", "moment")).toBeGreaterThan(0);
  });

  it("each column under the girder takes the girder's end reaction change, not the girder's whole change", () => {
    const dRi = delta(r, "GL", "end_reaction_i");
    const dRj = delta(r, "GL", "end_reaction_j");
    // the transfer member lands at GL's mid-span: each end takes half
    expect(dRi).toBeCloseTo(dRj, 9);
    // unit area load (dead only): reactions are factored by their governing 1.4 D, footings are service
    expect(delta(r, "F1", "footing_load") * 1.4).toBeCloseTo(dRi, 9);
    expect(delta(r, "F3", "footing_load") * 1.4).toBeCloseTo(dRj, 9);
    // rejects: C1 and C3 each taking the full change (twice what the girder passes on in total)
    expect(delta(r, "C1", "column_load") + delta(r, "C3", "column_load")).toBeCloseTo(dRi + dRj, 9);
  });
});

/** Two storeys: Cn (floor) under Cnu (roof), floor beams with live load, roof beams with roof live load. */
function twoStorey(opts: { cycle?: boolean; upperOnFooting?: boolean; wall?: boolean } = {}): SerializedElementGraph {
  const nodes: ElementNode[] = [];
  const edges: GraphEdge[] = [];
  for (const [c, x, y] of [["C1", 0, 0], ["C2", 10, 0], ["C3", 0, 8], ["C4", 10, 8]] as const) {
    nodes.push(line(c, "column", [x, y, 0], [x, y, 3], "L0"), line(`${c}u`, "column", [x, y, 3], [x, y, 6], "L1"));
    edges.push(sup(`${c}u`, c));
    if (opts.wall && c === "C2") {
      nodes.push(box("W", "wall", [10, 0, -0.6], [3, 0.15, 0.6]), box("FA", "footing", [8, 0, -1.5], [0.5, 0.5, 0.3]), box("FB", "footing", [12, 0, -1.5], [0.5, 0.5, 0.3]));
      edges.push(sup("C2", "W"), sup("W", "FA"), sup("W", "FB"));
    } else {
      nodes.push(box(`F${c.slice(1)}`, "footing", [x, y, -0.3], [0.5, 0.5, 0.3]));
      edges.push(sup(c, `F${c.slice(1)}`));
    }
  }
  if (opts.cycle) edges.push(sup("C2", "C2u"));
  if (opts.upperOnFooting) edges.push(sup("C2u", "F2"));
  for (const [s, Z, lv] of [["", 3, "L1"], ["u", 6, "L2"]] as const) {
    beam(nodes, edges, `G1${s}`, [0, 0.1, Z], [0, 7.9, Z], `C1${s}`, `C3${s}`, lv);
    beam(nodes, edges, `G2${s}`, [10, 0.1, Z], [10, 7.9, Z], `C2${s}`, `C4${s}`, lv);
    beam(nodes, edges, `E1${s}`, [0.1, 0, Z], [9.9, 0, Z], `C1${s}`, `C2${s}`, lv);
    beam(nodes, edges, `E2${s}`, [0.1, 8, Z], [9.9, 8, Z], `C3${s}`, `C4${s}`, lv);
    beam(nodes, edges, `B1${s}`, [0.1, 4, Z], [9.9, 4, Z], `G1${s}`, `G2${s}`, lv);
  }
  return graphOf([{ id: "L0", name: "Ground", elevation: 0 }, { id: "L1", name: "Level 1", elevation: 3 }, { id: "L2", name: "Roof", elevation: 6 }], nodes, edges);
}
/** Stated line loads and reactions: floor D 1 + L 2 klf, roof D 0.5 + Lr 0.6 klf. */
function beamFacts(): CalcFact[] {
  const f: CalcFact[] = [];
  for (const b of ["G1", "G2", "E1", "E2", "B1"]) {
    const L = (b.startsWith("G") ? 8 : 10) / FT;
    const R = (w: number) => kip((w * L) / 2);
    f.push({ id: `${b}#f`, kind: "beam", elements: [b], source: src(b), lineLoad: { dead: klf(1), live: klf(2) }, reactions: { i: { dead: R(1), live: R(2) }, j: { dead: R(1), live: R(2) } } });
    f.push({ id: `${b}#r`, kind: "beam", elements: [`${b}u`], source: src(`${b}u`), lineLoad: { dead: klf(0.5), roofLive: klf(0.6) }, reactions: { i: { dead: R(0.5), roofLive: R(0.6) }, j: { dead: R(0.5), roofLive: R(0.6) } } });
  }
  return f;
}

describe("columns: one factoring rule per column, never a borrowed combination (finding 4)", () => {
  const move = { column: "C2", dx: 1, dy: 0 };
  const roof = (combination?: string): CalcFact => ({
    id: "C2u#1", kind: "column", elements: ["C2u"], source: src("c2u"), axial: kip(80), utilisation: 0.5, ...(combination ? { combination } : {}),
  });
  const run = (facts: CalcFact[]) => impact({ graph: twoStorey(), graphSha256: GRAPH_SHA, move, facts: [...beamFacts(), ...facts] });

  it("a floor column without a calc row does not take the roof column's 1.2D + 0.5L + 1.6Lr", () => {
    const withRoofCombo = changesOf(run([roof("1.2D+0.5L+1.6Lr")]), "C2", "column_load");
    const noRoofRow = changesOf(run([]), "C2", "column_load");
    // rejects: the floor column factored by the roof column's combination (0.5 on its live-load change)
    // and its load before = the roof column's stated Pu + its own storey under another combination
    expect(withRoofCombo).toHaveLength(1);
    expect(withRoofCombo[0]!.before.value).toBeCloseTo(noRoofRow[0]!.before.value, 9);
    expect(withRoofCombo[0]!.after.value).toBeCloseTo(noRoofRow[0]!.after.value, 9);
  });

  it("a column's own stated combination factors both its load before and its change, and says so", () => {
    const r = run([{ id: "C2#1", kind: "column", elements: ["C2"], source: src("c2"), utilisation: 0.6, combination: "1.2D+1.6L+0.5Lr" }]);
    expect(r.estimates!.C2!.scaledBy).toMatch(/factored 1\.2D\+1\.6L\+0\.5Lr \(the calc's governing combination\)/);
    const none = run([{ id: "C2#1", kind: "column", elements: ["C2"], source: src("c2"), utilisation: 0.6 }]);
    expect(none.estimates!.C2!.scaledBy).toMatch(/governing combination of LC1-LC3 before \(LC\d\) and after \(LC\d\) - no combination stated/);
    expect(none.estimates!.C2!.method).toBe("estimate");
  });

  it("a member carrying only the column above (a pier) has that column's factored load exactly", () => {
    const g = twoStorey();
    // C2 becomes a pier-like member: no framing of its own
    g.edges = g.edges.filter((e) => !["K-G2-i", "K-E1-j"].includes(e.a));
    const r = impact({ graph: g, graphSha256: GRAPH_SHA, move: { column: "C2u", dx: 1, dy: 0 }, facts: [...beamFacts(), roof("1.2D+0.5L+1.6Lr")] });
    const up = changesOf(r, "C2u", "column_load")[0]!;
    const pier = changesOf(r, "C2", "column_load")[0]!;
    expect(pier.before.value).toBeCloseTo(up.before.value, 9);
    expect(pier.after.value).toBeCloseTo(up.after.value, 9);
  });
});

describe("a cycle among stacked columns is reported, never a crash (finding 6)", () => {
  it("C2 <-> C2u", () => {
    // rejects: TypeError (the cycle's members appended to the order, then read before they were computed)
    const r = impact({ graph: twoStorey({ cycle: true }), graphSha256: GRAPH_SHA, move: { column: "C1", dx: 1, dy: 0 } });
    expect(r.notes.some((n) => /support cycle among the columns C2, C2u/.test(n))).toBe(true);
    expect(changesOf(r, "C2", "column_load")).toHaveLength(0);
  });
});

describe("walls and two-path footings (finding 7)", () => {
  it("a column on a wall does not copy its change to every footing under the wall", () => {
    const r = impact({ graph: twoStorey({ wall: true }), graphSha256: GRAPH_SHA, move: { column: "C1", dx: 1, dy: 0 } });
    // rejects: FA and FB each with the column's full change
    expect(changesOf(r, "FA", "footing_load")).toHaveLength(0);
    expect(changesOf(r, "FB", "footing_load")).toHaveLength(0);
    expect(r.topological.some((t) => t.element === "W")).toBe(true);
    expect(r.notes.some((n) => /W: column\(s\) bear on this wall/.test(n))).toBe(true);
  });

  it("an upper column bearing on the lower one AND on the footing is counted once", () => {
    const one = impact({ graph: twoStorey(), graphSha256: GRAPH_SHA, move: { column: "C1", dx: 1, dy: 0 } });
    const two = impact({ graph: twoStorey({ upperOnFooting: true }), graphSha256: GRAPH_SHA, move: { column: "C1", dx: 1, dy: 0 } });
    // rejects: the upper column's change added to the footing again on top of the lower column's (which includes it)
    expect(delta(two, "F2", "footing_load")).toBeCloseTo(delta(one, "F2", "footing_load"), 9);
    expect(changesOf(two, "F2", "footing_load")[0]!.before.value).toBeCloseTo(changesOf(one, "F2", "footing_load")[0]!.before.value, 9);
  });
});

describe("footing clash on the same basis as the required width (finding 9)", () => {
  // F2: stated width 6 ft, modelled 5 ft square; C2 moved 8.65 m towards F5 (1 m square at x = 20 m)
  const graph = () => {
    const nodes: ElementNode[] = [];
    const edges: GraphEdge[] = [];
    for (const [c, x, y, h] of [["C1", 0, 0, 0.5], ["C2", 10, 0, 2.5 * FT], ["C3", 0, 8, 0.5], ["C4", 10, 8, 0.5], ["C5", 20, 0, 0.5]] as const) {
      nodes.push(line(c, "column", [x, y, 0], [x, y, 3], "L0"), box(`F${c.slice(1)}`, "footing", [x, y, -0.3], [h, h, 0.3]));
      edges.push(sup(c, `F${c.slice(1)}`));
    }
    beam(nodes, edges, "G1", [0, 0.1, 3], [0, 7.9, 3], "C1", "C3", "L1");
    beam(nodes, edges, "G2", [10, 0.1, 3], [10, 7.9, 3], "C2", "C4", "L1");
    beam(nodes, edges, "E1", [0.1, 0, 3], [9.9, 0, 3], "C1", "C2", "L1");
    beam(nodes, edges, "E3", [10.1, 0, 3], [19.9, 0, 3], "C2", "C5", "L1");
    return graphOf([{ id: "L0", name: "Ground", elevation: 0 }, { id: "L1", name: "Level 1", elevation: 3 }], nodes, edges);
  };
  const run = (service: number) =>
    impact({
      graph: graph(), graphSha256: GRAPH_SHA, move: { column: "C2", dx: 8.65, dy: 0 },
      facts: [
        { id: "E1#1", kind: "beam", elements: ["E1"], source: src("e1"), lineLoad: { dead: klf(1) } },
        { id: "E3#1", kind: "beam", elements: ["E3"], source: src("e3"), lineLoad: { dead: klf(1) } },
        { id: "F2#1", kind: "footing", elements: ["F2"], source: src("f2"), serviceLoad: kip(service), allowableBearing: { value: 4, unit: "ksf" }, width: { value: 6, unit: "ft" } },
      ],
    });

  it("a footing that needs exactly its stated width does not grow", () => {
    const r = run(140);
    expect(r.estimates!.F2!.requiredWidth).toEqual({ value: 6, unit: "ft" });
    // rejects: a clash with F5 from the footing grown by 6 / 5 (required width over the model's 5 ft side)
    expect(r.clashes).toEqual([]);
  });

  it("a footing that needs more than its stated width grows from it and can clash", () => {
    const r = run(180);
    expect(r.estimates!.F2!.requiredWidth).toEqual({ value: 7, unit: "ft" });
    expect(r.clashes).toEqual([{ a: "F2", b: "F5", kind: "footing-footing" }]);
  });
});
