// As-of date for impact (backend/calcgraph/as_of.py): presets + the cost / slip vs approval date timeline.
import { useQuery } from "@tanstack/react-query";
import { get, post } from "../../api/client";
import { moveAtDate, type Move } from "./api";

export interface AsOfPreset {
  key: string;
  label: string;
  date: string;
}

export interface AsOfInfo {
  today: string;
  status_date: string;
  presets: AsOfPreset[];
  assumption: string;
}

/** what an as-of meant for one response (impact.as_of) */
export interface AsOfDescribe {
  as_of: string;
  is_today: boolean;
  status_date: string;
  data_date: string | null;
  projected: boolean;
  adapters: { name: string; source: string; projected: boolean }[];
  assumption: string;
}

export interface TimelinePoint {
  date: string;
  labels: string[];
  is_today: boolean;
  total_cost: number | null;
  forecast_slip: number | null;
  finish_delay: number | null;
  worst_stage: string | null;
  stages: Record<string, string | null>;
  error?: string | null;
  /** present when this point's slip is LOWER than the point before (as_of.explain_slip_drop) */
  slip_change?: SlipChange;
}

export interface SlipChange {
  from: number;
  to: number;
  /** true only when every activity the change's work held on the driving path is complete by this date
   *  and its elements moved to a later stage; false = a model defect, shown as such */
  explained: boolean;
  reason: string;
}

export interface Boundary {
  date: string;
  approve_by: string;
  element: string;
  activity: string;
  activity_name: string;
  to_stage: string;
}

export interface Timeline {
  points: TimelinePoint[];
  next_jump: {
    date: string;
    approve_by: string;
    cost_before: number;
    cost_after: number;
    slip_before: number;
    slip_after: number;
    drivers: { element: string; from: string | null; to: string }[];
    boundaries: Boundary[];
  } | null;
  approve_by_line: string | null;
  boundaries: Boundary[];
  selected: string;
  assumption: string;
  horizon_days: number;
}

export const useAsOfInfo = () =>
  useQuery({
    queryKey: ["v2", "as-of"],
    queryFn: ({ signal }) => get<AsOfInfo>("/api/v2/as-of", signal),
    staleTime: 60_000,
  });

/** Key + placeholder: moveAtDate - while only the date changed, the previous date's timeline stays shown
 * (isPlaceholderData: dim it with "updating"); a late answer for an older date cannot overwrite a newer one. */
export const useImpactTimeline = (move: Move | null, asOf: string) =>
  useQuery({
    ...moveAtDate<Timeline>("timeline", move, asOf),
    enabled: !!move && (move.remove || move.dx !== 0 || move.dy !== 0),
    queryFn: () =>
      post<Timeline>("/api/v2/impact/timeline", { column: move!.column, dx: move!.dx, dy: move!.dy, remove: move!.remove, as_of: asOf }),
    staleTime: Infinity,
  });

/** "today" | "+1w" | ... | "YYYY-MM-DD" -> the label the control shows */
export function asOfLabel(asOf: string, info?: AsOfInfo): string {
  const p = info?.presets.find((x) => x.key === asOf);
  if (p)
    return p.key === "today" ? `today (${p.date})` : `${p.label} (${p.date})`;
  return asOf;
}
