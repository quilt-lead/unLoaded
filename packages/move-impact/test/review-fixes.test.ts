/**
 * Regression tests for the 2026-11-14 review of move-impact: load changes accumulated down a column
 * stack, footing bearing on the plan area / stated width, the removal branch's reaction basis, and the
 * transfer-member sizing note. Each test names the wrong behaviour it rejects.
 */
import { describe, expect, it } from "vitest";
import type { ElementNode, GraphEdge, SerializedElementGraph } from "@unloaded/element-graph";
import { impact, type CalcFact, type ImpactResult } from "../src/index.ts";

const GRAPH_SHA = "a".repeat(64);
const DOC_SHA = "b".repeat(64);
const FT = 0.3048;
const H = 3; // storey height, m
type V3 = [number, number, number];

function node(id: string, kind: string, extra: Partial<ElementNode> = {}): ElementNode {
  return { id, kind, name: id, params: {}, source: { format: "test" }, tags: {}, links: [], ...extra };
}
function line(id: string, kind: string, a: V3, b: V3, levelId: string, extra: Partial<ElementNode> = {}): ElementNode {
  const min = [0, 1, 2].map((k) => Math.min(a[k]!, b[k]!) - 0.05) as V3;
  const max = [0, 1, 2].map((k) => Math.max(a[k]!, b[k]!) + 0.05) as V3;
  return node(id, kind, { levelId, geometry: { bbox: { min, max }, axis: { start: a, end: b } }, ...extra });
}
const sup = (a: string, b: string): GraphEdge => ({ id: `supports:${a}->${b}`, kind: "supports", a, b, directed: true, evidence: [] });

/**
 * The impact.test.ts frame (columns C1..C5, girders G1 / G2, edge beams E1 / E2 / E3, infill B1 on the
 * girders, footings F1..F5), one column element per storey as an IFC with storey splices writes it:
 * storey 1 uses the plain ids, storey 2 the same ids + "u". The upper column bears on the lower one
 * (`supports` C1u -> C1, the element graph's column-base rule); the lower one on its footing.
 * `footing` overrides a footing's half widths (m).
 */
function building(storeys: 1 | 2, footing: Record<string, [number, number]> = {}): SerializedElementGraph {
  const cols: Record<string, [number, number]> = { C1: [0, 0], C2: [10, 0], C3: [0, 8], C4: [10, 8], C5: [20, 0] };
  const nodes: ElementNode[] = [];
  const edges: GraphEdge[] = [];
  const levels = [{ id: "L0", name: "Ground", elevation: 0 }];
  for (let s = 1; s <= storeys; s++) {
    const sfx = s === 1 ? "" : "u";
    const Z = H * s;
    const lv = `L${s}`;
    levels.push({ id: lv, name: `Level ${s}`, elevation: Z });
    for (const [c, [x, y]] of Object.entries(cols)) {
      nodes.push(line(c + sfx, "column", [x, y, Z - H], [x, y, Z], `L${s - 1}`));
      if (s === 1) {
        const [hx, hy] = footing[`F${c.slice(1)}`] ?? [0.5, 0.5];
        nodes.push(node(`F${c.slice(1)}`, "footing", { levelId: "L0", geometry: { bbox: { min: [x - hx, y - hy, -0.6], max: [x + hx, y + hy, 0] } } }));
        edges.push(sup(c, `F${c.slice(1)}`));
      } else edges.push(sup(c + sfx, c));
    }
    const beams: [string, V3, V3, string, string][] = [
      ["G1", [0, 0.1, Z], [0, 7.9, Z], "C1", "C3"],
      ["G2", [10, 0.1, Z], [10, 7.9, Z], "C2", "C4"],
      ["E1", [0.1, 0, Z], [9.9, 0, Z], "C1", "C2"],
      ["E2", [0.1, 8, Z], [9.9, 8, Z], "C3", "C4"],
      ["E3", [10.1, 0, Z], [19.9, 0, Z], "C2", "C5"],
      ["B1", [0.1, 4, Z], [9.9, 4, Z], "G1", "G2"],
    ];
    for (const [id, a, b, si, sj] of beams) {
      const sp = (x: string) => (x.startsWith("C") || x.startsWith("G") ? x + sfx : x);
      nodes.push(line(id + sfx, "beam", a, b, lv));
      for (const [end, p, sx] of [["i", a, si], ["j", b, sj]] as const) {
        const k = `K-${id}${sfx}-${end}`;
        nodes.push(node(k, "connection", { levelId: lv, geometry: { bbox: { min: [p[0] - 0.05, p[1] - 0.05, p[2] - 0.05], max: [p[0] + 0.05, p[1] + 0.05, p[2] + 0.05] } } }));
        edges.push(sup(id + sfx, k), sup(k, sp(sx)));
      }
    }
  }
  return { format: "unloaded.element-graph", version: 1, meta: null, levels, nodes, edges };
}

