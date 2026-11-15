import { describe, expect, it } from "vitest";
import type { ElementNode, GraphEdge, SerializedElementGraph } from "@unloaded/element-graph";
import { buildModel, impact, solveSpan, UnknownColumn, type CalcFact } from "../src/index.ts";

// A one-level frame (metres, Z up), the way Carl's graph stores it: columns C1..C5, girders G1 (C1-C3)
// and G2 (C2-C4) along y, edge beams E1 (C1-C2), E2 (C3-C4), E3 (C2-C5) along x, infill beam B1 from G1
// to G2 at y = 4. Each beam end goes through its own connection node; physical axes stop 0.1 m short of
// the support (as an IFC member stops at the face). Footings under every column.
const Z = 3;
type V3 = [number, number, number];

function node(id: string, kind: string, extra: Partial<ElementNode> = {}): ElementNode {
  return { id, kind, name: id, params: { "Pset_Test.Secret": `${id}-calc-records` }, source: { format: "test" }, tags: {}, links: [], ...extra };
}
function line(id: string, kind: string, a: V3, b: V3, extra: Partial<ElementNode> = {}): ElementNode {
  const min = [0, 1, 2].map((k) => Math.min(a[k]!, b[k]!) - 0.05) as V3;
  const max = [0, 1, 2].map((k) => Math.max(a[k]!, b[k]!) + 0.05) as V3;
  return node(id, kind, { levelId: kind === "column" ? "L0" : "L1", geometry: { bbox: { min, max }, axis: { start: a, end: b } }, ...extra });
}
function box(id: string, kind: string, c: V3, half: number, extra: Partial<ElementNode> = {}): ElementNode {
  return node(id, kind, {
    levelId: "L1",
    geometry: { bbox: { min: [c[0] - half, c[1] - half, c[2] - half], max: [c[0] + half, c[1] + half, c[2] + half] } },
    ...extra,
  });
}
const sup = (a: string, b: string): GraphEdge => ({ id: `supports:${a}->${b}`, kind: "supports", a, b, directed: true, evidence: [] });

function frame(): SerializedElementGraph {
  const cols: Record<string, [number, number]> = { C1: [0, 0], C2: [10, 0], C3: [0, 8], C4: [10, 8], C5: [20, 0] };
  const nodes: ElementNode[] = [];
  const edges: GraphEdge[] = [];
  for (const [c, [x, y]] of Object.entries(cols)) {
    nodes.push(line(c, "column", [x, y, 0], [x, y, Z]));
    nodes.push(node(`F${c.slice(1)}`, "footing", { levelId: "L0", geometry: { bbox: { min: [x - 0.5, y - 0.5, -0.6], max: [x + 0.5, y + 0.5, 0] } } }));
    edges.push(sup(c, `F${c.slice(1)}`));
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
    nodes.push(line(id, "beam", a, b));
    for (const [end, p, s] of [["i", a, si], ["j", b, sj]] as const) {
      const k = `K-${id}-${end}`;
      nodes.push(box(k, "connection", p, 0.05));
      edges.push(sup(id, k), sup(k, s));
    }
  }
  return {
    format: "unloaded.element-graph",
    version: 1,
    meta: null,
    levels: [
      { id: "L0", name: "Ground", elevation: 0 },
      { id: "L1", name: "Level 1", elevation: Z },
    ],
    nodes,
    edges,
  };
}

const b1Fact: CalcFact = {
  id: "B1#row1",
  kind: "beam",
  elements: ["B1"],
  source: { calcKey: "b1-floor-framing", page: 3, rects: [[10, 20, 300, 30]] },
  utilisation: 0.5,
  lineLoad: { dead: 1, live: 0, roofLive: 0, unit: "klf" },
  checks: [{ mode: "flexure", utilisation: 0.5 }],
};

describe("statics", () => {
  it("matches closed forms for a uniform and a point load", () => {
    const u = solveSpan(10, [2, 0, 0], [], false);
    expect(u.mu).toBeCloseTo((1.4 * 2 * 100) / 8, 6);
    expect(u.vu).toBeCloseTo((1.4 * 2 * 10) / 2, 6);
    expect(u.dTotal / ((5 * 2 * 10 ** 4) / 384)).toBeCloseTo(1, 3);
    const p = solveSpan(10, [0, 0, 0], [[5, [4, 0, 0]]], false);
    expect(p.mu).toBeCloseTo((1.4 * 4 * 10) / 4, 6);
    expect(p.dTotal / ((4 * 10 ** 3) / 48)).toBeCloseTo(1, 3);
    expect(p.lb).toBeCloseTo(5, 9);
  });
});

describe("model from the element graph", () => {
  it("resolves supports through connection nodes and projects spans onto them", () => {
    const m = buildModel(frame());
    const b1 = m.members.get("B1")!;
    expect(b1.sup).toEqual({ i: "G1", j: "G2" });
    expect(Math.hypot(b1.p2[0] - b1.p1[0], b1.p2[1] - b1.p1[1])).toBeCloseTo(10, 9);
    const g1 = m.members.get("G1")!;
    expect(Math.hypot(g1.p2[0] - g1.p1[0], g1.p2[1] - g1.p1[1])).toBeCloseTo(8, 9);
    expect(m.carried.get("C2")!.map(([x]) => x).sort()).toEqual(["E1", "E3", "G2"]);
  });
});

