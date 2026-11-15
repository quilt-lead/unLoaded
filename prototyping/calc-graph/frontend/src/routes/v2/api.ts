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
  float_before?: number | null; // null = the platform does not report float (assumed 0 for the delay)
  float_after?: number | null;
  float_known?: boolean;
  platform?: string;
  link?: string;
  /** synthetic CPM: the change's work inserted as its own activity (runs early_start..early_finish) */
  inserted?: boolean;
  early_start?: string;
  early_finish?: string;
  /** existing activities this work must finish before (float_before = baseline total float) */
  holds?: HeldActivity[];
}

export interface HeldActivity {
  ref: string;
  title: string;
  status?: string;
  early_finish_before?: string;
  early_finish_after?: string;
  slip_days?: number;
  float_before?: number;
  float_after?: number;
  /** working days this hold moves the project finish */
  finish_push: number;
  /** the change's work here is what sets the new project finish */
  drives_finish: boolean;
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
      /** set when this record's block could not be placed on the re-run sheets: why */
      missing?: string;
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
  /** set when this revision is an undo / redo of a re-run (POST /revisions/calc/restore) */
  restore?: {
    verb: "undo" | "redo";
    of: string;
    /** the calc revision whose content this carries; null = the original calc package */
    restored: string | null;
    /** the calc revision it superseded */
    parent: string;
  };
}

export interface ModelRevision {
  id: number;
  parent_id: number | null;
  seq: number;
  label: string;
  created_at: string;
  count?: number;
}

/** GET /revisions: model revisions split by design at the source, each list newest first. */
export interface RevisionsList {
  calc_revisions: CalcRevision[];
  /** the current design's history (its base revision and everything descended from it) */
  model_revisions: ModelRevision[];
  /** revisions of earlier designs (another base) */
  earlier_model_revisions: ModelRevision[];
  base_revision: number | null;
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
  /** the revision this one was derived from: the base design for an apply (every move is computed
   * from the base), the restored revision for an undo / redo; diff = parent -> revision for an apply */
  parent: number;
  /** the head this revision replaced (what undo restores); diff base for an undo / redo */
  previous_head: number;
  label: string;
  /** apply: parent -> revision; undo / redo: previous_head -> revision */
  diff: ModelDiff;
}

