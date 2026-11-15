// The app's handle on the calc engine: one module Web Worker running @unloaded/calc-mapper, so PDF
// text extraction and mapping never block the UI. Each call is a promise; progress messages go to
// the caller's callback (the app shows them in its toast).
import type { EngineOp, EngineOps, EngineRequest, EngineResponse } from './protocol';

let worker: Worker | null = null;
let nextId = 1;
const pending = new Map<number, { resolve: (v: unknown) => void; reject: (e: Error) => void; onProgress?: (m: string) => void }>();

function getWorker(): Worker {
  if (worker) return worker;
  const w = new Worker(new URL('./engine.worker.ts', import.meta.url), { type: 'module', name: 'calc-engine' });
  w.onmessage = (e: MessageEvent<EngineResponse>) => {
    const msg = e.data;
    const p = pending.get(msg.id);
    if (!p) return;
    if (msg.type === 'progress') {
      p.onProgress?.(msg.message);
      return;
    }
    pending.delete(msg.id);
    if (msg.type === 'result') p.resolve(msg.result);
    else p.reject(new Error(msg.error));
  };
  w.onerror = (e) => {
    // a worker that fails to load or crashes fails every call in flight; the next call starts a new one
    const err = new Error(`Calc engine worker failed: ${e.message || 'unknown error'}`);
    for (const p of pending.values()) p.reject(err);
    pending.clear();
    worker?.terminate();
    worker = null;
  };
  worker = w;
  return w;
}

export function runEngine<K extends EngineOp>(op: K, args: EngineOps[K]['args'], onProgress?: (m: string) => void): Promise<EngineOps[K]['result']> {
  const id = nextId++;
  return new Promise((resolve, reject) => {
    pending.set(id, { resolve: resolve as (v: unknown) => void, reject, onProgress });
    const req = { id, op, args } as EngineRequest;
    // hand PDF bytes over instead of copying them
    const transfer = op === 'extract' ? [(args as EngineOps['extract']['args']).bytes.buffer as ArrayBuffer] : [];
    getWorker().postMessage(req, transfer);
  });
}
