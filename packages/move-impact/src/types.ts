/**
 * @unloaded/move-impact - public data types. Pure data (JSON-serialisable), no classes.
 *
 * Inputs: a serialized element graph (Carl's `@unloaded/element-graph`, metres, Z up, ids = IFC
 * GlobalIds), a move, and OPTIONAL calc facts (values a calc states, with where it states them)
 * and calc links (`@unloaded/calc-mapper` `Link`s). Everything that depends on calc facts is
 * absent from the output when no facts are given; nothing is invented to fill the gap.
 *
 * Every number that is not read straight from the model or a calc is an ESTIMATE and says so:
 * `method: "estimate"` plus `scaledBy` (what it was scaled by). Nothing here is a recalculation.
 *
 * Shared contracts are calc-mapper's, not redefined here: physical values are its `Quantity`
 * (closed unit set, `convert()`), rects are its `SheetRect`, and every output record carries its
 * `Provenance` shape (producer "move-impact@<version>/<module>", rule, method, input sha256s).
 */
import type { SerializedElementGraph } from "@unloaded/element-graph";
import type { Link, Provenance, Quantity, SheetRect, Unit } from "@unloaded/calc-mapper/types";

export type { SerializedElementGraph, Link, Provenance, Quantity, SheetRect, Unit };

export const ENGINE_VERSION = "move-impact-v1.0" as const;

// ---------------------------------------------------------------- provenance

/** The modules of this package that produce records. */
export type MoveImpactModule = "impact" | "health";
/** "move-impact@0.1.0/impact". */
export type MoveImpactProducer = `move-impact@${string}/${MoveImpactModule}`;
/**
 * calc-mapper's `Provenance`, with this package as the producer. calc-mapper's `Producer` type only
 * admits its own modules, so the producer field is narrowed here; every other field (rule, method,
 * inputs - lowercase sha256, validated by calc-mapper's `inputList`) is calc-mapper's.
 */
export type MoveImpactProvenance = Omit<Provenance, "producer"> & { producer: MoveImpactProducer };

// ---------------------------------------------------------------- the move

/** Move a column in plan by (dx, dy) metres, or remove it. `column` is the element (GlobalId). */
export type Move =
  | { column: string; dx: number; dy: number; remove?: false }
  | { column: string; remove: true };

// ---------------------------------------------------------------- calc facts (optional input)

/**
 * Where a calc states a value: the calc (calc-mapper `Calc.key`), the page, the highlight rect(s)
 * (calc-mapper `SheetRect`), and the sha256 of the calc package's bytes (calc-mapper's
 * `CalcPage.doc_sha256`) - it goes into the provenance inputs of everything derived from the row.
 */
export interface CalcSource {
  calcKey: string;
  page: number | null;
  rects: SheetRect[];
  documentSha256: string;
}

/** Load components as a calc states them. `live` on a reaction is "L + Lr only" (the engine puts it
 * in the roof-live slot for a member at the roof level, as the hackathon did). */
export interface LoadComponents {
  dead?: Quantity;
  live?: Quantity;
  roofLive?: Quantity;
}

/** One check a calc row states: demand against capacity (and/or the ratio it prints). */
export interface StatedCheck {
  mode: CheckMode;
  demand?: Quantity;
  capacity?: Quantity;
  /** The printed ratio (demand / capacity, or deflection / allowable). */
  utilisation?: number;
}

export type CheckMode =
  | "flexure"
  | "shear"
  | "deflection_live"
  | "deflection_total"
  | "axial"
  | "bearing"
  | "connection"
  | "drift"
  | "combined"
  | (string & {});

/**
 * What the calc is about, in the engine's terms. A matcher reads it from the calc title / table
 * (e.g. "Gravity Beam Design", "Spread footing schedule", "Typical shear tab capacities").
 */
export type FactKind =
  | "beam"
  | "column"
  | "footing"
  | "connection"
  | "typical_detail"
  | "brace"
  | "frame"
  | "frame_girder"
  | "collector"
  | "seismic"
  | "other";

/**
 * The values ONE calc row states about the element(s) it designs. Every field but `id`, `kind`,
 * `elements` and `source` is optional: give what the calc prints, leave the rest out.
 *
 * Compatible with calc-mapper output: `source.calcKey` is a `Calc.key`, `elements` are the
 * `Link.global_id`s the row is linked to, `source.page` / `rects` are the link's evidence.
 */
