import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import type { ElementInput, ModelInput } from "@unloaded/element-graph/input";
import { ifcParser, parseIfc } from "../src/index.ts";
import { validateModelInput } from "./validate.ts";

const fixture = (name: string) => fileURLToPath(new URL(`../../../data/${name}`, import.meta.url));
const tinyText = readFileSync(fixture("tiny-frame-mm.ifc"), "utf8");
const enc = (s: string) => new TextEncoder().encode(s);

const COLUMN = "1xS3BCk291UvhgP2a6eflK";
const BEAM = "0B7c6BZwH2vRqkTNn7nH2u";
const PLATE = "2r9LhGpQf0ePbYwN$1aYzT";
const STOREY = "3pJ8V9cNX5fwlcXk4MmL1Q";

const byId = (m: ModelInput, id: string): ElementInput => {
  const e = m.elements.find((x) => x.id === id);
  if (!e) throw new Error(`no element ${id}`);
  return e;
};

describe("tiny hand-written IFC4 (millimetres)", async () => {
  const m = await parseIfc(enc(tinyText), { fileName: "tiny-frame-mm.ifc" });

  it("is a valid ModelInput", () => {
    expect(validateModelInput(m)).toEqual([]);
    expect(m.meta).toMatchObject({ version: 1, units: "m", schema: "IFC4", project: "Tiny frame" });
    expect(m.meta.source).toEqual({ format: "ifc", file: "tiny-frame-mm.ifc" });
  });

  it("converts the storey elevation to metres", () => {
    expect(m.levels).toEqual([{ id: STOREY, name: "Level 1", elevation: 3 }]);
  });

  it("maps kinds", () => {
    expect(m.elements.map((e) => [e.id, e.kind])).toEqual([
      [BEAM, "beam"],
      [COLUMN, "column"],
      [PLATE, "connection"],
    ]);
    for (const e of m.elements) expect(e.levelId).toBe(STOREY);
  });

  it("reads marks (skipping placeholders) and params", () => {
    const col = byId(m, COLUMN);
    expect(col.mark).toBe("C101");
    expect(col.name).toBe("Column C1");
    expect(col.material).toBe("S355");
    expect(col.profile).toBe("HEA200");
    expect(col.source).toEqual({ format: "ifc", nativeId: 46, nativeType: "IfcColumn" });
    expect(col.params).toMatchObject({
      "Attr.Name": "Column C1",
      "Attr.ObjectType": "C-TAG",
      "Attr.Tag": "C1-tag",
      "Attr.PredefinedType": "COLUMN",
      "Pset_ColumnCommon.Mark": "C101",
      "Pset_ColumnCommon.LoadBearing": true,
      "Pset_ColumnCommon.Span": 3, // instance 3000 mm overrides type 1 mm, converted to m
      "Pset_ColumnCommon.FireRating": "R60", // from the type object
      "Pset_ColumnCommon.Status": "NEW",
      "Pset_ColumnCommon.Range.Upper": 10,
      "Pset_ColumnCommon.Range.Lower": 1,
      "Pset_ColumnCommon.Codes": "1, 2",
    });

    const beam = byId(m, BEAM);
    expect(beam.mark).toBe("B201"); // Mark 'n.a.' is a placeholder -> Reference
    expect(beam.profile).toBe("400X200"); // synthesised from IfcRectangleProfileDef, mm
    expect(beam.params["Qto_BeamBaseQuantities.Length"]).toBe(6);
    expect(beam.params["Qto_BeamBaseQuantities.GrossWeight"]).toBe(250);

    const plate = byId(m, PLATE);
    expect(plate.mark).toBeUndefined();
    expect(plate.name).toBe("Shear tab");
    expect(plate.geometry).toBeUndefined();
  });

  it("emits geometry in metres, Z up", () => {
    const col = byId(m, COLUMN).geometry!;
    expect(col.bbox).toEqual({ min: [-0.1, -0.095, 3], max: [0.1, 0.095, 6] });
    expect(col.axis).toEqual({ start: [0, 0, 3], end: [0, 0, 6] });
    expect(col.section).toEqual({ depth: 0.19, width: 0.2 });

    const beam = byId(m, BEAM).geometry!;
    expect(beam.bbox).toEqual({ min: [0, -0.1, 5.6], max: [6, 0.1, 6] });
    expect(beam.axis).toEqual({ start: [0, 0, 5.8], end: [6, 0, 5.8] });
    expect(beam.section).toEqual({ depth: 0.4, width: 0.2 });
    expect(byId(m, BEAM).params["Geom.InclinationDeg"]).toBe(0);
  });

  it("emits the explicit IfcRelConnectsElements", () => {
    expect(m.relations).toEqual([
      {
        a: BEAM,
        b: COLUMN,
        kind: "connects",
        evidence: { rule: "IfcRelConnectsElements", source: "explicit", detail: { ifcRelId: 130, ifcRelGlobalId: "ASk5bP1f1BnhDkXa1YIh9V" } },
      },
    ]);
  });

  it("warns about the plate without geometry", () => {
    expect(m.warnings).toEqual(["geometry: 1 element(s) without own body geometry (IfcPlate: 1)"]);
  });

  it("honours kindMap, includeKinds and geometry:false", async () => {
    const m2 = await parseIfc(enc(tinyText), {
      kindMap: { IfcPlate: "other", "IfcColumn.COLUMN": "pile" },
      includeKinds: ["pile", "beam"],
      geometry: false,
    });
    expect(m2.elements.map((e) => [e.id, e.kind])).toEqual([
      [BEAM, "beam"],
      [COLUMN, "pile"],
    ]);
    expect(m2.elements.every((e) => e.geometry === undefined)).toBe(true);
    expect(m2.relations).toHaveLength(1);
  });

  it("handles conversion-based units (FOOT)", async () => {
    const feet = tinyText.replace(
      "#10=IFCSIUNIT(*,.LENGTHUNIT.,.MILLI.,.METRE.);",
      [
        "#10=IFCCONVERSIONBASEDUNIT(#14,.LENGTHUNIT.,'FOOT',#15);",
        "#14=IFCDIMENSIONALEXPONENTS(1,0,0,0,0,0,0);",
        "#15=IFCMEASUREWITHUNIT(IFCLENGTHMEASURE(0.3048),#16);",
        "#16=IFCSIUNIT(*,.LENGTHUNIT.,$,.METRE.);",
      ].join("\n"),
    );
    const mf = await parseIfc(enc(feet));
    expect(mf.levels[0]!.elevation).toBeCloseTo(3000 * 0.3048, 6);
    const col = byId(mf, COLUMN);
    // web-ifc applies the same factor to meshes: geometry and levels agree.
    expect(col.geometry!.bbox.min[2]).toBeCloseTo(3000 * 0.3048, 3);
    expect(col.geometry!.bbox.max[2]).toBeCloseTo(6000 * 0.3048, 3);
    expect(col.params["Pset_ColumnCommon.Span"]).toBeCloseTo(3000 * 0.3048, 6);
    expect(mf.warnings.some((w) => w.startsWith("units:"))).toBe(false);
  });

  it("works with an explicit wasmPath (Node)", async () => {
    const require = createRequire(import.meta.url);
    const wasmDir = dirname(require.resolve("web-ifc/web-ifc.wasm"));
    const m3 = await parseIfc(enc(tinyText), { wasmPath: wasmDir, fileName: "tiny-frame-mm.ifc" });
    expect(m3).toEqual(m);
  });

  it("reports progress and rejects non-IFC input", async () => {
    const phases: string[] = [];
    await parseIfc(enc(tinyText), { onProgress: (p) => phases.push(p) });
    expect(phases[0]).toBe("init");
    expect(phases.at(-1)).toBe("done");
    await expect(parseIfc(enc("hello world"))).rejects.toThrow(/ISO-10303-21/);
  });

  it("ifcParser sniffs extension and header", async () => {
    expect(ifcParser.id).toBe("ifc");
    expect(ifcParser.extensions).toEqual(["ifc"]);
    expect(ifcParser.canParse("Model.IFC")).toBe(true);
    expect(ifcParser.canParse("model.json")).toBe(false);
    expect(ifcParser.canParse("whatever.bin", enc("ISO-10303-21;\nHEADER;"))).toBe(true);
    expect(ifcParser.canParse("model.ifc", enc("{ json }"))).toBe(false);
    const viaParser = await ifcParser.parse(enc(tinyText), { fileName: "tiny-frame-mm.ifc" });
    expect(viaParser).toEqual(m);
  });
});
