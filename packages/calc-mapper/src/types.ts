/**
 * @unloaded/calc-mapper - public data types. Pure data (JSON-serialisable), no classes.
 *
 * These are the SAME shapes the retired Python backend returned (backend/calcgraph/api.py:
 * /export, /compare, /impact, the /state pieces, the decision log), plus `connectivity` on the
 * export, so a client that read those routes reads these unchanged. Snake_case field names are
 * kept on purpose for that reason.
 *
 * Auditability contract (additive to those shapes: fields were added, none renamed or removed):
 * - PROVENANCE (provenance.ts) is a REQUIRED field on every Link, GroupLink, CalcEdge, Calc,
 *   Finding, Impact and Decision: producer "calc-mapper@<version>/<module>", rule id, method
 *   ("rule" | "human" | "estimate") and the sha256 of each input document it rests on.
 * - PRODUCER RECORDS per mapping run (`MappingRun.producers`, `Export.producers`): who produced
 *   the element graph and the engine, and the sha256 of the graph JSON and of the PDF bytes.
 * - UNITS (units.ts): a physical quantity is a `Quantity { value, unit }` over a fixed unit set.
 * - FRAMES (frames.ts): rects are `SheetRect` (PDF points on a page, origin top-left, y down);
 *   graph geometry is `ModelPointM` (world metres). Type-level brands; JSON stays plain numbers.
 */
import type { SerializedElementGraph } from "@unloaded/element-graph";
import type { ModelPointM, SheetRect } from "./frames.ts";
import type { Provenance } from "./provenance.ts";
import type { Quantity } from "./units.ts";

export type { SerializedElementGraph };
export type { CalcMapperModule, CalcMapperProducer, Producer, Provenance, ProvenanceMethod } from "./provenance.ts";
export type { Dim, Quantity, Unit } from "./units.ts";
export type { BuildingPointFt, Framed, ModelPointM, SheetRect } from "./frames.ts";

/** The mapping engine's version. Bumped to v1.1 with the provenance contract, so a stored run made before it is recomputed. */
export const ENGINE_VERSION = "mapper-v1.1" as const;

// ---------------------------------------------------------------- PDF text

/** One word on a page: [x0, y0, x1, y1, start, end] - box in PDF points, [start, end) = its span in page.text. */
export type WordBox = [number, number, number, number, number, number];
/** [x0, y0, x1, y1] in PDF points on one calc page: the sheet frame (frames.ts). Every rect in these types is one. */
export type Rect = SheetRect;

export interface CalcPage {
  /** 1-based page number. */
  n: number;
  /** Text rebuilt line by line from word boxes (words joined by " ", lines by "\n"). */
  text: string;
  words: WordBox[];
  width: number;
  height: number;
  /** No text layer (< 25 characters of text): a scan / hand calc. Never mapped. */
  scanned: boolean;
  /** sha256 of the PDF's bytes: the document this page is a page of (with `n`, the page's sheet frame). */
  doc_sha256: string;
}

export interface PdfText {
  pages: CalcPage[];
  /** `sha256`: of the PDF's bytes (WebCrypto). */
  meta: { page_count: number; title: string; sha256: string };
}

// ---------------------------------------------------------------- calcs (segmentation)

export interface TitleBox {
  page: number;
  rects: Rect[];
  span: [number, number] | null;
  rule: string;
  note: string;
}

export type ElementCategory =
  | "Beam" | "Column" | "Slab" | "Wall" | "Footing" | "Pile" | "Brace" | "Connection" | "Other";

/**
 * A region of one page that belongs to a calc: the page's text range [start, end) and the box
 * around it (PDF points; full page width). A region can start mid-page (a calc titled half way
 * down a sheet) and end mid-page (the next calc starts below it).
 */
export interface CalcRegion {
  page: number;
  rect: Rect;
  start: number;
  end: number;
}

/** Consecutive regions that read on from one to the next (page bottom -> next page top). A gap starts a new span. */
export interface CalcSpan {
  regions: CalcRegion[];
}