export interface CalcFact {
  /** Stable id of the calc row (unique across facts), e.g. "<calcKey>#<row>". */
  id: string;
  kind: FactKind;
  /** Element ids (GlobalIds) the row designs. Empty for a type-level row (a typical detail). */
  elements: string[];
  source: CalcSource;
  /** Gravity or lateral system calc (a lateral calc on a column makes it part of that system). */
  role?: "gravity" | "lateral";
  /** The lateral system / frame line the row belongs to (e.g. "SMF-A"). */
  group?: string;

  /** Governing utilisation / unity check as printed. */
  utilisation?: number;
  /** Governing demand and capacity as printed (used when utilisation is not printed). */
  demand?: Quantity;
  capacity?: Quantity;
  /** Which check governs, as printed. */
  governs?: CheckMode;
  checks?: StatedCheck[];

  span?: Quantity;
  tributaryWidth?: Quantity;
  /** Uniform line load on a beam (e.g. "Uniform Load: D = 0.203, L = 0.65 k/ft"). */
  lineLoad?: LoadComponents;
  /** Unfactored end reactions by component (end "i" = axis start, "j" = axis end) and the
   * factored maximum the row prints. */
  reactions?: { i?: LoadComponents; j?: LoadComponents; factoredI?: Quantity; factoredJ?: Quantity };
  /** Factored axial load (column Pu, brace Pu). */
  axial?: Quantity;
  /** Footing: unfactored service column load, allowable bearing pressure, plan width. */
  serviceLoad?: Quantity;
  allowableBearing?: Quantity;
  width?: Quantity;
  /** Connection / typical detail: detail type (e.g. "ST-4"), bolts in the row (typical detail). */
  detailType?: string;
  bolts?: number;
  /** The governing load combination as printed (e.g. "1.2D+1.6L+0.5Lr", "LC2", or a seismic one:
   * "OM", "S1".."S4", anything naming E / Omega). Used to factor a gravity change on a column. */
  combination?: string;
  /** Seismic (ELF) row: printed Cs, R, Ie and the system name - SDS >= Cs R / Ie (a lower bound). */
  seismic?: { cs: number; r: number; ie?: number; system?: string };
  /** AISC 341 F2.3 chevron check printed for a braced-frame girder (frame_girder rows). */
  chevron?: {
    unbalancedLoad: Quantity;
    gravityMoment: Quantity;
    axial: Quantity;
    axialCapacity: Quantity;
    momentCapacity: Quantity;
    equation: "H1-1a" | "H1-1b";
  };
}

/**
 * Section properties for a profile designation, from a published shape table the caller supplies
 * (the package ships none). Optional: without them the engine takes the documented bounds instead
 * (bolt-row limit with flange thickness 0; brace pair taken as rigid).
 */
export interface SectionProps {
  /** Length unit of every property (areas / moduli / inertias are its powers). */
  unit: "in" | "mm";
  /** depth, flange thickness (unit), area (unit^2), strong-axis moment of inertia (unit^4) */
  d?: number;
  tf?: number;
  A?: number;
  Ix?: number;
  /** for the flexure capacity ratio at a changed unbraced length (AISC 360 F2 / F3): flange width,
   * plastic / elastic modulus (unit^3), ry, rts, ho (unit), torsion constant J (unit^4) */
  bf?: number;
  Zx?: number;
  Sx?: number;
  ry?: number;
  rts?: number;
  ho?: number;
  J?: number;
}

/** A link as the engine needs it: calc-mapper's `Link` (rejected links are ignored). */
export type CalcLink = Pick<Link, "global_id" | "calc_key"> & Partial<Pick<Link, "status" | "page" | "rects">>;

export interface ImpactInput {
  graph: SerializedElementGraph;
  /** sha256 of the graph's canonical JSON (calc-mapper `sha256Json(graph)`): a provenance input. */
  graphSha256: string;
  move: Move;
  facts?: CalcFact[];
  links?: CalcLink[];
  /** Profile designation (as the model names it, e.g. "W18X40") -> section properties. */
  sections?: Record<string, SectionProps>;
}

// ---------------------------------------------------------------- output

export interface Reason {
  element: string;
  reason: string;
  /** Element chain from the moved column to this element. */
  chain: string[];
}

export interface TopoElement {
  element: string;
  kind: string;
  name: string | null;
  reasons: string[];
  chain: string[];
  provenance: MoveImpactProvenance;
}

