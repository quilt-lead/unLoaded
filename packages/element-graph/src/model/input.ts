/**
 * ModelInput - the parser -> graph contract.
 *
 * Every model parser (IFC today; others later) produces a `ModelInput`.
 * `buildGraph()` in @unloaded/element-graph consumes it. This file is the ONLY
 * coupling between parsers and the graph: it is pure data (JSON-serialisable),
 * with no classes, no rendering types and no format-specific types.
 *
 * Conventions
 * - Units: metres, world coordinates, Z up. Parsers convert before emitting.
 * - Ids: stable across re-imports of the same source (e.g. IFC GlobalId). Never
 *   counters or array indices.
 * - Open-ended: `ElementKind`, relation `kind` and `params` accept values beyond
 *   the well-known ones, so new element / connection types need no schema change.
 * - Parsers report what the source states. Geometry-based connectivity inference
 *   is the graph's job, not the parser's.
 */

export const MODEL_INPUT_VERSION = 1 as const;

/** Well-known element kinds. Any other string is allowed (open set). */
export const KNOWN_ELEMENT_KINDS = [
  "beam",
  "column",
  "slab",
  "wall",
  "footing",
  "pile",
  "brace",
  "connection",
  "fastener",
  "other",
] as const;
export type KnownElementKind = (typeof KNOWN_ELEMENT_KINDS)[number];
/** `(string & {})` keeps autocomplete for known kinds while allowing any string. */
export type ElementKind = KnownElementKind | (string & {});

/** [x, y, z] in metres. */
export type Vec3 = [number, number, number];

export interface BBox {
  min: Vec3;
  max: Vec3;
}

/**
 * Minimal geometry the graph needs for connectivity inference.
 * Physical geometry (meshes) stays with the source / viewer, never here.
 */
export interface GeometrySummary {
  /** World-space axis-aligned bounding box. */
  bbox: BBox;
  /**
   * Analytical centreline for linear members (beam, column, brace, pile).
   * For columns `start` is the bottom end; otherwise order is arbitrary.
   */
  axis?: { start: Vec3; end: Vec3 };
  /** Optional cross-section depth/width in metres when known. */
  section?: { depth?: number; width?: number };
}

export type ParamValue = string | number | boolean | null;

/** Where a node or relation came from in the source file. */
export interface SourceRef {
  /** e.g. "ifc". Open set. */
  format: "ifc" | (string & {});
  /** Original file name, if known. */
  file?: string;
  /** Native id in the source (IFC express id, row number, ...). Not stable - use for lookup only. */
  nativeId?: string | number;
  /** Native entity type, e.g. "IfcBeam". */
  nativeType?: string;
}

export interface ElementInput {
  /** Stable id, e.g. IFC GlobalId. Unique within a ModelInput. */
  id: string;
  kind: ElementKind;
  /** Piece / design mark, e.g. "B101", "C2012". Used for calc mapping later. */
  mark?: string;
  name?: string;
  /** Normalised section designation, e.g. "W12X26", "HSS6X6X3/8", "600X300". */
  profile?: string;
  material?: string;
  /** Id of a LevelInput this element is contained in. */
  levelId?: string;
  /**
   * Open parameter bag. Keys namespaced by origin, e.g. "Pset_BeamCommon.Span",
   * "Qto_BeamBaseQuantities.Length", "Attr.ObjectType".
   */
  params: Record<string, ParamValue>;
  geometry?: GeometrySummary;
  source: SourceRef;
}

/** Well-known relation kinds. Any other string is allowed. */
export const KNOWN_RELATION_KINDS = ["connects", "supports", "part_of"] as const;
export type KnownRelationKind = (typeof KNOWN_RELATION_KINDS)[number];
export type RelationKind = KnownRelationKind | (string & {});

export interface RelationEvidence {
  /** Human-readable rule, e.g. "IfcRelConnectsElements", "beam end bears on column". */
  rule: string;
  /** "explicit" = stated by the source file; "inferred" = derived (graph-side only). */
  source: "explicit" | "inferred";
  /** Rule-specific detail, e.g. { gap_m: 0.004 } or { ifcRelId: 123 }. */
  detail?: Record<string, ParamValue>;
}

/**
 * A relation between two elements.
 * - "connects": undirected physical connectivity.
 * - "supports": directed load path; `a` is SUPPORTED BY `b` (load flows a -> b).
 * - "part_of":  directed; `a` is a part of assembly `b` (e.g. bolt part of a connection).
 */
export interface RelationInput {
  a: string;
  b: string;
  kind: RelationKind;
  evidence: RelationEvidence;
}

export interface LevelInput {
  id: string;
  name: string;
  /** Metres. */
  elevation: number;
}

export interface ModelMeta {
  /** Contract version of this object. */
  version: typeof MODEL_INPUT_VERSION;
  /** Source schema, e.g. "IFC4", "IFC2X3". */
  schema?: string;
  project?: string;
  units: "m";
  source: SourceRef;
}

export interface ModelInput {
  meta: ModelMeta;
  levels: LevelInput[];
  elements: ElementInput[];
  relations: RelationInput[];
  /** Non-fatal parse issues (unknown types, missing geometry, ...). */
  warnings: string[];
}

/** Implemented by every parser package so formats are interchangeable. */
export interface ModelParser<Options = unknown> {
  /** e.g. "ifc". */
  readonly id: string;
  /** File extensions handled, lower-case without dot, e.g. ["ifc"]. */
  readonly extensions: readonly string[];
  /** Cheap sniff on name and/or first bytes. */
  canParse(fileName: string, head?: Uint8Array): boolean;
  parse(data: Uint8Array, options?: Options & { fileName?: string }): Promise<ModelInput>;
}