const src = (calcKey: string) => ({ calcKey, page: 1, rects: [], documentSha256: DOC_SHA });
const changesOf = (r: ImpactResult, e: string, quantity: string) =>
  (r.screened.find((x) => x.element === e)?.changes ?? []).filter((c) => c.quantity === quantity);

describe("load changes accumulate down a column stack (finding 1)", () => {
  const move = { column: "C2", dx: 1, dy: 0 };
  const one = impact({ graph: building(1), graphSha256: GRAPH_SHA, move });
  const two = impact({ graph: building(2), graphSha256: GRAPH_SHA, move });

  it("the lower column carries its own storey plus everything from the column above, in ONE column_load change", () => {
    const [single] = changesOf(one, "C2", "column_load");
    const lower = changesOf(two, "C2", "column_load");
    // rejects: two column_load changes on the lower column (its own + the upper column's attached to it),
    // the first of which (its own storey only) decided the screen
    expect(lower).toHaveLength(1);
    expect(lower[0]!.before.value).toBeCloseTo(2 * single!.before.value, 9);
    expect(lower[0]!.after.value - lower[0]!.before.value).toBeCloseTo(2 * (single!.after.value - single!.before.value), 9);
    expect(Math.abs(single!.after.value - single!.before.value)).toBeGreaterThan(0.1);
  });

  it("the upper column carries only its own storey", () => {
    const [single] = changesOf(one, "C2", "column_load");
    const [upper] = changesOf(two, "C2u", "column_load");
    expect(upper!.before.value).toBeCloseTo(single!.before.value, 9);
    expect(upper!.after.value).toBeCloseTo(single!.after.value, 9);
  });

  it("the footing takes the whole stack, once, from the bottom column", () => {
    const [single] = changesOf(one, "F2", "footing_load");
    const f = changesOf(two, "F2", "footing_load");
    // rejects: one footing_load change per storey column (each with one storey's load), the first deciding
    expect(f).toHaveLength(1);
    expect(f[0]!.before.value).toBeCloseTo(2 * single!.before.value, 9);
    expect(f[0]!.after.value - f[0]!.before.value).toBeCloseTo(2 * (single!.after.value - single!.before.value), 9);
  });

  it("a footing estimate rests on the whole stack's change", () => {
    const facts = (graph: SerializedElementGraph): CalcFact[] => [
      { id: "G2#1", kind: "beam", elements: ["G2", ...(graph.nodes.some((n) => n.id === "G2u") ? ["G2u"] : [])], source: src("g2"), lineLoad: { dead: { value: 10, unit: "klf" } } },
      { id: "F4#1", kind: "footing", elements: ["F4"], source: src("f4"), serviceLoad: { value: 100, unit: "kip" }, allowableBearing: { value: 4, unit: "ksf" } },
    ];
    const e1 = impact({ graph: building(1), graphSha256: GRAPH_SHA, move, facts: facts(building(1)) }).estimates!.F4!;
    const e2 = impact({ graph: building(2), graphSha256: GRAPH_SHA, move, facts: facts(building(2)) }).estimates!.F4!;
    const ds = (e: { scaledBy: string }) => Number(/reaction deltas (-?[\d.]+) kip/.exec(e.scaledBy)![1]);
    // rejects: the footing estimate set once per storey column, the last one (one storey's delta) kept
    expect(ds(e1)).not.toBe(0);
    expect(ds(e2)).toBeCloseTo(2 * ds(e1), 1);
  });
});

