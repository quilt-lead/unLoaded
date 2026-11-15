// The local project store: everything a project is, kept in the browser (IndexedDB), so models and
// calc packages never leave the engineer's machine. Falls back to memory when IndexedDB is
// unavailable (private windows, blocked storage, tests): the app works, nothing persists, and
// `storeInfo().persistent` says so.
//
// Object stores (database "unloaded-calc-graph", version 1)
//   projects    id (string)              { id, name, createdAt, updatedAt, headModelRev, headCalcRev }
//   revisions   id (auto number)         { id, projectId, kind: 'model'|'calcs', seq, label, sourceName,
//                                          mediaType, createdAt, meta }           index: projectId
//   blobs       revisionId               { revisionId, blob }   the original IFC / PDF / JSON file
//   graphs      revisionId               { revisionId, graph }  model revisions: ElementGraph.serialize()
//                                                               (built once at import; never re-parse to get it)
//   extractions revisionId               { revisionId, data }   calc revisions: extracted pages + segmented calcs
//   runs        id (auto number)         { id, projectId, modelRev, calcRev, engine, createdAt, data }
//                                                               one mapping run per (model rev, calc rev, engine)
//   decisions   id (auto number)         { id, projectId, globalId, calcKey, action, actor, note, at,
//                                          modelRev, calcRev }   APPEND-ONLY; keyed by (globalId, calcKey),
//                                                               latest wins, so they carry across revisions
import type { SerializedElementGraph } from '@unloaded/element-graph';
import type { DecisionAction } from '../types/bim';

export interface ProjectRecord {
  id: string;
  name: string;
  createdAt: string;
  updatedAt: string;
  headModelRev: number | null;
  headCalcRev: number | null;
}

export interface RevisionRecord {
  id: number;
  projectId: string;
  kind: 'model' | 'calcs';
  seq: number;
  label: string;
  sourceName: string;
  mediaType: string;
  createdAt: string;
  meta: Record<string, string | number | boolean | null>;
}

export interface RunRecord<T = unknown> {
  id: number;
  projectId: string;
  modelRev: number;
  calcRev: number;
  engine: string;
  createdAt: string;
  data: T;
}

export interface DecisionRecord {
  id: number;
  projectId: string;
  globalId: string;
  calcKey: string;
  action: DecisionAction;
  actor: string;
  note: string | null;
  at: string;
  modelRev: number | null;
  calcRev: number | null;
}

type StoreName = 'projects' | 'revisions' | 'blobs' | 'graphs' | 'extractions' | 'runs' | 'decisions';
const AUTO: StoreName[] = ['revisions', 'runs', 'decisions'];
const KEYS: Record<StoreName, string> = {
  projects: 'id',
  revisions: 'id',
  blobs: 'revisionId',
  graphs: 'revisionId',
  extractions: 'revisionId',
  runs: 'id',
  decisions: 'id',
};
const BY_PROJECT: StoreName[] = ['revisions', 'runs', 'decisions'];

/** Times are stored with their Eastern offset, e.g. 2026-11-14T19:40:00-05:00 */
export function nowEastern(): string {
  const d = new Date();
  d.setMilliseconds(0);
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: 'America/New_York',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).formatToParts(d);
  const get = (t: string) => Number(parts.find((p) => p.type === t)?.value ?? 0);
  const hour = get('hour') % 24;
  const wall = Date.UTC(get('year'), get('month') - 1, get('day'), hour, get('minute'), get('second'));
  const offMin = Math.round((wall - d.getTime()) / 60000);
  const pad = (n: number) => String(Math.abs(n)).padStart(2, '0');
  const sign = offMin < 0 ? '-' : '+';
  return `${get('year')}-${pad(get('month'))}-${pad(get('day'))}T${pad(hour)}:${pad(get('minute'))}:${pad(get('second'))}${sign}${pad(Math.trunc(offMin / 60))}:${pad(offMin % 60)}`;
}

// ------------------------------------------------------------------------------------------------
// Two backends behind one tiny interface: IndexedDB, or memory.

interface Backend {
  persistent: boolean;
  get<T>(store: StoreName, key: IDBValidKey): Promise<T | undefined>;
  put<T extends object>(store: StoreName, value: T): Promise<IDBValidKey>;
  byProject<T>(store: StoreName, projectId: string): Promise<T[]>;
  all<T>(store: StoreName): Promise<T[]>;
  remove(store: StoreName, key: IDBValidKey): Promise<void>;
}

