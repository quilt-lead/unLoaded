/**
 * Regression tests for the round-2 review of drawing-parser (2026-11-14): columns as storey segments,
 * deck notes with abbreviations, levels ordered by stated elevation, and the grid's scale (plan title,
 * per-axis scale, dimension tolerance). Each test names the wrong behaviour it rejects. Pages are built
 * in code (helpers.ts), no PDF.
 */
import { describe, expect, it } from "vitest";
import { buildGraph } from "@unloaded/element-graph";
import { DEFAULT_PROFILE, parseDrawingPages, phrases, readSheets, type DrawingWord } from "../src/index.ts";
import { buildLevels, levelOrder } from "../src/assemble.ts";
import { emptyFacts, type Facts } from "../src/facts.ts";
import { agrees, buildingGrid, calibrate, planGrid, planTitle } from "../src/grid.ts";
import { deckThickness, levelName, LEVEL_IN_TEXT, sentenceEnd } from "../src/text.ts";
import { centred, details, framingPlan, page, run, schedule, titleBlock } from "./helpers.ts";

const FT = 0.3048;

describe("columns: one element per storey segment, id = position + storey (finding 2)", () => {
  const resized = () => {
    const s = schedule();
    s.words = s.words.map((w) => (w.s === "W10X33" && w.y0 < 200 ? { ...w, s: "W10X39" } : w)); // L2 - ROOF storey only
    return s;
  };

  it("an upper storey's size and level are on its own element, where a calc row for that storey can match", () => {
    const m = parseDrawingPages([framingPlan(), resized(), details()]);
    const cols = m.elements.filter((e) => e.kind === "column").map((e) => [e.id, e.profile, e.levelId, e.params["Drawing.Storeys"]]);
    // rejects: one column:1/A with profile W10X33 (lowest storey) and level-1 for both storeys
    expect(cols).toEqual([
      ["column:1/A:level-1..level-2", "W10X33", "level-1", "Level 1 - Level 2"],
      ["column:1/A:level-2..roof", "W10X39", "level-2", "Level 2 - Roof"],
    ]);
    expect(m.elements.some((e) => "Drawing.StoreySizes" in e.params)).toBe(false);
  });

  it("the base plate belongs to the lowest segment; the upper segment bears on the lower in the graph", () => {
    const m = parseDrawingPages([framingPlan(), schedule(), details()]);
    expect(m.relations.map((r) => `${r.a}|${r.b}`)).toContain("column:1/A:level-1..level-2|connection:base:1/A");
    const bp = m.elements.find((e) => e.id === "connection:base:1/A")!;
    expect(bp.params["Drawing.Member"]).toBe("column:1/A:level-1..level-2");
    const { graph } = buildGraph(m);
    expect(graph.supportsOf("column:1/A:level-2..roof")).toContain("column:1/A:level-1..level-2");
  });

  it("a storey range stated once (schedule tier L1 - ROOF) stays one element", () => {
    const s = schedule();
    s.words = s.words.filter((w) => !(w.y0 > 230 && w.y0 < 252)); // drop the "L1 - L2" row and its cell
    s.words = s.words.map((w) => (w.s === "L2" && w.y0 < 200 ? { ...w, s: "L1" } : w)); // "L2 - ROOF" -> "L1 - ROOF"
    const cols = parseDrawingPages([framingPlan(), s, details()]).elements.filter((e) => e.kind === "column").map((e) => e.id);
    expect(cols).toEqual(["column:1/A:level-1..roof"]);
  });
});

