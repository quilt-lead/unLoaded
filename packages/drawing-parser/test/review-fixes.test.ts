/**
 * Regression tests for the 2026-11-14 review of drawing-parser: grid dimensions checked against the
 * scale, the plan's scale note, assumed level elevations and order, position-only column ids,
 * column-base callouts on elevations, deck thickness and HSS designations. Each test names the wrong
 * behaviour it rejects. Pages are built in code (helpers.ts), no PDF.
 */
import { describe, expect, it } from "vitest";
import { DEFAULT_PROFILE, nominalSection, parseDrawingPages, phrases, readSheets, type DrawingWord } from "../src/index.ts";
import { buildLevels, levelOrder } from "../src/assemble.ts";
import { emptyFacts, type Facts } from "../src/facts.ts";
import { buildingGrid, calibrate, planGrid } from "../src/grid.ts";
import { deckThickness } from "../src/text.ts";
import { centred, details, framingPlan, page, run, schedule, titleBlock } from "./helpers.ts";

const IN = 0.0254;

/** A plan page: x-lines at the given page x, y-lines A (y=1200) and B (y=795), plus extra words. */
function plan(xLines: Array<[string, number]>, extra: DrawingWord[]) {
  const words: DrawingWord[] = [
    ...titleBlock("S-201", "LEVEL 2 FRAMING PLAN"),
    ...xLines.flatMap(([l, x]) => [...centred(l, x, 200, 16), ...centred(l, x, 1500, 16)]),
    ...centred("A", 150, 1200, 16), ...centred("A", 1900, 1200, 16),
    ...centred("B", 150, 795, 16), ...centred("B", 1900, 795, 16),
    ...extra,
  ];
  const pg = page(1, words);
  const sheet = readSheets([pg])[0]!;
  const phr = phrases(pg.words);
  const lines = planGrid(phr, sheet, DEFAULT_PROFILE);
  const cal = calibrate(phr, lines, sheet, DEFAULT_PROFILE);
  return { pg, cal, grid: buildingGrid(sheet, lines, cal) };
}

describe("grid: a written dimension states a span only if it agrees with the scale (finding 2)", () => {
  it("an overall dimension centred in a bay with no own dimension does not become that bay's length", () => {
    // 3 bays of 30 ft at 13.5 pt/ft; bay 2-3 has no dimension of its own, the overall 90'-0" sits in it
    const { cal, grid } = plan([["1", 300], ["2", 705], ["3", 1110], ["4", 1515]], [
      ...centred(`30'-0"`, 502.5, 250, 9), ...centred(`90'-0"`, 907.5, 250, 9), ...centred(`30'-0"`, 1312.5, 250, 9),
      ...centred(`30'-0"`, 200, 997.5, 9, 90),
    ]);
    // rejects: line 3 at 120 ft and line 4 at 150 ft (90 ft summed in as bay 2-3)
    expect(grid.x.get("3")).toBeCloseTo(60, 3);
    expect(grid.x.get("4")).toBeCloseTo(90, 3);
    expect(cal.pairs.find((p) => p.a === "2")).toMatchObject({ writtenFt: 90 });
    expect(cal.pairs.find((p) => p.a === "2")!.ft).toBeUndefined();
    expect(grid.measured).toEqual([{ axis: "x", a: "2", b: "3", ft: 30, writtenFt: 90 }]);
  });

  it("a pair spanning two bays (middle line not drawn) does not take one bay's dimension", () => {
    const { grid } = plan([["1", 300], ["3", 1110]], [
      ...centred(`30'-0"`, 502.5, 250, 9), ...centred(`30'-0"`, 907.5, 250, 9),
      ...centred(`30'-0"`, 200, 997.5, 9, 90),
      ...run("LEVEL 2 FRAMING PLAN", 700, 1600, 14), ...run(`SCALE: 3/16" = 1'-0"`, 700, 1622, 10),
    ]);
    // rejects: line 3 at 30 ft (the 1-2 bay's string taken for the 1-3 pair)
    expect(grid.x.get("3")).toBeCloseTo(60, 3);
    expect(grid.measured[0]).toMatchObject({ a: "1", b: "3", writtenFt: 30 });
  });

  it("buildingGrid applies the same test to any Calibration it is handed", () => {
    const { cal, grid: good } = plan([["1", 300], ["2", 705]], [...centred(`30'-0"`, 502.5, 250, 9), ...centred(`30'-0"`, 200, 997.5, 9, 90)]);
    const sheet = readSheets([page(1, titleBlock("S-201", "LEVEL 2 FRAMING PLAN"))])[0]!;
    const forged = { ...cal, pairs: cal.pairs.map((p) => (p.axis === "x" ? { ...p, ft: 90 } : p)) };
    const lines = [...good.x].map(([label, ft]) => ({ label, axis: "x" as const, pos: 300 + ft * 13.5, rects: [] }));
    // rejects: a hand-built pair.ft of 90 ft accepted for a 30 ft span
    expect(buildingGrid(sheet, lines, forged).x.get("2")).toBeCloseTo(30, 3);
  });

  it("the parsed model warns that a span was measured, not stated", () => {
    const { pg } = plan([["1", 300], ["2", 705], ["3", 1110], ["4", 1515]], [
      ...centred(`30'-0"`, 502.5, 250, 9), ...centred(`90'-0"`, 907.5, 250, 9), ...centred(`30'-0"`, 1312.5, 250, 9),
      ...centred(`30'-0"`, 200, 997.5, 9, 90),
    ]);
    expect(parseDrawingPages([pg]).warnings.join("\n")).toMatch(/grid 2-3: dimension 90 ft disagrees with the scale.*measured, not stated/);
  });
});

