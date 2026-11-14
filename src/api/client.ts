// Thin fetch client for the calc-graph FastAPI backend (backend/). Every call goes through
// `request`, which turns a non-2xx response into an ApiError carrying FastAPI's `detail`
// (never swallowed). In dev, Vite proxies /api to http://127.0.0.1:8000.
import type { SerializedElementGraph } from '@unloaded/element-graph';
import type {
  ApiCompare,
  ApiDecisionIn,
  ApiExport,
  ApiHealth,
  ApiImpact,
  ApiProject,
  ApiRevisions,
  ApiSampleOut,
  ApiState,
  ApiUploadOut,
} from './types';

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public url: string,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  let r: Response;
  try {
    r = await fetch(url, init);
  } catch (e) {
    if ((e as Error)?.name === 'AbortError') throw e;
    throw new ApiError('Backend not reachable', 0, url);
  }
  if (!r.ok) {
    let msg = `${r.status} ${r.statusText}`;
    try {
      const j = await r.json();
      if (j?.detail) msg = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail);
    } catch {
      /* body is not JSON */
    }
    throw new ApiError(msg, r.status, url);
  }
  return (await r.json()) as T;
}

const get = <T>(url: string, signal?: AbortSignal) => request<T>(url, { signal });
const post = <T>(url: string, body?: unknown) =>
  request<T>(url, {
    method: 'POST',
    headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
const postForm = <T>(url: string, form: FormData) => request<T>(url, { method: 'POST', body: form });

const enc = encodeURIComponent;

export const api = {
  health: (signal?: AbortSignal) => get<ApiHealth>('/api/health', signal),
  projects: (signal?: AbortSignal) => get<ApiProject[]>('/api/projects', signal),
  state: (pid: number, signal?: AbortSignal) => get<ApiState>(`/api/projects/${pid}/state`, signal),
  exportProject: (pid: number, signal?: AbortSignal) => get<ApiExport>(`/api/projects/${pid}/export`, signal),
  revisions: (pid: number, signal?: AbortSignal) => get<ApiRevisions>(`/api/projects/${pid}/revisions`, signal),
  compare: (pid: number, a: number, b: number, signal?: AbortSignal) =>
    get<ApiCompare>(`/api/projects/${pid}/compare?a=${a}&b=${b}`, signal),
  impact: (pid: number, gid: string, mode: 'change' | 'remove', signal?: AbortSignal) =>
    get<ApiImpact>(`/api/projects/${pid}/impact?gid=${enc(gid)}&mode=${mode}`, signal),
  decide: (pid: number, d: ApiDecisionIn) => post<{ id: number }>(`/api/projects/${pid}/decisions`, d),
  /** the sample calc package (the sample model is uploaded like any other, through the element graph) */
  sampleCalcs: (pid: number) => post<ApiSampleOut>(`/api/projects/${pid}/sample`),
  /** a sample IFC, as a File, for the same client-side import path as an upload */
  sampleFile: async (name: string): Promise<File> => {
    const url = `/api/sample/files/${enc(name)}`;
    let r: Response;
    try {
      r = await fetch(url);
    } catch {
      throw new ApiError('Backend not reachable', 0, url);
    }
    if (!r.ok) throw new ApiError(`${r.status} ${r.statusText} for ${url}`, r.status, url);
    return new File([await r.blob()], name, { type: 'application/x-step' });
  },
  /** a model revision = the IFC file + the element graph the browser built from it */
  uploadModel: (pid: number, file: File, graph: SerializedElementGraph, label?: string) => {
    const fd = new FormData();
    fd.append('file', file);
    // ElementGraph.serialize() JSON, sent as a file part (the backend stores it verbatim)
    fd.append('graph', new Blob([JSON.stringify(graph)], { type: 'application/json' }), 'element-graph.json');
    if (label) fd.append('label', label);
    return postForm<ApiUploadOut>(`/api/projects/${pid}/model`, fd);
  },
  uploadCalcs: (pid: number, file: File, label?: string) => {
    const fd = new FormData();
    fd.append('file', file);
    if (label) fd.append('label', label);
    return postForm<ApiUploadOut>(`/api/projects/${pid}/calcs`, fd);
  },
  /** the element graph stored with a model revision */
  revisionGraph: (rid: number, signal?: AbortSignal) => get<SerializedElementGraph>(`/api/revisions/${rid}/graph`, signal),
};

/** URL builders for binary resources (PDFs, IFC) - not JSON, so not fetched here. */
export const urls = {
  revisionFile: (rid: number) => `/api/revisions/${rid}/file`,
  exportProject: (pid: number) => `/api/projects/${pid}/export`,
};
