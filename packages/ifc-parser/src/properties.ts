/**
 * Flattening of IfcPropertySet / IfcElementQuantity definitions into
 * "PsetName.PropName" -> primitive ParamValue.
 *
 * Unit policy: values typed as length / area / volume / mass measures (in
 * properties and quantities alike) are converted to SI (m, m2, m3, kg) using
 * the property's own Unit if given, else the project unit assignment.
 * Everything else (counts, ratios, forces, ...) is emitted raw.
 */
import type { ParamValue } from "@unloaded/element-graph/input";
import { IfcReader, measureName, primitive, ref, refs, str } from "./reader.ts";
import { measureScale, resolveUnit, type UnitScales } from "./units.ts";

type Params = Record<string, ParamValue>;

function convert(r: IfcReader, raw: unknown, unitRef: unknown, units: UnitScales): ParamValue | undefined {
  const v = primitive(raw);
  if (typeof v !== "number") return v;
  const explicit = ref(unitRef);
  if (explicit !== undefined) {
    const u = resolveUnit(r, explicit);
    if (u && ["LENGTHUNIT", "AREAUNIT", "VOLUMEUNIT", "MASSUNIT"].includes(u.unitType)) return v * u.scale;
    return v;
  }
  const s = measureScale(measureName(raw), units);
  return s === undefined ? v : v * s;
}

function set(out: Params, key: string, v: ParamValue | undefined) {
  if (v !== undefined) out[key] = v;
}

function flattenProperty(r: IfcReader, id: number, prefix: string, out: Params, units: UnitScales, depth: number) {
  const p = r.line(id);
  if (!p || depth > 4) return;
  const t = r.nameOfCode(p.type);
  const name = str(p.Name);
  if (!name) return;
  const key = `${prefix}.${name}`;
  switch (t) {
    case "IfcPropertySingleValue":
      set(out, key, p.NominalValue == null ? null : convert(r, p.NominalValue, p.Unit, units));
      break;
    case "IfcPropertyEnumeratedValue":
      set(out, key, primitive(p.EnumerationValues) ?? null);
      break;
    case "IfcPropertyBoundedValue":
      set(out, `${key}.Upper`, convert(r, p.UpperBoundValue, p.Unit, units));
      set(out, `${key}.Lower`, convert(r, p.LowerBoundValue, p.Unit, units));
      set(out, `${key}.SetPoint`, convert(r, p.SetPointValue, p.Unit, units));
      break;
    case "IfcPropertyListValue": {
      const list = Array.isArray(p.ListValues) ? p.ListValues : [];
      if (list.length === 1) set(out, key, convert(r, list[0], p.Unit, units));
      else set(out, key, primitive(list) ?? null);
      break;
    }
    case "IfcPropertyTableValue":
      // Not representable as a primitive; skip.
      break;
    case "IfcComplexProperty":
      for (const c of refs(p.HasProperties)) flattenProperty(r, c, key, out, units, depth + 1);
      break;
    case "IfcQuantityLength":
    case "IfcQuantityArea":
    case "IfcQuantityVolume":
    case "IfcQuantityWeight":
    case "IfcQuantityCount":
    case "IfcQuantityTime":
    case "IfcQuantityNumber": {
      const field = Object.keys(p).find((k) => k.endsWith("Value") && k !== "Value");
      if (field) set(out, key, convert(r, p[field], p.Unit, units));
      break;
    }
    case "IfcPhysicalComplexQuantity":
      for (const c of refs(p.HasQuantities)) flattenProperty(r, c, key, out, units, depth + 1);
      break;
    default:
      break;
  }
}

/** Flattens one IfcPropertySet / IfcElementQuantity (other definitions ignored). */
export function flattenPropertyDefinition(r: IfcReader, id: number, out: Params, units: UnitScales) {
  const d = r.line(id);
  if (!d) return;
  const t = r.nameOfCode(d.type);
  const psetName = str(d.Name) ?? t;
  if (t === "IfcPropertySet") {
    for (const p of refs(d.HasProperties)) flattenProperty(r, p, psetName, out, units, 0);
  } else if (t === "IfcElementQuantity") {
    for (const q of refs(d.Quantities)) flattenProperty(r, q, psetName, out, units, 0);
  }
}