describe("footing bearing uses the plan area or the stated width (finding 5)", () => {
  const move = { column: "C2", dx: 1, dy: 0 };
  const facts = (width?: number): CalcFact[] => [
    { id: "B1#1", kind: "beam", elements: ["B1"], source: src("b1"), lineLoad: { dead: { value: 1, unit: "klf" } } },
    { id: "G2#1", kind: "beam", elements: ["G2"], source: src("g2"), lineLoad: { dead: { value: 1, unit: "klf" } } },
    {
      id: "F4#1", kind: "footing", elements: ["F4"], source: src("f4"), serviceLoad: { value: 100, unit: "kip" }, allowableBearing: { value: 4, unit: "ksf" },
      ...(width ? { width: { value: width, unit: "ft" } } : {}),
    },
  ];
  const run = (half: [number, number], width?: number) =>
    impact({ graph: building(1, { F4: half }), graphSha256: GRAPH_SHA, move, facts: facts(width) }).estimates!.F4!;

  it("a 1 x 2 m footing is checked on its 1 x 2 m area, not as 1 x 1 m", () => {
    const square = run([0.5, 0.5]);
    const rect = run([0.5, 1.0]);
    // rejects: equal utilisations (both checked as min(bx, by) squared)
    expect(square.utilisationAfter! / rect.utilisationAfter!).toBeCloseTo(2, 2);
    expect(rect.scaledBy).toMatch(/model's 3\.28 x 6\.56 ft plan/);
    expect(rect.method).toBe("estimate");
  });

  it("a stated footing width is used as stated", () => {
    const model = run([0.5, 0.5]);
    const stated = run([0.5, 0.5], 5);
    // rejects: the stated 5 ft width ignored (bearing over the model's 3.28 ft square)
    expect(stated.utilisationAfter! / model.utilisationAfter!).toBeCloseTo((1 / FT) ** 2 / 25, 2);
    expect(stated.scaledBy).toMatch(/stated width 5 ft/);
  });
});

describe("removal: transfer and old reactions on the same basis (finding 6)", () => {
  // E1 and E3 (W36X300, self weight 0.3 klf) merge into a transfer member when C2 goes; C1 is a far support
  const graph = () => {
    const g = building(1);
    for (const n of g.nodes) if (n.id === "E1" || n.id === "E3") n.profile = "W36X300";
    return g;
  };
  const facts = (withSelfWeight: boolean): CalcFact[] => {
    const L = 10 / FT; // analytical span, ft
    const R = 0.5 * (1 + (withSelfWeight ? 0.3 : 0)) * L;
    const beam = (id: string): CalcFact => ({
      id: `${id}#1`, kind: "beam", elements: [id], source: src(id), lineLoad: { dead: { value: 1, unit: "klf" } },
      reactions: { i: { dead: { value: R, unit: "kip" } }, j: { dead: { value: R, unit: "kip" } } },
    });
    return [beam("E1"), beam("E3"), { id: "C1#1", kind: "column", elements: ["C1"], source: src("c1"), axial: { value: 100, unit: "kip" }, utilisation: 0.5 }];
  };
  const est = (withSelfWeight: boolean) =>
    impact({ graph: graph(), graphSha256: GRAPH_SHA, move: { column: "C2", remove: true }, facts: facts(withSelfWeight) }).estimates!.C1!;

  it("the far column's change does not depend on whether the stated reaction includes self weight", () => {
    // rejects: a change larger by the self weight reaction (transfer solve with self weight minus a
    // stated reaction without it) when the calc's reactions leave self weight out
    expect(est(false).utilisationAfter).toBe(est(true).utilisationAfter);
    expect(est(false).utilisationAfter).toBeGreaterThan(0.5);
  });
});

describe("transfer member sizing note (finding 10)", () => {
  const move = { column: "C2", remove: true } as const;
  it("says no section table only when none was supplied", () => {
    const without = impact({ graph: building(1), graphSha256: GRAPH_SHA, move });
    const withTable = impact({ graph: building(1), graphSha256: GRAPH_SHA, move, sections: { W18X35: { unit: "in", d: 17.7, tf: 0.425 } } });
    expect(without.notes.some((n) => /required size not estimated - no section table supplied/.test(n))).toBe(true);
    // rejects: "no section table in the model" while a section table was supplied
    expect(withTable.notes.some((n) => /no section table/.test(n))).toBe(false);
    expect(withTable.notes.some((n) => /supplied section table covers only the model's profiles/.test(n))).toBe(true);
  });
});