export interface Calc {
  /** Stable key: slug of the title (scanned runs: scanned-<n>), de-duplicated with -2, -3 ... */
  key: string;
  /** Position in the package. */
  ord: number;
  title: string;
  software: string;
  /** Element category the calc designs ("" when the title / line under it names none). */
  cat: ElementCategory | "";
  pages: number[];
  scanned: boolean;
  /** Front matter / contents page. Never mapped. */
  front: boolean;
  title_box: TitleBox;
  /** Hash of title + text (what the store used to detect a changed calc between packages). */
  content_hash: string;
  /** The calc as ordered spans of page regions (`pages` stays: the distinct pages, in order). */
  spans: CalcSpan[];
  /** Which segmentation rule made this calc, resting on the PDF. */
  provenance: Provenance;
}

/** A segmented calc package: its pages + calcs (`segmentCalcs(extractPdf(bytes).pages)`). */
export interface CalcPackage {
  /** File name shown in exports, e.g. "calc_package.pdf". */
  source_name: string | null;
  /** sha256 of the PDF's bytes (every page's `doc_sha256`). */
  source_sha256: string;
  pages: CalcPage[];
  calcs: Calc[];
}

// ---------------------------------------------------------------- elements (from the graph)

/** An element row read from a serialized element graph node (see elements.ts for the mapping). */
export interface ElementRow {
  global_id: string;
  express_id: number | string | null;
  ifc_type: string;
  cat: ElementCategory;
  mark: string;
  name: string;
  type_name: string;
  profile: string;
  storey: string;
  params: Record<string, string | number | boolean | null>;
  /** Bounding box + axis, in the graph's world metres. */
  geom: { min: ModelPointM; max: ModelPointM; p1?: ModelPointM; p2?: ModelPointM } | null;
  /** Hash of the fields a revision diff compares (diff.ts). */
  content_hash: string;
}

export type ElementStatus = "confirmed" | "review" | "unmapped";

export interface ElementState extends ElementRow {
  status: ElementStatus;
}

/** A `supports` edge of the graph: src is supported by dst (load flows src -> dst). */
export interface LoadPathEdge {
  src: string;
  dst: string;
  kind: "supports";
  /** First evidence rule of the graph edge. */
  rule: string;
  gap_m: number | null;
  /** `gap_m` as a quantity (metres). */
  gap: Quantity<"m"> | null;
}

/** A `connects` edge of the graph (undirected, a < b). */
export interface ConnectivityEdge {
  a: string;
  b: string;
  rule: string;
  /** Any evidence stated by the source file (e.g. IfcRelConnectsElements). */
  explicit: boolean;
}

// ---------------------------------------------------------------- links (mapping)

export type Tier = "exact" | "range" | "loose" | "family" | "size" | "partial" | "xref" | "type" | "manual";
export type LinkReview = "auto" | "confirmed" | "rejected" | "manual";

export interface Snippet {
  before: string;
  match: string;
  after: string;
}

/** Does the calc size the element, or only take loads from / refer to it? */
export type LinkRole = "design" | "loads";
export type ConfidenceBand = "high" | "medium" | "low";

/**
 * One item of evidence behind a link. A link's confidence is the sum of its evidence weights,
 * clamped to [0, 1]. The first item is always the matching tier (kind "tier"), so tier metrics
 * still compute; negative weights are evidence against (a size or storey that contradicts the model).
 */
export interface LinkEvidence {
  kind: "tier" | "storey-match" | "storey-conflict" | "size-match" | "size-mismatch" | "loads-context" | "group" | "human" | (string & {});
  weight: number;
  note: string;
  page: number | null;
  rects: Rect[];
}

export interface Link {
  global_id: string;
  calc_key: string;
  /** Sum of `evidence` weights, clamped to [0, 1]. */
  conf: number;
  tier: Tier;
  rule: string;
  page: number | null;
  token: string;
  span: [number, number] | null;
  snippet: Snippet | null;
  rects: Rect[];
  status: LinkReview;
  decided_at?: string;
  decided_by?: string | null;
  role: LinkRole;
  band: ConfidenceBand;
  evidence: LinkEvidence[];
  /** Plain-language reasons to doubt the link (size / storey conflict, loads only, via a typical group ...). */
  caveats: string[];
  /** Set when the element is linked through its typical group (a size-only calc). */
  via_group?: string;
  /** Who / what rule made the link (matcher; a hand link: the decision). */
  provenance: Provenance;
  /** The human decision that set `status`, when one did (confirm / reject / manual). */
  review_provenance?: Provenance;
}

