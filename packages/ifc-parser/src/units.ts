/**
 * Project unit handling. Produces SI scale factors (file unit -> metre, m2, m3,
 * kg) from the project's IfcUnitAssignment.
 */
import { IFCPROJECT } from "web-ifc";
import { IfcReader, num, ref, refs, str } from "./reader.ts";

export interface UnitScales {
  /** file length unit -> metres */
  length: number;
  /** file area unit -> m2 */
  area: number;
  /** file volume unit -> m3 */
  volume: number;
  /** file mass unit -> kg */
  mass: number;
  /** Human-readable name of the length unit, e.g. "MILLIMETRE", "FOOT". */
  lengthName: string;
}

const SI_PREFIX: Record<string, number> = {
  EXA: 1e18,
  PETA: 1e15,
  TERA: 1e12,
  GIGA: 1e9,
  MEGA: 1e6,
  KILO: 1e3,
  HECTO: 1e2,
  DECA: 1e1,
  DECI: 1e-1,
  CENTI: 1e-2,
  MILLI: 1e-3,
  MICRO: 1e-6,
  NANO: 1e-9,
  PICO: 1e-12,
  FEMTO: 1e-15,
  ATTO: 1e-18,
};

/** Fallback factors for conversion-based units with a missing/odd ConversionFactor. */
const CONVERSION_BY_NAME: Record<string, number> = {
  FOOT: 0.3048,
  FEET: 0.3048,
  "US SURVEY FOOT": 1200 / 3937,
  INCH: 0.0254,
  YARD: 0.9144,
  MILE: 1609.344,
  "SQUARE FOOT": 0.09290304,
  "SQUARE INCH": 0.00064516,
  "SQUARE YARD": 0.83612736,
  ACRE: 4046.8564224,
  "CUBIC FOOT": 0.028316846592,
  "CUBIC INCH": 0.000016387064,
  "CUBIC YARD": 0.764554857984,
  GALLON: 0.003785411784,
  POUND: 0.45359237,
  "POUND-MASS": 0.45359237,
  TON: 907.18474,
  "SHORT TON": 907.18474,
  "LONG TON": 1016.0469088,
};

interface ResolvedUnit {
  unitType: string;
  scale: number;
  name: string;
}

/** Resolves an IfcSIUnit / IfcConversionBasedUnit line to an SI scale factor. */
export function resolveUnit(r: IfcReader, id: number | undefined, depth = 0): ResolvedUnit | undefined {
  const u = r.line(id);
  if (!u || depth > 4) return undefined;
  const t = r.nameOfCode(u.type);
  const unitType = (str(u.UnitType) ?? "").toUpperCase();
  if (t === "IfcSIUnit") {
    const prefix = (str(u.Prefix) ?? "").toUpperCase();
    const name = (str(u.Name) ?? "").toUpperCase();
    const p = prefix ? (SI_PREFIX[prefix] ?? 1) : 1;
    let scale = p;
    if (name === "SQUARE_METRE") scale = p * p;
    else if (name === "CUBIC_METRE") scale = p * p * p;
    else if (name === "GRAM") scale = p / 1000;
    return { unitType, scale, name: `${prefix}${name}` };
  }
  if (t === "IfcConversionBasedUnit" || t === "IfcConversionBasedUnitWithOffset") {
    const name = (str(u.Name) ?? "").toUpperCase();
    const mwu = r.line(ref(u.ConversionFactor));
    let scale: number | undefined;
    if (mwu) {
      const v = num(mwu.ValueComponent);
      const base = resolveUnit(r, ref(mwu.UnitComponent), depth + 1);
      if (v !== undefined && base) scale = v * base.scale;
    }
    const byName = CONVERSION_BY_NAME[name.replace(/_/g, " ")];
    if ((scale === undefined || !(scale > 0)) && byName !== undefined) scale = byName;
    if (scale === undefined || !(scale > 0)) return undefined;
    return { unitType, scale, name };
  }
  return undefined;
}

/** Reads the project's unit assignment. Falls back to SI (metre) with a warning. */
export function readUnits(r: IfcReader, warnings: string[]): UnitScales {
  const out: UnitScales = { length: 1, area: NaN, volume: NaN, mass: 1, lengthName: "METRE" };
  let found = false;
  const projectId = r.ids(IFCPROJECT)[0];
  const project = r.line(projectId);
  const assignment = r.line(ref(project?.UnitsInContext));
  for (const uid of refs(assignment?.Units)) {
    const u = resolveUnit(r, uid);
    if (!u) continue;
    switch (u.unitType) {
      case "LENGTHUNIT":
        out.length = u.scale;
        out.lengthName = u.name;
        found = true;
        break;
      case "AREAUNIT":
        out.area = u.scale;
        break;
      case "VOLUMEUNIT":
        out.volume = u.scale;
        break;
      case "MASSUNIT":
        out.mass = u.scale;
        break;
    }
  }
  if (!found) warnings.push("units: no length unit in IfcUnitAssignment; assuming metres");
  if (!Number.isFinite(out.area)) out.area = out.length * out.length;
  if (!Number.isFinite(out.volume)) out.volume = out.length * out.length * out.length;
  return out;
}

const LENGTH_MEASURES = new Set([
  "IFCLENGTHMEASURE",
  "IFCPOSITIVELENGTHMEASURE",
  "IFCNONNEGATIVELENGTHMEASURE",
]);
const AREA_MEASURES = new Set(["IFCAREAMEASURE", "IFCPOSITIVEAREAMEASURE"]);
const VOLUME_MEASURES = new Set(["IFCVOLUMEMEASURE"]);
const MASS_MEASURES = new Set(["IFCMASSMEASURE"]);

/**
 * SI factor for a typed measure value (by its IFC measure name), or undefined
 * if the measure is not a length/area/volume/mass.
 */
export function measureScale(measure: string | undefined, units: UnitScales): number | undefined {
  if (!measure) return undefined;
  if (LENGTH_MEASURES.has(measure)) return units.length;
  if (AREA_MEASURES.has(measure)) return units.area;
  if (VOLUME_MEASURES.has(measure)) return units.volume;
  if (MASS_MEASURES.has(measure)) return units.mass;
  return undefined;
}