class MemoryBackend implements Backend {
  persistent = false;
  private data = new Map<StoreName, Map<IDBValidKey, unknown>>();
  private seq = 0;
  private table(s: StoreName) {
    let t = this.data.get(s);
    if (!t) this.data.set(s, (t = new Map()));
    return t;
  }
  async get<T>(store: StoreName, key: IDBValidKey) {
    return this.table(store).get(key) as T | undefined;
  }
  async put<T extends object>(store: StoreName, value: T) {
    const k = KEYS[store];
    const rec = { ...value } as Record<string, unknown>;
    if (AUTO.includes(store) && rec[k] == null) rec[k] = ++this.seq;
    this.table(store).set(rec[k] as IDBValidKey, rec);
    return rec[k] as IDBValidKey;
  }
  async byProject<T>(store: StoreName, projectId: string) {
    return [...this.table(store).values()].filter((v) => (v as { projectId?: string }).projectId === projectId) as T[];
  }
  async all<T>(store: StoreName) {
    return [...this.table(store).values()] as T[];
  }
  async remove(store: StoreName, key: IDBValidKey) {
    this.table(store).delete(key);
  }
}

const req = <T>(r: IDBRequest<T>) =>
  new Promise<T>((resolve, reject) => {
    r.onsuccess = () => resolve(r.result);
    r.onerror = () => reject(r.error);
  });

class IdbBackend implements Backend {
  persistent = true;
  constructor(private db: IDBDatabase) {}
  private tx(store: StoreName, mode: IDBTransactionMode) {
    return this.db.transaction(store, mode).objectStore(store);
  }
  get<T>(store: StoreName, key: IDBValidKey) {
    return req(this.tx(store, 'readonly').get(key)) as Promise<T | undefined>;
  }
  put<T extends object>(store: StoreName, value: T) {
    const k = KEYS[store];
    const rec = { ...value } as Record<string, unknown>;
    if (AUTO.includes(store) && rec[k] == null) delete rec[k]; // let autoIncrement assign it
    return req(this.tx(store, 'readwrite').put(rec));
  }
  byProject<T>(store: StoreName, projectId: string) {
    return req(this.tx(store, 'readonly').index('projectId').getAll(projectId)) as Promise<T[]>;
  }
  all<T>(store: StoreName) {
    return req(this.tx(store, 'readonly').getAll()) as Promise<T[]>;
  }
  async remove(store: StoreName, key: IDBValidKey) {
    await req(this.tx(store, 'readwrite').delete(key));
  }
}

function openIdb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    if (typeof indexedDB === 'undefined') return reject(new Error('IndexedDB is not available'));
    const r = indexedDB.open('unloaded-calc-graph', 1);
    r.onupgradeneeded = () => {
      const db = r.result;
      for (const name of Object.keys(KEYS) as StoreName[]) {
        if (db.objectStoreNames.contains(name)) continue;
        const os = db.createObjectStore(name, { keyPath: KEYS[name], autoIncrement: AUTO.includes(name) });
        if (BY_PROJECT.includes(name)) os.createIndex('projectId', 'projectId');
      }
    };
    r.onsuccess = () => resolve(r.result);
    r.onerror = () => reject(r.error);
    r.onblocked = () => reject(new Error('IndexedDB upgrade blocked by another tab'));
  });
}

let backendPromise: Promise<Backend> | null = null;
function backend(): Promise<Backend> {
  if (!backendPromise) {
    backendPromise = openIdb()
      .then((db) => new IdbBackend(db) as Backend)
      .catch((e) => {
        console.warn(`Project store: IndexedDB unavailable (${(e as Error)?.message ?? e}); projects will not persist.`);
        return new MemoryBackend();
      });
  }
  return backendPromise;
}

/** Wrap a store call: an IndexedDB failure mid-session falls back to memory for the rest of it. */
async function withStore<T>(fn: (b: Backend) => Promise<T>): Promise<T> {
  const b = await backend();
  try {
    return await fn(b);
  } catch (e) {
    if (!b.persistent) throw e;
    console.warn('Project store: IndexedDB call failed; switching to memory for this session.', e);
    const mem = new MemoryBackend();
    backendPromise = Promise.resolve(mem);
    return fn(mem);
  }
}

// ------------------------------------------------------------------------------------------------
// Public API

export async function storeInfo(): Promise<{ persistent: boolean }> {
  return { persistent: (await backend()).persistent };
}

