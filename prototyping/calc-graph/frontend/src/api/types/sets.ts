// Response types of the drawing-set endpoints (/api/sets/{sid}/graph and /integrated).
// Moved verbatim from the vanilla set view (the former vanilla page) so the React port shares one copy;
// these files are not schema-shaped yet (the schema-shaped form is /api/store/sets/{sid}/bundle).
/* eslint-disable @typescript-eslint/no-explicit-any */
export interface Ev {
  table?: string;
  doc: string;
  page: number;
  rects: number[][];
  text: string;
  note?: string;
  sheet?: string;
  calc?: string;
  extra?: Ev[];
}
export interface Model3D {
  in3d: boolean;
  gid?: string;
  reason?: string;
  rule?: string;
  position?: string;
  elevation?: string;
  assumed?: string[];
  profile?: string;
  status3d?: string;
  grid3d?: string;
}
export interface El {
  model?: Model3D;
  id: string;
  doc: string;
  page: number;
  sheet: string;
  sheet_title: string;
  sheet_kind: string;
  cat: string;
  type: string;
  mark: string;
  size: string;
  size_norm: string;
  family: string;
  level: string;
  grid: string;
  grid_node: string | null;
  bbox: number[];
  rects: number[][];
  text: string;
  params: Record<string, string>;
}
export interface EEdge {
  src: string;
  dst: string;
  rule: string;
  evidence: Ev[];
}
export interface SetCalc {
  id: string;
  doc: string;
  page: number;
  sheet_id: string;
  sheet_rect: number[] | null;
  section: string;
  group: string;
  title: string;
  title_rect: number[] | null;
  level: string;
  software: string;
  kind: string;
  toc: boolean;
  width: number;
  height: number;
  sizes: string[];
  labels: Record<string, number>;
}
export interface CEdge {
  src: string;
  dst: string;
  rule: string;
  labels: string[];
  evidence: { src: Ev[]; dst: Ev[] };
}
export interface Lnk {
  el: string;
  calc: string;
  score: number;
  tier: string;
  rule: string;
  evidence: { el: Ev; calc: Ev };
}
export interface SetFinding {
  kind: string;
  severity: string;
  text: string;
  el?: string;
  calc?: string;
  rec?: string;
  evidence: Ev[];
}
export interface Sheet {
  sheet: string;
  title: string;
  page: number;
  width: number;
  height: number;
  kind: string;
  level: string;
}
export interface SetGraph {
  id: string;
  name: string;
  built_at: string;
  docs: Record<string, { name: string; role: string; pages?: number }>;
  sheets: Sheet[];
  elements: El[];
  element_edges: EEdge[];
  calcs: SetCalc[];
  calc_edges: CEdge[];
  links: Lnk[];
  findings: SetFinding[];
  coverage: Record<string, any>;
}

// ---- integrated layer: calc records, calc load path, connections, calc-model overlay ----
export interface Rec {
  id: string;
  type: string;
  run: string;
  run_title: string;
  section: string;
  label: string;
  title: string;
  level: string;
  size: string;
  table: string;
  tables: string[];
  pages: number[];
  values: Record<string, any>;
  ev: (Ev & { table?: string })[];
}
export interface REdge {
  src: string;
  dst: string | null;
  kind: string;
  join: "exact" | "inferred" | "absent";
  rule: string;
  end?: string;
  evidence: { src: Ev[]; dst: Ev[] };
}
export interface RLink {
  el: string;
  calc: string;
  records: string[];
  tier: string;
  score: number;
  rule: string;
}
export interface Note {
  id: string;
  doc: string;
  page: number;
  sheet: string;
  rects: number[][];
  bbox: number[];
  colour: string;
  text: string;
  attached: { record: string; join: string; rule: string }[];
}
export interface Att {
  id: string;
  cat: string;
  type: string;
  size: string;
  dist: number;
  at_end?: boolean;
  role?: string;
}
export interface CType {
  id: string;
  detail: string;
  sheet: string;
  page: number;
  doc: string;
  sheet_title: string;
  category: string;
  title: string;
  is_connection: boolean;
  scale: string;
  bbox: number[];
  number_rect: number[];
  title_rects: number[][];
  spec: { text: string; rect: number[] }[];
  sizes: string[];
  instances: string[];
  referenced_from_details: string[];
  calc_refs: any[];
  rule: string;
}
export interface CInst {
  id: string;
  type_id: string | null;
  ref: string;
  sheet: string;
  page: number;
  doc: string;
  via: string;
  symbol: string | null;
  symbol_name?: string;
  legend_text?: string;
  bbox: number[];
  rects: number[][];
  point: number[];
  leader_end: number[] | null;
  grid: string;
  grid_node: string | null;
  attached: Att[];
  attach_rule: string;
  unattached_reason?: string;
  in_view: string;
  context?: string;
}
export interface Marker {
  inst: string;
  el: string;
  pos: number[];
  rule: string;
}
export interface OvMember {
  rec: string;
  label: string;
  size: string;
  level: string;
  a: number[];
  b: number[];
  elev: number;
  absent_ends: number;
}
export interface OvColumn {
  rec: string;
  label: string;
  size: string;
  z: number;
  x: number;
  bot: number;
  top: number;
}
export interface Overlay {
  levels: Record<string, number>;
  axes: string;
  members: OvMember[];
  columns: OvColumn[];
  transform_dropped: string;
  differences: { what: string; text: string; calc: Ev[]; draw: Ev[] }[];
}
export interface Integrated {
  built_at: string;
  stale: string[];
  runs: Record<string, string>;
  records: Rec[];
  record_edges: REdge[];
  notes: Note[];
  record_links: RLink[];
  conn_types: CType[];
  conn_instances: CInst[];
  conn_markers: Marker[];
  overlay: Overlay;
  findings: SetFinding[];
  coverage: Record<string, any>;
}
