// TanStack Query hooks. Every read hook hands back VIEW data (src/types/bim.ts): backend payloads are
// converted by src/data/loadProject.ts, element graphs by src/loaders/elementGraphToBim.ts, and the two
// are joined by src/data/mergeProject.ts. Components never see a backend shape or an ElementGraph.
// Keys are rooted at ["projects", pid] so a mutation can invalidate a whole project in one call.
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ElementGraph } from '@unloaded/element-graph';
import { ApiError, api } from './client';
import type { DecisionAction, ElementTopology } from '../types/bim';
import { exportToElementGraph, toCalcData, toImpactView, toModelDiff, toRevisionList } from '../data/loadProject';
import { elementGraphToBim } from '../loaders/elementGraphToBim';
import { importModel } from '../loaders/parsers';

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

/** The calc engine's view of the project (links, evidence, review status, calcs, calc graph). */
export const useProjectCalc = (pid: number | null) =>
  useQuery({
    queryKey: ['projects', pid, 'calc'],
    enabled: pid != null,
    queryFn: async ({ signal }) => {
      const [exp, state] = await Promise.all([api.exportProject(pid!, signal), api.state(pid!, signal)]);
      return {
        calc: toCalcData(exp, state),
        /** topology from the export alone, for a revision whose element graph the backend cannot return */
        fallbackTopology: (): ElementTopology => elementGraphToBim(exportToElementGraph(exp, state)),
      };
    },
  });

/**
 * The element graph stored with a model revision (built in the browser when it was uploaded), as
 * topology. A revision never changes, so this is fetched once per revision. 404 = the revision has
 * no stored graph (an older store): the caller falls back to the export's topology.
 */
export const useRevisionTopology = (rid: number | null) =>
  useQuery({
    queryKey: ['revision-graph', rid],
    enabled: rid != null,
    staleTime: Infinity,
    retry: (n, e) => !(e instanceof ApiError && (e.status === 404 || e.status === 405)) && n < 2,
    queryFn: async ({ signal }) => elementGraphToBim(ElementGraph.deserialize(await api.revisionGraph(rid!, signal))),
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

/**
 * Upload an IFC as a model revision: parse it in the browser (ifc-parser -> element graph), then
 * POST the file together with the serialized graph. The backend never re-parses the IFC for topology.
 */
async function uploadIfc(pid: number, file: File, label: string | undefined, onProgress: (m: string) => void) {
  const res = await importModel(file.name, new Uint8Array(await file.arrayBuffer()), onProgress);
  if (res.kind !== 'model' || res.format !== 'ifc') throw new Error(`${file.name} is not an IFC model`);
  onProgress(`Uploading ${file.name} (${res.elementGraph.nodeCount} elements)`);
  const out = await api.uploadModel(pid, file, res.elementGraph.serialize(), label);
  return { revisionId: out.revision, warnings: res.warnings };
}

export function useUploadModel(pid: number | null, onProgress: (m: string) => void) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ file, label }: { file: File; label?: string }) => uploadIfc(pid!, file, label, onProgress),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['projects', pid] }),
  });
}

export function useUploadCalcs(pid: number | null) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (file: File) => ({ revisionId: (await api.uploadCalcs(pid!, file)).revision }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['projects', pid] }),
  });
}

const SAMPLE_MODELS = {
  1: { file: 'model_rev1.ifc', label: 'Sample - Rev 1 issued for permit' },
  2: { file: 'model_rev2.ifc', label: 'Sample - Rev 2 column C8 removed' },
} as const;

/** The sample: its IFC goes through the same browser import + upload as any model; rev 1 also loads the sample calc package. */
export function useLoadSample(pid: number | null, onProgress: (m: string) => void) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (rev: 1 | 2) => {
      const s = SAMPLE_MODELS[rev];
      // calcs first: the backend generates the synthetic package (IFCs included) on first use
      if (rev === 1) {
        onProgress('Ingesting the sample calc package');
        await api.sampleCalcs(pid!);
      }
      onProgress(`Fetching ${s.file}`);
      const file = await api.sampleFile(s.file);
      const model = await uploadIfc(pid!, file, s.label, onProgress);
      return { modelRevisionId: model.revisionId };
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['projects', pid] }),
  });
}