const newId = () =>
  typeof crypto !== 'undefined' && 'randomUUID' in crypto ? crypto.randomUUID() : `p-${Date.now()}-${Math.random().toString(36).slice(2)}`;

export async function listProjects(): Promise<ProjectRecord[]> {
  const ps = await withStore((b) => b.all<ProjectRecord>('projects'));
  return ps.sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
}

export async function getProject(id: string): Promise<ProjectRecord | undefined> {
  return withStore((b) => b.get<ProjectRecord>('projects', id));
}

export async function createProject(name: string): Promise<ProjectRecord> {
  const now = nowEastern();
  const p: ProjectRecord = { id: newId(), name, createdAt: now, updatedAt: now, headModelRev: null, headCalcRev: null };
  await withStore((b) => b.put('projects', p));
  return p;
}

export async function saveProject(p: ProjectRecord): Promise<void> {
  await withStore((b) => b.put('projects', { ...p, updatedAt: nowEastern() }));
}

export async function deleteProject(id: string): Promise<void> {
  await withStore(async (b) => {
    const revs = await b.byProject<RevisionRecord>('revisions', id);
    for (const r of revs) {
      await b.remove('blobs', r.id);
      await b.remove('graphs', r.id);
      await b.remove('extractions', r.id);
      await b.remove('revisions', r.id);
    }
    for (const r of await b.byProject<RunRecord>('runs', id)) await b.remove('runs', r.id);
    for (const d of await b.byProject<DecisionRecord>('decisions', id)) await b.remove('decisions', d.id);
    await b.remove('projects', id);
  });
}

export async function listRevisions(projectId: string): Promise<RevisionRecord[]> {
  const rs = await withStore((b) => b.byProject<RevisionRecord>('revisions', projectId));
  return rs.sort((a, b) => a.id - b.id);
}

export async function getRevision(id: number): Promise<RevisionRecord | undefined> {
  return withStore((b) => b.get<RevisionRecord>('revisions', id));
}

/**
 * Add a revision with its source file (and, for a model, its element graph; for calcs, the
 * extraction), and make it the head of its kind.
 */
export async function addRevision(
  projectId: string,
  rev: Omit<RevisionRecord, 'id' | 'projectId' | 'seq' | 'createdAt'> & { createdAt?: string },
  blob: Blob,
  extra: { graph?: SerializedElementGraph; extraction?: unknown },
): Promise<RevisionRecord> {
  return withStore(async (b) => {
    const p = await b.get<ProjectRecord>('projects', projectId);
    if (!p) throw new Error(`project ${projectId} not found`);
    const existing = await b.byProject<RevisionRecord>('revisions', projectId);
    const seq = existing.filter((r) => r.kind === rev.kind).length + 1;
    const rec = { ...rev, projectId, seq, createdAt: rev.createdAt ?? nowEastern() } as Omit<RevisionRecord, 'id'>;
    const id = Number(await b.put('revisions', rec));
    await b.put('blobs', { revisionId: id, blob });
    if (extra.graph) await b.put('graphs', { revisionId: id, graph: extra.graph });
    if (extra.extraction !== undefined) await b.put('extractions', { revisionId: id, data: extra.extraction });
    const head = rev.kind === 'model' ? { headModelRev: id } : { headCalcRev: id };
    await b.put('projects', { ...p, ...head, updatedAt: nowEastern() });
    return { ...rec, id };
  });
}

export async function getBlob(revisionId: number): Promise<Blob | undefined> {
  return (await withStore((b) => b.get<{ blob: Blob }>('blobs', revisionId)))?.blob;
}

export async function getGraph(revisionId: number): Promise<SerializedElementGraph | undefined> {
  return (await withStore((b) => b.get<{ graph: SerializedElementGraph }>('graphs', revisionId)))?.graph;
}

export async function getExtraction<T>(revisionId: number): Promise<T | undefined> {
  return (await withStore((b) => b.get<{ data: T }>('extractions', revisionId)))?.data;
}

/** Replace a calc revision's extraction (re-extracted by a newer engine); the file itself never changes. */
export async function replaceExtraction(revisionId: number, data: unknown): Promise<void> {
  await withStore((b) => b.put('extractions', { revisionId, data }));
}

export async function findRun<T>(projectId: string, modelRev: number, calcRev: number, engine: string): Promise<RunRecord<T> | undefined> {
  const runs = await withStore((b) => b.byProject<RunRecord<T>>('runs', projectId));
  return runs.filter((r) => r.modelRev === modelRev && r.calcRev === calcRev && r.engine === engine).sort((a, b) => b.id - a.id)[0];
}

