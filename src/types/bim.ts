// The VIEW MODEL every component consumes. Two adapters feed it and one function merges them:
//   ElementGraph (packages/element-graph) -> src/loaders/elementGraphToBim.ts -> ElementTopology
//   calc-mapper Export (Web Worker)       -> src/data/loadProject.ts          -> CalcData
//   mergeProject(topology, calc)          -> src/data/mergeProject.ts         -> ProjectViewModel
// Neither a calc-engine type (@unloaded/calc-mapper) nor an ElementGraph ever reaches a component.

export type WorkspaceView = 'element-graph' | 'calculation-graph' | '3d' | 'docs';
export type TraceDirection = 'down' | 'up' | 'both';
export type DockSide = 'float' | 'left' | 'right';

/** How elements are coloured in the graph and the 3D model. 'utilisation' needs element utilisation data. */
export type ColorMode = 'type' | 'review' | 'confidence' | 'utilisation';

/** Review state of one element <-> calc link (auto = proposed by the matcher, not yet reviewed). */
export type LinkReview = 'auto' | 'confirmed' | 'rejected' | 'manual';
/** Mapping state of an element across all its links. */
export type MappingStatus = 'confirmed' | 'review' | 'unmapped';
// The view model's own copy (no engine type reaches a component). src/data/projectStore.ts fails the
// typecheck if it ever differs from the engine's DECISION_ACTIONS, which the project file uses.
export type DecisionAction = 'confirm' | 'reject' | 'manual' | 'undo';

export type NodeKind =
  | 'project'
  | 'category' // element category = IFC type (IfcBeam, IfcColumn...)
  | 'family' // mark family inside a category (B, G, ST...)
  | 'element' // one IFC element (id = GlobalId)
  | 'calc-root'
  | 'calc-category' // calcs grouped by the element type they design
  | 'calc' // one calculation in the package (id = calcNodeId(key))
  | 'mapped-element'; // an element drawn beside its calc in the calc graph

/** [x0, y0, x1, y1] in PDF points, top-left origin. */
export type PdfRect = number[];

export interface LinkEvidence {
  page: number | null;
  rects: PdfRect[];
  snippet: { before: string; match: string; after: string } | null;
}

/** One element <-> calc link, as the matcher proposed it and the reviewer decided it. */
export interface CalcLink {
  elementId: string;
  calcKey: string;
  confidence: number; // 0..1
  tier: string; // exact | range | loose | family | partial | xref | size | type | manual
  rule: string; // the matcher rule, in words
  matchedText: string;
  review: LinkReview;
  evidence: LinkEvidence;
  /** does the calc size the element ('design') or only take loads from / mention it ('loads')? */
  role: LinkRole;
  band: ConfidenceBand;
  /** the weighted evidence the confidence is the sum of (first item = the matching tier) */
  reasons: LinkReason[];
  /** plain-language reasons to doubt the link */
  caveats: string[];
  /** set when the link comes through the element's typical group (a size-only calc) */
  viaGroup?: string;
  /** who / which rule made the link, on which input documents */
  provenance: ProvenanceView | null;
  /** the human decision behind its review state (confirm / reject / by hand), when there is one */
  reviewProvenance: ProvenanceView | null;
}

/** Why a record exists: the producing code, its rule, the method, and the sha256 of each input document. */
export interface ProvenanceView {
  producer: string;
  rule: string;
  method: 'rule' | 'human' | 'estimate';
  inputs: string[];
  actor: string | null;
  at: string | null;
}

/** Who produced the inputs of the mapping, and the sha256 of each input document. */
export interface ProducerRecords {
  engine: string;
  engineProducer: string | null;
  graph: { producer: string; source: string; sha256: string } | null;
  calcPackage: { name: string | null; sha256: string; pages: number } | null;
}

export type LinkRole = 'design' | 'loads';
export type ConfidenceBand = 'high' | 'medium' | 'low';

/** One weighted item of evidence behind a link (negative weight = evidence against). */
export interface LinkReason {
  kind: string; // tier | storey-match | storey-conflict | size-match | size-mismatch | loads-context | group | human ...
  weight: number;
  note: string;
  page: number | null;
  rects: PdfRect[];
}

/** Elements of one size on one storey, of one kind: what a size-only ("W12X19 typ.") calc links to. */
export interface TypicalGroupView {
  id: string;
  category: string;
  storey: string;
  profile: string;
  title: string;
  members: string[];
  links: {
    calcKey: string;
    confidence: number;
    band: ConfidenceBand;
    role: LinkRole;
    rule: string;
    page: number | null;
    rects: PdfRect[];
    caveats: string[];
  }[];
}