/** POST /revisions/model/restore: /apply's shape plus what was restored */
export interface RestoreResult extends ApplyResult {
  restored: number;
  of: number;
  verb: "undo" | "redo";
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
  /** where the records come from now: "live" (signed in, live selected) or "mock" */
  source: "live" | "mock";
  /** the mode chosen by env (CALCGRAPH_PLATFORM_<NAME>) */
  selected: "live" | "mock";
  /** why the mock is served (default selection, or why live failed) */
  fallback_reason?: string | null;
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

/** GET /platforms/{name}/{type}/{id} or /platform-record?url=: one record + where it came from. */
export interface PlatformRecordFull extends PlatformRecord {
  record_type: string;
  platform_label: string;
  source: "live" | "mock";
  source_label?: string | null;
  raw?: Record<string, unknown>;
}

/** GET /scenarios: the answer key's design scenarios (kind "design": another lateral layout, column null)
 * then its move scenarios (kind "move" / "remove"). */
export interface Scenario {
  id: string;
  label: string;
  kind: string;
  column: string | null;
  dx: number;
  dy: number;
  difficulty: Band | null;
  difficulty_why?: string | null;
  stale: number;
  resized: number;
  /** design scenarios only */
  lateral?: string;
  frames?: Record<string, Record<string, string>>;
  design_drift?: Record<string, number>;
  real_etabs?: EtabsRunSummary[];
  stale_etabs?: EtabsRunSummary[];
}

/** A saved REAL ETABS run (etabs_runs.py) - what it found, worded from its own numbers. */
export interface EtabsRunSummary {
  run_id: string;
  label: string;
  etabs_version: string;
  etabs_source: string;
  run_at: string;
  design: string;
  e2k_sha1: string;
  identity: string;
  stale_reason?: string;
  finding: {
    headline: string;
    mode1: { mode: number; period_s: number; ux: number; uy: number; rz: number; shape: string };
    drift_ng: { line: string; system: string; level: string; etabs_ratio: number; design_ratio: number }[];
    worst_drift: { line: string; system: string; level: string; etabs_ratio: number };
    flagged: number;
    compared: number;
  };
}

export interface EtabsRunsForDesign {
  design: string;
  e2k: string | null;
  e2k_sha1: string | null;
  runs: EtabsRunSummary[];
  stale: EtabsRunSummary[];
}

export interface EtabsRun extends EtabsRunSummary {
  code_ta_s: { x: number; y: number };
  modes: { mode: number; period_s: number; ux: number; uy: number; rz: number }[];
  base_shear: { case: string; etabs_kip: number; design_kip: number }[];
  totals: { case: string; etabs_kip: number; design_kip: number }[];
  lines: { line: string; etabs_pos_ecc_kip: number; etabs_neg_ecc_kip: number; design_kip: number; design_share_of_v: number }[];
  drift: { line: string; level: string; etabs_in: number; design_in: number; pct: number | null; allow_in: number; etabs_ratio: number }[];
  members: {
    flag_pct: number;
    agreement: {
      line: string;
      members: string;
      qty: string;
      rows: number;
      n: number;
      within: number;
      flagged: number;
      median_abs_pct: number | null;
      max_abs_pct: number | null;
    }[];
  };
}

const moveBody = (m: Move) => ({
  column: m.column,
  dx: m.dx,
  dy: m.dy,
  remove: m.remove,
});

// ---- reads
// The heat view: the server keeps it on disk keyed by its inputs, so after a restart it answers at once.
// The browser also keeps the last answer it saw, shown immediately (as placeholder data, labelled) while
// the request is in flight - e.g. while the server recomputes after the design changed.
const heatKey = (probe: number) => `cg.v2.heat.${probe}`;
function readHeat(probe: number): Record<string, Health> | undefined {
  try {
    const s = localStorage.getItem(heatKey(probe));
    return s ? (JSON.parse(s) as Record<string, Health>) : undefined;
  } catch {
    return undefined;
  }
}
export const useHealthHeat = (probe = 2) =>
  useQuery<Record<string, Health>>({
    queryKey: ["v2", "health", probe],
    staleTime: 5 * 60_000,
    placeholderData: () => readHeat(probe),
    queryFn: async ({ signal }) => {
      const h = await get<Record<string, Health>>(`/api/v2/health?probe=${probe}`, signal);
      try {
        localStorage.setItem(heatKey(probe), JSON.stringify(h));
      } catch {
        /* storage full or blocked: the server cache still serves it */
      }
      return h;
    },
  });

/** The ONE key + placeholder rule for every query of a move at an approval date (impact, cost / slip
 * timeline): keyed by (move, date), so a slow answer for an earlier date lands in its own cache entry and
 * can never replace the current date's; and while ONLY the date changed, the previous date's answer for the
 * same move stays as placeholder data (isPlaceholderData = true: show it dimmed with "updating"), so a panel
 * never blanks while it re-estimates. A different move never inherits another move's answer. */
export function moveAtDate<T>(kind: string, m: Move | null, asOf: string) {
  const queryKey = ["v2", kind, m?.column ?? null, m?.dx ?? 0, m?.dy ?? 0, m?.remove ?? false, asOf] as const;
  return {
    queryKey,
    placeholderData: (prev: T | undefined, prevQuery?: { queryKey: readonly unknown[] }) => {
      const k = prevQuery?.queryKey;
      return k && k.length === queryKey.length && queryKey.slice(0, -1).every((v, i) => k[i] === v) ? prev : undefined;
    },
  };
}

/** POST /impact as a query keyed by the move (the call is read-only on the server).
 * asOf = the approval date (as_of.py): "today" (default, current behaviour), "+1w", "+2w", "+1m" or a date.
 * Key + placeholder: moveAtDate (the colouring never drops back to the heat view between dates). */
export const useMoveImpact = (m: Move | null, asOf = "today") =>
  useQuery({
    ...moveAtDate<Impact>("impact", m, asOf),
    enabled: !!m && (m.remove || m.dx !== 0 || m.dy !== 0),
    staleTime: 5 * 60_000,
    queryFn: () => post<Impact>("/api/v2/impact", { ...moveBody(m!), as_of: asOf }),
  });

export const useConstructionStatus = (eid: string | null | undefined, asOf = "today") =>
  useQuery({
    queryKey: ["v2", "construction", eid, asOf],
    enabled: !!eid,
    queryFn: ({ signal }) =>
      get<ConstructionStatus>(
        `/api/v2/construction-status/${enc(eid!)}${asOf === "today" ? "" : `?as_of=${enc(asOf)}`}`,
        signal,
      ),
  });

export const useRevisions = () =>
  useQuery({
    queryKey: ["v2", "revisions"],
    queryFn: ({ signal }) =>
      get<RevisionsList>("/api/v2/revisions", signal),
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
/** One platform record by its link (links.self of any record, mock:// or a live API URL). */
export const usePlatformRecordByLink = (url: string | null) =>
  useQuery({
    queryKey: ["v2", "platform-record", url],
    enabled: !!url,
    staleTime: 5 * 60_000,
    queryFn: ({ signal }) => get<PlatformRecordFull>(`/api/v2/platform-record?url=${enc(url!)}`, signal),
  });

/** Rebuild the platform adapters on the server (after a login, or to re-fetch live records). */
export function usePlatformsRefresh() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => post<PlatformInfo[]>("/api/v2/platforms/refresh"),
    onSuccess: (d) => {
      qc.setQueryData(["v2", "platforms"], d);
      return qc.invalidateQueries({ predicate: (q) => q.queryKey[0] === "v2" && q.queryKey[1] !== "platforms" });
    },
  });
}

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

/** Saved real ETABS runs of a design ("current" or a design scenario id); refetched on the default schedule. */
export const useEtabsRuns = (design: string) =>
  useQuery({
    queryKey: ["v2", "etabs", "runs", design],
    staleTime: 60_000,
    queryFn: ({ signal }) => get<EtabsRunsForDesign>(`/api/v2/etabs/runs?design=${enc(design)}`, signal),
  });

export const useEtabsRun = (runId: string | null) =>
  useQuery({
    queryKey: ["v2", "etabs", "run", runId],
    enabled: !!runId,
    staleTime: 5 * 60_000,
    queryFn: ({ signal }) => get<EtabsRun>(`/api/v2/etabs/runs/${enc(runId!)}`, signal),
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

// undo / redo of a store write: a NEW revision restoring the other side (nothing is deleted)
export function useRestore() {
  const qc = useQueryClient();
  const done = () => qc.invalidateQueries({ queryKey: ["v2", "revisions"] });
  return {
    model: async (b: { target: number; of: number; verb: "undo" | "redo"; expect_head: number }) => {
      const r = await post<RestoreResult>("/api/v2/revisions/model/restore", b);
      await done();
      return r;
    },
    calc: async (b: { target: string | null; reverts: string; of: string; verb: "undo" | "redo" }) => {
      const r = await post<CalcRevision>("/api/v2/revisions/calc/restore", b);
      await done();
      return r;
    },
  };
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
