/**
 * The app's whole-project file (`*.calcgraph.json`), read without the app.
 *
 * The app writes it from `src/data/projectStore.ts` (`exportProject`, format
 * "unloaded.calc-graph-project", version 1): one JSON document holding every revision's original
 * file base64-encoded (`blob`), each model revision's element graph (`graph`, built once in the
 * browser at import; never re-parsed) and each calc revision's extraction (`extraction`, the
 * calc-mapper `CalcPackage`), plus the append-only decision log. The shape below mirrors that
 * writer field for field; `parseProjectFile` rejects anything else with the reason.
 *
 * Head revisions: the file does not store the app's head pointers. The app's importer
 * (`importProject`) re-adds revisions in id order and each add makes itself the head of its kind,
 * so the head of a kind is the revision with the highest id. `headOf` does the same.
 */
import type { DecisionFields, SerializedElementGraph } from "@unloaded/calc-mapper";

export const PROJECT_FILE_FORMAT = "unloaded.calc-graph-project" as const;
export const PROJECT_FILE_VERSION = 1 as const;

export type RevisionKind = "model" | "calcs";

/** One revision as the project file stores it (the app's RevisionRecord without projectId, plus its payloads). */
export interface ProjectFileRevision {
  id: number;
  kind: RevisionKind;
  seq: number;
  label: string;
  sourceName: string;
  mediaType: string;
  createdAt: string;
  meta: Record<string, string | number | boolean | null>;
  /** The original file (IFC / JSON / PDF), base64. */
  blob: string;
  /** Model revisions: ElementGraph.serialize(). */
  graph?: SerializedElementGraph;
  /** Calc revisions: the calc-mapper CalcPackage extracted when the PDF was added. */
  extraction?: unknown;
}

/** One decision as the project file stores it (the app's DecisionRecord without id / projectId). */
export interface ProjectFileDecision {
  globalId: string;
  calcKey: string;
  action: "confirm" | "reject" | "manual" | "undo";
  actor: string | null;
  note: string | null;
  at: string;
  modelRev: number | null;
  calcRev: number | null;
}

export interface ProjectFile {
  format: typeof PROJECT_FILE_FORMAT;
  version: typeof PROJECT_FILE_VERSION;
  exportedAt: string;
  project: { name: string; createdAt: string };
  revisions: ProjectFileRevision[];
  decisions: ProjectFileDecision[];
}

export class ProjectFileError extends Error {
  name = "ProjectFileError";
}

const isObj = (v: unknown): v is Record<string, unknown> => Boolean(v) && typeof v === "object" && !Array.isArray(v);

/** Validate a parsed project file. Throws ProjectFileError naming the first thing wrong. */
export function parseProjectFile(data: unknown): ProjectFile {
  if (!isObj(data)) throw new ProjectFileError("project file must be a JSON object");
  if (data.format !== PROJECT_FILE_FORMAT) {
    throw new ProjectFileError(
      `not a calc-graph project file: format is ${JSON.stringify(data.format ?? null)}, expected ${JSON.stringify(PROJECT_FILE_FORMAT)} ` +
        `(save one from the app with "Save project")`,
    );
  }
  if (data.version !== PROJECT_FILE_VERSION) {
    throw new ProjectFileError(`project file version ${JSON.stringify(data.version ?? null)} is not supported (this server reads version 1)`);
  }
  if (!isObj(data.project) || typeof data.project.name !== "string") throw new ProjectFileError("project.name must be a string");
  if (!Array.isArray(data.revisions)) throw new ProjectFileError("revisions must be a list");
  if (!Array.isArray(data.decisions)) throw new ProjectFileError("decisions must be a list");
  const ids = new Set<number>();
  data.revisions.forEach((r, i) => {
    if (!isObj(r)) throw new ProjectFileError(`revisions[${i}] must be an object`);
    if (typeof r.id !== "number" || !Number.isInteger(r.id)) throw new ProjectFileError(`revisions[${i}].id must be an integer`);
    if (ids.has(r.id)) throw new ProjectFileError(`revisions[${i}]: duplicate revision id ${r.id}`);
    ids.add(r.id);
    if (r.kind !== "model" && r.kind !== "calcs") throw new ProjectFileError(`revisions[${i}].kind must be "model" or "calcs"`);
    if (typeof r.blob !== "string") throw new ProjectFileError(`revisions[${i}].blob must be a base64 string`);
    if (typeof r.sourceName !== "string") throw new ProjectFileError(`revisions[${i}].sourceName must be a string`);
  });
  data.decisions.forEach((d, i) => {
    if (!isObj(d) || typeof d.globalId !== "string" || typeof d.calcKey !== "string" || typeof d.action !== "string") {
      throw new ProjectFileError(`decisions[${i}] needs globalId, calcKey and action`);
    }
  });
  return data as unknown as ProjectFile;
}

/** The head revision of a kind: the highest id (what the app's importer leaves as head). */
export function headOf(revisions: readonly ProjectFileRevision[], kind: RevisionKind): ProjectFileRevision | null {
  let best: ProjectFileRevision | null = null;
  for (const r of revisions) if (r.kind === kind && (!best || r.id > best.id)) best = r;
  return best;
}

/**
 * The decision log as the engine reads it (calc-mapper DecisionFields), oldest first. The file keeps
 * the log in order and without ids; ids are re-assigned 1..n in that order, exactly as the app's
 * importer's auto-increment does, so "the latest decision per pair wins" resolves the same way.
 * The engine states each decision's provenance from these fields (decisionFrom).
 */
export function decisionsOf(file: ProjectFile): DecisionFields[] {
  return file.decisions.map((d, i) => ({
    id: i + 1,
    global_id: d.globalId,
    calc_key: d.calcKey,
    action: d.action,
    actor: d.actor ?? null,
    note: d.note ?? null,
    at: d.at,
    model_rev: d.modelRev ?? null,
    calc_rev: d.calcRev ?? null,
  }));
}

/** base64 -> bytes (Node's Buffer, viewed as a plain Uint8Array). */
export function decodeBase64(b64: string): Uint8Array {
  const buf = Buffer.from(b64, "base64");
  return new Uint8Array(buf.buffer, buf.byteOffset, buf.byteLength);
}
