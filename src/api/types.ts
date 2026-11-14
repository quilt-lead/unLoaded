// Response types of the backend routes this app uses (backend/calcgraph/api.py). Ported from the
// calc-graph prototype's frontend/src/api/types/projects.ts, trimmed to these routes.
//
// These are BACKEND shapes. Only src/api/* and src/data/loadProject.ts may import them; every
// component consumes the view model in src/types/bim.ts instead.
//
// Schema-shaped types (the /api/store/* bundles) are GENERATED into src/types/schema.ts from the
// Python models - never hand-edit that file.
export type * from '../types/schema';

export type LinkReview = 'auto' | 'confirmed' | 'rejected' | 'manual';
export type ElementStatus = 'confirmed' | 'review' | 'unmapped';
export type DecisionAction = 'confirm' | 'reject' | 'manual' | 'undo';

export interface ApiHealth {
  ok: boolean;
  store: string;
}

/** GET /api/projects (v1 columns) */
export interface ApiProject {
  id: number;
  name: string;
  created_at: string;
  head_model_rev: number | null;
  head_calc_rev: number | null;
}

export interface ApiSnippet {
  before: string;
  match: string;
  after: string;
}

// ---------------------------------------------------------------- GET /api/projects/{pid}/export

export interface ApiExportLink {
  calc: string;
  title: string;
  page: number | null;
  confidence: number;
  tier: string;
  rule: string;
  matched_text: string;
  review: LinkReview;
  evidence: {
    page: number | null;
    span: number[] | null;
    rects: number[][];
    snippet: ApiSnippet | null;
  };
}

export interface ApiExportElement {
  global_id: string;
  ifc_type: string;
  mark: string;
  storey: string;
  size: string;
  status: ElementStatus;
  calcs: ApiExportLink[];
}

export interface ApiTitleBox {
  page: number;
  rects: number[][];
  span?: number[] | null;
  rule?: string;
  note?: string;
}

export interface ApiExportCalc {
  key: string;
  title: string;
  software: string;
  element_type: string;
  pages: number[];
  scanned: boolean;
  front_matter: boolean;
  title_box: ApiTitleBox | null;
}

export interface ApiCalcEdgeEvidence {
  calc: string;
  page: number;
  text: string;
  line?: string;
  global_id?: string;
  rects?: number[][];
}

export interface ApiCalcEdge {
  src: string;
  dst: string;
  rules: string[];
  evidence: ApiCalcEdgeEvidence[];
}

export interface ApiLoadPathEdge {
  src: string;
  dst: string;
  rule: string;
}

export interface ApiExport {
  model: string | null;
  model_revision: number | null;
  calc_package: string | null;
  calc_revision: number | null;
  engine: string;
  producers?: Record<string, unknown>;
  calcs: ApiExportCalc[];
  calc_edges: ApiCalcEdge[];
  load_path: ApiLoadPathEdge[];
  elements: ApiExportElement[];
}

// ---------------------------------------------------------------- GET /api/projects/{pid}/state

export interface ApiElement {
  global_id: string;
  express_id: number | null;
  ifc_type: string;
  cat: string;
  mark: string;
  name: string;
  type_name: string;
  profile: string;
  storey: string;
  params: Record<string, string>;
  geom: { min: number[]; max: number[]; p1?: number[]; p2?: number[] } | null;
  content_hash: string;
  status: ElementStatus;
}

export interface ApiEdge {
  src: string;
  dst: string;
  kind: string;
  rule: string;
  gap_m?: number | null;
}

export interface ApiCalc {
  key: string;
  ord: number;
  title: string;
  software: string;
  cat: string;
  pages: number[];
  scanned: boolean;
  front: boolean;
  content_hash: string;
  color: string;
}

export interface ApiLink {
  global_id: string;
  calc_key: string;
  conf: number;
  tier: string;
  rule: string;
  page: number | null;
  token: string;
  span: number[] | null;
  snippet: ApiSnippet | null;
  rects: number[][];
  status: LinkReview;
  decided_at?: string;
  decided_by?: string;
}

/** One row of /revisions (meta parsed) and of /state's revisions list. */
export interface ApiRevision {
  id: number;
  project_id: number;
  kind: 'model' | 'calcs';
  parent_id: number | null;
  seq: number;
  label: string | null;
  source_name: string;
  sha256: string;
  created_at: string;
  meta?: Record<string, unknown>;
  /** /state's model_rev / calc_rev carry the raw column instead of `meta` */
  meta_json?: string;
  count?: number;
}

export interface ApiRun {
  id: number;
  project_id: number;
  model_rev: number;
  calc_rev: number;
  engine_version: string;
  created_at: string;
}

export interface ApiState {
  project: ApiProject;
  model_rev: ApiRevision | null;
  calc_rev: ApiRevision | null;
  run: ApiRun | null;
  elements: ApiElement[];
  edges: ApiEdge[];
  calcs: ApiCalc[];
  pages: { n: number; text: string; scanned: boolean; width: number | null; height: number | null }[];
  links: ApiLink[];
  calc_edges: ApiCalcEdge[];
  counts: Record<ElementStatus, number>;
  revisions: ApiRevision[];
}

// ---------------------------------------------------------------- other routes

/** GET /api/projects/{pid}/revisions */
export interface ApiRevisions {
  revisions: ApiRevision[];
  runs: ApiRun[];
}

/** GET /api/projects/{pid}/compare?a=&b= */
export interface ApiCompare {
  a: number;
  b: number;
  removed: { global_id: string; mark: string; cat: string }[];
  added: { global_id: string; mark: string; cat: string }[];
  changed: { global_id: string; mark: string; fields: Record<string, [unknown, unknown]> }[];
  edges_removed: [string, string][];
  edges_added: [string, string][];
}

/** GET /api/projects/{pid}/impact?gid=&mode= */
export interface ApiImpact {
  global_id: string;
  mode: 'change' | 'remove';
  removed: string[];
  hit: Record<string, number>;
  why: Record<string, string>;
  stale: Record<string, string>;
  waves: number;
}

/** POST /api/projects/{pid}/decisions body */
export interface ApiDecisionIn {
  global_id: string;
  calc_key: string;
  action: DecisionAction;
  actor?: string | null;
  note?: string | null;
}

/** POST /api/projects/{pid}/sample response */
export interface ApiSampleOut {
  model?: number;
  calcs?: number;
}

/** POST /api/projects/{pid}/model | /calcs response */
export interface ApiUploadOut {
  revision: number;
}
