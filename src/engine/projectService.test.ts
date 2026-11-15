// Project operations over the store's memory backend (Node), with a stand-in engine Worker that
// records which ops reached it.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { SerializedElementGraph } from '@unloaded/element-graph';
import { SEGMENTER_VERSION, sha256 } from '@unloaded/calc-mapper';
import { __testing, addRevision, createProject, getExtraction, getRevision, listRevisions } from '../data/projectStore';
import { addModelRevision, compareRevisions, projectSnapshot } from './projectService';

// one memory backend for the whole file, set before any test: tests remove stored blobs through it.
// (Swapping backends between tests would restart revision ids under projectService's per-id caches.)
const mem = new __testing.MemoryBackend();
__testing.useBackend(mem);
const dropBlob = (rid: number) => mem.run(['blobs'], 'readwrite', (t) => t.remove('blobs', rid));

const graph = (id: string): SerializedElementGraph =>
  ({
    format: 'unloaded.element-graph',
    version: 1,
    meta: { version: 1, units: 'm' },
    levels: [{ id: 'L1', name: 'Level 1', elevation: 0 }],
    nodes: [{ id, kind: 'column', ifcType: 'IfcColumn', mark: id, levelId: 'L1', params: {} }],
    edges: [],
  }) as unknown as SerializedElementGraph;

const model = (label: string) => ({ kind: 'model' as const, label, sourceName: `${label}.json`, mediaType: 'application/json', meta: {} });
const calcs = { kind: 'calcs' as const, label: 'c', sourceName: 'c.pdf', mediaType: 'application/pdf', meta: {} };
const pdf = new Uint8Array([37, 80, 68, 70, 45, 1, 2, 3]);

/**
 * The smallest calc package storedExtractionFor accepts as stored for a PDF of sha256 `h`: made by the
 * current segmenter, every field calcPackageProblem checks present, every page hashed to `h`.
 */
const storedPkg = (h: string) => ({
  source_name: 'c.pdf',
  source_sha256: h,
  segmenter: SEGMENTER_VERSION,
  pages: [{ n: 1, text: '', words: [], width: 612, height: 792, scanned: false, doc_sha256: h }],
  calcs: [],
});

const ops: string[] = [];
const FRESH = { source_name: 'c.pdf', source_sha256: 'f'.repeat(64), pages: [{ n: 1, doc_sha256: 'f'.repeat(64) }], calcs: [] };
class FakeWorker {
  onmessage: ((e: MessageEvent) => void) | null = null;
  onmessageerror: (() => void) | null = null;
  onerror: (() => void) | null = null;
  postMessage(msg: { id: number; op: string }) {
    ops.push(msg.op);
    queueMicrotask(() => this.onmessage?.({ data: { id: msg.id, type: 'result', result: msg.op === 'extract' ? FRESH : null } } as MessageEvent));
  }
  terminate() {}
}
beforeEach(() => {
  ops.length = 0;
  vi.stubGlobal('Worker', FakeWorker);
});
afterEach(() => vi.unstubAllGlobals());

describe('revisions are checked to belong to the project', () => {
  // the old compareRevisions(a, b) diffed any two ids, so a stale pair from another project diffed
  // that project's models; the old projectSnapshot had no model revision to check
  it('compare and snapshot refuse another project\'s or a calc revision', async () => {
    const p = await createProject('P');
    const q = await createProject('Q');
    const a = await addRevision(p.id, model('a'), new Blob(['a']), { graph: graph('C1') });
    const b = await addRevision(p.id, model('b'), new Blob(['b']), { graph: graph('C2') });
    const c = await addRevision(p.id, calcs, new Blob([pdf]), {});
    const foreign = await addRevision(q.id, model('x'), new Blob(['x']), { graph: graph('X') });
    await expect(compareRevisions(p.id, a.id, foreign.id)).rejects.toThrow(/not a model revision of this project/);
    await expect(compareRevisions(q.id, a.id, b.id)).rejects.toThrow(/not a model revision of this project/);
    await expect(compareRevisions(p.id, a.id, c.id)).rejects.toThrow(/not a model revision of this project/);
    await expect(projectSnapshot(p.id, () => {}, foreign.id)).rejects.toThrow(/not a model revision of this project/);
    // a refused snapshot starts no engine work: p's head calc revision has no extraction, so before the
    // check moved ahead of the work, its PDF extraction kept running after the rejection
    await new Promise((r) => setTimeout(r, 50));
    expect(ops).toEqual([]);
  });

  // the old snapshot always showed the head, so a diff of (A, B) with head != B was laid over the wrong model
  it('the snapshot shows the model revision asked for, else the head', async () => {
    const p = await createProject('P');
    const a = await addRevision(p.id, model('a'), new Blob(['a']), { graph: graph('C1') });
    const b = await addRevision(p.id, model('b'), new Blob(['b']), { graph: graph('C2') });
    expect((await projectSnapshot(p.id)).modelRev?.id).toBe(b.id);
    const s = await projectSnapshot(p.id, () => {}, a.id);
    expect([s.modelRev?.id, s.graph?.nodes[0]?.id]).toEqual([a.id, 'C1']);
  });
});

