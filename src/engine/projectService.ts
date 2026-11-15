// Project operations: the local project store (src/data/projectStore.ts) + the calc engine worker
// (src/engine/engineClient.ts). This is what the old HTTP routes did, now in the browser:
//   upload model     -> parse IFC / JSON into an element graph (main thread, web-ifc), store file + graph
//   upload calcs     -> extract + segment the PDF in the worker, place it (a new calc document, or a
//                       new revision of one), store file + extraction
//   project export   -> a model revision's graph (default the head) x the calc SET (every calc
//                       document's head revision) -> mapping run (cached per model rev + set) -> export
//                       with the decision log applied (worker)
//   decide / impact / compare / revision files
// Results are handed back as engine types; src/data/loadProject.ts converts them to view data.
import { ENGINE_VERSION } from '@unloaded/calc-mapper/types';
import { sha256 } from '@unloaded/calc-mapper';
import { documentHeads, docIdOf, storedExtractionFor, type ProjectFileDocument } from '@unloaded/project-file';
import type { CalcPackage, Compare, DecisionFields, Export, Impact, ImpactMode, MappingRun, SerializedElementGraph } from '@unloaded/calc-mapper/types';
import type { CalcSetDiff, CalcSetDocument, KnownDocument, RevisionTarget } from '@unloaded/calc-mapper';
import type { DecisionAction } from '../types/bim';
import { importModel, type ImportResult } from '../loaders/parsers';
import {
  addDecision,
  addRevision,
  addRun,
  calcSetKey,
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
  listDocuments,
  listProjects,
  newDocumentId,
  replaceExtraction,
  listRevisions,
  setRevisionDocument,
  updateDocument,
  type DecisionRecord,
  type ProjectRecord,
  type RevisionRecord,
} from '../data/projectStore';
import { runEngine } from './engineClient';

type Progress = (message: string) => void;

const MEDIA: Record<string, string> = { ifc: 'application/x-step', json: 'application/json', pdf: 'application/pdf' };
const mediaOf = (name: string) => MEDIA[name.split('.').pop()?.toLowerCase() ?? ''] ?? 'application/octet-stream';

function pdfHeaderWindow(bytes: Uint8Array): string {
  return new TextDecoder().decode(bytes.subarray(0, 1024));
}

function isGitLfsPointer(bytes: Uint8Array): boolean {
  return /^version https:\/\/git-lfs\.github\.com\/spec\/v1(?:\r?\n|$)/.test(pdfHeaderWindow(bytes));
}

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
// Keyed by revision id. The store keeps one backend for the whole session and its revision ids come
// from one auto-increment that never reuses an id (not even after a project is deleted), so an entry
// can never answer for a different revision.

const graphCache = new Map<number, Promise<SerializedElementGraph | undefined>>();
const pkgCache = new Map<number, Promise<CalcPackage>>();
const urlCache = new Map<number, Promise<string | null>>();

function revisionGraph(rid: number) {
  let p = graphCache.get(rid);
  if (!p) graphCache.set(rid, (p = getGraph(rid)));
  return p;
}

/**
 * A calc revision's calc package: the stored extraction when `storedExtractionFor` (the rule the MCP
 * server applies too) accepts it against the sha256 of the revision's PDF; otherwise re-extracted from
 * that PDF once, and the new extraction kept. The PDF's sha256 is the one the store recorded when the
 * revision was added (meta.fileSha256), so a valid extraction is used without reading or hashing the
 * PDF; records older than that hash the stored PDF instead. Rejects (with the revision named) when the
 * package cannot be had: no usable extraction and no stored PDF to extract from.
 */