/** Something the evidence says is wrong: today, the calc designs a different size than the model has. */
export interface FindingView {
  kind: 'size-mismatch';
  elementId: string;
  calcKey: string;
  modelSize: string;
  calcSize: string;
  page: number;
  rects: PdfRect[];
  snippet: { before: string; match: string; after: string } | null;
  note: string;
}

/** A region of one page that belongs to a calc (can start or end mid-page). */
export interface CalcRegionView {
  page: number;
  rect: PdfRect;
}

export interface CalcPackage {
  key: string;
  title: string;
  software: string;
  elementType: string; // '' when the calc does not design one element type
  pages: number[];
  scanned: boolean;
  frontMatter: boolean;
  titleBox: { page: number; rects: PdfRect[] } | null;
  color: string;
  /** the calc as ordered regions of pages (a calc can start half way down a sheet); [] when unknown */
  regions: CalcRegionView[];
}

/** calc -> calc: the source calc's output feeds the target calc's input. */
export interface CalcDependency {
  source: string; // calc key
  target: string; // calc key
  rules: string[];
  evidence: { calcKey: string; page: number; text: string; line: string | null; rects: PdfRect[] }[];
}

/** element -> element on the gravity load path: `source` delivers load to `target`. */
export interface LoadPathEdge {
  source: string;
  target: string;
  rule: string;
}

/** A document attached to an element by a legacy demo JSON. Invented; not a calc, never matched. */
export interface DemoDocument {
  id: string;
  title: string;
  type: string;
  code: string;
  rev: string;
  pages: number | null;
  date: string;
  summary: string;
}

export interface BimNode {
  id: string;
  label: string;
  kind: NodeKind;
  level: number; // 0 project, 1 category, 1.5 family, 2 leaf
  parent?: string;
  categoryParent?: string;
  r: number;
  x: number;
  y: number;
  color?: string;
  desc?: string;
  // element nodes
  /** element-graph kind: beam, column, slab, connection, ... (categories, families and elements) */
  elementKind?: string;
  ifcType?: string;
  material?: string;
  storey?: string;
  storeyOrder?: number;
  mark?: string;
  size?: string;
  name?: string;
  typeName?: string;
  params?: Record<string, string>;
  mappingStatus?: MappingStatus;
  calcLinks?: CalcLink[]; // strongest first, rejected included
  /** world bbox from the element graph (metres, Z up): the 3D fallback when there is no IFC to mesh */
  bbox?: { min: [number, number, number]; max: [number, number, number] };
  /** invented documents carried by legacy demo JSON - shown labelled "demo data", never as calc links */
  demoDocuments?: DemoDocument[];
  /** demand / capacity, 0..1. No source provides it yet, so it is always undefined today. */
  utilization?: number;
  // calc / mapped-element nodes
  calcKey?: string;
  elementId?: string;
  link?: CalcLink;
  // revision diff (set only while a diff is active)
  diffStatus?: DiffStatus;
  diffChanges?: NodeDiffFieldChange[];
  /** a ghost: in the diff but not in the head model (geometry comes from its own revision) */
  isGhost?: boolean;
}

export type LinkRelation = 'hierarchy' | 'load-path' | 'calc-dependency' | 'calc-mapping';

export interface BimLink {
  source: string;
  target: string;
  relation: LinkRelation;
  /** calc-mapping links carry the review state they are styled by */
  review?: LinkReview;
  confidence?: number;
}

export interface RevisionInfo {
  id: number;
  kind: 'model' | 'calcs';
  seq: number;
  label: string;
  sourceName: string;
  createdAt: string;
  count: number | null;
  isHead: boolean;
  /** model revisions: the source file is an IFC (real meshes) rather than a JSON model (boxes) */
  isIfc: boolean;
}

/** physical connectivity between two elements (element-graph `connects` / `part_of`), undirected */
export interface ConnectivityEdge {
  source: string;
  target: string;
  kind: 'connects' | 'part_of';
  rule: string;
}

/** What the element graph says, as view data (built only by src/loaders/elementGraphToBim.ts). */
export interface ElementTopology {
  projectName: string;
  /** laid out: project -> kind category -> column stack / mark family -> element */
  elementNodes: BimNode[];
  hierarchyLinks: BimLink[];
  loadPath: LoadPathEdge[];
  connectivity: ConnectivityEdge[];
}