describe('the stored extraction is used only when storedExtractionFor accepts it', () => {
  it('a valid extraction of this PDF is used as stored', async () => {
    const p = await createProject('P');
    const h = await sha256(pdf);
    const pkg = storedPkg(h);
    await addRevision(p.id, calcs, new Blob([pdf]), { extraction: pkg });
    await projectSnapshot(p.id);
    expect(ops).not.toContain('extract');
  });

  // the old app trusted any extraction carrying source_sha256 and crashed on `pkg.pages.every`
  // (TypeError) when pages was missing; the MCP server re-extracted. Both re-extract now.
  it('a malformed extraction (hash, no pages) is re-extracted and replaced', async () => {
    const p = await createProject('P');
    const c = await addRevision(p.id, calcs, new Blob([pdf]), { extraction: { source_sha256: await sha256(pdf), calcs: [] } });
    await expect(projectSnapshot(p.id)).resolves.toBeTruthy();
    expect(ops).toEqual(['extract']);
    expect(await getExtraction(c.id)).toEqual(FRESH);
  });

  it("an extraction of another PDF is re-extracted", async () => {
    const p = await createProject('P');
    await addRevision(p.id, calcs, new Blob([pdf]), { extraction: { ...FRESH, source_name: 'other.pdf' } });
    await projectSnapshot(p.id);
    expect(ops).toEqual(['extract']);
  });
});

describe('a calc revision whose package cannot be read degrades the view', () => {
  // round 1 threw from revisionPackage when the PDF was missing, which rejected the whole snapshot:
  // the element graph was not shown either
  it('the model is still shown; calcError names the revision and why', async () => {
    const p = await createProject('P');
    await addRevision(p.id, model('a'), new Blob(['a']), { graph: graph('C1') });
    const c = await addRevision(p.id, calcs, new Blob([pdf]), {});
    await dropBlob(c.id);
    const s = await projectSnapshot(p.id);
    expect(s.graph?.nodes[0]?.id).toBe('C1');
    expect(s.exp).toBeNull();
    expect(s.calcError).toMatch(new RegExp(`Calc revision #${c.id} \\(c\\.pdf\\) has no stored PDF`));
  });
});

describe("a calc revision's PDF is hashed once, when it is added", () => {
  it('the store records the sha256 of the file it stores, whatever the caller claims', async () => {
    const p = await createProject('P');
    const c = await addRevision(p.id, { ...calcs, meta: { fileSha256: 'not-the-hash' } }, new Blob([pdf]), {});
    expect((await getRevision(c.id))?.meta.fileSha256).toBe(await sha256(pdf));
  });

  // round 1 read and hashed the whole head PDF in every session before using a valid extraction; with
  // the PDF gone, a read of it fails, so this passes only when the recorded hash is used instead
  it('a valid stored extraction is used against the recorded hash, without reading the PDF', async () => {
    const p = await createProject('P');
    const h = await sha256(pdf);
    const pkg = storedPkg(h);
    const c = await addRevision(p.id, calcs, new Blob([pdf]), { extraction: pkg });
    await dropBlob(c.id);
    const s = await projectSnapshot(p.id);
    expect(s.calcError).toBeNull();
    expect(ops).not.toContain('extract');
  });

  it('a record without a recorded hash (stored before) falls back to hashing its PDF', async () => {
    const p = await createProject('P');
    const h = await sha256(pdf);
    const pkg = storedPkg(h);
    const c = await addRevision(p.id, calcs, new Blob([pdf]), { extraction: pkg });
    await mem.run(['revisions'], 'readwrite', async (t) => {
      const r = (await t.get<{ meta: Record<string, unknown> }>('revisions', c.id))!;
      delete r.meta.fileSha256;
      await t.put('revisions', r);
    });
    const s = await projectSnapshot(p.id);
    expect(s.calcError).toBeNull();
    expect(ops).not.toContain('extract');
  });
});

describe('an imported model is stored only if it can be saved and reopened', () => {
  // round 1 imported a serialized graph through ElementGraph.deserialize alone and stored it; only
  // parseGraph on reopening the saved project refused it (here: units other than metres)
  it('a serialized graph parseGraph refuses is refused at import, with the reason, and nothing is stored', async () => {
    const p = await createProject('P');
    const g = { ...graph('C1'), meta: { version: 1, units: 'mm' } };
    const file = new File([JSON.stringify(g)], 'feet.json', { type: 'application/json' });
    await expect(addModelRevision(p.id, file, undefined, () => {})).rejects.toThrow(/feet\.json: its element graph could not be reopened once saved \(graph\.meta\.units must be "m"/);
    expect(await listRevisions(p.id)).toEqual([]);
  });
});
