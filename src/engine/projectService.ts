// Project operations: the local project store (src/data/projectStore.ts) + the calc engine worker
// (src/engine/engineClient.ts). This is what the old HTTP routes did, now in the browser:
//   upload model     -> parse IFC / JSON into an element graph (main thread, web-ifc), store file + graph
//   upload calcs     -> extract + segment the PDF in the worker, store file + extraction
//   project export   -> head graph x head package -> mapping run (cached per revision pair) ->
//                       export with the decision log applied (worker)
//   decide / impact / compare / revision files
// Results are handed back as engine types; src/data/loadProject.ts converts them to view data.
import { ENGINE_VERSION } from '@unloaded/calc-mapper/types';
import type { CalcPackage, Compare, DecisionFields, Export, Impact, ImpactMode, MappingRun, SerializedElementGraph } from '@unloaded/calc-mapper/types';
import type { DecisionAction } from '../types/bim';
import { importModel, type ImportResult } from '../loaders/parsers';
import {
  addDecision,
  addRevision,
  addRun,
  createProject,
  decisionLog,
  exportProject,
  findRun,
  getBlob,
  getExtraction,
  getGraph,
  getProject,
  getRevision,
  importProject,
  listProjects,
  replaceExtraction,
  listRevisions,
  type DecisionRecord,
  type ProjectRecord,
  type RevisionRecord,
} from '../data/projectStore';
import { runEngine } from './engineClient';

type Progress = (message: string) => void;

const MEDIA: Record<string, string> = { ifc: 'application/x-step', json: 'application/json', pdf: 'application/pdf' };
const mediaOf = (name: string) => MEDIA[name.split('.').pop()?.toLowerCase() ?? ''] ?? 'application/octet-stream';

// ---------------------------------------------------------------- projects

const ACTIVE_KEY = 'calc-graph.active-project';

/** The project the app opens: the last one used (a per-browser convenience), else the newest, else a new one. */
export async function openActiveProject(): Promise<ProjectRecord> {
  let id: string | null = null;
  try {
    id = localStorage.getItem(ACTIVE_KEY);
  } catch {
    /* storage blocked: fine, fall through */
  }
  const p = (id && (await getProject(id))) || (await listProjects())[0] || (await createProject('Untitled project'));
  rememberActiveProject(p.id);
  return p;
}

export function rememberActiveProject(id: string) {
  try {
    localStorage.setItem(ACTIVE_KEY, id);
  } catch {
    /* storage blocked */
  }
}

// ---------------------------------------------------------------- caches (revisions never change)

const graphCache = new Map<number, Promise<SerializedElementGraph | undefined>>();
const pkgCache = new Map<number, Promise<CalcPackage | undefined>>();
const urlCache = new Map<number, Promise<string | null>>();

function revisionGraph(rid: number) {
  let p = graphCache.get(rid);
  if (!p) graphCache.set(rid, (p = getGraph(rid)));
  return p;
}
function revisionPackage(rid: number) {
  let p = pkgCache.get(rid);
  if (!p) {
    p = (async () => {
      const pkg = await getExtraction<CalcPackage>(rid);
      // extractions stored before the provenance contract carry no document hash, which the engine
      // requires: re-read them once from the stored PDF and keep the new extraction
      if (pkg && pkg.source_sha256 && pkg.pages.every((pg) => pg.doc_sha256)) return pkg;
      const blob = await getBlob(rid);
      if (!blob) return pkg;
      const rev = await getRevision(rid);
      const fresh = await runEngine('extract', { bytes: new Uint8Array(await blob.arrayBuffer()), sourceName: rev?.sourceName ?? 'calcs.pdf' });
      await replaceExtraction(rid, fresh);
      return fresh;
    })();
    p.catch(() => pkgCache.delete(rid));
    pkgCache.set(rid, p);
  }
  return p;
}

/** An object URL for a revision's source file (IFC for 3D, PDF for the viewer); made once per session. */
export function revisionFileUrl(rid: number): Promise<string | null> {
  let p = urlCache.get(rid);
  if (!p) {
    p = getBlob(rid).then((b) => (b ? URL.createObjectURL(b) : null));
    urlCache.set(rid, p);
  }
  return p;
}

export { revisionGraph as getRevisionGraph };

// ---------------------------------------------------------------- ingest

/** A model revision: the file + the element graph built from it in the browser (never re-parsed later). */
export async function addModelRevision(projectId: string, file: File, label: string | undefined, onProgress: Progress): Promise<{ revision: RevisionRecord; warnings: string[] }> {
  const res = await importModel(file.name, new Uint8Array(await file.arrayBuffer()), onProgress);
  if (res.kind !== 'model') throw new Error(`${file.name} is not a model (IFC, element graph, ModelInput or legacy BIM JSON)`);
  return storeModel(projectId, file, res, label, onProgress);
}

