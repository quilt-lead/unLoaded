/**
 * Section profile designation + section dimensions.
 *
 * Priority:
 *   1. IfcMaterialProfileSet(Usage) profile ProfileName
 *   2. IfcExtrudedAreaSolid SweptArea ProfileName (Body representation, through
 *      mapped items and boolean clipping)
 *   3. Regex over Name / ObjectType / type object name (W12X26, HSS6X6X3/8, IPE300, ...)
 *   4. Synthesised from parametric profile dims, in mm: "I<d>X<w>", "<d>X<w>", "D<d>"
 */
import { IfcReader, num, ref, refs, str } from "./reader.ts";

/** Upper case, no whitespace, 'x' / '×' / '*' between numbers -> 'X'. */
export function normaliseProfile(s: string): string {
  return s
    .trim()
    .toUpperCase()
    .replace(/×/g, "X")
    .replace(/(\d)\s*[X*]\s*(?=\d)/g, "$1X")
    .replace(/\s+/g, "");
}

const NUM = String.raw`\d+(?:[.,]\d+)?`;
const FRAC = String.raw`(?:\d+\s*-\s*)?\d+\/\d+|\d+(?:[.,]\d+)?`;
const X = String.raw`\s*[xX×*]\s*`;

/** Ordered: specific steel shapes first, generic WxD last. */
const PROFILE_PATTERNS: RegExp[] = [
  new RegExp(String.raw`\bHSS\s*(?:${FRAC})(?:${X}(?:${FRAC})){1,2}`, "i"),
  new RegExp(String.raw`\b(?:W|M|S|HP|C|MC|WT|MT|ST)\s?${NUM}${X}${NUM}\b`, "i"),
  new RegExp(String.raw`\bL\s?(?:${FRAC})${X}(?:${FRAC})${X}(?:${FRAC})`, "i"),
  new RegExp(String.raw`\b(?:IPE|IPN|UPN|UPE|PFC|HEA|HEB|HEM|HE\s?\d+\s?[ABM]|HD|HL|HP|CHS|SHS|RHS)\s?${NUM}(?:${X}${NUM}){0,2}\b`, "i"),
  new RegExp(String.raw`\b${NUM}${X}${NUM}${X}${NUM}\s*(?:UB|UC|UBP|PFC)\b`, "i"),
  new RegExp(String.raw`\b(?:UB|UC|UBP)\s*${NUM}${X}${NUM}${X}${NUM}\b`, "i"),
  new RegExp(String.raw`\b\d{2,4}${X}\d{2,4}(?:${X}\d{1,4})?\b`),
];

export function profileFromText(texts: Array<string | undefined>): string | undefined {
  for (const re of PROFILE_PATTERNS) {
    for (const t of texts) {
      if (!t) continue;
      const m = re.exec(t);
      if (m) return normaliseProfile(m[0]);
    }
  }
  return undefined;
}

export interface ProfileInfo {
  name?: string;
  /** Section depth / width in metres. */
  depth?: number;
  width?: number;
  synthesized?: string;
}

/** Reads ProfileName and nominal dimensions from any IfcProfileDef subtype. */
export function readProfileDef(r: IfcReader, id: number | undefined, lengthScale: number): ProfileInfo | undefined {
  const p = r.line(id);
  if (!p) return undefined;
  const t = r.nameOfCode(p.type);
  const name = str(p.ProfileName);
  const n = (k: string) => num(p[k]);
  let depth: number | undefined;
  let width: number | undefined;
  let prefix = "";
  switch (t) {
    case "IfcIShapeProfileDef":
    case "IfcAsymmetricIShapeProfileDef":
      depth = n("OverallDepth");
      width = n("OverallWidth") ?? n("BottomFlangeWidth");
      prefix = "I";
      break;
    case "IfcRectangleProfileDef":
    case "IfcRectangleHollowProfileDef":
    case "IfcRoundedRectangleProfileDef":
      depth = n("YDim");
      width = n("XDim");
      prefix = t === "IfcRectangleHollowProfileDef" ? "RHS" : "";
      break;
    case "IfcCircleProfileDef":
    case "IfcCircleHollowProfileDef": {
      const rad = n("Radius");
      depth = width = rad !== undefined ? rad * 2 : undefined;
      prefix = t === "IfcCircleHollowProfileDef" ? "CHS" : "D";
      break;
    }
    case "IfcLShapeProfileDef":
      depth = n("Depth");
      width = n("Width") ?? depth;
      prefix = "L";
      break;
    case "IfcUShapeProfileDef":
    case "IfcTShapeProfileDef":
    case "IfcZShapeProfileDef":
      depth = n("Depth");
      width = n("FlangeWidth");
      prefix = t === "IfcUShapeProfileDef" ? "U" : t === "IfcTShapeProfileDef" ? "T" : "Z";
      break;
    case "IfcCShapeProfileDef":
      depth = n("Depth");
      width = n("Width");
      prefix = "C";
      break;
    case "IfcDerivedProfileDef":
      return { ...readProfileDef(r, ref(p.ParentProfile), lengthScale), ...(name ? { name } : {}) };
    default:
      break;
  }
  const info: ProfileInfo = {};
  if (name && name.trim()) info.name = name;
  if (depth !== undefined) info.depth = depth * lengthScale;
  if (width !== undefined) info.width = width * lengthScale;
  if (depth !== undefined) {
    const mm = (v: number) => Math.round(v * lengthScale * 1000);
    if (prefix === "D" || prefix === "CHS") info.synthesized = `${prefix}${mm(depth)}`;
    else info.synthesized = `${prefix}${mm(depth)}${width !== undefined ? `X${mm(width)}` : ""}`;
  }
  return info;
}

/** Finds the swept profile def of the first extruded/swept solid in the Body representation. */
export function findSweptProfile(r: IfcReader, productShapeId: number | undefined): number | undefined {
  const shape = r.line(productShapeId);
  if (!shape) return undefined;
  const reps = refs(shape.Representations).map((id) => r.line(id)).filter((x) => x !== undefined);
  reps.sort((a, b) => Number(str(b!.RepresentationIdentifier) === "Body") - Number(str(a!.RepresentationIdentifier) === "Body"));
  for (const rep of reps) {
    for (const item of refs(rep!.Items)) {
      const found = sweptFromItem(r, item, 0);
      if (found !== undefined) return found;
    }
  }
  return undefined;
}

function sweptFromItem(r: IfcReader, id: number, depth: number): number | undefined {
  if (depth > 6) return undefined;
  const it = r.line(id);
  if (!it) return undefined;
  const t = r.nameOfCode(it.type);
  if (
    t === "IfcExtrudedAreaSolid" ||
    t === "IfcExtrudedAreaSolidTapered" ||
    t === "IfcRevolvedAreaSolid" ||
    t === "IfcSurfaceCurveSweptAreaSolid" ||
    t === "IfcFixedReferenceSweptAreaSolid" ||
    t === "IfcSweptDiskSolid"
  ) {
    return ref(it.SweptArea);
  }
  if (t === "IfcBooleanClippingResult" || t === "IfcBooleanResult") return sweptFromItem(r, ref(it.FirstOperand) ?? -1, depth + 1);
  if (t === "IfcMappedItem") {
    const map = r.line(ref(it.MappingSource));
    const rep = r.line(ref(map?.MappedRepresentation));
    for (const sub of refs(rep?.Items)) {
      const f = sweptFromItem(r, sub, depth + 1);
      if (f !== undefined) return f;
    }
  }
  return undefined;
}