describe("deck notes with abbreviations (finding 3)", () => {
  it("a full stop after an abbreviation does not end the value's clause", () => {
    // rejects: undefined for all three (the context was cut at the first ". ")
    expect(deckThickness(`ROOF DECK: 1-1/2" TYPE B 20 GA. DECK`)?.thicknessIn).toBe(1.5);
    expect(deckThickness(`FLOOR DECK: 3" COMP. DECK W/ 3-1/4" L.W. CONC. TOPPING`)).toEqual({ thicknessIn: 6.25, rule: "deck depth + concrete above the deck (deck note)" });
    expect(deckThickness(`5" N.W. CONC. SLAB ON 2" COMPOSITE DECK`)?.thicknessIn).toBe(5);
  });

  it("round 1's rules hold: TOTAL with a spaced fraction, never the rib depth alone", () => {
    expect(deckThickness(`FLOOR DECK: 3" COMPOSITE DECK, 6 1/4" TOTAL.`)?.thicknessIn).toBe(6.25);
    expect(deckThickness(`FLOOR DECK: 3" COMPOSITE DECK W/ NW CONCRETE FILL`)).toBeUndefined();
    expect(deckThickness(`FLOOR DECK: 3" COMP. DECK W/ NW CONC. FILL`)).toBeUndefined();
  });

  it("a real sentence end still ends the clause", () => {
    const t = `1-1/2" ROOF DECK. 4" CONC. PAD AT UNITS`;
    expect(sentenceEnd(t, 0)).toBe(t.indexOf("DECK.") + 4);
    // rejects: 5.5 in (the pad's 4" concrete, another sentence, added to the deck)
    expect(deckThickness(`ROOF DECK: ${t}`)).toEqual({ thicknessIn: 1.5, rule: "bare deck: deck depth (no concrete in the deck's sentence)" });
  });
});

describe("levels: ordered by stated elevation (finding 5)", () => {
  const facts = (stated: Record<string, number>, names: string[]): Facts => {
    const f = emptyFacts();
    const occ = { file: "t.pdf", sheet: "S-1", page: 1, rect: [0, 0, 1, 1] as [number, number, number, number], how: "note" as const, text: "" };
    for (const [level, ft] of Object.entries(stated)) f.levels.push({ level, ft, how: "test", occ });
    for (let i = 0; i + 1 < names.length; i++) f.tiers.push({ at: "1/A", lo: names[i]!, hi: names[i + 1]!, occ, rule: "test" });
    return f;
  };

  it("an unstated Level 2 sits between Level 1 and Level 3, not above a mezzanine stated at 22 ft", () => {
    const lv = buildLevels(facts({ "Level 1": 0, Mezzanine: 22, "Level 3": 28 }, ["Level 1", "Level 2", "Level 3"]), [], []);
    // rejects: Level 2 at 25 ft (evenly between the mezzanine, by name below it, and Level 3)
    expect(lv.get("Level 2")!.ft).toBeCloseTo(14, 9);
    expect([...lv.keys()]).toEqual(["Level 1", "Level 2", "Mezzanine", "Level 3"]);
  });

  it("an unstated foundation is 3 ft below the lowest level by elevation, not by name", () => {
    const lv = buildLevels(facts({ "Level 1": 0, Mezzanine: -6 }, ["Foundation", "Level 1"]), [], []);
    // rejects: -3 ft (3 ft below Level 1, the lowest by name) - above the mezzanine at -6 ft
    expect(lv.get("Foundation")!.ft).toBe(-9);
  });

  it("MEZZANINE 2 and PENTHOUSE ROOF are read as such", () => {
    // rejects: "MEZZANINE" and "PENTHOUSE" (the number dropped; the roof read as the penthouse below Roof)
    expect(levelName(LEVEL_IN_TEXT.exec("MEZZANINE 2 FRAMING PLAN")![1]!)).toBe("Mezzanine 2");
    expect(levelName(LEVEL_IN_TEXT.exec("PENTHOUSE ROOF FRAMING PLAN")![1]!)).toBe("Penthouse Roof");
    expect(levelOrder("Penthouse Roof")).toBeGreaterThan(levelOrder("Roof"));
    expect(levelOrder("Mezzanine 2")).toBeGreaterThan(levelOrder("Level 2"));
  });

  it("a MEZZANINE 2 plan's level is placed above Level 2", () => {
    const p = framingPlan();
    p.words = p.words.filter((w) => w.size !== 17 && !(w.x0 >= 2022 && w.y0 > 95 && w.y0 < 100)).concat(run("MEZZANINE 2 FRAMING PLAN", 2326, 1382, 17));
    const m = parseDrawingPages([p, schedule(), details()]);
    const ft = (id: string) => m.levels.find((l) => l.id === id)!.elevation / FT;
    // rejects: the plan read as "Mezzanine" (above Level 1), at 7 ft between Level 1 and Level 2
    expect(ft("mezzanine-2")).toBeCloseTo(21, 6);
  });
});