describe("grid: the scale note that governs the plan (finding 11)", () => {
  const detailNote = [...run("DETAIL 4", 300, 300, 12), ...run(`SCALE: 3/4" = 1'-0"`, 300, 320, 9)];
  it("the note under the plan title wins over a detail's note printed first", () => {
    const { cal } = plan([["1", 300], ["2", 705]], [
      ...detailNote, ...run("LEVEL 2 FRAMING PLAN", 700, 1600, 14), ...run(`SCALE: 3/16" = 1'-0"`, 700, 1622, 10),
    ]);
    // rejects: 1/54 ft per pt (the 3/4" detail note, first in reading order)
    expect(cal.source).toBe("scale note");
    expect(cal.k.x).toBeCloseTo(1 / 13.5, 9);
    expect(cal.scaleRule).toMatch(/plan title/);
  });

  it("with no plan title near a note, the smallest scale on the sheet is the plan's", () => {
    const { cal } = plan([["1", 300], ["2", 705]], [...detailNote, ...run(`SCALE: 3/16" = 1'-0"`, 1400, 1622, 10)]);
    expect(cal.k.x).toBeCloseTo(1 / 13.5, 9);
    expect(cal.scaleRule).toMatch(/smallest/);
  });
});

describe("levels: order and assumed elevations (finding 3)", () => {
  const facts = (stated: Record<string, number>, names: string[]): Facts => {
    const f = emptyFacts();
    const occ = { file: "t.pdf", sheet: "S-1", page: 1, rect: [0, 0, 1, 1] as [number, number, number, number], how: "note" as const, text: "" };
    for (const [level, ft] of Object.entries(stated)) f.levels.push({ level, ft, how: "test", occ });
    for (let i = 0; i + 1 < names.length; i++) f.tiers.push({ at: "1/A", lo: names[i]!, hi: names[i + 1]!, occ, rule: "test" });
    return f;
  };

  it("consecutive unstated levels get distinct elevations, evenly between their stated neighbours", () => {
    const w: string[] = [];
    const lv = buildLevels(facts({ "Level 1": 0, Roof: 40 }, ["Level 1", "Level 2", "Level 3", "Roof"]), [], w);
    // rejects: Level 2 and Level 3 both at 12 ft (stated level below + 12, a zero-height storey)
    expect(lv.get("Level 2")!.ft).toBeCloseTo(40 / 3, 9);
    expect(lv.get("Level 3")!.ft).toBeCloseTo(80 / 3, 9);
    expect(lv.get("Level 2")!.assumed).toMatch(/evenly between Level 1 and Roof/);
    expect(w.filter((x) => /assumed/.test(x))).toHaveLength(2);
  });

  it("with nothing stated above, unstated levels step up 12 ft each", () => {
    const lv = buildLevels(facts({ "Level 1": 0 }, ["Level 1", "Level 2", "Level 3"]), [], []);
    expect([lv.get("Level 2")!.ft, lv.get("Level 3")!.ft]).toEqual([12, 24]);
  });

  it("Basement sorts below Level 1 and Mezzanine between Level 1 and Level 2", () => {
    // rejects: Basement / Mezzanine ordered 500, above every numbered level
    expect(levelOrder("Basement 2")).toBeLessThan(levelOrder("Basement"));
    expect(levelOrder("Basement")).toBeLessThan(levelOrder("Level 1"));
    expect(levelOrder("Mezzanine")).toBeGreaterThan(levelOrder("Level 1"));
    expect(levelOrder("Mezzanine")).toBeLessThan(levelOrder("Level 2"));
    expect(levelOrder("Penthouse")).toBeLessThan(levelOrder("Roof"));
    expect(levelOrder("Foundation")).toBeLessThan(levelOrder("Basement 2"));
    const lv = buildLevels(facts({ "Level 1": 0, "Level 2": 14 }, ["Basement", "Level 1", "Mezzanine", "Level 2"]), [], []);
    // rejects: Basement at 26 ft (12 ft above Level 2) and Mezzanine at 26 ft
    expect(lv.get("Basement")!.ft).toBe(-12);
    expect(lv.get("Mezzanine")!.ft).toBeCloseTo(7, 9);
    expect([...lv.keys()]).toEqual(["Basement", "Level 1", "Mezzanine", "Level 2"]);
  });

  it("elements on an assumed level say so", () => {
    const sched = schedule();
    sched.words = sched.words.filter((w) => !(w.y0 > 200 && w.y0 < 222)); // drop "LEVEL 2 EL. 14'-0""
    const plan2 = framingPlan();
    plan2.words = plan2.words.filter((w) => !(w.x0 >= 2022 && w.y0 > 95 && w.y0 < 100)); // drop the T.O.S. note (baseline 104)
    const m = parseDrawingPages([plan2, sched, details()]);
    const b = m.elements.find((e) => e.id === "beam:level-2:1..2:A")!;
    expect(m.levels.find((l) => l.id === "level-2")!.elevation).toBeCloseTo(14 * 0.3048, 6);
    expect(String(b.params["Drawing.LevelElevationAssumed"])).toMatch(/evenly between Level 1 and Roof/);
  });
});

