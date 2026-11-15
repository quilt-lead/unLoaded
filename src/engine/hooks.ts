// TanStack Query hooks over the local project store + calc engine worker. Every read hook hands
// back VIEW data (src/types/bim.ts): engine output is converted by src/data/loadProject.ts, element
// graphs by src/loaders/elementGraphToBim.ts, and the two are joined by src/data/mergeProject.ts.
// Components never see an engine type, a store record or an ElementGraph.
// Keys are rooted at ["projects", id] so a mutation can invalidate a whole project in one call.
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ElementGraph } from '@unloaded/element-graph';
import type { DecisionAction, ProjectViewModel } from '../types/bim';
import { toCalcData, toImpactView, toModelDiff, toRevisionList } from '../data/loadProject';
import { mergeProject } from '../data/mergeProject';
import { elementGraphToBim } from '../loaders/elementGraphToBim';
import { createProject, deleteProject, listProjects, storeInfo } from '../data/projectStore';
import {
  addCalcRevision,
  addModelRevision,
  compareRevisions,
  decide,
  impactOf,
  openActiveProject,
  projectSnapshot,
  rememberActiveProject,
  revisionCounts,
  revisionFileUrl,
  sampleFile,
} from './projectService';

type Progress = (m: string) => void;

export const useStoreInfo = () => useQuery({ queryKey: ['store-info'], queryFn: storeInfo, staleTime: Infinity });

export const useProjectList = () => useQuery({ queryKey: ['projects'], queryFn: listProjects });

/** The active project id: the last one used, else the newest, else a new empty one. */
export const useInitialProject = () => useQuery({ queryKey: ['initial-project'], queryFn: openActiveProject, staleTime: Infinity });

/** The project as view data for one model revision (default: the head). */
async function projectView(projectId: string, onProgress: Progress, modelRev: number | null) {
  const snap = await projectSnapshot(projectId, onProgress, modelRev);
  const counts = await revisionCounts(snap.revisions);
  const revisions = toRevisionList(snap.revisions, { model: snap.project.headModelRev, calcs: snap.project.headCalcRev }, counts);
  let view: ProjectViewModel | null = null;
  // the engine's export needs the model's graph, so there is a view exactly when there is a graph
  // (a calc package without a model shows no element view; `hasCalcPackage` still says it exists)
  if (snap.graph) {
    const topology = elementGraphToBim(ElementGraph.deserialize(snap.graph), { projectName: snap.project.name });
    const calc = snap.exp
      ? toCalcData(snap.exp, { projectName: snap.project.name, modelRevisionId: snap.modelRev?.id ?? null, calcRevisionId: snap.calcRev?.id ?? null })
      : null;
    view = mergeProject(topology, calc, {
      source: 'project',
      projectId: snap.project.id,
      modelFileUrl: snap.modelRev && snap.modelRev.mediaType === 'application/x-step' ? await revisionFileUrl(snap.modelRev.id) : null,
    });
    if (!calc) {
      // a model without a calc package: name the revisions shown (the export would have)
      view = {
        ...view,
        modelName: snap.modelRev?.sourceName ?? null,
        modelRevisionId: snap.modelRev?.id ?? null,
        calcPackageName: snap.calcRev?.sourceName ?? null,
        calcRevisionId: snap.calcRev?.id ?? null,
      };
    }
  }
  return {
    project: { id: snap.project.id, name: snap.project.name },
    revisions,
    hasCalcPackage: Boolean(snap.calcRev),
    /** the head calc package could not be read: the model is shown without calc data, and this says why */
    calcError: snap.calcError,
    view,
    // one document: its PDF; a set: each document's PDF by docId (the view's calcs name their docId), and the first as the fallback
    pdfUrl: snap.calcSet.length ? await revisionFileUrl(snap.calcSet[0]!.rev.id) : null,
    pdfUrls: Object.fromEntries(
      (await Promise.all(snap.calcSet.map(async (h) => [h.doc.docId, await revisionFileUrl(h.rev.id)] as const))).filter((e): e is readonly [string, string] => !!e[1]),
    ) as Record<string, string>,
  };
}

/**
 * The project as view data: a model revision's element graph (topology; `modelRev`, default the
 * head) merged with the calc engine's export against the head calc package (links, evidence,
 * decisions applied). Also the revision list for the panel. A `modelRev` that is not a model
 * revision of this project fails the query. While another revision of the SAME project loads, the
 * previous view stays on screen (never another project's).
 */
export const useProjectView = (projectId: string | null, onProgress: Progress, modelRev?: number | null) =>
  useQuery({
    queryKey: ['projects', projectId, 'view', modelRev ?? null],
    enabled: projectId != null,
    queryFn: () => projectView(projectId!, onProgress, modelRev ?? null),
    placeholderData: (previous, previousQuery) => (previousQuery?.queryKey[1] === projectId ? previous : undefined),
  });

/** Object URLs for revisions' files (ghost geometry of a diff, opening a calc revision's PDF). */
export const useRevisionUrls = (rids: number[]) =>
  useQuery({
    queryKey: ['revision-urls', rids],
    enabled: rids.length > 0,
    staleTime: Infinity,
    queryFn: async () => {
      const out = new Map<number, string>();
      for (const rid of rids) {
        const u = await revisionFileUrl(rid);
        if (u) out.set(rid, u);
      }
      return out;
    },
  });