/** A plan page with the given x-lines (page x) and y-lines (page y), plus extra words. */
function plan(xLines: Array<[string, number]>, yLines: Array<[string, number]>, extra: DrawingWord[]) {
  const words: DrawingWord[] = [
    ...titleBlock("S-201", "LEVEL 2 FRAMING PLAN"),
    ...xLines.flatMap(([l, x]) => [...centred(l, x, 200, 16), ...centred(l, x, 1500, 16)]),
    ...yLines.flatMap(([l, y]) => [...centred(l, 150, y, 16), ...centred(l, 1900, y, 16)]),
    ...extra,
  ];
  const pg = page(1, words);
  const sheet = readSheets([pg])[0]!;
  const phr = phrases(pg.words);
  const lines = planGrid(phr, sheet, DEFAULT_PROFILE);
  const cal = calibrate(phr, lines, sheet, DEFAULT_PROFILE);
  return { cal, grid: buildingGrid(sheet, lines, cal) };
}

describe("grid scale (finding 8)", () => {
  it("an ENLARGED / PARTIAL PLAN title does not govern the plan's scale", () => {
    expect(planTitle("LEVEL 2 FRAMING PLAN")).toBe(true);
    expect(planTitle("ENLARGED STAIR PLAN")).toBe(false);
    expect(planTitle("PARTIAL PLAN AT GRID 3")).toBe(false);
    const { cal } = plan([["1", 300], ["2", 705]], [["A", 1200], ["B", 795]], [
      ...run("ENLARGED STAIR PLAN", 300, 300, 12), ...run(`SCALE: 1/4" = 1'-0"`, 300, 320, 9), ...run(`SCALE: 3/16" = 1'-0"`, 1400, 1622, 10),
    ]);
    // rejects: 18 pt/ft (the enlarged plan's 1/4" note, taken as "under a plan title")
    expect(1 / cal.k.x).toBeCloseTo(13.5, 9);
  });

  it("x and y scales are found per axis", () => {
    // x at 13.5 pt/ft (three 30 ft bays), y at 9 pt/ft (two 30 ft bays, 270 pt each)
    const { cal, grid } = plan([["1", 300], ["2", 705], ["3", 1110], ["4", 1515]], [["A", 1300], ["B", 1030], ["C", 760]], [
      ...centred(`30'-0"`, 502.5, 250, 9), ...centred(`30'-0"`, 907.5, 250, 9), ...centred(`30'-0"`, 1312.5, 250, 9),
      ...centred(`30'-0"`, 200, 1165, 9, 90), ...centred(`30'-0"`, 200, 895, 9, 90),
    ]);
    // rejects: y lines at 20 / 40 ft (the y strings out-voted by the x strings, y measured at the x scale)
    expect(1 / cal.k.y).toBeCloseTo(9, 9);
    expect([grid.y.get("B"), grid.y.get("C")]).toEqual([30, 60]);
    expect(grid.measured).toEqual([]);
  });

  it("mild drafting distortion keeps the written dimension; misreads are still rejected", () => {
    // bay 2-3 drawn 6 % long with 30'-0" written
    const { grid } = plan([["1", 300], ["2", 705], ["3", 1134.3], ["4", 1539.3]], [["A", 1200], ["B", 795]], [
      ...centred(`30'-0"`, 502.5, 250, 9), ...centred(`30'-0"`, 919.6, 250, 9), ...centred(`30'-0"`, 1336.8, 250, 9), ...centred(`30'-0"`, 200, 997.5, 9, 90),
    ]);
    // rejects: line 3 at 61.8 ft (the written 30 ft replaced by 31.8 ft measured under a 3 % tolerance)
    expect(grid.x.get("3")).toBeCloseTo(60, 3);
    expect(grid.measured).toEqual([]);
    const k = 1 / 13.5;
    expect(agrees(30, 1.15 * 30 / k, k)).toBe(true); // 15 % distortion accepted
    expect(agrees(30, 1.5 * 30 / k, k)).toBe(false); // an overall dimension over two bays (+50 %)
    expect(agrees(30, (30 / k) / 1.5, k)).toBe(false); // one bay's string on a two-bay pair (-33 %)
  });
});
