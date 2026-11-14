import { describe, expect, it } from "vitest";
import { ElementGraph, type GraphChange, type NodeInput } from "../src/index.ts";

const node = (id: string, kind = "beam"): NodeInput => ({ id, kind, params: {}, source: { format: "test" } });

function small(): ElementGraph {
  const g = new ElementGraph();
  g.batch(() => {
    g.addNode(node("A"));
    g.addNode(node("B", "column"));
    g.addNode(node("K", "connection"));
    g.addEdge({ kind: "connects", a: "A", b: "K" });
    g.addEdge({ kind: "supports", a: "A", b: "K" });
    g.addEdge({ kind: "supports", a: "K", b: "B" });
  });
  return g;
}

describe("ElementGraph mutations and events", () => {
  it("increments version once per mutation and once per batch", () => {
    const g = new ElementGraph();
    const changes: GraphChange[] = [];
    g.subscribe((c) => changes.push(c));
    expect(g.version).toBe(0);
    g.addNode(node("A"));
    expect(g.version).toBe(1);
    g.batch(() => {
      g.addNode(node("B"));
      g.addNode(node("C"));
      g.addEdge({ kind: "connects", a: "B", b: "C" });
    });
    expect(g.version).toBe(2);
    expect(changes).toHaveLength(2);
    expect(changes[1]).toMatchObject({ version: 2, nodesAdded: ["B", "C"], edgesAdded: ["connects:B|C"] });
  });

  it("getSnapshot is stable between changes", () => {
    const g = small();
    const s1 = g.getSnapshot();
    expect(g.getSnapshot()).toBe(s1);
    g.updateNode("A", { mark: "B101" });
    expect(g.getSnapshot()).not.toBe(s1);
  });

  it("updateNode replaces the object and reindexes kind", () => {
    const g = small();
    const before = g.getNode("A")!;
    const after = g.updateNode("A", { kind: "brace", tags: { reviewed: true } });
    expect(after).not.toBe(before);
    expect(g.nodesByKind("beam")).toHaveLength(0);
    expect(g.nodesByKind("brace").map((n) => n.id)).toEqual(["A"]);
    expect(g.lastChange?.nodesUpdated).toEqual(["A"]);
  });

  it("removeNode drops incident edges and reports them", () => {
    const g = small();
    let change: GraphChange | undefined;
    g.subscribe((c) => (change = c));
    expect(g.removeNode("K")).toBe(true);
    expect(g.edgeCount).toBe(0);
    expect(change!.nodesRemoved).toEqual(["K"]);
    expect(change!.edgesRemoved.sort()).toEqual(["connects:A|K", "supports:A->K", "supports:K->B"]);
    expect(g.edgesOf("A")).toEqual([]);
    expect(g.removeNode("K")).toBe(false);
  });

  it("add then remove inside a batch nets out", () => {
    const g = small();
    let change: GraphChange | undefined;
    g.subscribe((c) => (change = c));
    g.batch(() => {
      g.addNode(node("T"));
      g.removeNode("T");
      g.updateNode("A", { name: "x" });
    });
    expect(change!.nodesAdded).toEqual([]);
    expect(change!.nodesRemoved).toEqual([]);
    expect(change!.nodesUpdated).toEqual(["A"]);
  });

  it("unsubscribe stops notifications", () => {
    const g = small();
    let calls = 0;
    const off = g.subscribe(() => calls++);
    g.addNode(node("X"));
    off();
    g.addNode(node("Y"));
    expect(calls).toBe(1);
  });

  it("no-op batch emits nothing", () => {
    const g = small();
    let calls = 0;
    g.subscribe(() => calls++);
    const v = g.version;
    g.batch(() => {});
    g.addEdge({ kind: "connects", a: "A", b: "K" }); // duplicate, no new evidence
    expect(calls).toBe(0);
    expect(g.version).toBe(v);
  });

  it("throws on misuse", () => {
    const g = small();
    expect(() => g.addNode(node("A"))).toThrow(/duplicate/);
    expect(() => g.addEdge({ kind: "connects", a: "A", b: "nope" })).toThrow(/unknown endpoint/);
    expect(() => g.addEdge({ kind: "connects", a: "A", b: "A" })).toThrow(/self-loop/);
    expect(() => g.updateNode("nope", {})).toThrow(/unknown node/);
  });

  it("merges duplicate edges and keeps explicit evidence first", () => {
    const g = small();
    g.addEdge({ kind: "connects", a: "K", b: "A", evidence: { rule: "r1", source: "inferred" } });
    const e = g.addEdge({ kind: "connects", a: "A", b: "K", evidence: { rule: "ifc", source: "explicit" } });
    expect(e.id).toBe("connects:A|K");
    expect(e.evidence.map((x) => x.rule)).toEqual(["ifc", "r1"]);
    expect(g.edgeCount).toBe(3);
  });
});

describe("ElementGraph queries", () => {
  it("neighbours with direction and kind filters", () => {
    const g = small();
    expect(g.neighbours("K", { edgeKind: "supports", direction: "in" })).toEqual(["A"]);
    expect(g.neighbours("K", { edgeKind: "supports", direction: "out" })).toEqual(["B"]);
    expect(g.neighbours("K", { nodeKind: "column" })).toEqual(["B"]);
    expect(g.edgesOf("A", { kind: "connects" })).toHaveLength(1);
    expect(g.connectionsOf("A")).toEqual(["K"]);
    expect(g.membersOf("K").sort()).toEqual(["A", "B"]);
  });

  it("subgraph and connected components", () => {
    const g = small();
    g.addNode(node("Z"));
    const comps = g.connectedComponents();
    expect(comps).toHaveLength(2);
    expect(comps[0]!.sort()).toEqual(["A", "B", "K"]);
    const sub = g.subgraph(["A", "K"]);
    expect(sub.nodeCount).toBe(2);
    expect(sub.edges().map((e) => e.id).sort()).toEqual(["connects:A|K", "supports:A->K"]);
    expect(sub.version).toBe(0);
  });

  it("reports supports cycles without throwing", () => {
    const g = small();
    g.addEdge({ kind: "supports", a: "B", b: "A" });
    const cycles = g.findCycles();
    expect(cycles).toHaveLength(1);
    expect([...cycles[0]!].sort()).toEqual(["A", "B", "K"]);
    expect(g.findCycles("connects")).toEqual([]);
    expect(g.loadPathDown("A").size).toBe(3); // terminates on cycles
  });

  it("serialize round-trip is lossless", () => {
    const g = small();
    g.setLevel({ id: "L1", name: "One", elevation: 3 });
    g.updateNode("A", { tags: { ok: true }, links: [{ target: "calc-1", kind: "calc", data: { util: 0.8 } }] });
    const s = g.serialize();
    expect(s.format).toBe("unloaded.element-graph");
    expect(s.version).toBe(1);
    const back = ElementGraph.deserialize(s);
    expect(back.serialize()).toEqual(s);
    expect(() => ElementGraph.deserialize({ ...s, format: "x" as never })).toThrow();
  });
});