describe("columns: ids from position only (finding 4)", () => {
  const resized = () => {
    const s = schedule();
    s.words = s.words.map((w) => (w.s === "W10X33" && w.y0 < 200 ? { ...w, s: "W10X39" } : w)); // L2 - ROOF storey only
    return s;
  };

  it("resizing one storey keeps every element id", () => {
    const before = parseDrawingPages([framingPlan(), schedule(), details()]);
    const after = parseDrawingPages([framingPlan(), resized(), details()]);
    // rejects: ids that change with the sizes (a size-run split / merge shows a diff as removed + added)
    expect(after.elements.map((e) => e.id)).toEqual(before.elements.map((e) => e.id));
    expect(after.relations.map((r) => `${r.a}|${r.b}`)).toEqual(before.relations.map((r) => `${r.a}|${r.b}`));
  });

  it("each storey segment keeps its own size (round 2: one element per storey segment)", () => {
    const m = parseDrawingPages([framingPlan(), resized(), details()]);
    expect(m.elements.find((e) => e.id === "column:1/A:level-1..level-2")!.profile).toBe("W10X33");
    expect(m.elements.find((e) => e.id === "column:1/A:level-2..roof")!.profile).toBe("W10X39");
  });
});

describe("elevations: a callout beside a column is a base plate only at its base (finding 7)", () => {
  /** Elevation of line A: bubbles 1 (x=300) and 2 (x=705), Level 1 / Level 2 / Roof markers. */
  const elevation = (calloutY: number) => page(4, [
    ...titleBlock("S-301", "FRAME ELEVATIONS"),
    ...centred("1", 300, 900, 16), ...centred("2", 705, 900, 16),
    ...run("FRAME ELEVATION - LINE A", 400, 960, 12),
    ...run("LEVEL 1", 120, 850, 10), ...run(`EL. 0'-0"`, 120, 864, 9),
    ...run("LEVEL 2", 120, 600, 10), ...run(`EL. 14'-0"`, 120, 614, 9),
    ...run("ROOF", 120, 350, 10), ...run(`EL. 28'-0"`, 120, 364, 9),
    ...centred("5", 330, calloutY, 10), ...centred("S-501", 330, calloutY + 14, 7),
  ]);
  const det = () => {
    const d = details();
    d.words = [...d.words, ...centred("5", 1200, 545, 11), ...centred("S-501", 1200, 560, 6.5), ...run("TYPICAL CONNECTION", 1226, 551, 12)];
    return d;
  };

  it("a generic callout next to the column at Level 2 is not attributed to the column base", () => {
    const m = parseDrawingPages([framingPlan(), schedule(), det(), elevation(570)]);
    const bp = m.elements.find((e) => e.id === "connection:base:1/A")!;
    // rejects: Detail.Refs "5/S-501" on the base plate (the full-height column segment was within reach)
    expect(String(bp.params["Detail.Refs"] ?? "")).not.toContain("5/S-501");
  });

  it("the same callout at the column base is attributed to the base plate", () => {
    const m = parseDrawingPages([framingPlan(), schedule(), det(), elevation(830)]);
    expect(String(m.elements.find((e) => e.id === "connection:base:1/A")!.params["Detail.Refs"])).toContain("5/S-501");
  });
});