/** Elements of one size on one storey, of one kind: what a size-only ("W12X19 typ.") calc links to. */
export interface TypicalGroup {
  /** `group:<cat>:<storey>:<profile>` */
  id: string;
  cat: ElementCategory;
  storey: string;
  profile: string;
  /** Member GlobalIds, sorted. */
  members: string[];
  title: string;
}

/** A calc <-> typical group link (one per group, instead of a weak link fanned out to every member). */
export interface GroupLink {
  group: string;
  calc_key: string;
  conf: number;
  band: ConfidenceBand;
  tier: "size";
  role: LinkRole;
  rule: string;
  page: number | null;
  token: string;
  span: [number, number] | null;
  snippet: Snippet | null;
  rects: Rect[];
  evidence: LinkEvidence[];
  caveats: string[];
  provenance: Provenance;
}

/** Something the evidence says is wrong. Today: the calc designs a different size than the model has. */
export interface Finding {
  kind: "size-mismatch";
  global_id: string;
  calc_key: string;
  model_size: string;
  calc_size: string;
  page: number;
  span: [number, number];
  rects: Rect[];
  snippet: Snippet;
  note: string;
  provenance: Provenance;
}

export interface CalcEdgeEvidence {
  calc: string;
  page: number;
  text: string;
  line?: string;
  global_id?: string;
  rects?: Rect[];
}

/** Output of calc `src` feeds an input of calc `dst`. */
export interface CalcEdge {
  src: string;
  dst: string;
  rules: string[];
  evidence: CalcEdgeEvidence[];
  /** `rule`: the ids of `rules`, joined with "+". */
  provenance: Provenance;
}

/** Who produced each input of a mapping run, and the sha256 of each input document. */
export interface RunProducers {
  /** This engine. */
  calc_mapper: { producer: `calc-mapper@${string}`; engine: typeof ENGINE_VERSION };
  /** The element graph: producer from its format / version ("unloaded.element-graph@1"), sha256 of its canonical JSON. */
  element_graph: {
    producer: string;
    format: string;
    version: number;
    /** What the graph says it was built from (meta.source), e.g. { format: "ifc", file: "model.ifc" }. */
    source: unknown;
    sha256: string;
  };
  /** The calc package PDF: sha256 of its bytes. */
  calc_package: { name: string | null; sha256: string; pages: number };
}

/** One mapping run of a (graph, calc package) pair: the auto links (status "auto") + calc edges. */
export interface MappingRun {
  engine: typeof ENGINE_VERSION;
  links: Link[];
  calc_edges: CalcEdge[];
  groups: TypicalGroup[];
  group_links: GroupLink[];
  findings: Finding[];
  producers: RunProducers;
  /** The run's input documents: [element graph sha256, calc PDF sha256]. */
  inputs: string[];
}

// ---------------------------------------------------------------- decisions (append-only log)

export type DecisionAction = "confirm" | "reject" | "manual" | "undo";

export interface DecisionIn {
  global_id: string;
  calc_key: string;
  action: DecisionAction;
  actor?: string | null;
  note?: string | null;
}

/**
 * One human decision. The log is append-only and keyed by (global_id, calc_key) - not by
 * revision - so a decision carries forward to every later revision while both keys exist.
 * The latest decision per pair wins; "undo" clears the pair.
 */
export interface Decision extends DecisionIn {
  /** Monotonic within a log (ordering; the latest wins). */
  id: number;
  actor: string | null;
  note: string | null;
  /** ISO timestamp. */
  at: string;
  /** Revision labels the decision was made against (informational). */
  model_rev?: string | number | null;
  calc_rev?: string | number | null;
  /** method "human", rule "decision.<action>", actor + at; inputs: the documents it was made against, when known. */
  provenance: Provenance;
}

/**
 * A decision as a store or a decision-log file holds it: with or without its provenance (records
 * written before the contract lack one). The engine's entry points accept these and attach the
 * provenance the decision's own fields state (decisionFrom), so a Decision never lacks it.
 */
export type DecisionFields = Omit<Decision, "provenance"> & { provenance?: Provenance };

// ---------------------------------------------------------------- export (/export)

