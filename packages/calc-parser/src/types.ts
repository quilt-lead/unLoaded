/**
 * Data contract of the calc pipeline. Field names follow the Python prototype
 * (prototyping/calc-graph/backend/calcgraph) so its JSON stays readable by this
 * package and golden outputs compare one-to-one.
 */

/** [x0, y0, x1, y1] in PDF points, top-left origin. */
export type Rect = [number, number, number, number];

/** [x0, y0, x1, y1, start, end]: a word's box and its [start, end) span in the page text. */
export type WordBox = [number, number, number, number, number, number];

export interface CalcPage {
  /** 1-based page number. */
  n: number;
  /** Text rebuilt line by line from word boxes grouped by baseline. */
  text: string;
  words: WordBox[];
  width: number;
  height: number;
  /** Number of images drawn on the page. */
  images: number;
}

export interface CalcPackage {
  pages: CalcPage[];
  meta: { page_count: number; title: string };
}

/** Element categories the matcher reasons about (from IFC type, see `catOf`). */
export type ElementCat =
  | 'Beam'
  | 'Column'
  | 'Slab'
  | 'Footing'
  | 'Pile'
  | 'Wall'
  | 'Brace'
  | 'Connection'
  | 'Other';

/** Calc categories (keyword-classified). Empty string = unknown. */
export type CalcCat = Exclude<ElementCat, 'Other'> | '';

/** The element fields the matcher needs. */
export interface CalcElement {
  global_id: string;
  cat: ElementCat | (string & {});
  mark: string;
  profile: string;
  storey: string;
  name?: string;
}

export interface Calc {
  /** Stable, unique within the package: slug of the title, or `scanned-<n>`. */
  key: string;
  title: string;
  software: string;
  cat: CalcCat;
  pages: number[];
  /** No text layer (scanned / handwritten). Never mapped. */
  scanned: boolean;
  /** Front matter / contents. Never mapped. */
  front: boolean;
  /** Concatenated page text (each page prefixed with "\n"). */
  text: string;
  /** Set by the matcher: pages-level hits on a mark rule. */
  mark_hits?: number;
}

export type LinkTier = 'exact' | 'range' | 'loose' | 'family' | 'size' | 'partial' | 'xref' | 'type' | 'manual';
export type LinkStatus = 'auto' | 'confirmed' | 'rejected' | 'manual';

export interface Snippet {
  before: string;
  match: string;
  after: string;
}

export interface CalcLink {
  global_id: string;
  calc_key: string;
  /** Confidence 0..1. */
  conf: number;
  tier: LinkTier;
  /** Plain-language reason. */
  rule: string;
  page: number | null;
  /** [start, end) in the page text. */
  span: [number, number] | null;
  token: string;
  snippet: Snippet | null;
  /** Highlight boxes on the page, merged per line. */
  rects: Rect[];
  status?: LinkStatus;
  decided_at?: string;
  decided_by?: string | null;
}

export interface CalcEdgeEvidence {
  calc: string;
  page: number | null;
  text: string;
  line?: string;
  global_id?: string;
  rects: Rect[];
}

/** Calc dependency: output of `src` feeds the input of `dst`. */
export interface CalcEdge {
  src: string;
  dst: string;
  rules: string[];
  evidence: CalcEdgeEvidence[];
}

/** Load-path edge: `src` carries load to `dst`. */
export interface LoadEdge {
  src: string;
  dst: string;
}

export type DecisionAction = 'confirm' | 'reject' | 'manual' | 'undo';

/** A human review decision, keyed by (GlobalId, calc key) so it survives re-imports. */
export interface Decision {
  global_id: string;
  calc_key: string;
  action: DecisionAction;
  at: string;
  actor?: string | null;
  note?: string | null;
}

export type ImpactMode = 'change' | 'remove';

export interface ImpactResult {
  global_id: string;
  mode: ImpactMode;
  /** Removed elements (the element itself, connections that only served it, orphans). */
  removed: string[];
  /** Hit element -> wave number (0 = seed). */
  hit: Record<string, number>;
  why: Record<string, string>;
  /** Stale calc key -> reason. */
  stale: Record<string, string>;
  waves: number;
}
