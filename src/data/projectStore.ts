// The local project store: everything a project is, kept in the browser (IndexedDB), so models and
// calc packages never leave the engineer's machine. Falls back to memory when IndexedDB is
// unavailable (private windows, blocked storage, tests): the app works, nothing persists, and
// `storeInfo().persistent` says so.
//
// Object stores (database "unloaded-calc-graph", version 1)
//   projects    id (string)              { id, name, createdAt, updatedAt, headModelRev, headCalcRev, documents? }
//                                          documents: the calc documents in set order (absent on records
//                                          from before calc sets: read through projectDocuments)
//   revisions   id (auto number)         { id, projectId, kind: 'model'|'calcs', seq, label, sourceName,
//                                          mediaType, createdAt, meta }           index: projectId
//                                          meta.fileSha256: sha256 of the blob, recorded by the store
//                                          when the revision is added (absent on older records)
//                                          docId: calc revisions, the document (absent: LEGACY_DOC_ID)
//   blobs       revisionId               { revisionId, blob }   the original IFC / PDF / JSON file
//   graphs      revisionId               { revisionId, graph }  model revisions: ElementGraph.serialize()
//                                                               (built once at import; never re-parse to get it)
//   extractions revisionId               { revisionId, data }   calc revisions: extracted pages + segmented calcs
//   runs        id (auto number)         { id, projectId, modelRev, calcRev, calcSet, engine, createdAt, data }
//                                                               one mapping run per (model rev, calc set, engine);
//                                                               calcSet = the set's head revision ids (calcSetKey)
//   decisions   id (auto number)         { id, projectId, globalId, calcKey, action, actor, note, at,
//                                          modelRev, calcRev }   APPEND-ONLY; keyed by (globalId, calcKey),
//                                                               latest wins, so they carry across revisions;
//                                                               calcKey is a calc ref "<docId>#<key>" (a bare key
//                                                               from before calc sets is read as LEGACY_DOC_ID's)
// No IndexedDB schema change came with calc sets (records are schemaless): older records are read
// through the project-file rules (projectDocuments, docIdOf, legacyCalcRef), so nothing is migrated in place.
import type { SerializedElementGraph } from '@unloaded/element-graph';
import { parseGraph, sha256 } from '@unloaded/calc-mapper';
import {
  PROJECT_FILE_FORMAT,
  PROJECT_FILE_VERSION,
  decodeBase64,
  encodeBase64,
  docIdOf,
  legacyCalcRef,
  nextDocId,
  projectDocuments,
  type ProjectFile,
  type ProjectFileDocument,
  type ProjectFileDecision,
  type ProjectFileRevisionFields,
} from '@unloaded/project-file';
import type { DecisionAction as ViewDecisionAction } from '../types/bim';

// The view model declares its own DecisionAction (components never see engine types). It must be
// exactly the engine's, which the store and the project file use: either direction of drift fails here.
type Same<A, B> = [A] extends [B] ? ([B] extends [A] ? true : false) : false;
const _decisionActionsMatch: Same<ViewDecisionAction, ProjectFileDecision['action']> = true;
void _decisionActionsMatch;

export interface ProjectRecord {
  id: string;
  name: string;
  createdAt: string;
  updatedAt: string;
  headModelRev: number | null;
  /** The calc revision added last (any document). The calc SET is every document's head (documentHeads). */
  headCalcRev: number | null;
  /** Calc documents in set order; absent on projects from before calc sets (read with projectDocuments). */
  documents?: ProjectFileDocument[];
}

/** A revision's fields are the project file's (`@unloaded/project-file`), so Save/Open project cannot drift from the store. */
export interface RevisionRecord extends ProjectFileRevisionFields {
  projectId: string;
}

export interface RunRecord<T = unknown> {
  id: number;
  projectId: string;
  modelRev: number;
  /** The newest revision in the set (informational). */
  calcRev: number;
  /** The calc set the run mapped: calcSetKey of its head revisions. Absent on runs from before calc sets (never reused). */
  calcSet?: string;
  engine: string;
  createdAt: string;
  data: T;
}

