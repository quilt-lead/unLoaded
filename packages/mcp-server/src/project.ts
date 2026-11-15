/**
 * A project file loaded for querying: the revisions decoded, and, per (model revision, calc
 * revision) pair, the engine's output computed in-process by @unloaded/calc-mapper - the same
 * package, the same calls and the same order the app's worker makes (src/engine/ops.ts,
 * src/engine/projectService.ts):
 *
 *   graph   = the model revision's stored element graph (parseGraph; never re-parsed from the IFC)
 *   pkg     = the calc revision's stored extraction when `storedExtractionFor` (@unloaded/project-file,
 *             the rule the app uses too) accepts it against the sha256 of the PDF in the file;
 *             otherwise extractPdf + segmentCalcs on that PDF, so every provenance hash names the PDF
 *             actually in the file
 *   run     = mapCalcs(graph, pkg)
 *   state   = buildState(graph, pkg, run, decisions)
 *   exp     = buildExport(graph, pkg, run, decisions, info)   (info: the labels the app passes)
 *
 * Nothing here writes: the file is read, hashed and decoded; all results live in memory.
 * `ProjectSource` caches a loaded project per sha256 of the file's bytes and re-reads the file only
 * when its size or mtime changes (so saving a new version from the app is picked up on the next call).
 */
import { readFile, stat } from "node:fs/promises";
import { basename } from "node:path";
import {
  ENGINE_VERSION, buildExport, buildState, extractPdf, mapCalcs, parseGraph, segmentCalcs, sha256, sha256Json,
  type CalcPackage, type DecisionFields, type Export, type MappingRun, type PdfjsLike, type ProjectState,
  type SerializedElementGraph,
} from "@unloaded/calc-mapper";
import {
  ProjectFileError, decodeBase64, headOf, parseProjectFile, storedExtractionFor, type ProjectFile, type ProjectFileRevision,
} from "@unloaded/project-file";
import { decisionsOf } from "./decisionLog.ts";

let pdfjsPromise: Promise<PdfjsLike> | null = null;
/** pdf.js's legacy build: what pdf.js documents for Node, and what calc-mapper's own Node CLI uses. */
export function nodePdfjs(): Promise<PdfjsLike> {
  return (pdfjsPromise ??= import("pdfjs-dist/legacy/build/pdf.mjs") as unknown as Promise<PdfjsLike>);
}

/** How the calc package of a calc revision was obtained. */
export type ExtractionSource = "stored" | "re-extracted";

export interface CalcRevision {
  rev: ProjectFileRevision;
  bytes: Uint8Array;
  pkg: CalcPackage;
  extraction: ExtractionSource;
  /** Why the stored extraction was not used (when re-extracted). */
  extractionNote: string | null;
}

export interface ModelRevision {
  rev: ProjectFileRevision;
  graph: SerializedElementGraph;
}

/** The engine's view of one (model revision, calc revision) pair. */
export interface View {
  model: ModelRevision;
  calcs: CalcRevision | null;
  graphSha256: string;
  run: MappingRun | null;
  state: ProjectState;
  exp: Export;
  decisions: DecisionFields[];
}

export class LoadedProject {
  readonly decisions: DecisionFields[];
  private models = new Map<number, Promise<ModelRevision>>();
  private calcRevs = new Map<number, Promise<CalcRevision>>();
  private views = new Map<string, Promise<View>>();

  readonly path: string;
  readonly sha256: string;
  readonly bytes: number;
  readonly file: ProjectFile;

  constructor(path: string, sha256: string, bytes: number, file: ProjectFile) {
    this.path = path;
    this.sha256 = sha256;
    this.bytes = bytes;
    this.file = file;
    this.decisions = decisionsOf(file);
  }

  get revisions(): ProjectFileRevision[] {
    return [...this.file.revisions].sort((a, b) => a.id - b.id);
  }

  revision(id: number): ProjectFileRevision {
    const r = this.file.revisions.find((x) => x.id === id);
    if (!r) {
      const ids = this.revisions.map((x) => `${x.id} (${x.kind})`).join(", ") || "none";
      throw new ProjectFileError(`no revision ${id} in this project (revisions: ${ids})`);
    }
    return r;
  }

  head(kind: "model" | "calcs"): ProjectFileRevision | null {
    return headOf(this.file.revisions, kind);
  }

  model(id: number): Promise<ModelRevision> {
    let p = this.models.get(id);
    if (!p) {
      p = (async () => {
        const rev = this.revision(id);
        if (rev.kind !== "model") throw new ProjectFileError(`revision ${id} is a calc package, not a model revision`);
        if (!rev.graph) throw new ProjectFileError(`model revision ${id} (${rev.sourceName}) has no element graph in the project file`);
        return { rev, graph: parseGraph(rev.graph) };
      })();
      this.models.set(id, p);
    }
    return p;
  }

