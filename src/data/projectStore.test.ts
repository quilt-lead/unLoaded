// Save project -> Open project through the shared format (@unloaded/project-file): the app's writer
// (exportProject), the shared reader (parseProjectFile, what the MCP server also reads with) and the
// app's importer (importProject) agree, payloads and the decision log included. Runs on the store's
// memory backend (no IndexedDB in Node).
import { afterEach, describe, expect, it } from 'vitest';
import type { SerializedElementGraph } from '@unloaded/element-graph';
import { sha256 } from '@unloaded/calc-mapper';
import { decodeBase64, parseProjectFile, type ProjectFile } from '@unloaded/project-file';
import {
  __testing,
  addDecision,
  addRevision,
  createProject,
  decisionLog,
  exportProject,
  getBlob,
  getGraph,
  getProject,
  importProject,
  listProjects,
  listRevisions,
} from './projectStore';

const graph = (mark: string): SerializedElementGraph =>
  ({
    format: 'unloaded.element-graph',
    version: 1,
    meta: { version: 1, units: 'm' },
    levels: [{ id: 'L1', name: 'Level 1', elevation: 0 }],
    nodes: [{ id: 'C1', kind: 'column', ifcType: 'IfcColumn', mark, levelId: 'L1', params: {} }],
    edges: [],
  }) as unknown as SerializedElementGraph;

/** Bytes with every value, past the encoder's 32 KiB chunk. */
const pdfBytes = Uint8Array.from({ length: 40_000 }, (_, i) => (i * 13 + 5) % 256);

/** A file with store ids replaced by each revision's (kind, seq), so two imports compare equal. */
function normalise(f: ProjectFile) {
  const key = new Map(f.revisions.map((r) => [r.id, `${r.kind}#${r.seq}`]));
  return {
    project: f.project.name,
    revisions: f.revisions.map(({ id: _id, ...r }) => r),
    decisions: f.decisions.map((d) => ({
      ...d,
      modelRev: d.modelRev == null ? null : key.get(d.modelRev),
      calcRev: d.calcRev == null ? null : key.get(d.calcRev),
    })),
  };
}

describe('project file: app writer -> shared reader -> app importer', () => {
  it('round-trips revisions, payloads and decisions', async () => {
    const p = await createProject('Round trip');
    const m1 = await addRevision(p.id, { kind: 'model', label: 'rev 1', sourceName: 'a.ifc', mediaType: 'application/x-step', meta: { elements: 1, project: null } }, new Blob(['ISO-10303-21;']), { graph: graph('C-1') });
    const c1 = await addRevision(p.id, { kind: 'calcs', label: 'calcs', sourceName: 'c.pdf', mediaType: 'application/pdf', meta: { pages: 1 } }, new Blob([pdfBytes]), { extraction: { calcs: [], pages: [] } });
    const m2 = await addRevision(p.id, { kind: 'model', label: 'rev 2', sourceName: 'b.ifc', mediaType: 'application/x-step', meta: {} }, new Blob(['ISO-10303-21;2']), { graph: graph('C-1A') });
    await addDecision({ projectId: p.id, globalId: 'C1', calcKey: 'k1', action: 'confirm', actor: 'reviewer', note: null, modelRev: m1.id, calcRev: c1.id });
    await addDecision({ projectId: p.id, globalId: 'C1', calcKey: 'k1', action: 'reject', actor: 'reviewer', note: 'wrong size', modelRev: m2.id, calcRev: null });

    const saved = await exportProject(p.id);
    const read = parseProjectFile(JSON.parse(JSON.stringify(saved)));
    expect(read).toEqual(JSON.parse(JSON.stringify(saved)));
    expect(decodeBase64(read.revisions.find((r) => r.kind === 'calcs')!.blob)).toEqual(pdfBytes);

    const q = await importProject(read);
    expect(q.id).not.toBe(p.id);
    const revs = await listRevisions(q.id);
    const pdf = revs.find((r) => r.kind === 'calcs')!;
    expect(new Uint8Array(await (await getBlob(pdf.id))!.arrayBuffer())).toEqual(pdfBytes);
    const head = revs.filter((r) => r.kind === 'model').sort((a, b) => b.id - a.id)[0]!;
    expect((await getGraph(head.id))?.nodes[0]?.mark).toBe('C-1A');

    expect(normalise(await exportProject(q.id))).toEqual(normalise(saved));
  });

  it('refuses to save a model revision whose graph is missing (no reader could open the file)', async () => {
    const mem = new __testing.MemoryBackend();
    __testing.useBackend(mem);
    const p = await createProject('No graph');
    // addRevision refuses this now (below); a record stored before that check is still refused on save
    const r = await addRevision(p.id, { kind: 'model', label: 'x', sourceName: 'x.ifc', mediaType: 'application/x-step', meta: {} }, new Blob(['x']), { graph: graph('C-1') });
    await mem.run(['graphs'], 'readwrite', (t) => t.remove('graphs', r.id));
    await expect(exportProject(p.id)).rejects.toThrow(/has no stored element graph/);
    __testing.useBackend(new __testing.MemoryBackend());
  });
});

