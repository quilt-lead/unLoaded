/**
 * The whole-project file (`*.calcgraph.json`, format "unloaded.calc-graph-project", version 1).
 *
 * This module is the only declaration of the format. The app writes it (`src/data/projectStore.ts`
 * `exportProject`) and reads it (`importProject`, via `src/loaders/parsers.ts`); the MCP server reads
 * it (`packages/mcp-server/src/project.ts`) and its tooling writes it (`makeProjectFile`). All four go
 * through the type, `parseProjectFile` and the base64 codec here, so a writer and a reader cannot drift.
 *
 * One JSON document: every revision's original file base64-encoded (`blob`), each model revision's
 * element graph (`graph`, built once at import and never re-parsed from the IFC), each calc revision's
 * extraction (`extraction`, the calc-mapper `CalcPackage`, optional: both readers re-extract from the
 * PDF when it is missing or its hash does not match), plus the append-only decision log. Chosen over a
 * zip because it needs no dependency, stays inspectable, and the ~33 % base64 overhead is small next
 * to the IFC and PDF it carries.
 *
 * Head revisions are not stored: importing re-adds revisions in id order and each add becomes the head
 * of its kind, so the head of a kind is the revision with the highest id (`headOf`).
 */
import { DECISION_ACTIONS, parseGraph, type DecisionAction } from "@unloaded/calc-mapper";
import type { SerializedElementGraph } from "@unloaded/element-graph";

export const PROJECT_FILE_FORMAT = "unloaded.calc-graph-project" as const;
export const PROJECT_FILE_VERSION = 1 as const;

export type RevisionKind = "model" | "calcs";
export type RevisionMeta = Record<string, string | number | boolean | null>;

/** A revision's own fields: what the app's store keeps per revision (it adds only `projectId`). */
export interface ProjectFileRevisionFields {
  id: number;
  kind: RevisionKind;
  /** 1-based position within its kind. */
  seq: number;
  label: string;
  sourceName: string;
  mediaType: string;
  createdAt: string;
  meta: RevisionMeta;
}

/** One revision as the file stores it: its fields plus its payloads. */
export interface ProjectFileRevision extends ProjectFileRevisionFields {
  /** The original file (IFC / JSON / PDF), base64 (`encodeBase64`). */
  blob: string;
  /** Model revisions (required): ElementGraph.serialize(). */
  graph?: SerializedElementGraph;
  /** Calc revisions (optional): the calc-mapper CalcPackage extracted when the PDF was added. */
  extraction?: unknown;
}

/**
 * One decision as the file stores it: the app's decision record without its store id / projectId.
 * The log is kept in order (oldest first); readers re-number it 1..n in that order.
 */
