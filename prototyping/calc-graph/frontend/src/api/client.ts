// Thin fetch client for the calc-graph FastAPI backend. Every call goes through `request`, which
// turns a non-2xx response into an ApiError carrying FastAPI's `detail` (never swallowed).

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public url: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const r = await fetch(url, init);
  if (!r.ok) {
    let msg = `${r.status} ${r.statusText}`;
    try {
      const j = await r.json();
      if (j?.detail) msg = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail);
    } catch {
      /* body is not JSON */
    }
    throw new ApiError(msg, r.status, url);
  }
  return (await r.json()) as T;
}

export const get = <T>(url: string, signal?: AbortSignal) => request<T>(url, { signal });
export const post = <T>(url: string, body?: unknown) =>
  request<T>(url, {
    method: "POST",
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
export const postForm = <T>(url: string, form: FormData) => request<T>(url, { method: "POST", body: form });

const enc = encodeURIComponent;

/** URL builders for binary resources (PDFs, IFC, page renders) - not JSON, so not fetched here. */
export const urls = {
  revisionFile: (rid: number) => `/api/revisions/${rid}/file`,
  setDocFile: (sid: string, doc: string) => `/api/sets/${enc(sid)}/docs/${enc(doc)}/file`,
  setModelIfc: (sid: string) => `/api/sets/${enc(sid)}/model.ifc`,
  v2DocFile: (doc: string) => `/api/v2/docs/${enc(doc)}/file`,
  v2ModelIfc: () => `/api/v2/model.ifc`,
  v2RevisionPdf: (rev: string, name: string) => `/api/v2/revisions/${enc(rev)}/${enc(name)}.pdf`,
  exportProject: (pid: number) => `/api/projects/${pid}/export`,
};