/** A decision's fields are the project file's (`@unloaded/project-file`); the store adds its id and projectId. */
export interface DecisionRecord extends ProjectFileDecision {
  id: number;
  projectId: string;
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
// Two backends behind one tiny interface: IndexedDB, or memory. The backend is chosen ONCE, when the
// store is first opened; after that a failing call rejects with its own error (a full disk, a missing
// project) and the session stays on the same backend, so nothing saved disappears mid-session.
//
// Every public call is one transaction (`run`): all of its writes commit together or none do, and
// read-write transactions over the same stores never interleave (across tabs too, for IndexedDB).
// Inside `fn`, await only the Tx's own calls: awaiting anything else (a Blob's bytes, the worker)
// lets an IndexedDB transaction commit early.

interface Tx {
  get<T>(store: StoreName, key: IDBValidKey): Promise<T | undefined>;
  put<T extends object>(store: StoreName, value: T): Promise<IDBValidKey>;
  byProject<T>(store: StoreName, projectId: string): Promise<T[]>;
  all<T>(store: StoreName): Promise<T[]>;
  remove(store: StoreName, key: IDBValidKey): Promise<void>;
}

type Mode = 'readonly' | 'readwrite';

interface Backend {
  persistent: boolean;
  run<T>(stores: readonly StoreName[], mode: Mode, fn: (tx: Tx) => Promise<T>): Promise<T>;
}

/**
 * Memory: values are structured-cloned in and out, as IndexedDB does. Transactions run one at a
 * time; a failing one restores the tables it could have written, so it leaves nothing behind.
 */
class MemoryBackend implements Backend {
  persistent = false;
  private data = new Map<StoreName, Map<IDBValidKey, unknown>>();
  private seq = 0;
  private queue: Promise<unknown> = Promise.resolve();
  private table(s: StoreName) {
    let t = this.data.get(s);
    if (!t) this.data.set(s, (t = new Map()));
    return t;
  }
  private tx(stores: readonly StoreName[], mode: Mode): Tx {
    const scope = (s: StoreName) => {
      if (!stores.includes(s)) throw new Error(`store ${s} is not in this transaction`);
      return this.table(s);
    };
    const writable = (s: StoreName) => {
      if (mode !== 'readwrite') throw new Error('read-only transaction');
      return scope(s);
    };
    return {
      get: async <T,>(store: StoreName, key: IDBValidKey) => structuredClone(scope(store).get(key)) as T | undefined,
      put: async <T extends object>(store: StoreName, value: T) => {
        const k = KEYS[store];
        const rec = structuredClone(value) as Record<string, unknown>;
        const t = writable(store);
        if (AUTO.includes(store) && rec[k] == null) rec[k] = ++this.seq;
        t.set(rec[k] as IDBValidKey, rec);
        return rec[k] as IDBValidKey;
      },
      byProject: async <T,>(store: StoreName, projectId: string) =>
        structuredClone([...scope(store).values()].filter((v) => (v as { projectId?: string }).projectId === projectId)) as T[],
      all: async <T,>(store: StoreName) => structuredClone([...scope(store).values()]) as T[],
      remove: async (store: StoreName, key: IDBValidKey) => {
        writable(store).delete(key);
      },
    };
  }
  run<T>(stores: readonly StoreName[], mode: Mode, fn: (tx: Tx) => Promise<T>): Promise<T> {
    const go = async () => {
      const before = mode === 'readwrite' ? stores.map((s) => [s, new Map(this.table(s))] as const) : [];
      try {
        return await fn(this.tx(stores, mode));
      } catch (e) {
        for (const [s, t] of before) this.data.set(s, t);
        throw e;
      }
    };
    const result = this.queue.then(go, go);
    this.queue = result.catch(() => {});
    return result;
  }
}

const req = <T,>(r: IDBRequest<T>) =>
  new Promise<T>((resolve, reject) => {
    r.onsuccess = () => resolve(r.result);
    r.onerror = () => reject(r.error);
  });

class IdbBackend implements Backend {
  persistent = true;
  constructor(private db: IDBDatabase) {}
  async run<T>(stores: readonly StoreName[], mode: Mode, fn: (tx: Tx) => Promise<T>): Promise<T> {
    const t = this.db.transaction([...stores], mode);
    const done = new Promise<void>((resolve, reject) => {
      t.oncomplete = () => resolve();
      t.onabort = () => reject(t.error ?? new DOMException('Project store transaction aborted', 'AbortError'));
    });
    done.catch(() => {}); // observed below; a failing fn reports its own error instead
    const tx: Tx = {
      get: <T,>(store: StoreName, key: IDBValidKey) => req(t.objectStore(store).get(key)) as Promise<T | undefined>,
      put: <T extends object>(store: StoreName, value: T) => {
        const k = KEYS[store];
        const rec = { ...value } as Record<string, unknown>;
        if (AUTO.includes(store) && rec[k] == null) delete rec[k]; // let autoIncrement assign it
        return req(t.objectStore(store).put(rec));
      },
      byProject: <T,>(store: StoreName, projectId: string) => req(t.objectStore(store).index('projectId').getAll(projectId)) as Promise<T[]>,
      all: <T,>(store: StoreName) => req(t.objectStore(store).getAll()) as Promise<T[]>,
      remove: async (store: StoreName, key: IDBValidKey) => {
        await req(t.objectStore(store).delete(key));
      },
    };
    let result: T;
    try {
      result = await fn(tx);
    } catch (e) {
      try {
        t.abort();
      } catch {
        /* already finished or aborting */
      }
      throw e;
    }
    await done;
    return result;
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

const ALL_STORES = Object.keys(KEYS) as StoreName[];

/** One transaction on the session's backend. */
async function run<T>(stores: readonly StoreName[], mode: Mode, fn: (tx: Tx) => Promise<T>): Promise<T> {
  return (await backend()).run(stores, mode, fn);
}
const read = <T,>(store: StoreName, fn: (tx: Tx) => Promise<T>) => run([store], 'readonly', fn);

/** Tests only: put the store on a given backend (a memory one that says it persists, or fails on demand). */
export const __testing = {
  MemoryBackend,
  IdbBackend,
  openIdb,
  useBackend(b: Backend) {
    backendPromise = Promise.resolve(b);
  },
};

// ------------------------------------------------------------------------------------------------
// Public API

export async function storeInfo(): Promise<{ persistent: boolean }> {
  return { persistent: (await backend()).persistent };
}

const newId = () =>
  typeof crypto !== 'undefined' && 'randomUUID' in crypto ? crypto.randomUUID() : `p-${Date.now()}-${Math.random().toString(36).slice(2)}`;

export async function listProjects(): Promise<ProjectRecord[]> {
  const ps = await read('projects', (t) => t.all<ProjectRecord>('projects'));
  return ps.sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
}

export async function getProject(id: string): Promise<ProjectRecord | undefined> {
  return read('projects', (t) => t.get<ProjectRecord>('projects', id));
}

function newProject(name: string): ProjectRecord {
  const now = nowEastern();
  return { id: newId(), name, createdAt: now, updatedAt: now, headModelRev: null, headCalcRev: null };
}

export async function createProject(name: string): Promise<ProjectRecord> {
  const p = newProject(name);
  await run(['projects'], 'readwrite', (t) => t.put('projects', p));
  return p;
}

export async function saveProject(p: ProjectRecord): Promise<void> {
  await run(['projects'], 'readwrite', (t) => t.put('projects', { ...p, updatedAt: nowEastern() }));
}

/** Delete a project and everything it holds, in one transaction. */
export async function deleteProject(id: string): Promise<void> {
  await run(ALL_STORES, 'readwrite', async (t) => {
    for (const r of await t.byProject<RevisionRecord>('revisions', id)) {
      await t.remove('blobs', r.id);
      await t.remove('graphs', r.id);
      await t.remove('extractions', r.id);
      await t.remove('revisions', r.id);
    }
    for (const r of await t.byProject<RunRecord>('runs', id)) await t.remove('runs', r.id);
    for (const d of await t.byProject<DecisionRecord>('decisions', id)) await t.remove('decisions', d.id);
    await t.remove('projects', id);
  });
}

export async function listRevisions(projectId: string): Promise<RevisionRecord[]> {
  const rs = await read('revisions', (t) => t.byProject<RevisionRecord>('revisions', projectId));
  return rs.sort((a, b) => a.id - b.id);
}

export async function getRevision(id: number): Promise<RevisionRecord | undefined> {
  return read('revisions', (t) => t.get<RevisionRecord>('revisions', id));
}

/** documentName: the name a NEW calc document gets (default: the file name without its extension). */
type NewRevision = Omit<RevisionRecord, 'id' | 'projectId' | 'seq' | 'createdAt'> & { createdAt?: string; documentName?: string };
const REVISION_STORES: StoreName[] = ['projects', 'revisions', 'blobs', 'graphs', 'extractions'];
type RevisionPayload = { graph?: SerializedElementGraph; extraction?: unknown };

/**
 * The one gate every revision passes on its way into the store (addRevision, importProject). It
 * refuses what the project file's reader (`parseProjectFile`, which reopens a saved project here and
 * in the MCP server) would refuse, so whatever is stored can always be saved and reopened: an empty
 * file, a model revision without an element graph or with one `parseGraph` rejects, a calc revision
 * carrying a graph. Synchronous, so it runs inside the transaction before any write.
 */
export function checkStorableRevision(rev: Pick<NewRevision, 'kind' | 'sourceName'>, blob: Blob, extra: RevisionPayload): void {
  if (blob.size === 0) throw new Error(`${rev.sourceName}: the file is empty`);
  if (rev.kind === 'model') {
    if (!extra.graph) throw new Error(`${rev.sourceName}: a model revision needs its element graph`);
    try {
      parseGraph(extra.graph);
    } catch (e) {
      throw new Error(`${rev.sourceName}: its element graph could not be reopened once saved (${(e as Error).message})`);
    }
  } else if (extra.graph !== undefined) {
    throw new Error(`${rev.sourceName}: a calc revision must not carry an element graph`);
  }
}

/** A calc set's identity for the run cache: its documents' head revision ids, in set order. */
export const calcSetKey = (heads: readonly { doc: { docId: string }; rev: { id: number } }[]): string =>
  heads.map((h) => `${h.doc.docId}:${h.rev.id}`).join(',');

/** sha256 of a revision's file, recorded once when it is added (read before the transaction opens). */
const fileSha256 = async (blob: Blob) => sha256(new Uint8Array(await blob.arrayBuffer()));

/** The writes of one added revision, inside the caller's transaction (which must cover REVISION_STORES). */
async function addRevisionIn(t: Tx, projectId: string, rev: NewRevision, blob: Blob, extra: RevisionPayload, sha: string): Promise<RevisionRecord> {
  checkStorableRevision(rev, blob, extra);
  const p = await t.get<ProjectRecord>('projects', projectId);
  if (!p) throw new Error(`project ${projectId} not found`);
  // counted inside the transaction, so two adds can never take the same seq
  const seq = (await t.byProject<RevisionRecord>('revisions', projectId)).filter((r) => r.kind === rev.kind).length + 1;
  // the hash is the store's own, never a caller's (an imported file's meta could claim any value)
  const rec = { ...rev, meta: { ...rev.meta, fileSha256: sha }, projectId, seq, createdAt: rev.createdAt ?? nowEastern() } as Omit<RevisionRecord, 'id'>;
  let documents = p.documents;
  if (rev.kind === 'calcs') {
    // every calc revision belongs to a listed document; adding one to a removed document restores it
    const docId = docIdOf(rev);
    documents = projectDocuments(p.documents, await t.byProject<RevisionRecord>('revisions', projectId));
    const known = documents.find((d) => d.docId === docId);
    documents = known
      ? documents.map((d) => (d.docId === docId ? { ...d, removed: false } : d))
      : [...documents, { docId, name: rev.documentName ?? rev.sourceName.replace(/\.[A-Za-z0-9]{2,4}$/, ''), removed: false }];
    (rec as { docId?: string }).docId = docId;
  }
  delete (rec as { documentName?: string }).documentName;
  const id = Number(await t.put('revisions', rec));
  await t.put('blobs', { revisionId: id, blob });
  if (extra.graph) await t.put('graphs', { revisionId: id, graph: extra.graph });
  if (extra.extraction !== undefined) await t.put('extractions', { revisionId: id, data: extra.extraction });
  const head = rev.kind === 'model' ? { headModelRev: id } : { headCalcRev: id };
  await t.put('projects', { ...p, ...head, ...(documents ? { documents } : {}), updatedAt: nowEastern() });
  return { ...rec, id };
}

/**
 * Add a revision with its source file (and, for a model, its element graph; for calcs, the
 * extraction), and make it the head of its kind. One transaction: it is all stored or none of it.
 * Refused, with the reason, when it could not be saved and reopened (checkStorableRevision).
 */
export async function addRevision(projectId: string, rev: NewRevision, blob: Blob, extra: RevisionPayload): Promise<RevisionRecord> {
  checkStorableRevision(rev, blob, extra);
  const sha = await fileSha256(blob);
  return run(REVISION_STORES, 'readwrite', (t) => addRevisionIn(t, projectId, rev, blob, extra, sha));
}

export async function getBlob(revisionId: number): Promise<Blob | undefined> {
  return (await read('blobs', (t) => t.get<{ blob: Blob }>('blobs', revisionId)))?.blob;
}

export async function getGraph(revisionId: number): Promise<SerializedElementGraph | undefined> {
  return (await read('graphs', (t) => t.get<{ graph: SerializedElementGraph }>('graphs', revisionId)))?.graph;
}

export async function getExtraction<T>(revisionId: number): Promise<T | undefined> {
  return (await read('extractions', (t) => t.get<{ data: T }>('extractions', revisionId)))?.data;
}

/** Replace a calc revision's extraction (re-extracted by a newer engine); the file itself never changes. */
export async function replaceExtraction(revisionId: number, data: unknown): Promise<void> {
  await run(['extractions'], 'readwrite', (t) => t.put('extractions', { revisionId, data }));
}

export async function findRun<T>(projectId: string, modelRev: number, calcSet: string, engine: string): Promise<RunRecord<T> | undefined> {
  const runs = await read('runs', (t) => t.byProject<RunRecord<T>>('runs', projectId));
  return runs.filter((r) => r.modelRev === modelRev && r.calcSet === calcSet && r.engine === engine).sort((a, b) => b.id - a.id)[0];
}

/** The project's calc documents in set order (a project from before calc sets: derived from its revisions). */
export async function listDocuments(projectId: string): Promise<ProjectFileDocument[]> {
  return run(['projects', 'revisions'], 'readonly', async (t) => {
    const p = await t.get<ProjectRecord>('projects', projectId);
    if (!p) throw new Error(`project ${projectId} not found`);
    return projectDocuments(p.documents, await t.byProject<RevisionRecord>('revisions', projectId));
  });
}

/** The id a new calc document of this project gets. */
export async function newDocumentId(projectId: string): Promise<string> {
  return nextDocId(await listDocuments(projectId));
}

/** Rename a calc document, or withdraw it from / restore it to the set (its revisions and decisions are kept). */
export async function updateDocument(projectId: string, docId: string, change: { name?: string; removed?: boolean }): Promise<ProjectFileDocument[]> {
  return run(['projects', 'revisions'], 'readwrite', async (t) => {
    const p = await t.get<ProjectRecord>('projects', projectId);
    if (!p) throw new Error(`project ${projectId} not found`);
    const docs = projectDocuments(p.documents, await t.byProject<RevisionRecord>('revisions', projectId));
    if (!docs.some((d) => d.docId === docId)) throw new Error(`calc document ${docId} is not in this project`);
    const name = change.name?.trim();
    const documents = docs.map((d) => (d.docId === docId ? { ...d, ...(name ? { name } : {}), ...(change.removed !== undefined ? { removed: change.removed } : {}) } : d));
    await t.put('projects', { ...p, documents, updatedAt: nowEastern() });
    return documents;
  });
}

export async function addRun<T>(r: Omit<RunRecord<T>, 'id' | 'createdAt'>): Promise<RunRecord<T>> {
  const rec = { ...r, createdAt: nowEastern() };
  const id = Number(await run(['runs'], 'readwrite', (t) => t.put('runs', rec)));
  return { ...rec, id };
}

export async function addDecision(d: Omit<DecisionRecord, 'id' | 'at'>): Promise<DecisionRecord> {
  const rec = { ...d, at: nowEastern() };
  const id = Number(await run(['decisions'], 'readwrite', (t) => t.put('decisions', rec)));
  return { ...rec, id };
}

/**
 * Move a calc revision to another calc document (a new id makes a new document, named after the file).
 * A document left with no revision is dropped from the list: a document always has a revision.
 */
export async function setRevisionDocument(projectId: string, revisionId: number, docId: string): Promise<ProjectFileDocument[]> {
  if (!docId || docId.includes('#')) throw new Error(`calc document id must be non-empty without "#": ${docId}`);
  return run(['projects', 'revisions'], 'readwrite', async (t) => {
    const p = await t.get<ProjectRecord>('projects', projectId);
    const r = await t.get<RevisionRecord>('revisions', revisionId);
    if (!p) throw new Error(`project ${projectId} not found`);
    if (!r || r.projectId !== projectId || r.kind !== 'calcs') throw new Error(`revision #${revisionId} is not a calc revision of this project`);
    const before = await t.byProject<RevisionRecord>('revisions', projectId);
    let documents = projectDocuments(p.documents, before);
    await t.put('revisions', { ...r, docId });
    const after = before.map((x) => (x.id === revisionId ? { ...x, docId } : x));
    if (!documents.some((d) => d.docId === docId)) documents.push({ docId, name: r.sourceName.replace(/.[A-Za-z0-9]{2,4}$/, ''), removed: false });
    documents = documents
      .filter((d) => after.some((x) => x.kind === 'calcs' && docIdOf(x) === d.docId))
      .map((d) => (d.docId === docId ? { ...d, removed: false } : d));
    await t.put('projects', { ...p, documents, updatedAt: nowEastern() });
    return documents;
  });
}

/** The decision log, oldest first; calc keys as calc refs (a bare key from before calc sets names LEGACY_DOC_ID's calc). */
export async function decisionLog(projectId: string): Promise<DecisionRecord[]> {
  const ds = await read('decisions', (t) => t.byProject<DecisionRecord>('decisions', projectId));
  return ds.sort((a, b) => a.id - b.id).map((d) => ({ ...d, calcKey: legacyCalcRef(d.calcKey) }));
}

// ------------------------------------------------------------------------------------------------
// Whole-project file (`*.calcgraph.json`). The format - its type, validator and base64 codec - is
// declared once in `@unloaded/project-file`, which the MCP server reads it with too. Files reach
// importProject only through `parseProjectFile` (src/loaders/parsers.ts).

export async function exportProject(projectId: string): Promise<ProjectFile> {
  // one read-only transaction, so the file is one consistent state of the project; the blobs'
  // bytes are read after it (awaiting them inside would end the transaction)
  const snap = await run(ALL_STORES, 'readonly', async (t) => {
    const p = await t.get<ProjectRecord>('projects', projectId);
    if (!p) throw new Error(`project ${projectId} not found`);
    const revs = (await t.byProject<RevisionRecord>('revisions', projectId)).sort((a, b) => a.id - b.id);
    const payloads = [];
    for (const r of revs) {
      payloads.push({
        r,
        blob: (await t.get<{ blob: Blob }>('blobs', r.id))?.blob,
        graph: r.kind === 'model' ? (await t.get<{ graph: SerializedElementGraph }>('graphs', r.id))?.graph : undefined,
        extraction: r.kind === 'calcs' ? (await t.get<{ data: unknown }>('extractions', r.id))?.data : undefined,
      });
    }
    const decisions = (await t.byProject<DecisionRecord>('decisions', projectId)).sort((a, b) => a.id - b.id);
    return { p, payloads, decisions, documents: projectDocuments(p.documents, revs) };
  });
  const revisions: ProjectFile['revisions'] = [];
  for (const { r, blob, graph, extraction } of snap.payloads) {
    const { projectId: _omit, ...rest } = r;
    // a revision without its file, or a model revision without its graph, would save a file that
    // no reader can open (parseProjectFile refuses both): fail here instead
    if (!blob) throw new Error(`${r.kind === 'model' ? 'model' : 'calc'} revision ${r.seq} (${r.sourceName}) has no stored file; re-import it before saving`);
    if (r.kind === 'model' && !graph) throw new Error(`model revision ${r.seq} (${r.sourceName}) has no stored element graph; re-import it before saving`);
    const docId = r.kind === 'calcs' ? { docId: docIdOf(r) } : {};
    revisions.push({ ...rest, ...docId, blob: encodeBase64(new Uint8Array(await blob.arrayBuffer())), graph, extraction });
  }
  const decisions = snap.decisions.map(({ id: _i, projectId: _p, ...d }) => ({ ...d, calcKey: legacyCalcRef(d.calcKey) }));
  return {
    format: PROJECT_FILE_FORMAT, version: PROJECT_FILE_VERSION, exportedAt: nowEastern(), project: { name: snap.p.name, createdAt: snap.p.createdAt },
    documents: snap.documents, revisions, decisions,
  };
}

/**
 * Import a project file as a NEW project (revision ids are re-assigned; decisions keep their order),
 * in one transaction: a failure leaves no half-imported project behind.
 * `file` must come from `parseProjectFile`, which has already checked every field this reads,
 * including that each decision's revisions exist in the file.
 */
export async function importProject(file: ProjectFile): Promise<ProjectRecord> {
  const blobs = new Map(file.revisions.map((r) => [r.id, new Blob([decodeBase64(r.blob)], { type: r.mediaType })]));
  const shas = new Map<number, string>();
  for (const [id, blob] of blobs) shas.set(id, await fileSha256(blob));
  return run([...REVISION_STORES, 'decisions'], 'readwrite', async (t) => {
    const p: ProjectRecord = { ...newProject(file.project.name), documents: file.documents };
    await t.put('projects', p);
    const idMap = new Map<number, number>();
    for (const r of [...file.revisions].sort((a, b) => a.id - b.id)) {
      const added = await addRevisionIn(
        t,
        p.id,
        { kind: r.kind, label: r.label, sourceName: r.sourceName, mediaType: r.mediaType, meta: r.meta, createdAt: r.createdAt, ...(r.kind === 'calcs' ? { docId: r.docId } : {}) },
        blobs.get(r.id)!,
        { graph: r.graph, extraction: r.extraction },
        shas.get(r.id)!,
      );
      idMap.set(r.id, added.id);
    }
    // built field by field: the store assigns the id, the project is this one
    for (const d of file.decisions) {
      const rec: Omit<DecisionRecord, 'id'> = {
        projectId: p.id,
        globalId: d.globalId,
        calcKey: d.calcKey,
        action: d.action,
        actor: d.actor,
        note: d.note,
        at: d.at,
        modelRev: d.modelRev != null ? idMap.get(d.modelRev) ?? null : null,
        calcRev: d.calcRev != null ? idMap.get(d.calcRev) ?? null : null,
      };
      await t.put('decisions', rec);
    }
    // re-adding a revision restores its document (addRevisionIn): the file's list (names, withdrawn ones) is the truth
    const imported = (await t.get<ProjectRecord>('projects', p.id)) ?? p;
    const done = { ...imported, documents: file.documents };
    await t.put('projects', done);
    return done;
  });
}