async function storeModel(
  projectId: string,
  file: File,
  res: Extract<ImportResult, { kind: 'model' }>,
  label: string | undefined,
  onProgress: Progress,
): Promise<{ revision: RevisionRecord; warnings: string[] }> {
  onProgress(`Saving ${file.name} (${res.elementGraph.nodeCount} elements)`);
  const revision = await addRevision(
    projectId,
    {
      kind: 'model',
      label: label ?? res.projectName ?? file.name,
      sourceName: file.name,
      mediaType: mediaOf(file.name),
      meta: { format: res.format, elements: res.elementGraph.nodeCount, project: res.projectName ?? null },
    },
    file,
    { graph: res.elementGraph.serialize() },
  );
  return { revision, warnings: res.warnings };
}

/** A calc revision: the PDF + its extracted pages and calcs (the worker reads the PDF). */
export async function addCalcRevision(projectId: string, file: File, label: string | undefined, onProgress: Progress): Promise<RevisionRecord> {
  onProgress(`Reading ${file.name}`);
  const pkg = await runEngine('extract', { bytes: new Uint8Array(await file.arrayBuffer()), sourceName: file.name }, onProgress);
  return addRevision(
    projectId,
    {
      kind: 'calcs',
      label: label ?? file.name,
      sourceName: file.name,
      mediaType: mediaOf(file.name),
      meta: { pages: pkg.pages.length, calcs: pkg.calcs.length },
    },
    file,
    { extraction: pkg },
  );
}

export type OpenedFile =
  | { kind: 'revision'; revision: RevisionRecord; warnings: string[] }
  | { kind: 'project'; projectId: string }
  | { kind: 'export'; export: Export };

/**
 * Any file the app accepts, dispatched by content: a calc PDF or a model (IFC, element graph,
 * ModelInput, legacy BIM JSON) becomes a revision of the current project; a project file becomes a
 * new project; a plain calc-graph export opens read-only.
 */
export async function openAnyFile(projectId: string, file: File, onProgress: Progress): Promise<OpenedFile> {
  const bytes = new Uint8Array(await file.arrayBuffer());
  const head = new TextDecoder().decode(bytes.subarray(0, 5));
  if (/\.pdf$/i.test(file.name) || head === '%PDF-') {
    return { kind: 'revision', revision: await addCalcRevision(projectId, file, undefined, onProgress), warnings: [] };
  }
  const res = await importModel(file.name, bytes, onProgress);
  if (res.kind === 'project-file') {
    onProgress(`Importing project ${res.project.project.name}`);
    const p = await importProject(res.project);
    rememberActiveProject(p.id);
    return { kind: 'project', projectId: p.id };
  }
  if (res.kind === 'export') return { kind: 'export', export: res.export };
  const { revision, warnings } = await storeModel(projectId, file, res, undefined, onProgress);
  return { kind: 'revision', revision, warnings };
}

// ---------------------------------------------------------------- the project as the engine sees it

// the engine attaches each decision's provenance from these fields (decisionFrom)
const toDecision = (d: DecisionRecord): DecisionFields => ({
  id: d.id,
  global_id: d.globalId,
  calc_key: d.calcKey,
  action: d.action,
  actor: d.actor,
  note: d.note,
  at: d.at,
  model_rev: d.modelRev,
  calc_rev: d.calcRev,
});

/** The head mapping run of a (model, calcs) pair: from the store, else computed once in the worker and stored. */
async function headRun(projectId: string, modelRev: number, calcRev: number, graph: SerializedElementGraph, pkg: CalcPackage, onProgress: Progress): Promise<MappingRun> {
  const stored = await findRun<MappingRun>(projectId, modelRev, calcRev, ENGINE_VERSION);
  // runs stored before typical groups / findings existed are recomputed rather than read half-empty
  if (stored && Array.isArray(stored.data.groups) && Array.isArray(stored.data.findings)) return stored.data;
  onProgress('Mapping calcs onto the model');
  const run = await runEngine('map', { graph, pkg }, onProgress);
  await addRun({ projectId, modelRev, calcRev, engine: ENGINE_VERSION, data: run });
  return run;
}

export interface ProjectSnapshot {
  project: ProjectRecord;
  revisions: RevisionRecord[];
  modelRev: RevisionRecord | null;
  calcRev: RevisionRecord | null;
  graph: SerializedElementGraph | null;
  /** null until the project has both a model and a calc package */
  exp: Export | null;
}

