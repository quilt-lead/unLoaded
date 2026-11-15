// Progress of the /api/v2/rerun in flight (GET /api/v2/rerun/progress, backend move_api.RerunProgress).
import { useQuery } from "@tanstack/react-query";
import { get } from "../../api/client";

export interface RerunProgress {
  running: boolean;
  column?: string | null;
  stage?:
    | "design"
    | "math"
    | "layout"
    | "package_sheets"
    | "done"
    | "failed"
    | string
    | null;
  stage_label?: string | null;
  done: number;
  total: number;
  seconds: number;
  rev_id?: string | null;
}

/** Polls while `busy` (a re-run request is pending); off otherwise. */
export const useRerunProgress = (busy: boolean) =>
  useQuery({
    queryKey: ["v2", "rerun-progress"],
    queryFn: () => get<RerunProgress>("/api/v2/rerun/progress"),
    enabled: busy,
    refetchInterval: busy ? 700 : false,
    staleTime: 0,
    gcTime: 0,
  });

/** "laying out the re-run sheets 12/40 - 14 s" */
export function progressText(p: RerunProgress | undefined): string | null {
  if (!p || !p.running) return null;
  const units =
    p.stage === "layout" && p.total ? ` ${p.done}/${p.total} chunks` : "";
  return `${p.stage_label ?? p.stage ?? "starting"}${units} - ${Math.round(p.seconds)} s`;
}
