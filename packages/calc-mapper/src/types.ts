/**
 * @unloaded/calc-mapper - public data types. Pure data (JSON-serialisable), no classes.
 *
 * These are the SAME shapes the retired Python backend returned (backend/calcgraph/api.py:
 * /export, /compare, /impact, the /state pieces, the decision log), plus `connectivity` on the
 * export, so a client that read those routes reads these unchanged. Snake_case field names are
 * kept on purpose for that reason.
 *
 * Coordinates: PDF points, origin top-left, y down (as PyMuPDF and the backend reported them).
 */
import type { SerializedElementGraph } from "@unloaded/element-graph";

export type { SerializedElementGraph };

export const ENGINE_VERSION = "mapper-v1.0" as const;

// ---------------------------------------------------------------- PDF text

/** One word on a page: [x0, y0, x1, y1, start, end] - box in PDF points, [start, end) = its span in page.text. */
export type WordBox = [number, number, number, number, number, number];
/** [x0, y0, x1, y1] in PDF points. */
export type Rect = [number, number, number, number];

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
}

export interface PdfText {
  pages: CalcPage[];
  meta: { page_count: number; title: string };
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
}

/** A segmented calc package: its pages + calcs (`segmentCalcs(extractPdf(bytes).pages)`). */
export interface CalcPackage {
  /** File name shown in exports, e.g. "calc_package.pdf". */
  source_name: string | null;
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
  geom: { min: number[]; max: number[]; p1?: number[]; p2?: number[] } | null;
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

export interface Link {
  global_id: string;
  calc_key: string;
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
}

/** One mapping run of a (graph, calc package) pair: the auto links (status "auto") + calc edges. */
export interface MappingRun {
  engine: typeof ENGINE_VERSION;
  links: Link[];
  calc_edges: CalcEdge[];
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
}

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
}

export interface Export {
  model: string | null;
  model_revision: string | number | null;
  calc_package: string | null;
  calc_revision: string | number | null;
  engine: typeof ENGINE_VERSION;
  producers: Record<string, unknown>;
  calcs: ExportCalc[];
  calc_edges: CalcEdge[];
  /** The graph's `supports` edges. */
  load_path: { src: string; dst: string; rule: string }[];
  /** The graph's `connects` edges. */
  connectivity: ConnectivityEdge[];
  elements: ExportElement[];
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
}
