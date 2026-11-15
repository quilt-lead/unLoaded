// IdbBackend.run against a real IndexedDB implementation (fake-indexeddb: transactions, auto-commit
// and abort as the spec has them). The other store suites run on the memory backend, which cannot
// show any of this.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { IDBFactory } from 'fake-indexeddb';
import { __testing, addDecision, createProject, decisionLog, getProject, type ProjectRecord } from './projectStore';

type Idb = InstanceType<typeof __testing.IdbBackend>;
let backend: Idb;

beforeEach(async () => {
  vi.stubGlobal('indexedDB', new IDBFactory());
  backend = new __testing.IdbBackend(await __testing.openIdb());
});
afterEach(() => {
  vi.unstubAllGlobals();
  __testing.useBackend(new __testing.MemoryBackend());
});

const proj = (id: string): ProjectRecord => ({ id, name: id, createdAt: 't', updatedAt: 't', headModelRev: null, headCalcRev: null });
const allProjects = () => backend.run(['projects'], 'readonly', (t) => t.all<ProjectRecord>('projects'));

describe('IdbBackend.run', () => {
  // without the abort, IndexedDB auto-commits the writes made before fn threw
  it('a throwing fn aborts the transaction: none of its writes stay, and fn\'s own error is reported', async () => {
    await expect(
      backend.run(['projects'], 'readwrite', async (t) => {
        await t.put('projects', proj('a'));
        await t.put('projects', proj('b'));
        throw new Error('boom');
      }),
    ).rejects.toThrow('boom');
    expect(await allProjects()).toEqual([]);
  });

  // a run that returned fn's result without waiting for oncomplete would resolve before the commit
  // (and resolve even when the commit then failed)
  it('resolves with fn\'s result only after the transaction completed', async () => {
    const db = await __testing.openIdb();
    const order: string[] = [];
    const open = db.transaction.bind(db);
    db.transaction = ((...args: Parameters<IDBDatabase['transaction']>) => {
      const t = open(...args);
      t.addEventListener('complete', () => order.push('complete'));
      return t;
    }) as IDBDatabase['transaction'];
    const result = await new __testing.IdbBackend(db).run(['projects'], 'readwrite', async (t) => {
      await t.put('projects', proj('a'));
      return 'done';
    });
    order.push('resolved');
    expect(result).toBe('done');
    expect(order).toEqual(['complete', 'resolved']);
  });

  // if the transaction committed between two of the Tx's own awaited calls, the later call would
  // fail (TransactionInactiveError) and the earlier writes would survive the throw
  it('a chain of the Tx\'s own awaited calls is one transaction: no commit between them', async () => {
    await expect(
      backend.run(['projects', 'decisions'], 'readwrite', async (t) => {
        await t.put('projects', proj('a'));
        const got = await t.get<ProjectRecord>('projects', 'a');
        await t.put('projects', { ...got!, name: 'renamed' });
        await t.byProject('decisions', 'a');
        await t.put('decisions', { projectId: 'a', globalId: 'C1', calcKey: 'd1#k', action: 'confirm', actor: 'r', note: null, at: 't', modelRev: null, calcRev: null });
        throw new Error('late');
      }),
    ).rejects.toThrow('late');
    expect(await allProjects()).toEqual([]);
    expect(await backend.run(['decisions'], 'readonly', (t) => t.all('decisions'))).toEqual([]);
  });

  // the store's documented constraint (await only the Tx's own calls inside fn), shown to hold here,
  // which is what makes the test above meaningful
  it('awaiting anything else inside fn lets the transaction commit early', async () => {
    await expect(
      backend.run(['projects'], 'readwrite', async (t) => {
        await t.put('projects', proj('a'));
        await new Promise((r) => setTimeout(r, 10));
        await t.put('projects', proj('b'));
      }),
    // the second write must fail, never half-apply: a still-open-but-inactive transaction throws
    // TransactionInactiveError, an already-committed one InvalidStateError (both per the IndexedDB spec)
    ).rejects.toSatisfy((e: unknown) => e instanceof DOMException && ['TransactionInactiveError', 'InvalidStateError'].includes(e.name));
  });

  it('the public API runs on it: projects and the decision log (autoIncrement, projectId index)', async () => {
    __testing.useBackend(backend);
    const p = await createProject('P');
    expect((await getProject(p.id))?.name).toBe('P');
    const d = await addDecision({ projectId: p.id, globalId: 'C1', calcKey: 'd1#k', action: 'reject', actor: 'r', note: null, modelRev: null, calcRev: null });
    expect(await decisionLog(p.id)).toEqual([d]);
  });
});