export interface ProjectFileDecision {
  globalId: string;
  calcKey: string;
  action: DecisionAction;
  actor: string;
  note: string | null;
  at: string;
  /** The model / calc revision ids (in this file) the decision was made against. */
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
const isInt = (v: unknown): v is number => typeof v === "number" && Number.isInteger(v);
const BASE64 = /^[A-Za-z0-9+/]*={0,2}$/;
function fail(msg: string): never {
  throw new ProjectFileError(msg);
}

/** Does this parsed JSON claim to be a project file? (Routing only: `parseProjectFile` validates it.) */
export function isProjectFileFormat(data: unknown): boolean {
  return isObj(data) && data.format === PROJECT_FILE_FORMAT;
}

/**
 * Validate a parsed project file, field by field, against what every reader relies on. Throws
 * ProjectFileError naming the first thing wrong. Returns the same object, typed.
 */
export function parseProjectFile(data: unknown): ProjectFile {
  if (!isObj(data)) fail("project file must be a JSON object");
  const d = data as Record<string, unknown>;
  if (d.format !== PROJECT_FILE_FORMAT) {
    fail(
      `not a calc-graph project file: format is ${JSON.stringify(d.format ?? null)}, expected ${JSON.stringify(PROJECT_FILE_FORMAT)} ` +
        `(save one from the app with "Save project")`,
    );
  }
  if (d.version !== PROJECT_FILE_VERSION) {
    fail(`project file version ${JSON.stringify(d.version ?? null)} is not supported (this reader reads version ${PROJECT_FILE_VERSION})`);
  }
  if (typeof d.exportedAt !== "string") fail("exportedAt must be a string");
  if (!isObj(d.project) || typeof d.project.name !== "string") fail("project.name must be a string");
  if (typeof (d.project as Record<string, unknown>).createdAt !== "string") fail("project.createdAt must be a string");
  if (!Array.isArray(d.revisions)) fail("revisions must be a list");
  if (!Array.isArray(d.decisions)) fail("decisions must be a list");

  const kinds = new Map<number, RevisionKind>();
  (d.revisions as unknown[]).forEach((r, i) => {
    const at = `revisions[${i}]`;
    if (!isObj(r)) return fail(`${at} must be an object`);
    if (!isInt(r.id)) fail(`${at}.id must be an integer`);
    const id = r.id as number;
    if (kinds.has(id)) fail(`${at}: duplicate revision id ${id}`);
    if (r.kind !== "model" && r.kind !== "calcs") fail(`${at}.kind must be "model" or "calcs"`);
    kinds.set(id, r.kind as RevisionKind);
    if (!isInt(r.seq) || r.seq < 1) fail(`${at}.seq must be a positive integer`);
    for (const k of ["label", "sourceName", "mediaType", "createdAt"] as const) {
      if (typeof r[k] !== "string") fail(`${at}.${k} must be a string`);
    }
    if (!isObj(r.meta)) fail(`${at}.meta must be an object`);
    for (const [k, v] of Object.entries(r.meta as Record<string, unknown>)) {
      if (v !== null && !["string", "number", "boolean"].includes(typeof v)) fail(`${at}.meta.${k} must be a string, number, boolean or null`);
    }
    if (typeof r.blob !== "string" || r.blob.length % 4 !== 0 || !BASE64.test(r.blob)) fail(`${at}.blob must be a base64 string`);
    if (r.kind === "model") {
      if (r.graph === undefined) fail(`${at}: model revision ${id} has no element graph`);
      try {
        parseGraph(r.graph);
      } catch (e) {
        fail(`${at}.graph: ${(e as Error).message}`);
      }
    } else if (r.graph !== undefined) {
      fail(`${at}: calc revision ${id} must not carry an element graph`);
    }
  });

  (d.decisions as unknown[]).forEach((x, i) => {
    const at = `decisions[${i}]`;
    if (!isObj(x)) return fail(`${at} must be an object`);
    for (const k of ["globalId", "calcKey", "actor", "at"] as const) {
      if (typeof x[k] !== "string") fail(`${at}.${k} must be a string`);
    }
    if (!(DECISION_ACTIONS as readonly unknown[]).includes(x.action)) fail(`${at}.action must be one of ${DECISION_ACTIONS.join(", ")}`);
    if (x.note !== null && typeof x.note !== "string") fail(`${at}.note must be a string or null`);
    for (const [k, kind] of [["modelRev", "model"], ["calcRev", "calcs"]] as const) {
      const v = x[k];
      if (v === null) continue;
      if (!isInt(v)) fail(`${at}.${k} must be a revision id or null`);
      if (kinds.get(v as number) !== kind) fail(`${at}.${k} = ${String(v)} is not a ${kind} revision in this file`);
    }
  });
  return data as ProjectFile;
}

/** The head revision of a kind: the highest id (what importing leaves as head). */
export function headOf<R extends Pick<ProjectFileRevisionFields, "id" | "kind">>(revisions: readonly R[], kind: RevisionKind): R | null {
  let best: R | null = null;
  for (const r of revisions) if (r.kind === kind && (!best || r.id > best.id)) best = r;
  return best;
}

/** bytes -> base64, in the browser and in Node (both have btoa). Chunked so large files don't overflow the stack. */
export function encodeBase64(bytes: Uint8Array): string {
  let s = "";
  for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return btoa(s);
}

/** base64 -> bytes, in the browser and in Node (both have atob). Backed by a plain ArrayBuffer, so it is a valid BlobPart. */
export function decodeBase64(b64: string): Uint8Array<ArrayBuffer> {
  const s = atob(b64);
  const bytes = new Uint8Array(s.length);
  for (let i = 0; i < s.length; i++) bytes[i] = s.charCodeAt(i);
  return bytes;
}