/** Impact in a model revision (`modelRev`, default the head: pass the revision of the view on screen). */
export const useImpact = (projectId: string | null, gid: string | null, mode: 'change' | 'remove', modelRev?: number | null) =>
  useQuery({
    queryKey: ['projects', projectId, 'impact', gid, mode, modelRev ?? null],
    enabled: projectId != null && !!gid,
    queryFn: async () => toImpactView(await impactOf(projectId!, gid!, mode, modelRev)),
  });

export const useCompare = (projectId: string | null, a: number | null, b: number | null) =>
  useQuery({
    queryKey: ['projects', projectId, 'compare', a, b],
    enabled: projectId != null && a != null && b != null && a !== b,
    queryFn: async () => {
      const { compare, boxes, kinds } = await compareRevisions(projectId!, a!, b!);
      return { ...toModelDiff(compare, kinds), ghostBoxes: boxes };
    },
  });

/**
 * Review decisions. Each one names the model revision it was made on (`modelRev`: the revision of the
 * view on screen when the reviewer clicked, never a revision still loading), so its provenance is
 * what the reviewer saw.
 */
export function useDecide(projectId: string | null) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { elementId: string; calcKey: string; action: DecisionAction; modelRev: number | null }) =>
      decide(projectId!, v.elementId, v.calcKey, v.action, v.modelRev),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['projects', projectId] }),
  });
}

/** A model file as a new revision of `projectId` (named per call: the project the upload started in). */
export function useUploadModel(onProgress: Progress) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ projectId, file, label }: { projectId: string; file: File; label?: string }) => {
      const { revision, warnings } = await addModelRevision(projectId, file, label, onProgress);
      return { revisionId: revision.id, warnings };
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['projects'] }),
  });
}

/**
 * A calc PDF into `projectId` (named per call, as useUploadModel), placed as a new calc document or the
 * next revision of one (`target`, default the engine's suggestion). `revisionId` is null when the same PDF
 * was already loaded (`placement.kind` "duplicate").
 */
export function useUploadCalcs(onProgress: Progress) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ projectId, file, label, target }: { projectId: string; file: File; label?: string; target?: string | 'new' | 'auto' }) => {
      const { revision, placement } = await addCalcRevision(projectId, file, label, onProgress, target);
      return { revisionId: revision?.id ?? null, placement };
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['projects'] }),
  });
}

const SAMPLE = {
  calcs: { path: 'calc_package.pdf', label: 'Sample calc package' },
  1: { path: 'model_rev1.ifc', label: 'Sample - Rev 1 issued for permit' },
  2: { path: 'model_rev2.ifc', label: 'Sample - Rev 2 column C8 removed' },
} as const;

/** The synthetic sample: rev 1 = model + calc package into a new project; rev 2 = a second model revision of the current one. */
export function useLoadSample(onProgress: Progress) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ rev, projectId }: { rev: 1 | 2; projectId: string | null }) => {
      const model = await sampleFile(SAMPLE[rev].path, SAMPLE[rev].path);
      let pid = projectId;
      if (rev === 1 || !pid) {
        pid = (await createProject('Sample office building')).id;
        rememberActiveProject(pid);
      }
      const { revision } = await addModelRevision(pid, model, SAMPLE[rev].label, onProgress);
      if (rev === 1) {
        const pdf = await sampleFile(SAMPLE.calcs.path, SAMPLE.calcs.path);
        await addCalcRevision(pid, pdf, SAMPLE.calcs.label, onProgress);
      }
      return { projectId: pid, modelRevisionId: revision.id };
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['projects'] }),
  });
}

/** The synthetic calc supplement (design vs loads roles, a typical group, a size mismatch) as a new calc revision. */
export function useLoadSupplement(onProgress: Progress) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (projectId: string) => {
      const pdf = await sampleFile('calc_supplement.pdf', 'calc_supplement.pdf');
      await addCalcRevision(projectId, pdf, 'Sample calc supplement', onProgress);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['projects'] }),
  });
}

/** Noah's Harborview A/B demo (legacy JSON with invented documents): two model revisions of a new project. */
export function useLoadDemo(onProgress: Progress) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const a = await sampleFile('demo/harborview-tower-rev1-base.json', 'harborview-tower-rev1-base.json');
      const b = await sampleFile('demo/harborview-tower-rev2-compare.json', 'harborview-tower-rev2-compare.json');
      const pid = (await createProject('Harborview Corporate Center (demo data)')).id;
      rememberActiveProject(pid);
      const ra = await addModelRevision(pid, a, 'Rev 1 base (demo)', onProgress);
      const rb = await addModelRevision(pid, b, 'Rev 2 compare (demo)', onProgress);
      return { projectId: pid, a: ra.revision.id, b: rb.revision.id };
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['projects'] }),
  });
}

export function useCreateProject() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (name: string) => {
      const p = await createProject(name);
      rememberActiveProject(p.id);
      return p.id;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['projects'] }),
  });
}

export function useDeleteProject() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteProject(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['projects'] }),
  });
}
