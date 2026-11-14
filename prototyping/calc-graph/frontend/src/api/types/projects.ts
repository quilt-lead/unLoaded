// Response types of the IFC-path project endpoints (/api/projects/{pid}/...). Moved from the former vanilla
// app; not schema-shaped (the schema-shaped form is /api/store/projects/{pid}/bundle).
export interface IfcElement {
  global_id: string;
  express_id: number;
  ifc_type: string;
  cat: string;
  mark: string;
  name: string;
  type_name: string;
  profile: string;
  storey: string;
  params: Record<string, string>;
  geom: { min: number[]; max: number[]; p1: number[]; p2: number[] } | null;
  content_hash: string;
  status: "confirmed" | "review" | "unmapped";
}
export interface IfcEdge {
  src: string;
  dst: string;
  kind: string;
  rule: string;
  gap_m?: number;
}
export interface IfcCalc {
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
export interface IfcLink {
  global_id: string;
  calc_key: string;
  conf: number;
  tier: string;
  rule: string;
  page: number | null;
  token: string;
  span: number[] | null;
  snippet: { before: string; match: string; after: string } | null;
  rects: number[][];
  status: "auto" | "confirmed" | "rejected" | "manual";
  decided_at?: string;
  decided_by?: string;
}
export interface CalcEdge {
  src: string;
  dst: string;
  rules: string[];
  evidence: { calc: string; page: number; text: string }[];
}
export interface IfcRevision {
  id: number;
  kind: "model" | "calcs";
  seq: number;
  parent_id: number | null;
  label: string | null;
  source_name: string;
  sha256: string;
  created_at: string;
  count?: number;
}
export interface ProjectState {
  project: {
    id: number;
    name: string;
    head_model_rev: number | null;
    head_calc_rev: number | null;
  };
  model_rev: IfcRevision | null;
  calc_rev: IfcRevision | null;
  run: { id: number; engine_version: string; created_at: string } | null;
  elements: IfcElement[];
  edges: IfcEdge[];
  calcs: IfcCalc[];
  pages: { n: number; text: string; scanned: boolean }[];
  links: IfcLink[];
  calc_edges: CalcEdge[];
  counts: Record<string, number>;
  revisions: IfcRevision[];
}
export interface IfcImpact {
  global_id: string;
  mode: "change" | "remove";
  removed: string[];
  hit: Record<string, number>;
  why: Record<string, string>;
  stale: Record<string, string>;
  waves: number;
}