export async function addRun<T>(run: Omit<RunRecord<T>, 'id' | 'createdAt'>): Promise<RunRecord<T>> {
  const rec = { ...run, createdAt: nowEastern() };
  const id = Number(await withStore((b) => b.put('runs', rec)));
  return { ...rec, id };
}

export async function addDecision(d: Omit<DecisionRecord, 'id' | 'at'>): Promise<DecisionRecord> {
  const rec = { ...d, at: nowEastern() };
  const id = Number(await withStore((b) => b.put('decisions', rec)));
  return { ...rec, id };
}

/** The decision log, oldest first. */
export async function decisionLog(projectId: string): Promise<DecisionRecord[]> {
  const ds = await withStore((b) => b.byProject<DecisionRecord>('decisions', projectId));
  return ds.sort((a, b) => a.id - b.id);
}

// ------------------------------------------------------------------------------------------------
// Whole-project file: one JSON document, blobs base64-encoded. Chosen over a zip because it needs no
// dependency, round-trips through the same JSON importer as every other file the app opens, and stays
// inspectable; the ~33 % base64 overhead is small next to the IFC and PDF it carries.

export const PROJECT_FILE_FORMAT = 'unloaded.calc-graph-project' as const;

export interface ProjectFile {
  format: typeof PROJECT_FILE_FORMAT;
  version: 1;
  exportedAt: string;
  project: { name: string; createdAt: string };
  revisions: (Omit<RevisionRecord, 'projectId'> & { blob: string; graph?: SerializedElementGraph; extraction?: unknown })[];
  decisions: Omit<DecisionRecord, 'id' | 'projectId'>[];
}

async function blobToBase64(b: Blob): Promise<string> {
  const bytes = new Uint8Array(await b.arrayBuffer());
  let s = '';
  for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return btoa(s);
}

function base64ToBlob(b64: string, type: string): Blob {
  const s = atob(b64);
  const bytes = new Uint8Array(s.length);
  for (let i = 0; i < s.length; i++) bytes[i] = s.charCodeAt(i);
  return new Blob([bytes], { type });
}

export async function exportProject(projectId: string): Promise<ProjectFile> {
  const p = await getProject(projectId);
  if (!p) throw new Error(`project ${projectId} not found`);
  const revisions: ProjectFile['revisions'] = [];
  for (const r of await listRevisions(projectId)) {
    const blob = await getBlob(r.id);
    const { projectId: _omit, ...rest } = r;
    revisions.push({
      ...rest,
      blob: blob ? await blobToBase64(blob) : '',
      graph: r.kind === 'model' ? await getGraph(r.id) : undefined,
      extraction: r.kind === 'calcs' ? await getExtraction(r.id) : undefined,
    });
  }
  const decisions = (await decisionLog(projectId)).map(({ id: _i, projectId: _p, ...d }) => d);
  return { format: PROJECT_FILE_FORMAT, version: 1, exportedAt: nowEastern(), project: { name: p.name, createdAt: p.createdAt }, revisions, decisions };
}

export function isProjectFile(d: unknown): d is ProjectFile {
  return Boolean(d && typeof d === 'object' && (d as { format?: unknown }).format === PROJECT_FILE_FORMAT);
}

/** Import a project file as a NEW project (revision ids are re-assigned; decisions keep their keys). */
export async function importProject(file: ProjectFile): Promise<ProjectRecord> {
  if (file.version !== 1) throw new Error(`unsupported project file version ${String(file.version)}`);
  const p = await createProject(file.project.name);
  const idMap = new Map<number, number>();
  for (const r of [...file.revisions].sort((a, b) => a.id - b.id)) {
    const added = await addRevision(
      p.id,
      { kind: r.kind, label: r.label, sourceName: r.sourceName, mediaType: r.mediaType, meta: r.meta, createdAt: r.createdAt },
      base64ToBlob(r.blob, r.mediaType),
      { graph: r.graph, extraction: r.extraction },
    );
    idMap.set(r.id, added.id);
  }
  for (const d of file.decisions) {
    await withStore((b) =>
      b.put('decisions', {
        ...d,
        projectId: p.id,
        modelRev: d.modelRev != null ? idMap.get(d.modelRev) ?? null : null,
        calcRev: d.calcRev != null ? idMap.get(d.calcRev) ?? null : null,
      }),
    );
  }
  return (await getProject(p.id)) ?? p;
}
