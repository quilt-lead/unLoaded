/**
 * IfcRelAssociatesMaterial targets -> primary material name and (for profile
 * sets) the material profile's IfcProfileDef id.
 */
import { IfcReader, ref, refs, str } from "./reader.ts";

export interface MaterialInfo {
  name?: string;
  /** IfcProfileDef id from an IfcMaterialProfileSet, if any. */
  profileDefId?: number;
  /** IfcMaterialProfileSet / profile Name (sometimes the section designation). */
  profileSetName?: string;
}

export function readMaterial(r: IfcReader, id: number | undefined, depth = 0): MaterialInfo {
  const m = r.line(id);
  if (!m || depth > 4) return {};
  const t = r.nameOfCode(m.type);
  const first = (list: unknown) => refs(list)[0];
  switch (t) {
    case "IfcMaterial":
      return { name: str(m.Name) };
    case "IfcMaterialLayerSetUsage":
      return readMaterial(r, ref(m.ForLayerSet), depth + 1);
    case "IfcMaterialLayerSet":
      return { ...readMaterial(r, first(m.MaterialLayers), depth + 1) };
    case "IfcMaterialLayer":
    case "IfcMaterialLayerWithOffsets":
      return readMaterial(r, ref(m.Material), depth + 1);
    case "IfcMaterialProfileSetUsage":
    case "IfcMaterialProfileSetUsageTapering":
      return readMaterial(r, ref(m.ForProfileSet), depth + 1);
    case "IfcMaterialProfileSet": {
      const inner = readMaterial(r, first(m.MaterialProfiles), depth + 1);
      return { ...inner, profileSetName: inner.profileSetName ?? str(m.Name) };
    }
    case "IfcMaterialProfile":
    case "IfcMaterialProfileWithOffsets":
      return {
        name: readMaterial(r, ref(m.Material), depth + 1).name,
        profileDefId: ref(m.Profile),
        profileSetName: str(m.Name),
      };
    case "IfcMaterialConstituentSet":
      return readMaterial(r, first(m.MaterialConstituents), depth + 1);
    case "IfcMaterialConstituent":
      return readMaterial(r, ref(m.Material), depth + 1);
    case "IfcMaterialList":
      return readMaterial(r, first(m.Materials), depth + 1);
    default:
      return {};
  }
}
