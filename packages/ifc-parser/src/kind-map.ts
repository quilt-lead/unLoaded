/**
 * IFC entity -> contract ElementKind mapping. This is the single source of
 * truth for which IFC entities are extracted and how they are classified.
 *
 * Resolution order for an element of IFC type `T` with predefined type `P`
 * (P = instance PredefinedType, or the type object's when the instance is
 * NOTDEFINED/USERDEFINED/absent):
 *   1. opts.kindMap["T.P"]        e.g. { "IfcMember.STUD": "column" }
 *   2. opts.kindMap["T"]          e.g. { "IfcChimney": "other" } (also adds new entity types)
 *   3. KIND_TABLE[T].byPredefined[P]
 *   4. KIND_TABLE[T].byName       regex over Name / ObjectType / type object name
 *   5. KIND_TABLE[T].kind
 * Entity types with no table row and no kindMap entry are skipped (and counted
 * in the warnings). Lookups are case-insensitive on the IFC type name.
 */
import type { ElementKind } from "@unloaded/element-graph/input";

export interface KindRule {
  /** Default kind for the entity. */
  kind: ElementKind;
  /** Overrides by PredefinedType (upper-case enum value without dots). */
  byPredefined?: Record<string, ElementKind>;
  /** First matching regex (tested against Name, ObjectType, type name) wins. */
  byName?: Array<[RegExp, ElementKind]>;
}

/** Names that mark a plate / proxy / assembly as a connection. */
export const CONNECTION_NAME_RE =
  /\b(conn(ection)?s?|shear[\s_-]*tab|base[\s_-]*plate|fin[\s_-]*plate|end[\s_-]*plate|cap[\s_-]*plate|splice|gusset|cleat|bracket|clip[\s_-]*angle|knee[\s_-]*brace[\s_-]*plate|hanger|beam[\s_-]*shoe|joist[\s_-]*hanger|anchor[\s_-]*plate)\b/i;

const MEMBER_BY_PREDEFINED: Record<string, ElementKind> = {
  BRACE: "brace",
  STRUT: "brace",
  CHORD: "beam",
  COLLAR: "beam",
  PURLIN: "beam",
  RAFTER: "beam",
  STRINGER: "beam",
  POST: "column",
  STUD: "other",
  MULLION: "other",
  PLATE: "other",
};

/** Keyed by IFC entity name as returned by web-ifc (CamelCase). */
export const KIND_TABLE: Record<string, KindRule> = {
  IfcBeam: { kind: "beam" },
  IfcBeamStandardCase: { kind: "beam" },
  IfcColumn: { kind: "column" },
  IfcColumnStandardCase: { kind: "column" },
  IfcSlab: { kind: "slab" },
  IfcSlabStandardCase: { kind: "slab" },
  IfcSlabElementedCase: { kind: "slab" },
  IfcRoof: { kind: "slab" },
  IfcWall: { kind: "wall" },
  IfcWallStandardCase: { kind: "wall" },
  IfcWallElementedCase: { kind: "wall" },
  IfcFooting: { kind: "footing" },
  IfcPile: { kind: "pile" },
  // Member defaults to brace; inclination is recorded as Geom.InclinationDeg.
  IfcMember: { kind: "brace", byPredefined: MEMBER_BY_PREDEFINED },
  IfcMemberStandardCase: { kind: "brace", byPredefined: MEMBER_BY_PREDEFINED },
  IfcPlate: { kind: "connection", byPredefined: { CURTAIN_PANEL: "other" } },
  IfcPlateStandardCase: { kind: "connection", byPredefined: { CURTAIN_PANEL: "other" } },
  IfcMechanicalFastener: { kind: "fastener" },
  IfcFastener: { kind: "fastener" },
  IfcDiscreteAccessory: { kind: "connection" },
  IfcElementAssembly: {
    kind: "other",
    byPredefined: { ACCESSORY_ASSEMBLY: "connection" },
    byName: [[CONNECTION_NAME_RE, "connection"]],
  },
  IfcBuildingElementProxy: {
    kind: "other",
    byName: [[CONNECTION_NAME_RE, "connection"]],
  },
  // IFC4x3 bearing devices behave like connections in the element graph.
  IfcBearing: { kind: "connection" },
};

/** Kinds that get an analytical axis (centreline) from geometry. */
export const LINEAR_KINDS: ReadonlySet<string> = new Set(["beam", "column", "brace", "pile"]);

/**
 * Element-ish entities that are never extracted and not worth a warning
 * (spatial structure, voids, annotations, ...). Lower-case names.
 */
export const IGNORED_TYPES: ReadonlySet<string> = new Set(
  [
    "IfcSite",
    "IfcBuilding",
    "IfcBuildingStorey",
    "IfcSpace",
    "IfcExternalSpatialElement",
    "IfcSpatialZone",
    "IfcOpeningElement",
    "IfcOpeningStandardCase",
    "IfcVoidingFeature",
    "IfcAnnotation",
    "IfcGrid",
    "IfcVirtualElement",
    "IfcFacility",
    "IfcFacilityPart",
    "IfcBridge",
    "IfcBridgePart",
    "IfcRoad",
    "IfcRoadPart",
    "IfcRailway",
    "IfcRailwayPart",
    "IfcMarineFacility",
    "IfcAlignment",
  ].map((s) => s.toLowerCase()),
);

export type KindMap = Partial<Record<string, ElementKind>>;

export interface KindInputs {
  ifcType: string;
  predefinedType?: string;
  names: Array<string | undefined>;
}

const lowerTable = new Map(Object.entries(KIND_TABLE).map(([k, v]) => [k.toLowerCase(), v]));

function lowerKeys(map: KindMap | undefined): Map<string, ElementKind> {
  const out = new Map<string, ElementKind>();
  if (!map) return out;
  for (const [k, v] of Object.entries(map)) if (v !== undefined) out.set(k.toLowerCase(), v);
  return out;
}

export interface KindResolver {
  /** True if the entity type is extracted at all. */
  handles(ifcType: string): boolean;
  /** Resolved kind plus whether a user override decided it. */
  resolve(input: KindInputs): { kind: ElementKind; overridden: boolean };
}

export function createKindResolver(kindMap?: KindMap): KindResolver {
  const overrides = lowerKeys(kindMap);
  const overrideTypes = new Set([...overrides.keys()].map((k) => k.split(".")[0]!));
  return {
    handles(ifcType) {
      const t = ifcType.toLowerCase();
      return lowerTable.has(t) || overrideTypes.has(t);
    },
    resolve({ ifcType, predefinedType, names }) {
      const t = ifcType.toLowerCase();
      const p = predefinedType?.toUpperCase();
      if (p) {
        const o = overrides.get(`${t}.${p.toLowerCase()}`);
        if (o !== undefined) return { kind: o, overridden: true };
      }
      const o = overrides.get(t);
      if (o !== undefined) return { kind: o, overridden: true };
      const rule = lowerTable.get(t);
      if (!rule) return { kind: "other", overridden: false };
      if (p && rule.byPredefined?.[p] !== undefined) return { kind: rule.byPredefined[p]!, overridden: false };
      if (rule.byName) {
        for (const [re, kind] of rule.byName) {
          if (names.some((n) => n !== undefined && re.test(n))) return { kind, overridden: false };
        }
      }
      return { kind: rule.kind, overridden: false };
    },
  };
}