  calcRevision(id: number): Promise<CalcRevision> {
    let p = this.calcRevs.get(id);
    if (!p) {
      p = (async () => {
        const rev = this.revision(id);
        if (rev.kind !== "calcs") throw new ProjectFileError(`revision ${id} is a model revision, not a calc package`);
        // parseProjectFile refuses an empty blob, so this is the PDF
        const bytes = decodeBase64(rev.blob);
        const stored = storedExtractionFor(rev.extraction, await sha256(bytes));
        if (stored.pkg) return { rev, bytes, pkg: stored.pkg, extraction: "stored" as const, extractionNote: null };
        const text = await extractPdf(bytes, { pdfjs: await nodePdfjs() });
        const pkg = segmentCalcs(text.pages, rev.sourceName);
        return { rev, bytes, pkg, extraction: "re-extracted" as const, extractionNote: stored.reason };
      })();
      this.calcRevs.set(id, p);
    }
    return p;
  }

  /** Resolve the (model, calc) pair a tool asked for, defaulting to the heads (what the app shows). */
  pair(modelRev?: number | null, calcRev?: number | null): { model: number; calcs: number | null } {
    const m = modelRev ?? this.head("model")?.id ?? null;
    if (m == null) throw new ProjectFileError("this project has no model revision yet (add an IFC in the app, then save the project again)");
    const c = calcRev ?? this.head("calcs")?.id ?? null;
    return { model: m, calcs: c };
  }

  view(modelRev?: number | null, calcRev?: number | null): Promise<View> {
    const { model: m, calcs: c } = this.pair(modelRev, calcRev);
    const key = `${m}:${c ?? "-"}`;
    let p = this.views.get(key);
    if (!p) {
      p = (async () => {
        const model = await this.model(m);
        const calcs = c == null ? null : await this.calcRevision(c);
        const graphSha256 = await sha256Json(model.graph);
        const run = calcs ? await mapCalcs(model.graph, calcs.pkg) : null;
        const pkg = calcs?.pkg ?? null;
        const state = buildState(model.graph, pkg, run, this.decisions);
        // the same header labels the app's projectSnapshot passes
        const exp = buildExport(model.graph, pkg, run, this.decisions, {
          model: model.rev.sourceName, model_revision: model.rev.id,
          calc_package: calcs?.rev.sourceName ?? null, calc_revision: calcs?.rev.id ?? null,
        });
        return { model, calcs, graphSha256, run, state, exp, decisions: this.decisions };
      })();
      p.catch(() => this.views.delete(key));
      this.views.set(key, p);
    }
    return p;
  }

  /** Where a result came from: the file, the revisions, the engine and its producer records. */
  async source(v: View): Promise<Record<string, unknown>> {
    return {
      project_file: basename(this.path),
      project_file_sha256: this.sha256,
      model_revision: { id: v.model.rev.id, label: v.model.rev.label, source_name: v.model.rev.sourceName, graph_sha256: v.graphSha256 },
      calc_revision: v.calcs
        ? {
          id: v.calcs.rev.id, label: v.calcs.rev.label, source_name: v.calcs.rev.sourceName, pdf_sha256: v.calcs.pkg.source_sha256,
          extraction: v.calcs.extraction, ...(v.calcs.extractionNote ? { extraction_note: v.calcs.extractionNote } : {}),
        }
        : null,
      engine: ENGINE_VERSION,
      producers: v.exp.producers,
    };
  }
}

/** Read and validate a project file into a LoadedProject (no engine work yet: views compute lazily). */
export async function loadProject(path: string, bytes?: Uint8Array): Promise<LoadedProject> {
  const raw = bytes ?? new Uint8Array(await readFile(path));
  const hash = await sha256(raw);
  let data: unknown;
  try {
    data = JSON.parse(new TextDecoder().decode(raw));
  } catch (e) {
    throw new ProjectFileError(`${basename(path)} is not valid JSON: ${(e as Error).message}`);
  }
  return new LoadedProject(path, hash, raw.length, parseProjectFile(data));
}

/**
 * The project file a server serves, cached per sha256 of its bytes. Each call checks the file's size
 * and mtime; a changed file is re-read and re-hashed, and a new hash gets a fresh LoadedProject (so
 * nothing computed from the old bytes is reused).
 */
export class ProjectSource {
  private current: { size: number; mtimeMs: number; project: LoadedProject } | null = null;
  private loading: Promise<LoadedProject> | null = null;

  readonly path: string;

  constructor(path: string) {
    this.path = path;
  }

  async get(): Promise<LoadedProject> {
    const st = await stat(this.path);
    const cur = this.current;
    if (cur && cur.size === st.size && cur.mtimeMs === st.mtimeMs) return cur.project;
    if (this.loading) return this.loading;
    this.loading = (async () => {
      try {
        const raw = new Uint8Array(await readFile(this.path));
        const hash = await sha256(raw);
        const project = cur && cur.project.sha256 === hash ? cur.project : await loadProject(this.path, raw);
        this.current = { size: st.size, mtimeMs: st.mtimeMs, project };
        return project;
      } finally {
        this.loading = null;
      }
    })();
    return this.loading;
  }
}
