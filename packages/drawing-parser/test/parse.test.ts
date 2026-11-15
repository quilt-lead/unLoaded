import { buildGraph } from "@unloaded/element-graph";
import { describe, expect, it } from "vitest";
import { validateModelInput } from "../../ifc-parser/test/validate.ts";
import { drawingParser, hasPdfHeader, parseDrawingPages, readSheets, type Occurrence } from "../src/index.ts";
import { details, framingPlan, page, schedule, titleBlock } from "./helpers.ts";

const FT = 0.3048;
const set = () => parseDrawingPages([framingPlan(), schedule(), details()]);
const byId = (m: ReturnType<typeof set>, id: string) => {
  const e = m.elements.find((x) => x.id === id);
  if (!e) throw new Error(`missing ${id}: ${m.elements.map((x) => x.id).join(", ")}`);
  return e;
};

describe("sheets", () => {
  it("reads sheet number (tallest title-block word), title, kind and level", () => {
    const [plan, sched, det] = readSheets([framingPlan(), schedule(), details()]);
    expect(plan).toMatchObject({ number: "S-201", title: "LEVEL 2 FRAMING PLAN", kind: "framing", level: "Level 2" });
    expect(plan!.cutoff).toBeLessThan(2006);
    expect(sched).toMatchObject({ number: "S-401", kind: "schedule" });
    expect(det).toMatchObject({ number: "S-501", kind: "details" });
  });

  it("skips pages without a sheet number, with a warning", () => {
    const m = parseDrawingPages([page(1, [])]);
    expect(m.elements).toEqual([]);
    expect(m.warnings.join("\n")).toMatch(/no sheet number/);
  });
});

