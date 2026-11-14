// Types + TanStack Query hooks for the v2 move-a-column UI. Kept inside src/routes/v2 (R3's folder)
// so the shared src/api files only change for things other phases also need. Shapes follow
// backend/calcgraph/move_api.py as served (checked against live responses, 2026-11-14).
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { get, post } from "../../api/client";
import type { V2Occurrence, V2Record } from "../../api/types";

const enc = encodeURIComponent;

export interface Move {
  column: string; // "COL-2B"
  dx: number; // ft
  dy: number; // ft
  remove: boolean;
}

export type Band = "easy" | "moderate" | "hard" | "do-not-move";

export interface HealthReason {
  band: Band;
  reason: string;
  factor: string;
}

export interface Health {
  band: Band;
  score: number;
  band_construction?: Band;
  score_construction?: number;
  construction_status_used?: boolean;
  reasons: HealthReason[];
  worst_uc?: number | null;
  stale_records?: number;
  sheets?: string[];
  probe?: [number, number];
}

export interface StaleItem {
  record: string;
  calc: string;
  kind: string;
  reasons: string[];
  chain: string[];
  screened: boolean;
}

export interface Estimate {
  element: string;
  size?: string;
  span_old?: number;
  span_new?: number;
  mu_old?: number;
  mu_new?: number;
  pu_old?: number;
  pu_new?: number;
  ru_old?: number;
  ru_new?: number;
  p_old?: number;
  p_new?: number;
  B_old?: number;
  B_req?: number;
  capacity?: number;
  detail?: string;
  uc_old?: number;
  uc_new?: number;
  governs?: string;
  size_est?: string;
  next_typical?: string;
  special?: boolean;
  method: string;
  record?: string;
}

export interface Figure {
  value: number;
  unit: string;
  estimate: boolean;
  basis: string;
}

export interface PlatformSource {
  platform: string;
  id: string;
  url: string;
}

export interface CoItem {
  ref?: string;
  number?: string;
  title?: string | null;
  status?: string;
  stage?: string | null;
  platform?: string;
  link?: string;
  sources?: PlatformSource[];
  element_ids?: string[];
  action?: string;
  flag?: string;
  source?: string;
}

export interface CostLine {
  category: string;
  element_id?: string;
  description: string;
  figure: Figure;
  platform?: string;
  link?: string;
}

export interface ScheduleActivity {
  ref: string;
  title: string;
  added_days: number;
  reasons: string[];
  early_finish_before?: string;
  early_finish_after?: string;
  slip_days?: number;
  float_before?: number;
  float_after?: number;
  platform?: string;
  link?: string;
}

export interface ChangeOrder {
  error?: string;
  summary?: {
    total_cost: Figure;
    cost_range: { low: Figure; high: Figure };
    finish_delay: Figure;
    forecast_slip: Figure;
    float_consumed: Figure;
    worst_stage?: string;
    counts: Record<string, number>;
    headline: string;
  };
  submittals?: CoItem[];
  rfis?: CoItem[];
  sheets?: CoItem[];
  spec_articles?: { article: string; source?: string }[];
  calc_records?: string[];
  cost?: { lines: CostLine[]; [k: string]: unknown };
  schedule?: { activities: ScheduleActivity[]; [k: string]: unknown };
  assumptions?: {
    as_of?: string;
    rates?: Record<string, unknown>;
    schedule_rules?: Record<string, unknown>;
    note?: string;
  };
  warnings?: string[];
  estimate?: boolean;
  synthetic?: boolean;
}

export interface GeometryChange {
  p1: [number, number];
  p2: [number, number];
  why: string;
  L0: number;
  L1: number;
}

export interface Impact {
  column: string;
  dx: number;
  dy: number;
  remove: boolean;
  stale: StaleItem[];
  estimates: Record<string, Estimate>;
  geometry: Record<string, GeometryChange>;
  clashes: unknown[];
  lateral: unknown[];
  notes: string[];
  health: Health;
  occurrences: Record<string, V2Occurrence[]>;
  labels: Record<string, string>;
  change_order: ChangeOrder;
}

export interface RerunSide {
  demand?: number | null;
  capacity?: number | null;
  uc?: number | null;
  check?: string;
  lc?: string;
  unit?: string;
  values?: Record<string, unknown>;
}