const model = (label: string) => ({ kind: 'model' as const, label, sourceName: `${label}.ifc`, mediaType: 'application/x-step', meta: {} });
const calcs = (label: string) => ({ kind: 'calcs' as const, label, sourceName: `${label}.pdf`, mediaType: 'application/pdf', meta: {} });

describe('the store keeps the backend it opened with', () => {
  afterEach(() => __testing.useBackend(new __testing.MemoryBackend()));

  // the old withStore caught every error on a persistent backend, swapped the session onto a new
  // EMPTY memory store and re-ran the call there: the quota error became "project not found" and
  // every saved project vanished until reload
  it('a failing call rejects with its own error, and saved projects stay', async () => {
    type Run = InstanceType<typeof __testing.MemoryBackend>['run'];
    class Flaky extends __testing.MemoryBackend {
      persistent = true;
      fail = false;
      override run<T>(stores: Parameters<Run>[0], mode: Parameters<Run>[1], fn: (tx: Parameters<Parameters<Run>[2]>[0]) => Promise<T>): Promise<T> {
        if (this.fail) return Promise.reject(new DOMException('disk full', 'QuotaExceededError'));
        return super.run(stores, mode, fn);
      }
    }
    const b = new Flaky();
    __testing.useBackend(b);
    const p = await createProject('Kept');
    b.fail = true;
    await expect(addRevision(p.id, model('m'), new Blob(['x']), { graph: graph('C-1') })).rejects.toThrow(/disk full/);
    b.fail = false;
    expect((await listProjects()).map((x) => x.id)).toEqual([p.id]);
  });
});

describe('adding a revision is one transaction', () => {
  afterEach(() => __testing.useBackend(new __testing.MemoryBackend()));

  // the old addRevision wrote revision, blob, graph, extraction and head in separate transactions:
  // a failure at the extraction left an orphan revision that made every later Save project fail
  it('a failure part-way stores nothing', async () => {
    const p = await createProject('Atomic');
    const unclonable = { calcs: [], pages: [], f: () => 1 };
    await expect(addRevision(p.id, calcs('c'), new Blob([pdfBytes]), { extraction: unclonable })).rejects.toThrow();
    expect(await listRevisions(p.id)).toEqual([]);
    expect((await getProject(p.id))?.headCalcRev).toBeNull();
    const ok = await addRevision(p.id, calcs('c'), new Blob([pdfBytes]), { extraction: { calcs: [], pages: [] } });
    expect(ok.seq).toBe(1);
    await expect(exportProject(p.id)).resolves.toBeTruthy();
  });

  // the old addRevision read the project row first and wrote it back whole at the end, with seq
  // counted outside any transaction: overlapping adds lost a head and took the same seq
  it('overlapping adds keep both heads and distinct seqs', async () => {
    const p = await createProject('Overlap');
    const [m, c] = await Promise.all([
      addRevision(p.id, model('m1'), new Blob(['a']), { graph: graph('C-1') }),
      addRevision(p.id, calcs('c1'), new Blob([pdfBytes]), { extraction: { calcs: [], pages: [] } }),
    ]);
    const head = await getProject(p.id);
    expect([head?.headModelRev, head?.headCalcRev]).toEqual([m.id, c.id]);
    const [m2, m3] = await Promise.all([
      addRevision(p.id, model('m2'), new Blob(['b']), { graph: graph('C-2') }),
      addRevision(p.id, model('m3'), new Blob(['c']), { graph: graph('C-3') }),
    ]);
    expect([m.seq, m2.seq, m3.seq].sort()).toEqual([1, 2, 3]);
    expect((await getProject(p.id))?.headModelRev).toBe(Math.max(m2.id, m3.id));
  });
});

