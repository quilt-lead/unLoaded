// The calc engine worker: runs @unloaded/calc-mapper off the main thread (see engineClient.ts).
import * as pdfjs from 'pdfjs-dist';
import pdfWorkerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url';
import type { EngineRequest, EngineResponse } from './protocol';
import { engineOps } from './ops';

// pdf.js inside a worker: it starts its own nested worker from this URL (same version as the viewer)
pdfjs.GlobalWorkerOptions.workerSrc = pdfWorkerUrl;

// (typed against the DOM lib the app compiles with; in a worker `self.postMessage` takes one argument)
const post = (m: EngineResponse) => (self as unknown as { postMessage: (msg: EngineResponse) => void }).postMessage(m);

self.onmessage = async (e: MessageEvent<EngineRequest>) => {
  const req = e.data;
  const progress = (message: string) => post({ id: req.id, type: 'progress', message });
  try {
    const result = await engineOps(pdfjs)[req.op](req.args as never, progress);
    post({ id: req.id, type: 'result', result });
  } catch (err) {
    post({ id: req.id, type: 'error', error: err instanceof Error ? err.message : String(err) });
  }
};