describe("deck thickness (finding 8)", () => {
  it("reads a TOTAL value written with a space before the fraction", () => {
    // rejects: 4 in (the regex matched the "4" of "1/4")
    expect(deckThickness(`FLOOR DECK: 3" COMPOSITE DECK, 6 1/4" TOTAL.`)?.thicknessIn).toBe(6.25);
    expect(deckThickness(`FLOOR DECK: 3" COMPOSITE DECK, 6-1/4" TOTAL.`)?.thicknessIn).toBe(6.25);
  });

  it("without TOTAL it never takes the first inch value (the rib depth)", () => {
    // rejects: 3 in (the deck's rib depth) for both
    expect(deckThickness(`FLOOR DECK: 3" COMPOSITE DECK W/ 3-1/4" LW CONCRETE`)).toEqual({ thicknessIn: 6.25, rule: "deck depth + concrete above the deck (deck note)" });
    expect(deckThickness(`FLOOR DECK: 3" COMPOSITE DECK W/ NW CONCRETE FILL`)).toBeUndefined();
    expect(deckThickness(`ROOF DECK: 1-1/2" TYPE B ROOF DECK`)?.thicknessIn).toBe(1.5);
    expect(deckThickness(`5" NW CONCRETE SLAB ON 2" DECK`)?.thicknessIn).toBe(5);
  });

  it("the parsed slab takes it, with its rule", () => {
    const p = framingPlan();
    p.words = p.words.map((w) => (w.s === `6-1/4"` ? { ...w, s: "6" } : w));
    const i = p.words.findIndex((w) => w.s === "6");
    p.words.splice(i + 1, 0, { ...p.words[i]!, s: `1/4"`, x0: p.words[i]!.x1 + 2.2, x1: p.words[i]!.x1 + 2.2 + 4 * 0.55 * 8 });
    for (const w of p.words.slice(i + 2)) if (w.y0 === p.words[i]!.y0) Object.assign(w, { x0: w.x0 + 20, x1: w.x1 + 20 });
    const s = parseDrawingPages([p, schedule(), details()]).elements.find((e) => e.id === "slab:level-2")!;
    expect(s.params["Drawing.ThicknessIn"]).toBe(6.25);
    expect(s.params["Drawing.ThicknessRule"]).toMatch(/TOTAL/);
  });
});

describe("HSS designations (finding 9)", () => {
  it("a two-dimension HSS is round: OD x t", () => {
    // rejects: width 0.375 in (the wall thickness read as the second side)
    expect(nominalSection("HSS5.563X0.375")).toEqual({ depth: 5.563 * IN, width: 5.563 * IN });
  });

  it("fractional sides are read", () => {
    // rejects: undefined
    expect(nominalSection("HSS3-1/2X3-1/2X1/4")).toEqual({ depth: 3.5 * IN, width: 3.5 * IN });
    expect(nominalSection("HSS6X4X1/4")).toEqual({ depth: 6 * IN, width: 4 * IN });
  });
});
