import { describe, expect, it } from "vitest";
import { feetInches, levelName, memberTag, nominalSection, phrases } from "../src/index.ts";
import { scalePtPerFt } from "../src/text.ts";
import { run } from "./helpers.ts";

describe("member tags", () => {
  it("reads size, SFRS star, studs and camber", () => {
    expect(memberTag(`*W18X40 (30) c=3/4"`)).toEqual({ profile: "W18X40", sfrs: true, studs: 30, camberIn: 0.75 });
    expect(memberTag("W24X68 (30)")).toEqual({ profile: "W24X68", sfrs: false, studs: 30 });
    expect(memberTag("*HSS6X6X1/4")).toEqual({ profile: "HSS6X6X1/4", sfrs: true });
    expect(memberTag("HSS 6x6x3/8")?.profile).toBe("HSS6X6X3/8");
    expect(memberTag("C12x20.7")?.profile).toBe("C12X20.7");
    expect(memberTag("L4X4X1/4")?.profile).toBe("L4X4X1/4");
    expect(memberTag("IPE300")?.profile).toBe("IPE300");
  });

  it("rejects marks and labels", () => {
    for (const t of ["GB1", "F5.5", "P2", "*SMF", "S-201", "LEVEL 2", "BP-4", `30'-0"`, "A", "1"]) expect(memberTag(t)).toBeUndefined();
  });

  it("nominal sections come from the designation only", () => {
    expect(nominalSection("W18X40")!.depth).toBeCloseTo(18 * 0.0254, 6);
    expect(nominalSection("HSS6X4X1/4")).toEqual({ depth: 6 * 0.0254, width: 4 * 0.0254 });
    expect(nominalSection("XYZ")).toBeUndefined();
  });
});

describe("values", () => {
  it("feet-inches in every spelling a set uses", () => {
    expect(feetInches(`30'-0"`)).toEqual([30]);
    expect(feetInches(`5' - 6" 5' - 6" 1' - 6"`)).toEqual([5.5, 5.5, 1.5]);
    expect(feetInches(`TOP OF FOOTING EL. -3'-0" AND TOP OF PIER EL. -0'-6"`)).toEqual([-3, -0.5]);
    expect(feetInches(`20'-1 1/2"`)[0]).toBeCloseTo(20 + 1.5 / 12, 9);
  });

  it("drawing scales", () => {
    expect(scalePtPerFt(`SCALE: 3/16" = 1'-0"`)).toBe(13.5);
    expect(scalePtPerFt(`1/8" = 1'-0"`)).toBe(9);
    expect(scalePtPerFt(`1-1/2" = 1'-0"`)).toBe(108);
  });

  it("level names", () => {
    expect(levelName("LEVEL 2")).toBe("Level 2");
    expect(levelName("L3")).toBe("Level 3");
    expect(levelName("ROOF")).toBe("Roof");
    expect(levelName("RF")).toBe("Roof");
    expect(levelName("FRAMING")).toBeUndefined();
  });
});

describe("phrases", () => {
  it("joins words of one run in reading order, for flat and rotated text", () => {
    const ws = [...run("W18X40 (30)", 100, 200, 9), ...run("*W36X150 (30)", 400, 600, 9, 90), ...run("FAR", 300, 200, 9)];
    const ps = phrases(ws).map((p) => [p.text, p.rot]);
    expect(ps).toContainEqual(["W18X40 (30)", 0]);
    expect(ps).toContainEqual(["*W36X150 (30)", 90]);
    expect(ps).toContainEqual(["FAR", 0]);
  });
});