/** What the calc engine says, as view data (built only by src/data/loadProject.ts). */
export interface CalcData {
  projectName: string | null;
  modelName: string | null;
  modelRevisionId: number | null;
  calcPackageName: string | null;
  calcRevisionId: number | null;
  engine: string;
  calcs: CalcPackage[];
  calcDependencies: CalcDependency[];
  calcNodes: BimNode[];
  calcLinks: BimLink[];
  calcToElementIds: Map<string, string[]>;
  /** element GlobalId -> its links, strongest first (rejected included) */
  linksByElement: Map<string, CalcLink[]>;
  statusByElement: Map<string, MappingStatus>;
  groups: TypicalGroupView[];
  findings: FindingView[];
  producers: ProducerRecords | null;
}

/**
 * Where the open view came from: a project in the local store ('project', writable), or a plain
 * calc-graph export JSON opened from disk ('file', read-only).
 */
export type ProjectSource = 'project' | 'file';

export interface ProjectViewModel {
  source: ProjectSource;
  projectId: string | null;
  projectName: string;
  modelName: string | null;
  modelRevisionId: number | null;
  calcPackageName: string | null;
  calcRevisionId: number | null;
  engine: string;
  elementNodes: BimNode[];
  hierarchyLinks: BimLink[];
  loadPath: LoadPathEdge[];
  connectivity: ConnectivityEdge[];
  /** IFC file for the 3D view (an object URL of the model revision's IFC), null when there is none */
  modelFileUrl: string | null;
  calcs: CalcPackage[];
  calcDependencies: CalcDependency[];
  calcNodes: BimNode[];
  calcLinks: BimLink[];
  /** calc key -> element ids it is linked to (rejected links excluded) */
  calcToElementIds: Map<string, string[]>;
  groups: TypicalGroupView[];
  findings: FindingView[];
  producers: ProducerRecords | null;
  counts: Record<MappingStatus, number>;
  hasUtilization: boolean;
  /** some elements carry legacy demo documents (invented data, labelled as such) */
  hasDemoData: boolean;
}

export interface ImpactView {
  elementId: string;
  mode: 'change' | 'remove';
  removed: string[];
  hit: Map<string, number>; // element id -> wave
  why: Map<string, string>;
  stale: Map<string, string>; // calc key -> reason
  waves: number;
}

// ---- Revision diff (base model revision A vs compare model revision B). ONE implementation: the
// backend's GET /api/projects/{pid}/compare (key join on GlobalId + content hash), converted in
// src/data/loadProject.ts. The client never computes its own diff.
export type DiffStatus = 'added' | 'removed' | 'modified' | 'unchanged';

export interface NodeDiffFieldChange {
  field: string;
  before: string;
  after: string;
}

export interface NodeDiffMeta {
  status: DiffStatus;
  changes: NodeDiffFieldChange[];
}

export interface DatabaseDiffSummary {
  baseName: string;
  compareName: string;
  baseRevisionId: number;
  compareRevisionId: number;
  addedCount: number;
  removedCount: number;
  modifiedCount: number;
  unchangedCount: number;
  edgesAdded: number;
  edgesRemoved: number;
}

/** The backend diff as a view model: per-element status + field changes, and who exists only on one side. */
export interface ModelDiff {
  a: number;
  b: number;
  meta: Map<string, NodeDiffMeta>; // added / removed / modified elements by GlobalId
  onlyInA: { elementId: string; mark: string; category: string }[];
  onlyInB: { elementId: string; mark: string; category: string }[];
  edgesAdded: number;
  edgesRemoved: number;
  /** element-graph boxes of the elements only one side has (ghost geometry when there is no IFC) */
  ghostBoxes?: Map<string, { min: [number, number, number]; max: [number, number, number] }>;
}

/** Elements that are not in the head model but are part of the diff, drawn as ghosts from their own revision. */
export interface GhostSource {
  revisionId: number;
  elementIds: string[];
}

/** An impact check laid over the graphs and 3D model. */
export type HighlightTone = 'origin' | 'removed' | 'hit' | 'stale';
export interface HighlightOverlay {
  tones: Map<string, HighlightTone>; // element ids and calc node ids
}

/** What the PDF viewer should show: a calc page, optionally with evidence boxes. */
export interface PdfTarget {
  calcKey: string | null;
  page: number;
  rects: PdfRect[];
  caption?: string;
  /** a calc region on this page: zoomed to and outlined */
  region?: PdfRect;
}

export interface NodeGroup {
  id: string;
  name: string;
  nodeIds: string[];
}

export interface FilterState {
  search: string;
  type: string;
  level: string;
}
