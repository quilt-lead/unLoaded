import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import type { ModelInput } from "@unloaded/element-graph/input";
import { parseIfc } from "../src/index.ts";
import { summariseModel } from "../scripts/dump.ts";
import { validateModelInput } from "./validate.ts";

const file = fileURLToPath(new URL("./fixtures/Building-Structural-IFC4.ifc", import.meta.url));
const bytes = () => new Uint8Array(readFileSync(file));
const GLOBAL_ID = /^[0-9A-Za-z_$]{22}$/;

describe("buildingSMART Building-Structural (IFC4)", async () => {
  const m: ModelInput = await parseIfc(bytes(), { fileName: "Building-Structural-IFC4.ifc" });

  it("prints a summary", () => {
    console.log(summariseModel(m));
  });

  it("conforms structurally to the contract and is JSON-serialisable", () => {
    expect(validateModelInput(m)).toEqual([]);
    expect(JSON.parse(JSON.stringify(m))).toEqual(m);
    expect(m.meta.schema).toBe("IFC4");
  });

  it("has sensible counts by kind", () => {
    const counts: Record<string, number> = {};
    for (const e of m.elements) counts[e.kind] = (counts[e.kind] ?? 0) + 1;
    expect(counts).toEqual({ beam: 6, wall: 4, footing: 1, slab: 1, connection: 2, other: 2 });
    expect(m.warnings.some((w) => w.includes("IfcChimney"))).toBe(true);
  });

  it("uses unique GlobalIds and records the native type", () => {
    const ids = m.elements.map((e) => e.id);
    expect(new Set(ids).size).toBe(ids.length);
    for (const e of m.elements) {
      expect(e.id).toMatch(GLOBAL_ID);
      expect(e.source.nativeType).toMatch(/^Ifc/);
      expect(e.source.format).toBe("ifc");
    }
  });

  it("emits finite geometry for everything except the decomposed roof", () => {
    for (const e of m.elements) {
      if (e.source.nativeType === "IfcRoof") {
        expect(e.geometry).toBeUndefined();
        continue;
      }
      const { min, max } = e.geometry!.bbox;
      for (let k = 0; k < 3; k++) {
        expect(Number.isFinite(min[k]!) && Number.isFinite(max[k]!)).toBe(true);
        expect(min[k]!).toBeLessThanOrEqual(max[k]!);
      }
    }
    // Beam centrelines match the quantity take-off lengths (metres).
    for (const e of m.elements.filter((x) => x.kind === "beam")) {
      expect(e.geometry!.axis).toBeDefined();
      expect(e.params["Geom.Length"]).toBeCloseTo(e.params["Qto_BeamBaseQuantities.Length"] as number, 3);
    }
  });

  it("has storey elevations consistent with contained element z ranges (Z up)", () => {
    expect(m.levels).toEqual([{ id: "1Ano2ZUxnEIvVQ_beukl8b", name: "00 groundfloor", elevation: 0 }]);
    for (const lvl of m.levels) {
      const onLevel = m.elements.filter((e) => e.levelId === lvl.id && e.geometry);
      expect(onLevel.length).toBeGreaterThan(0);
      const zMin = Math.min(...onLevel.map((e) => e.geometry!.bbox.min[2]));
      const zMax = Math.max(...onLevel.map((e) => e.geometry!.bbox.max[2]));
      expect(lvl.elevation).toBeGreaterThanOrEqual(zMin);
      expect(lvl.elevation).toBeLessThanOrEqual(zMax);
      // Walls stand on the storey: they start at most a slab depth below it.
      for (const w of onLevel.filter((e) => e.kind === "wall")) {
        expect(Math.abs(w.geometry!.bbox.min[2] - lvl.elevation)).toBeLessThan(0.5);
        expect(w.geometry!.bbox.max[2] - w.geometry!.bbox.min[2]).toBeGreaterThan(2); // tall in Z, not Y
      }
    }
    // Footing below the walls.
    const footing = m.elements.find((e) => e.kind === "footing")!;
    expect(footing.geometry!.bbox.max[2]).toBeLessThanOrEqual(0);
  });

  it("emits the explicit roof decomposition as part_of relations", () => {
    const roof = m.elements.find((e) => e.source.nativeType === "IfcRoof")!;
    expect(m.relations.length).toBe(8);
    for (const r of m.relations) {
      expect(r.kind).toBe("part_of");
      expect(r.b).toBe(roof.id);
      expect(r.evidence).toMatchObject({ rule: "IfcRelAggregates", source: "explicit" });
    }
  });

  it("is deterministic", async () => {
    const again = await parseIfc(bytes(), { fileName: "Building-Structural-IFC4.ifc" });
    expect(JSON.stringify(again)).toBe(JSON.stringify(m));
    const sortedIds = [...m.elements.map((e) => e.id)].sort();
    expect(m.elements.map((e) => e.id)).toEqual(sortedIds);
  });
});