export interface MemberGeometry {
  element: string;
  /** Analytical plan endpoints (metres) before / after. */
  before: { p1: [number, number]; p2: [number, number] };
  after: { p1: [number, number]; p2: [number, number] };
  why: string;
  /** End -> new support element when the member re-frames. */
  reframe?: Record<"i" | "j", string>;
}

/** One governing-geometry quantity that changes, with before / after numbers and their ratio. */
export interface GeometryChange {
  quantity:
    | "span"
    | "moment"
    | "shear"
    | "deflection_live"
    | "deflection_total"
    | "end_reaction_i"
    | "end_reaction_j"
    | "column_load"
    | "footing_load"
    | "connection_reaction"
    | "brace_force"
    | "tributary_width";
  /** Unit "1" = a relative magnitude (unit area load, or a deflection with EI = 1): compare ratios only. */
  before: Quantity;
  after: Quantity;
  /** after / before (Infinity when before is 0 and after is not; serialises as null). */
  ratio: number;
  /** "stated loads" = the calc's line loads / reactions; "unit area load" = geometry only. */
  basis: "stated loads" | "unit area load" | "geometry";
}

export interface ScreenedElement {
  element: string;
  kind: string;
  name: string | null;
  /** The quantity the 5 % screen was decided on and its change. */
  governing: GeometryChange | null;
  changes: GeometryChange[];
  /** True when the screen could not compute a change and kept the element because topology says
   * it is on the path (the hackathon's rule). */
  keptWithoutEstimate: boolean;
  provenance: MoveImpactProvenance;
}

export interface Estimate {
  element: string;
  method: "estimate";
  /** What the printed value was scaled by, in words, e.g. "flexure x moment ratio 1.21 (local statics, stated loads)". */
  scaledBy: string;
  utilisationBefore: number | null;
  utilisationAfter: number;
  governs: string | null;
  source: CalcSource;
  fact: string;
  provenance: MoveImpactProvenance;
  /** Footing: required plan width from the stated allowable bearing (estimate). */
  requiredWidth?: Quantity;
  /** Connection: next typical detail whose capacity covers the new end reaction, or null. */
  nextTypical?: string | null;
  special?: boolean;
  why?: string;
  /** Braced-frame girder: in-frame (F2.3 / frame combo) estimate beside the gravity one. */
  frameUtilisationBefore?: number;
  frameUtilisationAfter?: number;
}

export type Band = "easy" | "moderate" | "hard" | "do-not-move";
export const BANDS: Band[] = ["easy", "moderate", "hard", "do-not-move"];

export interface Health {
  band: Band;
  score: number;
  reasons: { band: Band; reason: string; factor: string }[];
  worstUtilisation: number | null;
  method: "estimate";
  provenance: MoveImpactProvenance;
}

export interface StaleCalc {
  /** calc-mapper calc key. */
  calcKey: string;
  /** Calc rows (fact ids) on the affected elements, when facts are supplied. */
  rows: string[];
  elements: string[];
  screened: boolean;
  reasons: string[];
  provenance: MoveImpactProvenance;
}

export interface StaleRow {
  fact: string;
  calcKey: string;
  screened: boolean;
  elements: string[];
  provenance: MoveImpactProvenance;
}

export interface Clash {
  a: string;
  b: string;
  kind: "footing-footing" | "footing-grade_beam";
}

export interface ImpactResult {
  engine: typeof ENGINE_VERSION;
  move: Move;
  /** sha256 of every input document the result rests on: the graph, then each calc package the facts came from. */
  inputs: string[];
  /** Elements reachable from the moved column through supports / connection nodes, with why. */
  topological: TopoElement[];
  /** Of those, the ones whose governing geometry changes > 5 % (or that the screen kept). */
  screened: ScreenedElement[];
  geometry: MemberGeometry[];
  clashes: Clash[];
  lateral: string[];
  notes: string[];
  /** Data gaps the engine worked around (said, not hidden). */
  assumptions: string[];
  /** Present only with calc facts. */
  estimates?: Record<string, Estimate>;
  /** Present only with calc facts that allow it. */
  health?: Health;
  /** Present only with facts or links: calcs linked to affected elements. */
  stale?: StaleCalc[];
  /** Present only with facts: calc rows on topological elements and whether the screen keeps them. */
  staleRows?: StaleRow[];
  labels: Record<string, string>;
}