export interface ExportLink {
  calc: string;
  title: string;
  page: number | null;
  confidence: number;
  tier: Tier;
  rule: string;
  matched_text: string;
  review: LinkReview;
  evidence: { page: number | null; span: [number, number] | null; rects: Rect[]; snippet: Snippet | null };
  role: LinkRole;
  band: ConfidenceBand;
  /** The weighted evidence items (the `evidence` key above keeps the backend's location shape). */
  reasons: LinkEvidence[];
  caveats: string[];
  via_group?: string;
  provenance: Provenance;
  review_provenance?: Provenance;
}

export interface ExportElement {
  global_id: string;
  ifc_type: string;
  mark: string;
  storey: string;
  size: string;
  status: ElementStatus;
  calcs: ExportLink[];
}

export interface ExportCalc {
  key: string;
  title: string;
  software: string;
  element_type: ElementCategory | "";
  pages: number[];
  scanned: boolean;
  front_matter: boolean;
  title_box: TitleBox | null;
  spans: CalcSpan[];
  provenance: Provenance;
}

export interface Export {
  model: string | null;
  model_revision: string | number | null;
  calc_package: string | null;
  calc_revision: string | number | null;
  engine: typeof ENGINE_VERSION;
  producers: ExportProducers;
  calcs: ExportCalc[];
  calc_edges: CalcEdge[];
  /** The graph's `supports` edges. */
  load_path: { src: string; dst: string; rule: string }[];
  /** The graph's `connects` edges. */
  connectivity: ConnectivityEdge[];
  elements: ExportElement[];
  groups: TypicalGroup[];
  group_links: GroupLink[];
  findings: Finding[];
}

/**
 * The export's producer records. `model` and `mapping` are the original keys (kept); the rest were
 * added with the provenance contract and are optional only because export files written before it
 * lack them - buildExport always writes them.
 */
export interface ExportProducers {
  model?: { element_graph: { format: string; version: number; source: unknown } };
  mapping?: { "calc-mapper": string };
  calc_mapper?: RunProducers["calc_mapper"];
  element_graph?: RunProducers["element_graph"];
  calc_package?: RunProducers["calc_package"];
  /** The input documents every derived record rests on: [element graph sha256, calc PDF sha256]. */
  inputs?: string[];
  [key: string]: unknown;
}

/** Labels written into the export header (the backend's revision ids / file names). */
export interface ExportInfo {
  model?: string | null;
  model_revision?: string | number | null;
  calc_package?: string | null;
  calc_revision?: string | number | null;
}

// ---------------------------------------------------------------- state (/state pieces)

export interface CalcState extends Calc {
  /** Palette colour by calc order. */
  color: string;
}

/** The parts of the backend's /state the UI used, computed client-side. */
export interface ProjectState {
  elements: ElementState[];
  edges: LoadPathEdge[];
  calcs: CalcState[];
  pages: { n: number; text: string; scanned: boolean; width: number; height: number }[];
  /** Auto links with the decision log applied. */
  links: Link[];
  calc_edges: CalcEdge[];
  counts: Record<ElementStatus, number>;
  groups: TypicalGroup[];
  group_links: GroupLink[];
  /** Findings of links that are not rejected. */
  findings: Finding[];
}

// ---------------------------------------------------------------- compare (/compare)

export interface CompareChange {
  global_id: string;
  mark: string;
  /** Per changed field: [before, after]. Params by key; plus mark / profile / storey / type_name; "geometry". */
  fields: Record<string, [unknown, unknown]>;
}

export interface Compare {
  a: string | number;
  b: string | number;
  removed: { global_id: string; mark: string; cat: ElementCategory }[];
  added: { global_id: string; mark: string; cat: ElementCategory }[];
  changed: CompareChange[];
  /** Load-path (supports) edges as [src, dst]. */
  edges_removed: [string, string][];
  edges_added: [string, string][];
}

// ---------------------------------------------------------------- impact (/impact)

export type ImpactMode = "change" | "remove";

export interface Impact {
  global_id: string;
  mode: ImpactMode;
  removed: string[];
  /** Element -> wave (depth). A connection node and the member it bears on share a wave. */
  hit: Record<string, number>;
  why: Record<string, string>;
  /** Calc key -> reason it is stale. */
  stale: Record<string, string>;
  waves: number;
  provenance: Provenance;
}