export interface RerunResult {
  step: number;
  record: string;
  calc: string;
  kind: string;
  elements?: string[];
  job: "gravity" | "lateral" | string;
  method?: string;
  old: RerunSide | null;
  new: RerunSide | null;
  size_old?: string | null;
  size_new?: string | null;
  status: string;
  ok_old?: boolean | null;
  ok_new?: boolean | null;
  ng_to_ok?: boolean;
  uc_current_size_new_layout?: number | null;
  ok_current_size_new_layout?: boolean | null;
  new_page?: {
    page: number;
    bbox: [number, number, number, number];
    sheet?: string;
    rerun_sheet?: {
      page: number;
      bbox: [number, number, number, number];
      sheet?: string;
      recomputed?: boolean;
      asserts?: number;
      mismatches?: unknown[];
    };
  };
}

export interface CalcRevision {
  rev_id: string;
  created_at: string;
  change: { moved?: Record<string, [number, number]>; removed?: string[] };
  method?: string;
  order_rule?: string;
  results?: RerunResult[];
  summary: {
    records: number;
    resized: number;
    ng_to_ok: number;
    still_ng: number;
    new: number;
    removed: number;
    seconds: number;
  };
  files: Record<string, string>;
}

export interface ModelRevision {
  id: number;
  parent_id: number | null;
  seq: number;
  label: string;
  created_at: string;
  count?: number;
}

export interface ModelDiff {
  a: number;
  b: number;
  removed: { global_id: string; mark?: string }[];
  added: { global_id: string; mark?: string }[];
  changed: {
    global_id: string;
    mark?: string;
    fields: Record<string, [string, string]>;
  }[];
  edges_removed: unknown[];
  edges_added: unknown[];
}

export interface ApplyResult {
  project: number;
  revision: number;
  parent: number;
  label: string;
  diff: ModelDiff;
}

export interface ConstructionStatus {
  element_id: string;
  stage: string;
  stage_rank?: number;
  stages?: string[];
  submittals: CoItem[];
  open_rfis: CoItem[];
  float_days?: number | null;
  reasons: string[];
  move_difficulty?: string;
}

export interface AnsweredBy {
  adapter: string; // "etabs" (mock) | "bhom_etabs" (Windows bridge)
  adapter_name: string;
  mock: boolean;
}

export interface EtabsObject {
  kind: string;
  label: string;
  element_id: string | null;
  record_ids: string[];
  props: Record<string, unknown>;
  raw: Record<string, unknown>;
  story: string | null;
}

export interface EtabsJob {
  job_id: string;
  adapter: string;
  status: string;
  note?: string;
  source?: string;
  method?: string;
  diff_summary?: Record<string, number>;
  story_drifts?: Record<string, unknown>[];
  frame_design?: Record<string, unknown>[];
  summary?: {
    max_drift_dc?: Record<string, number>;
    base_max_drift_dc?: Record<string, number>;
    max_ratio?: number;
    frames_over_1?: unknown[];
    sections_changed?: number;
    sections_changed_list?: {
      label: string;
      story: string;
      element_id: string;
      from: string;
      to: string;
    }[];
  };
  answered_by: AnsweredBy;
  [k: string]: unknown;
}

export interface PlatformInfo {
  name: string;
  label: string;
  capabilities: string[];
  counts: Record<string, Record<string, number>>;
  doc_urls: Record<string, string>;
  mock: boolean;
}

export interface PlatformRecord {
  kind: string;
  id: string;
  ref: string;
  platform: string;
  number?: string;
  title?: string;
  status?: string;
  element_ids?: string[];
  dates?: Record<string, string>;
  links?: { self?: string };
  fields?: Record<string, unknown>;
}

export interface Scenario {
  id: string;
  label: string;
  kind: string;
  column: string;
  dx: number;
  dy: number;
  difficulty: Band;
  difficulty_why?: string;
  stale: number;
  resized: number;
}

const moveBody = (m: Move) => ({
  column: m.column,
  dx: m.dx,
  dy: m.dy,
  remove: m.remove,
});

// ---- reads
export const useHealthHeat = (probe = 2) =>
  useQuery({
    queryKey: ["v2", "health", probe],
    staleTime: 5 * 60_000,
    queryFn: ({ signal }) =>
      get<Record<string, Health>>(`/api/v2/health?probe=${probe}`, signal),
  });