export async function projectSnapshot(projectId: string, onProgress: Progress = () => {}): Promise<ProjectSnapshot> {
  const project = await getProject(projectId);
  if (!project) throw new Error('This project no longer exists.');
  const m = project.headModelRev;
  const k = project.headCalcRev;
  const [revisions, modelRev, calcRev, graph, pkg] = await Promise.all([
    listRevisions(projectId),
    m != null ? getRevision(m).then((r) => r ?? null) : null,
    k != null ? getRevision(k).then((r) => r ?? null) : null,
    m != null ? revisionGraph(m).then((g) => g ?? null) : null,
    k != null ? revisionPackage(k).then((x) => x ?? null) : null,
  ]);
  let exp: Export | null = null;
  if (modelRev && calcRev && graph && pkg) {
    const run = await headRun(projectId, modelRev.id, calcRev.id, graph, pkg, onProgress);
    const decisions = (await decisionLog(projectId)).map(toDecision);
    exp = await runEngine('export', {
      graph,
      pkg,
      run,
      decisions,
      info: { model: modelRev.sourceName, model_revision: modelRev.id, calc_package: calcRev.sourceName, calc_revision: calcRev.id },
    });
  }
  return { project, revisions, modelRev, calcRev, graph, exp };
}

export async function decide(projectId: string, elementId: string, calcKey: string, action: DecisionAction): Promise<void> {
  const p = await getProject(projectId);
  await addDecision({ projectId, globalId: elementId, calcKey, action, actor: 'reviewer', note: null, modelRev: p?.headModelRev ?? null, calcRev: p?.headCalcRev ?? null });
}

export async function impactOf(projectId: string, globalId: string, mode: ImpactMode): Promise<Impact> {
  const project = await getProject(projectId);
  if (!project?.headModelRev) throw new Error('No model in this project.');
  const graph = await revisionGraph(project.headModelRev);
  if (!graph) throw new Error('The head model revision has no element graph.');
  const pkg = project.headCalcRev != null ? ((await revisionPackage(project.headCalcRev)) ?? null) : null;
  const run = pkg && project.headCalcRev != null ? await headRun(projectId, project.headModelRev, project.headCalcRev, graph, pkg, () => {}) : null;
  const decisions = (await decisionLog(projectId)).map(toDecision);
  return runEngine('impact', { graph, pkg, run, decisions, globalId, mode });
}

/** The one revision diff (`diffGraphs`): the element graphs of two model revisions. */
export async function compareRevisions(a: number, b: number): Promise<{ compare: Compare; boxes: Map<string, { min: [number, number, number]; max: [number, number, number] }> }> {
  const [ga, gb] = await Promise.all([revisionGraph(a), revisionGraph(b)]);
  if (!ga || !gb) throw new Error(`Revision #${!ga ? a : b} has no element graph to compare.`);
  const compare = await runEngine('diff', { a: ga, b: gb, labelA: a, labelB: b });
  // boxes of the elements only one side has, for ghosts when a revision has no IFC to mesh
  const boxes = new Map<string, { min: [number, number, number]; max: [number, number, number] }>();
  const want = new Set([...compare.removed, ...compare.added].map((x) => x.global_id));
  for (const n of [...ga.nodes, ...gb.nodes]) {
    const bb = n.geometry?.bbox;
    if (bb && want.has(n.id)) boxes.set(n.id, { min: [bb.min[0], bb.min[1], bb.min[2]], max: [bb.max[0], bb.max[1], bb.max[2]] });
  }
  return { compare, boxes };
}

/** Element counts per revision, for the revision panel. */
export async function revisionCounts(revs: RevisionRecord[]): Promise<Map<number, number>> {
  const out = new Map<number, number>();
  for (const r of revs) {
    const n = r.kind === 'model' ? r.meta.elements : r.meta.calcs;
    if (typeof n === 'number') out.set(r.id, n);
  }
  return out;
}

/** Save the whole project (files, graphs, extractions, decision log) as one file for a colleague. */
export async function downloadProjectFile(projectId: string): Promise<string> {
  const file = await exportProject(projectId);
  const name = `${file.project.name.replace(/[^\w.-]+/g, '-').replace(/^-|-$/g, '') || 'project'}.calcgraph.json`;
  const url = URL.createObjectURL(new Blob([JSON.stringify(file)], { type: 'application/json' }));
  const a = document.createElement('a');
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
  return name;
}

// ---------------------------------------------------------------- samples (shipped in public/samples by scripts/copy-assets.mjs)

export class SampleMissingError extends Error {
  constructor(file: string) {
    super(`Sample not generated (${file} missing). Run: cd tools/calcgraph-reference && uv run python -m synth.generate, then npm run assets.`);
    this.name = 'SampleMissingError';
  }
}

export async function sampleFile(path: string, name: string): Promise<File> {
  const url = `${import.meta.env.BASE_URL}samples/${path}`;
  const r = await fetch(url);
  // Vite's SPA fallback answers a missing file with index.html, so check the type too
  const type = r.headers.get('content-type') ?? '';
  if (!r.ok || type.includes('text/html')) throw new SampleMissingError(path);
  return new File([await r.blob()], name, { type: mediaOf(name) });
}
