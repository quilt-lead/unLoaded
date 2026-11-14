// Typed client for the calc-graph FastAPI backend.

export interface Element {
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
export interface Edge {
  src: string;
  dst: string;
  kind: string;
  rule: string;
  gap_m?: number;
}
export interface Calc {
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
export interface Link {
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
export interface Revision {
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
export interface State {
  project: {
    id: number;
    name: string;
    head_model_rev: number | null;
    head_calc_rev: number | null;
  };
  model_rev: Revision | null;
  calc_rev: Revision | null;
  run: { id: number; engine_version: string; created_at: string } | null;
  elements: Element[];
  edges: Edge[];
  calcs: Calc[];
  pages: { n: number; text: string; scanned: boolean }[];
  links: Link[];
  calc_edges: CalcEdge[];
  counts: Record<string, number>;
  revisions: Revision[];
}
export interface Impact {
  global_id: string;
  mode: "change" | "remove";
  removed: string[];
  hit: Record<string, number>;
  why: Record<string, string>;
  stale: Record<string, string>;
  waves: number;
}

const PID = 1;

async function ok<T>(r: Response): Promise<T> {
  if (!r.ok) {
    let msg = `${r.status} ${r.statusText}`;
    try {
      const j = await r.json();
      if (j.detail)
        msg =
          typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail);
    } catch {
      /* not json */
    }
    throw new Error(msg);
  }
  return r.json() as Promise<T>;
}

export const api = {
  state: () => fetch(`/api/projects/${PID}/state`).then((r) => ok<State>(r)),
  sample: (modelRev = 1) =>
    fetch(`/api/projects/${PID}/sample?model_rev=${modelRev}`, {
      method: "POST",
    }).then((r) => ok(r)),
  upload: (kind: "model" | "calcs", file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return fetch(`/api/projects/${PID}/${kind}`, {
      method: "POST",
      body: fd,
    }).then((r) => ok(r));
  },
  decide: (
    global_id: string,
    calc_key: string,
    action: "confirm" | "reject" | "manual" | "undo",
  ) =>
    fetch(`/api/projects/${PID}/decisions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ global_id, calc_key, action, actor: "reviewer" }),
    }).then((r) => ok(r)),
  impact: (gid: string, mode: "change" | "remove") =>
    fetch(
      `/api/projects/${PID}/impact?gid=${encodeURIComponent(gid)}&mode=${mode}`,
    ).then((r) => ok<Impact>(r)),
  fileUrl: (rid: number) => `/api/revisions/${rid}/file`,
  pageUrl: (rid: number, n: number, rects: number[][] = []) =>
    `/api/revisions/${rid}/pages/${n}.png?width=1100&hl=${encodeURIComponent(rects.map((r) => r.map((v) => v.toFixed(1)).join(",")).join(";"))}`,
  exportUrl: () => `/api/projects/${PID}/export`,
};