function revisionPackage(rid: number) {
  let p = pkgCache.get(rid);
  if (!p) {
    p = (async () => {
      const [stored, rev] = await Promise.all([getExtraction<unknown>(rid), getRevision(rid)]);
      const name = rev?.sourceName ?? 'calcs.pdf';
      let bytes: Promise<Uint8Array> | null = null;
      const pdf = (): Promise<Uint8Array> =>
        (bytes ??= getBlob(rid).then(async (blob) => {
          if (!blob) throw new Error(`Calc revision #${rid} (${name}) has no stored PDF, so its calc package cannot be read; re-add the PDF as a new calc revision.`);
          return new Uint8Array(await blob.arrayBuffer());
        }));
      const recorded = rev?.meta.fileSha256;
      const use = storedExtractionFor(stored, typeof recorded === 'string' && recorded ? recorded : await sha256(await pdf()));
      if (use.pkg) return use.pkg;
      const fresh = await runEngine('extract', { bytes: await pdf(), sourceName: name });
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

/** What the project holds of each calc document, for placing a new PDF (calc-mapper resolveRevisionTarget). */
async function knownDocuments(projectId: string): Promise<KnownDocument[]> {
  const [documents, revisions] = await Promise.all([listDocuments(projectId), listRevisions(projectId)]);
  const heads = new Map(documentHeads(documents.map((d) => ({ ...d, removed: false })), revisions).map((h) => [h.doc.docId, h.rev]));
  return Promise.all(documents.map(async (d) => {
    const revs = revisions.filter((r) => r.kind === 'calcs' && docIdOf(r) === d.docId);
    const head = heads.get(d.docId);
    const keys = head ? await revisionPackage(head.id).then((p) => p.calcs.map((c) => c.key), () => []) : [];
    return {
      doc_id: d.docId,
      names: revs.map((r) => r.sourceName),
      shas: revs.map((r) => r.meta.fileSha256).filter((x): x is string => typeof x === 'string' && !!x),
      keys,
    };
  }));
}

/** Where an added PDF went: which document, and the rule that placed it (the UI shows it and offers to move it). */
export interface CalcPlacement {
  kind: 'revision' | 'new' | 'duplicate';
  docId: string;
  docName: string;
  /** Why (the engine's suggestion), or "chosen" when the caller named the document. */
  note: string;
  rule: string;
}

/**
 * A calc revision: the PDF + its extracted pages and calcs (the worker reads the PDF), placed in a calc
 * document. `target`: a document id to add it to, 'new' for a new document, or 'auto' (default): the
 * engine's suggestion - the same PDF already loaded is not added again (placement "duplicate", revision
 * null); a file name or calcs matching one document make it that document's next revision; else a new one.
 */
export async function addCalcRevision(
  projectId: string, file: File, label: string | undefined, onProgress: Progress, target: string | 'new' | 'auto' = 'auto',
): Promise<{ revision: RevisionRecord | null; placement: CalcPlacement }> {
  onProgress(`Reading ${file.name}`);
  const bytes = new Uint8Array(await file.arrayBuffer());
  if (isGitLfsPointer(bytes)) {
    throw new Error(`${file.name} is a Git LFS pointer, not PDF content. Install Git LFS and run "git lfs pull" before adding this file.`);
  }
  if (!pdfHeaderWindow(bytes).includes('%PDF-')) {
    throw new Error(`${file.name} is not a readable PDF: no PDF header was found in the first 1024 bytes.`);
  }
  const known = target === 'auto' ? await knownDocuments(projectId) : [];
  const { pkg, target: suggested }: { pkg: CalcPackage; target: RevisionTarget | null } = target === 'auto'
    ? await runEngine('extractPlaced', { bytes, sourceName: file.name, known }, onProgress)
    : { pkg: await runEngine('extract', { bytes, sourceName: file.name }, onProgress), target: null };
  const documents = await listDocuments(projectId);
  const nameOf = (id: string) => documents.find((d) => d.docId === id)?.name ?? id;
  if (suggested?.kind === 'duplicate') {
    return { revision: null, placement: { kind: 'duplicate', docId: suggested.doc_id, docName: nameOf(suggested.doc_id), note: suggested.note, rule: suggested.rule } };
  }
  let docId: string;
  let kind: CalcPlacement['kind'];
  if (target !== 'auto' && target !== 'new') {
    if (!documents.some((d) => d.docId === target)) throw new Error(`Calc document ${target} is not in this project.`);
    [docId, kind] = [target, 'revision'];
  } else if (suggested?.kind === 'revision') {
    [docId, kind] = [suggested.doc_id, 'revision'];
  } else {
    [docId, kind] = [await newDocumentId(projectId), 'new'];
  }
  const revision = await addRevision(
    projectId,
    {
      kind: 'calcs',
      docId,
      label: label ?? file.name,
      sourceName: file.name,
      mediaType: mediaOf(file.name),
      meta: { pages: pkg.pages.length, calcs: pkg.calcs.length },
    },
    file,
    { extraction: pkg },
  );
  const docName = kind === 'new' ? file.name.replace(/\.[A-Za-z0-9]{2,4}$/, '') : nameOf(docId);
  const note = suggested ? suggested.note : 'chosen';
  return { revision, placement: { kind, docId, docName, note, rule: suggested?.rule ?? 'chosen' } };
}

/** Move a calc revision to another document, or to a new one of its own (overriding where an upload was placed). */
export async function moveCalcRevision(projectId: string, revisionId: number, docId: string | 'new'): Promise<string> {
  const to = docId === 'new' ? await newDocumentId(projectId) : docId;
  await setRevisionDocument(projectId, revisionId, to);
  return to;
}

/** Rename a calc document, or withdraw it from / restore it to the calc set. */
export async function changeDocument(projectId: string, docId: string, change: { name?: string; removed?: boolean }): Promise<void> {
  await updateDocument(projectId, docId, change);
}

export type OpenedFile =
  | { kind: 'revision'; revision: RevisionRecord; warnings: string[]; placement?: CalcPlacement }
  | { kind: 'duplicate'; placement: CalcPlacement }
  | { kind: 'project'; projectId: string }
  | { kind: 'export'; export: Export };

/**
 * Any file the app accepts, dispatched by content: a calc PDF or a model (IFC, element graph,
 * ModelInput, legacy BIM JSON) becomes a revision of the current project; a project file becomes a
 * new project; a plain calc-graph export opens read-only.
 */
export async function openAnyFile(projectId: string, file: File, onProgress: Progress): Promise<OpenedFile> {
  const bytes = new Uint8Array(await file.arrayBuffer());
  if (/\.pdf$/i.test(file.name) || pdfHeaderWindow(bytes).includes('%PDF-') || isGitLfsPointer(bytes)) {
    const { revision, placement } = await addCalcRevision(projectId, file, undefined, onProgress);
    return revision ? { kind: 'revision', revision, warnings: [], placement } : { kind: 'duplicate', placement };
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

/** The calc set of a project: every calc document's head revision with its package, in set order. */
export interface CalcSetHead {
  doc: ProjectFileDocument;
  rev: RevisionRecord;
}

/** The mapping run of a (model revision, calc set): from the store, else computed once in the worker and stored. */
async function setRun(
  projectId: string, modelRev: number, heads: CalcSetHead[], graph: SerializedElementGraph, docs: CalcSetDocument[], onProgress: Progress,
): Promise<MappingRun> {
  const calcSet = calcSetKey(heads);
  const stored = await findRun<MappingRun>(projectId, modelRev, calcSet, ENGINE_VERSION);
  // runs stored before typical groups / findings existed are recomputed rather than read half-empty
  if (stored && Array.isArray(stored.data.groups) && Array.isArray(stored.data.findings)) return stored.data;
  onProgress('Mapping calcs onto the model');
  const run = await runEngine('map', { graph, docs }, onProgress);
  await addRun({ projectId, modelRev, calcRev: Math.max(...heads.map((h) => h.rev.id)), calcSet, engine: ENGINE_VERSION, data: run });
  return run;
}

/**
 * The project's calc set: each document's head and its package. A document whose package cannot be read
 * is left out of the set and named in `errors` (the rest still map).
 */
async function calcSetOf(projectId: string, revisions: RevisionRecord[]): Promise<{ heads: CalcSetHead[]; docs: CalcSetDocument[]; errors: string[] }> {
  const all = documentHeads(await listDocuments(projectId), revisions);
  const read = await Promise.all(all.map((h) => revisionPackage(h.rev.id).then(
    (pkg) => ({ h, pkg, error: null as string | null }),
    (e: unknown) => ({ h, pkg: null, error: e instanceof Error ? e.message : String(e) }),
  )));
  const ok = read.filter((x): x is { h: CalcSetHead; pkg: CalcPackage; error: null } => x.pkg !== null);
  return {
    heads: ok.map((x) => x.h),
    docs: ok.map((x) => ({ doc_id: x.h.doc.docId, name: x.h.doc.name, revision: x.h.rev.id, package: x.pkg })),
    errors: read.filter((x) => x.error).map((x) => `${x.h.doc.name}: ${x.error}`),
  };
}

export interface ProjectSnapshot {
  project: ProjectRecord;
  revisions: RevisionRecord[];
  modelRev: RevisionRecord | null;
  /** The calc revision when the set is one document, else the newest head (labels only: the set is `calcSet`). */
  calcRev: RevisionRecord | null;
  /** Every calc document (removed ones too), in set order. */
  documents: ProjectFileDocument[];
  /** The calc set mapped: each live document's head revision (documents whose package could not be read are left out). */
  calcSet: CalcSetHead[];
  /** Set page = document page + offset, per document of the set (the export's `documents`). */
  pageOffsets: Map<string, number>;
  graph: SerializedElementGraph | null;
  /** null until the project has both a model and a calc package (or when the package failed: calcError) */
  exp: Export | null;
  /** why a calc document's package could not be read; the model (and the other documents) are still shown */
  calcError: string | null;
}

/** A model revision of this project, or throw: a stale id (another project's, a deleted one) must fail, not answer. */
async function modelRevisionOf(projectId: string, rid: number): Promise<RevisionRecord> {
  const r = await getRevision(rid);
  if (!r || r.projectId !== projectId || r.kind !== 'model') throw new Error(`Revision #${rid} is not a model revision of this project.`);
  return r;
}

/** The model revision to show: the one asked for (checked to be this project's), else the head. */
async function chosenModelRev(project: ProjectRecord, modelRev: number | null | undefined): Promise<RevisionRecord | null> {
  if (modelRev != null) return modelRevisionOf(project.id, modelRev);
  return project.headModelRev != null ? ((await getRevision(project.headModelRev)) ?? null) : null;
}

/** The project as the engine sees it, for one model revision (default: the head) and the head calc package. */
export async function projectSnapshot(projectId: string, onProgress: Progress = () => {}, modelRev?: number | null): Promise<ProjectSnapshot> {
  const project = await getProject(projectId);
  if (!project) throw new Error('This project no longer exists.');
  // the revision asked for is checked before any engine work starts, so a refused snapshot never
  // leaves a PDF extraction running in the background
  const model = await chosenModelRev(project, modelRev);
  const revisions = await listRevisions(projectId);
  // a calc package that cannot be read degrades the view (that document left out, calcError says
  // why) rather than failing it: the element graph does not depend on it
  const [documents, set] = await Promise.all([listDocuments(projectId), calcSetOf(projectId, revisions)]);
  const graph = model ? ((await revisionGraph(model.id)) ?? null) : null;
  const one = set.heads.length === 1 ? set.heads[0]!.rev : null;
  const calcRev = one ?? (set.heads.length ? set.heads.reduce((a, b) => (b.rev.id > a.rev.id ? b : a)).rev : null);
  let exp: Export | null = null;
  if (model && graph && set.heads.length) {
    const run = await setRun(projectId, model.id, set.heads, graph, set.docs, onProgress);
    const decisions = (await decisionLog(projectId)).map(toDecision);
    exp = await runEngine('export', {
      graph,
      docs: set.docs,
      run,
      decisions,
      info: {
        model: model.sourceName,
        model_revision: model.id,
        calc_package: one ? one.sourceName : `${set.heads.length} calc documents`,
        calc_revision: one ? one.id : null,
      },
    });
  }
  let offset = 0;
  const pageOffsets = new Map<string, number>();
  for (const d of set.docs) {
    pageOffsets.set(d.doc_id, offset);
    offset += Math.max(...d.package.pages.map((p) => p.n));
  }
  return {
    project, revisions, modelRev: model, calcRev, documents, calcSet: set.heads, pageOffsets, graph, exp,
    calcError: set.errors.length ? set.errors.join('; ') : null,
  };
}

/** Calc revision diff: a calc document's revision `a` against `b` (both of this project), or the whole set at two moments. */
export async function compareCalcRevisions(projectId: string, a: number, b: number): Promise<CalcSetDiff> {
  const [ra, rb] = await Promise.all([getRevision(a), getRevision(b)]);
  for (const [id, r] of [[a, ra], [b, rb]] as const) {
    if (!r || r.projectId !== projectId || r.kind !== 'calcs') throw new Error(`Revision #${id} is not a calc revision of this project.`);
  }
  const [pa, pb] = await Promise.all([revisionPackage(a), revisionPackage(b)]);
  // the two revisions are compared as one document (a later revision of the same, or a document moved)
  const doc = docIdOf(rb!);
  return runEngine('calcDiff', {
    before: [{ doc_id: doc, name: ra!.sourceName, revision: a, package: pa }],
    after: [{ doc_id: doc, name: rb!.sourceName, revision: b, package: pb }],
  });
}

/**
 * Record a review decision against the model revision on screen (default: the head) and the head revision
 * of the calc's document. `calcKey` is the calc ref the export gave ("<docId>#<key>").
 */
export async function decide(projectId: string, elementId: string, calcKey: string, action: DecisionAction, modelRev?: number | null): Promise<void> {
  const p = await getProject(projectId);
  if (!p) throw new Error('This project no longer exists.');
  const m = await chosenModelRev(p, modelRev);
  const docId = calcKey.includes('#') ? calcKey.slice(0, calcKey.indexOf('#')) : null;
  const head = docId ? documentHeads(await listDocuments(projectId), await listRevisions(projectId)).find((h) => h.doc.docId === docId) : null;
  await addDecision({ projectId, globalId: elementId, calcKey, action, actor: 'reviewer', note: null, modelRev: m?.id ?? null, calcRev: head?.rev.id ?? p.headCalcRev });
}

/** Impact of changing / removing an element in a model revision (default: the head) with the head calc package. */
export async function impactOf(projectId: string, globalId: string, mode: ImpactMode, modelRev?: number | null): Promise<Impact> {
  const project = await getProject(projectId);
  if (!project) throw new Error('This project no longer exists.');
  const m = await chosenModelRev(project, modelRev);
  if (!m) throw new Error('No model in this project.');
  const graph = await revisionGraph(m.id);
  if (!graph) throw new Error(`Model revision #${m.id} has no element graph.`);
  const set = await calcSetOf(projectId, await listRevisions(projectId));
  const docs = set.heads.length ? set.docs : null;
  const run = docs ? await setRun(projectId, m.id, set.heads, graph, docs, () => {}) : null;
  const decisions = (await decisionLog(projectId)).map(toDecision);
  return runEngine('impact', { graph, docs, run, decisions, globalId, mode });
}

type Box = { min: [number, number, number]; max: [number, number, number] };

/**
 * The one revision diff (`diffGraphs`): the element graphs of two model revisions of this project
 * (a or b from elsewhere is refused). Also, for the elements only one side has, their element-graph
 * box (ghost geometry when a revision has no IFC to mesh) and element-graph kind (the engine's `cat`
 * folds kinds together, e.g. fastener into Connection).
 */
export async function compareRevisions(projectId: string, a: number, b: number): Promise<{ compare: Compare; boxes: Map<string, Box>; kinds: Map<string, string> }> {
  await Promise.all([modelRevisionOf(projectId, a), modelRevisionOf(projectId, b)]);
  const [ga, gb] = await Promise.all([revisionGraph(a), revisionGraph(b)]);
  if (!ga || !gb) throw new Error(`Revision #${!ga ? a : b} has no element graph to compare.`);
  const compare = await runEngine('diff', { a: ga, b: gb, labelA: a, labelB: b });
  const boxes = new Map<string, Box>();
  const kinds = new Map<string, string>();
  const want = new Set([...compare.removed, ...compare.added].map((x) => x.global_id));
  for (const n of [...ga.nodes, ...gb.nodes]) {
    if (!want.has(n.id)) continue;
    kinds.set(n.id, n.kind);
    const bb = n.geometry?.bbox;
    if (bb) boxes.set(n.id, { min: [bb.min[0], bb.min[1], bb.min[2]], max: [bb.max[0], bb.max[1], bb.max[2]] });
  }
  return { compare, boxes, kinds };
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
