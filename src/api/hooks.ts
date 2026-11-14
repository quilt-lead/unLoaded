// TanStack Query hooks. Every read hook hands back VIEW MODELS (src/types/bim.ts), converted by
// src/data/loadProject.ts, so components never see a backend shape. Keys are rooted at
// ["projects", pid] so a mutation can invalidate a whole project in one call.
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './client';
import type { DecisionAction } from '../types/bim';
import { loadProject, toModelDiff, toImpactView, toRevisionList } from '../data/loadProject';

export const useBackendHealth = () =>
  useQuery({
    queryKey: ['health'],
    queryFn: ({ signal }) => api.health(signal),
    retry: false,
    // poll while the backend is down so the app comes alive when it starts
    refetchInterval: (q) => (q.state.status === 'error' ? 5000 : false),
  });

/** The IFC-path project this app works on: the first one the backend lists (it always ensures one). */
export const useProjectId = (enabled: boolean) =>
  useQuery({
    queryKey: ['projects'],
    enabled,
    queryFn: async ({ signal }) => {
      const ps = await api.projects(signal);
      return ps.length ? ps[0].id : 1;
    },
  });

export const useProjectView = (pid: number | null) =>
  useQuery({
    queryKey: ['projects', pid, 'view'],
    enabled: pid != null,
    queryFn: async ({ signal }) => {
      const [exp, state] = await Promise.all([api.exportProject(pid!, signal), api.state(pid!, signal)]);
      return loadProject({ export: exp, state }, { source: 'api', projectId: pid! });
    },
  });

export const useRevisions = (pid: number | null) =>
  useQuery({
    queryKey: ['projects', pid, 'revisions'],
    enabled: pid != null,
    queryFn: async ({ signal }) => toRevisionList(await api.revisions(pid!, signal)),
  });

export const useImpact = (pid: number | null, gid: string | null, mode: 'change' | 'remove') =>
  useQuery({
    queryKey: ['projects', pid, 'impact', gid, mode],
    enabled: pid != null && !!gid,
    queryFn: async ({ signal }) => toImpactView(await api.impact(pid!, gid!, mode, signal)),
  });

export const useCompare = (pid: number | null, a: number | null, b: number | null) =>
  useQuery({
    queryKey: ['projects', pid, 'compare', a, b],
    enabled: pid != null && a != null && b != null && a !== b,
    queryFn: async ({ signal }) => toModelDiff(await api.compare(pid!, a!, b!, signal)),
  });

export function useDecide(pid: number | null) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (v: { elementId: string; calcKey: string; action: DecisionAction }) => {
      await api.decide(pid!, { global_id: v.elementId, calc_key: v.calcKey, action: v.action, actor: 'reviewer' });
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['projects', pid] }),
  });
}

export function useLoadSample(pid: number | null) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (modelRev: 1 | 2) => {
      const out = await api.sample(pid!, modelRev);
      return { modelRevisionId: out.model ?? null, calcRevisionId: out.calcs ?? null };
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['projects', pid] }),
  });
}

export function useUpload(pid: number | null) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ kind, file }: { kind: 'model' | 'calcs'; file: File }) => ({ revisionId: (await api.upload(pid!, kind, file)).revision }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['projects', pid] }),
  });
}
