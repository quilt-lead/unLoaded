// TanStack Query hooks, one per read endpoint the shared UI needs. Keys are arrays rooted at the
// endpoint family so a mutation can invalidate a whole family (e.g. ["projects", pid]).
// R2/R3 add hooks for their own endpoints here in small, announced commits.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { get, post, postForm } from "./client";
import type {
  Bundle,
  IfcImpact,
  ProjectState,
  SetGraph,
  Integrated,
  StoreProject,
  V2Design,
  V2ElementPage,
  V2RecordPage,
  V2Summary,
} from "./types";

const enc = encodeURIComponent;

export interface SetListItem {
  id: string;
  name: string;
  docs: Record<string, { name: string; role: string; pages?: number }>;
}

// ---- IFC path (project API). /ifc reads the Harbor View (synthetic v2) project: GET /api/projects/v2.
export interface V2Project {
  id: number;
  name: string;
  head_model_rev: number | null;
  head_calc_rev: number | null;
}
export const useV2Project = () =>
  useQuery({ queryKey: ["projects", "v2"], queryFn: ({ signal }) => get<V2Project>("/api/projects/v2", signal) });

export const useProjectState = (pid: number | undefined) =>
  useQuery({
    queryKey: ["projects", pid, "state"],
    enabled: pid != null,
    queryFn: ({ signal }) => get<ProjectState>(`/api/projects/${pid}/state`, signal),
  });

export const useImpact = (pid: number, gid: string | null, mode: "change" | "remove") =>
  useQuery({
    queryKey: ["projects", pid, "impact", gid, mode],
    enabled: !!gid,
    queryFn: ({ signal }) => get<IfcImpact>(`/api/projects/${pid}/impact?gid=${enc(gid!)}&mode=${mode}`, signal),
  });

export function useDecide(pid: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { global_id: string; calc_key: string; action: "confirm" | "reject" | "manual" | "undo" }) =>
      post(`/api/projects/${pid}/decisions`, { ...v, actor: "reviewer" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["projects", pid] }),
  });
}

/** ingest what the Harbor View project lacks from data/synthetic_v2 (base model.ifc, calc_package.pdf) */
export function useLoadV2Documents() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => post("/api/projects/v2/documents"),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["projects"] }),
  });
}

export function useUpload(pid: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ kind, file }: { kind: "model" | "calcs"; file: File }) => {
      const fd = new FormData();
      fd.append("file", file);
      return postForm(`/api/projects/${pid}/${kind}`, fd);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["projects", pid] }),
  });
}

// ---- drawing sets
export const useSets = () => useQuery({ queryKey: ["sets"], queryFn: ({ signal }) => get<SetListItem[]>("/api/sets", signal) });
export const useSetGraph = (sid: string | undefined) =>
  useQuery({ queryKey: ["sets", sid, "graph"], enabled: !!sid, queryFn: ({ signal }) => get<SetGraph>(`/api/sets/${enc(sid!)}/graph`, signal) });
export const useSetIntegrated = (sid: string | undefined) =>
  useQuery({
    queryKey: ["sets", sid, "integrated"],
    enabled: !!sid,
    queryFn: ({ signal }) => get<Integrated>(`/api/sets/${enc(sid!)}/integrated`, signal),
  });

// ---- revision store (schema-shaped)
export const useStoreProjects = () =>
  useQuery({ queryKey: ["store", "projects"], queryFn: ({ signal }) => get<StoreProject[]>("/api/store/projects", signal) });
export const useStoreProjectBundle = (pid: number | undefined) =>
  useQuery({
    queryKey: ["store", "projects", pid, "bundle"],
    enabled: pid != null,
    queryFn: ({ signal }) => get<Bundle>(`/api/store/projects/${pid}/bundle`, signal),
  });
export const useStoreSetBundle = (sid: string | undefined) =>
  useQuery({
    queryKey: ["store", "sets", sid, "bundle"],
    enabled: !!sid,
    queryFn: ({ signal }) => get<Bundle>(`/api/store/sets/${enc(sid!)}/bundle`, signal),
  });

// ---- synthetic v2
export const useV2Summary = () => useQuery({ queryKey: ["v2", "summary"], queryFn: ({ signal }) => get<V2Summary>("/api/v2/summary", signal) });
export const useV2Design = () =>
  useQuery({ queryKey: ["v2", "design"], staleTime: 60_000, queryFn: ({ signal }) => get<V2Design>("/api/v2/design", signal) });
export const useV2Element = (eid: string | undefined) =>
  useQuery({ queryKey: ["v2", "elements", eid], enabled: !!eid, queryFn: ({ signal }) => get<V2ElementPage>(`/api/v2/elements/${enc(eid!)}`, signal) });
export const useV2Record = (rid: string | undefined) =>
  useQuery({ queryKey: ["v2", "records", rid], enabled: !!rid, queryFn: ({ signal }) => get<V2RecordPage>(`/api/v2/records/${enc(rid!)}`, signal) });