describe("impact without calc facts", () => {
  const r = impact({ graph: frame(), move: { column: "C2", dx: 1, dy: 0 } });

  it("walks the path: moved framing, re-spanned infill, connections, foundation", () => {
    const ids = r.topological.map((t) => t.element);
    for (const e of ["C2", "F2", "E1", "E3", "G2", "B1", "K-B1-j"]) expect(ids).toContain(e);
    const g = r.geometry.find((x) => x.element === "B1")!;
    expect(g.after.p2[0]).toBeCloseTo(10.5, 9);
  });

  it("screens on geometry: the infill beam's moment grows by (10.5 / 10)^2", () => {
    const s = r.screened.find((x) => x.element === "B1")!;
    expect(s.governing?.quantity).toBe("moment");
    expect(s.governing?.ratio).toBeCloseTo(1.1025, 6);
    expect(s.governing?.basis).toBe("unit area load");
  });

  it("leaves every calc-dependent field out", () => {
    expect(r.estimates).toBeUndefined();
    expect(r.health).toBeUndefined();
    expect(r.stale).toBeUndefined();
    expect(r.staleRows).toBeUndefined();
  });

  it("never reads params: clearing them changes nothing", () => {
    const g = frame();
    for (const n of g.nodes) n.params = {};
    expect(impact({ graph: g, move: { column: "C2", dx: 1, dy: 0 } })).toEqual(r);
  });

  it("refuses an element that is not a column", () => {
    expect(() => impact({ graph: frame(), move: { column: "B1", dx: 1, dy: 0 } })).toThrow(UnknownColumn);
  });

  it("removal merges the collinear pair with the shortest span into a transfer member", () => {
    const rr = impact({ graph: frame(), move: { column: "C2", remove: true } });
    expect(rr.notes.some((n) => n.includes("E1") && n.includes("E3") && n.includes("transfer"))).toBe(true);
    const g2 = rr.topological.find((t) => t.element === "G2")!;
    expect(g2.reasons.some((x) => x.includes("transfer member"))).toBe(true);
    expect(rr.geometry).toEqual([]);
  });

  it("links alone give stale calcs (no rows, no estimates)", () => {
    const rl = impact({ graph: frame(), move: { column: "C2", dx: 1, dy: 0 }, links: [{ global_id: "B1", calc_key: "b1-calc" }, { global_id: "C5", calc_key: "far" }] });
    expect(rl.stale?.map((s) => s.calcKey)).toEqual(["b1-calc"]);
    expect(rl.stale?.[0]?.screened).toBe(true);
    expect(rl.staleRows).toBeUndefined();
    expect(rl.estimates).toBeUndefined();
  });
});

describe("impact with calc facts", () => {
  const r = impact({ graph: frame(), move: { column: "C2", dx: 1, dy: 0 }, facts: [b1Fact] });

  it("estimates utilisation only where a calc states one, labelled as an estimate with its scaling", () => {
    const e = r.estimates!.B1!;
    expect(e.method).toBe("estimate");
    expect(e.utilisationBefore).toBe(0.5);
    expect(e.utilisationAfter).toBeCloseTo(0.551, 3);
    expect(e.scaledBy).toMatch(/flexure/);
    expect(e.source.calcKey).toBe("b1-floor-framing");
    expect(Object.keys(r.estimates!)).toEqual(["B1"]);
  });

  it("returns the calc row as stale and screened, and a health band", () => {
    expect(r.staleRows).toEqual([{ fact: "B1#row1", calcKey: "b1-floor-framing", screened: true, elements: ["B1"] }]);
    expect(r.stale?.[0]?.calcKey).toBe("b1-floor-framing");
    expect(r.health?.band).toBe("easy");
    expect(r.health?.method).toBe("estimate");
  });

  it("gives no estimate for a row that states no utilisation", () => {
    const { utilisation: _u, checks: _c, ...noUc } = b1Fact;
    const r2 = impact({ graph: frame(), move: { column: "C2", dx: 1, dy: 0 }, facts: [noUc] });
    expect(r2.estimates).toEqual({});
  });

  it("puts a column on a lateral frame when a lateral calc row on it names the frame", () => {
    const lat: CalcFact = { id: "C2#frame", kind: "column", role: "lateral", group: "SMF-1", elements: ["C2", "C5"], source: { calcKey: "smf", page: 9, rects: [] }, utilisation: 0.4 };
    const r3 = impact({ graph: frame(), move: { column: "C2", dx: 1, dy: 0 }, facts: [b1Fact, lat] });
    expect(r3.lateral.some((l) => l.includes("SMF-1"))).toBe(true);
    expect(r3.topological.map((t) => t.element)).toContain("C5");
    expect(r3.health?.band).toBe("hard");
  });
});