describe("parseDrawingPages on a constructed mini set", () => {
  it("produces a valid ModelInput", () => {
    expect(validateModelInput(set())).toEqual([]);
  });

  it("is deterministic", () => {
    expect(JSON.stringify(set())).toBe(JSON.stringify(set()));
  });

  it("levels come from the stated elevations (schedule rows, T.O.S. note)", () => {
    expect(set().levels).toEqual([
      { id: "level-1", name: "Level 1", elevation: 0 },
      { id: "level-2", name: "Level 2", elevation: 14 * FT },
      { id: "roof", name: "Roof", elevation: 28 * FT },
    ]);
  });

  it("girders on grid lines get grid ids and exact grid positions, top of steel at the level", () => {
    const m = set();
    const g1 = byId(m, "beam:level-2:A..B:1"); // rotated tag beside line 1
    expect(g1).toMatchObject({ kind: "beam", profile: "W24X55", levelId: "level-2" });
    expect(g1.params["Drawing.Role"]).toBe("girder");
    expect(g1.params["Drawing.SFRS"]).toBe(true);
    expect(g1.params["Drawing.Studs"]).toBe(30);
    expect(g1.geometry!.axis!.start.slice(0, 2)).toEqual([0, 0]);
    expect(g1.geometry!.axis!.end.slice(0, 2)).toEqual([0, 9.144]);
    expect(g1.geometry!.bbox.max[2]).toBeCloseTo(14 * FT, 6);
    const gA = byId(m, "beam:level-2:1..2:A");
    expect(gA.profile).toBe("W21X44");
    expect(gA.params["Drawing.FrameSystem"]).toBe("SMF");
  });

  it("infill beams: ordinal id across the bay, size kept out of the id, position measured from the tag", () => {
    const b = byId(set(), "beam:level-2:1..2:A..B#1");
    expect(b.profile).toBe("W16X26");
    expect(b.params["Drawing.CamberIn"]).toBe(0.75);
    expect(b.geometry!.axis!.start[1]).toBeCloseTo(10 * FT, 2);
    expect(b.params["Drawing.GeometrySource"]).toBe("drawing-derived");
    expect(b.params["Drawing.ScaleSource"]).toBe("dimension strings");
    expect(Number(b.params["Drawing.PlanErrorM"])).toBeGreaterThan(0);
  });

  it("a resize keeps the id", () => {
    const resized = framingPlan();
    resized.words = resized.words.map((w) => (w.s === "W16X26" ? { ...w, s: "W18X35" } : w));
    const m = parseDrawingPages([resized, schedule(), details()]);
    expect(byId(m, "beam:level-2:1..2:A..B#1").profile).toBe("W18X35");
  });

  it("columns from schedule storeys: one element per storey segment, base plate from its row", () => {
    const m = set();
    const c = byId(m, "column:1/A:level-1..level-2");
    expect(c).toMatchObject({ kind: "column", profile: "W10X33", levelId: "level-1" });
    expect(c.params["Drawing.Storeys"]).toBe("Level 1 - Level 2");
    expect(c.geometry!.axis).toEqual({ start: [0, 0, 0], end: [0, 0, 14 * FT] });
    const u = byId(m, "column:1/A:level-2..roof");
    expect(u).toMatchObject({ kind: "column", profile: "W10X33", levelId: "level-2" });
    expect(u.geometry!.axis).toEqual({ start: [0, 0, 14 * FT], end: [0, 0, 28 * FT] });
    const bp = byId(m, "connection:base:1/A");
    expect(bp).toMatchObject({ kind: "connection", mark: "BP-1", levelId: "level-1" });
    expect(bp.params["Detail.Title"]).toBe("COLUMN BASE PLATE BP-1");
  });

  it("a detail callout becomes a connection at the nearest member end, with an explicit relation", () => {
    const m = set();
    const k = byId(m, "connection:beam:level-2:1..2:A..B#1@1");
    expect(k.mark).toBe("ST-3");
    expect(k.params["Detail.Ref"]).toBe("3/S-501");
    expect(k.params["Detail.Title"]).toBe("SINGLE-PLATE SHEAR TAB ST-3");
    const r = m.relations.find((x) => x.b === k.id || x.a === k.id)!;
    expect(r).toMatchObject({ kind: "connects", evidence: { rule: "drawing detail callout", source: "explicit" } });
    expect([r.a, r.b]).toContain("beam:level-2:1..2:A..B#1");
  });

  it("every element carries its printed occurrences (sheet, page, rect) for two-sided evidence", () => {
    const m = set();
    for (const e of m.elements) {
      const occ: Occurrence[] = JSON.parse(String(e.params["Drawing.Occurrences"]));
      expect(occ.length).toBe(e.params["Drawing.OccurrenceCount"]);
      expect(occ[0]).toMatchObject({ sheet: e.params["Drawing.Sheet"], page: e.params["Drawing.Page"] });
      expect(occ[0]!.rect).toHaveLength(4);
      expect(e.source.format).toBe("drawing");
    }
    const col: Occurrence[] = JSON.parse(String(byId(m, "column:1/A:level-1..level-2").params["Drawing.Occurrences"]));
    expect(col.map((o) => o.how)).toEqual(["schedule_row"]);
  });

  it("slab from the deck note, bearing on the beams in the graph", () => {
    const m = set();
    const s = byId(m, "slab:level-2");
    expect(s.params["Drawing.ThicknessIn"]).toBe(6.25);
    const { graph } = buildGraph(m);
    expect(graph.supportsOf("slab:level-2")).toContain("beam:level-2:1..2:A..B#1");
    // geometric connectivity is inferred by the graph, not emitted by the parser
    expect(m.relations.every((r) => r.evidence.rule !== "bbox contact")).toBe(true);
    expect(graph.supportsOf("beam:level-2:1..2:A")).toContain("column:1/A:level-1..level-2");
  });

  it("without a readable grid there is no geometry, and it says so", () => {
    const m = parseDrawingPages([page(1, titleBlock("S-201", "LEVEL 2 FRAMING PLAN"))]);
    expect(m.warnings.join("\n")).toMatch(/grid/);
  });
});

describe("drawingParser", () => {
  it("implements ModelParser for PDFs", () => {
    expect(drawingParser.id).toBe("drawing");
    expect(drawingParser.canParse("plans.PDF")).toBe(true);
    expect(drawingParser.canParse("model.ifc")).toBe(false);
    expect(hasPdfHeader(new TextEncoder().encode("%PDF-1.7"))).toBe(true);
    expect(drawingParser.canParse("x.bin", new TextEncoder().encode("ISO-10303-21;"))).toBe(false);
  });
});
