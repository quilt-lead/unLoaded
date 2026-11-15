// Project operations over the store's memory backend (Node), with a stand-in engine Worker that
// records which ops reached it.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { SerializedElementGraph } from '@unloaded/element-graph';
import { sha256 } from '@unloaded/calc-mapper';
import { addRevision, createProject, getExtraction } from '../data/projectStore';
import { compareRevisions, projectSnapshot } from './projectService';

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
    expect(ops).not.toContain('diff');
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
    const pkg = { source_name: 'c.pdf', source_sha256: h, pages: [{ n: 1, doc_sha256: h }], calcs: [] };
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