describe('save / open refuse what they cannot round-trip', () => {
  afterEach(() => __testing.useBackend(new __testing.MemoryBackend()));

  // the old exportProject wrote blob: '' for a missing file, saving a project that reopened with an empty file
  it('refuses to save a revision whose file is missing', async () => {
    const mem = new __testing.MemoryBackend();
    __testing.useBackend(mem);
    const p = await createProject('No file');
    const r = await addRevision(p.id, calcs('c'), new Blob([pdfBytes]), {});
    await mem.run(['blobs'], 'readwrite', (t) => t.remove('blobs', r.id));
    await expect(exportProject(p.id)).rejects.toThrow(/has no stored file/);
  });

  // the old importer spread each file decision into the store, so an `id` key in the file (IndexedDB
  // keeps explicit keys) overwrote another project's decision
  it("an imported decision never takes another record's id", async () => {
    const other = await createProject('Other');
    const m = await addRevision(other.id, model('m'), new Blob(['a']), { graph: graph('C-1') });
    const mine = await addDecision({ projectId: other.id, globalId: 'C1', calcKey: 'k', action: 'confirm', actor: 'me', note: null, modelRev: m.id, calcRev: null });
    const file = await exportProject(other.id);
    const hostile = { ...file, decisions: file.decisions.map((d) => ({ ...d, id: mine.id, projectId: other.id, action: 'reject' as const })) };
    const q = await importProject(hostile as ProjectFile);
    expect(await decisionLog(other.id)).toEqual([mine]);
    expect((await decisionLog(q.id)).map((d) => [d.action, d.id !== mine.id])).toEqual([['reject', true]]);
  });
});

describe('the store refuses what a saved project could not reopen with', () => {
  afterEach(() => __testing.useBackend(new __testing.MemoryBackend()));
  const m = { kind: 'model' as const, label: 'm', sourceName: 'm.json', mediaType: 'application/json', meta: {} };

  // round 1 stored any graph the importer produced; parseProjectFile (parseGraph) refused it only
  // when the saved project was reopened, so the app could save a project it then could not open
  it.each([
    ['a model without its graph', m, new Blob(['x']), {}, /m\.json: a model revision needs its element graph/],
    ['a graph parseGraph refuses', m, new Blob(['x']), { graph: { ...graph('C-1'), meta: { version: 1, units: 'mm' } } as unknown as SerializedElementGraph }, /could not be reopened once saved \(graph\.meta\.units/],
    ['an edge to a missing node', m, new Blob(['x']), { graph: { ...graph('C-1'), edges: [{ id: 'e', kind: 'connects', a: 'C1', b: 'nope' }] } as unknown as SerializedElementGraph }, /references a node that is not in graph\.nodes/],
    ['an empty file', m, new Blob([]), { graph: graph('C-1') }, /m\.json: the file is empty/],
    ['a calc revision carrying a graph', calcs('c'), new Blob([pdfBytes]), { graph: graph('C-1') }, /must not carry an element graph/],
  ])('refuses %s, and stores nothing', async (_what, rev, blob, extra, why) => {
    const p = await createProject('Gate');
    await expect(addRevision(p.id, rev, blob, extra)).rejects.toThrow(why);
    expect(await listRevisions(p.id)).toEqual([]);
  });

  it('whatever it accepted saves and reopens', async () => {
    const p = await createProject('Gate');
    await addRevision(p.id, m, new Blob(['x']), { graph: graph('C-1') });
    await addRevision(p.id, calcs('c'), new Blob([pdfBytes]), {});
    const q = await importProject(parseProjectFile(JSON.parse(JSON.stringify(await exportProject(p.id)))));
    expect((await listRevisions(q.id)).length).toBe(2);
  });

  // the recorded hash is the store's: an imported file's meta cannot plant one
  it('an imported revision gets the sha256 of its own file, not the one its meta claims', async () => {
    const p = await createProject('Hash');
    await addRevision(p.id, calcs('c'), new Blob([pdfBytes]), {});
    const file = await exportProject(p.id);
    const forged = { ...file, revisions: file.revisions.map((r) => ({ ...r, meta: { ...r.meta, fileSha256: 'f'.repeat(64) } })) };
    const q = await importProject(parseProjectFile(JSON.parse(JSON.stringify(forged))));
    const [r] = await listRevisions(q.id);
    expect(r?.meta.fileSha256).toBe(await sha256(pdfBytes));
  });
});
