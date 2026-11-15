// runEngine always settles: a request that cannot be posted, or a reply that cannot be read, rejects
// instead of leaving its promise pending forever. Runs in Node with a stand-in Worker.
import { afterEach, describe, expect, it, vi } from 'vitest';

class FakeWorker {
  static last: FakeWorker | null = null;
  onmessage: ((e: MessageEvent) => void) | null = null;
  onmessageerror: ((e: MessageEvent) => void) | null = null;
  onerror: ((e: ErrorEvent) => void) | null = null;
  posted: { id: number; op: string; args: unknown }[] = [];
  constructor() {
    FakeWorker.last = this;
  }
  postMessage(msg: { id: number; op: string; args: unknown }) {
    structuredClone(msg); // what the real postMessage does first: throws DataCloneError for a function
    this.posted.push(msg);
  }
  terminate() {}
}

async function freshClient() {
  vi.resetModules();
  vi.stubGlobal('Worker', FakeWorker);
  return import('./engineClient');
}

afterEach(() => vi.unstubAllGlobals());

describe('runEngine settles every call', () => {
  // the old runEngine registered the call, then let postMessage throw past it: the promise never
  // settled and the pending entry leaked
  it('rejects when the request cannot be posted, and later calls still work', async () => {
    const { runEngine } = await freshClient();
    const bad = runEngine('diff', { a: (() => 1) as never, b: null as never, labelA: 1, labelB: 2 });
    await expect(bad).rejects.toThrow();
    const ok = runEngine('diff', { a: null as never, b: null as never, labelA: 1, labelB: 2 });
    const w = FakeWorker.last!;
    const id = w.posted[0]!.id;
    w.onmessage!({ data: { id, type: 'result', result: 'done' } } as MessageEvent);
    await expect(ok).resolves.toBe('done');
  });

  // the old client had no onmessageerror handler: an unreadable reply left its call pending forever
  it('rejects calls in flight when a reply cannot be deserialised', async () => {
    const { runEngine } = await freshClient();
    const p = runEngine('diff', { a: null as never, b: null as never, labelA: 1, labelB: 2 });
    FakeWorker.last!.onmessageerror!({} as MessageEvent);
    await expect(p).rejects.toThrow(/could not be read/);
  });
});