/** POST /impact as a query keyed by the move (the call is read-only on the server). */
export const useMoveImpact = (m: Move | null) =>
  useQuery({
    queryKey: ["v2", "impact", m?.column, m?.dx, m?.dy, m?.remove],
    enabled: !!m && (m.remove || m.dx !== 0 || m.dy !== 0),
    staleTime: 5 * 60_000,
    queryFn: () => post<Impact>("/api/v2/impact", moveBody(m!)),
  });

export const useConstructionStatus = (eid: string | null | undefined) =>
  useQuery({
    queryKey: ["v2", "construction", eid],
    enabled: !!eid,
    queryFn: ({ signal }) =>
      get<ConstructionStatus>(
        `/api/v2/construction-status/${enc(eid!)}`,
        signal,
      ),
  });

export const useRevisions = () =>
  useQuery({
    queryKey: ["v2", "revisions"],
    queryFn: ({ signal }) =>
      get<{ calc_revisions: CalcRevision[]; model_revisions: ModelRevision[] }>(
        "/api/v2/revisions",
        signal,
      ),
  });

export const useCalcRevision = (rev: string | null) =>
  useQuery({
    queryKey: ["v2", "revisions", rev],
    enabled: !!rev,
    queryFn: ({ signal }) =>
      get<CalcRevision>(`/api/v2/revisions/${enc(rev!)}`, signal),
  });

export const useCompare = (a: number | null, b: number | null) =>
  useQuery({
    queryKey: ["v2", "compare", a, b],
    enabled: a != null && b != null && a !== b,
    queryFn: ({ signal }) =>
      get<ModelDiff>(`/api/v2/compare?a=${a}&b=${b}`, signal),
  });

export const useEtabsObjects = () =>
  useQuery({
    queryKey: ["v2", "etabs", "objects"],
    staleTime: 5 * 60_000,
    queryFn: ({ signal }) =>
      get<{ answered_by: AnsweredBy; items: EtabsObject[] }>(
        "/api/v2/etabs/objects",
        signal,
      ),
  });

export const usePlatforms = () =>
  useQuery({
    queryKey: ["v2", "platforms"],
    staleTime: 5 * 60_000,
    queryFn: ({ signal }) => get<PlatformInfo[]>("/api/v2/platforms", signal),
  });

export const usePlatformRecords = (
  name: string | null,
  type: string | null,
  raw = false,
) =>
  useQuery({
    queryKey: ["v2", "platforms", name, type, raw],
    enabled: !!name && !!type,
    staleTime: 5 * 60_000,
    queryFn: ({ signal }) =>
      get<unknown[]>(
        `/api/v2/platforms/${enc(name!)}/${enc(type!)}${raw ? "?raw=true" : ""}`,
        signal,
      ),
  });

export const useScenarios = () =>
  useQuery({
    queryKey: ["v2", "scenarios"],
    staleTime: 5 * 60_000,
    queryFn: ({ signal }) => get<Scenario[]>("/api/v2/scenarios", signal),
  });

// ---- writes (each creates a NEW revision on the server; nothing is overwritten)
export function useRerun() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { move: Move; records?: string[] }) =>
      post<CalcRevision>("/api/v2/rerun", {
        ...moveBody(v.move),
        ...(v.records ? { records: v.records } : {}),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["v2", "revisions"] }),
  });
}

export function useApply() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { move: Move; label?: string }) =>
      post<ApplyResult>("/api/v2/apply", {
        ...moveBody(v.move),
        label: v.label || undefined,
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["v2", "revisions"] }),
  });
}

export const useEtabsSend = () =>
  useMutation({
    mutationFn: (m: Move) => post<EtabsJob>("/api/v2/etabs/send", moveBody(m)),
  });
export const useEtabsPull = () =>
  useMutation({
    mutationFn: (job: string) =>
      post<EtabsJob>(`/api/v2/etabs/pull/${enc(job)}`),
  });

export const e2kUrl = (m?: Move | null) =>
  m
    ? `/api/v2/etabs/model.e2k?column=${enc(m.column)}&dx=${m.dx}&dy=${m.dy}&remove=${m.remove}`
    : "/api/v2/etabs/model.e2k";

export type { V2Occurrence, V2Record };
