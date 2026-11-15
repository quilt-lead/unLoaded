/**
 * The whole-project file (`*.calcgraph.json`, format "unloaded.calc-graph-project", version 1).
 *
 * This module is the only declaration of the format. The app writes it (`src/data/projectStore.ts`
 * `exportProject`) and reads it (`importProject`, via `src/loaders/parsers.ts`); the MCP server reads
 * it (`packages/mcp-server/src/project.ts`, through its `src/engine.ts`) and its tooling writes it
 * (`packages/mcp-server/scripts/makeProjectFile.ts`). All four go through the type,
 * `parseProjectFile` and the base64 codec here, so a writer and a reader cannot drift.
 *
 * One JSON document: every revision's original file base64-encoded (`blob`), each model revision's
 * element graph (`graph`, built once at import and never re-parsed from the IFC), each calc revision's
 * extraction (`extraction`, the calc-mapper `CalcPackage`, optional: both readers decide whether to use
 * it with `storedExtractionFor` and re-extract from the PDF otherwise), plus the append-only decision log. Chosen over a
 * zip because it needs no dependency, stays inspectable, and the ~33 % base64 overhead is small next
 * to the IFC and PDF it carries.
 *
 * Head revisions are not stored: importing re-adds revisions in id order and each add becomes the head
 * of its kind, so the head of a kind is the revision with the highest id (`headOf`).
 *
 * Version 2 (calc sets): calcs are MANY documents (PDFs), each with its own revisions. Every calc revision
 * names its document (`docId`), `documents` lists them in set order (a removed one stays, flagged), and a
 * decision's `calcKey` is a calc ref "<docId>#<key>" (calc-mapper calcset.ts). The head of a document is
 * its revision with the highest id (`documentHeads`). A version-1 file still opens: its calc revisions
 * are one document, LEGACY_DOC_ID, and its decisions' bare calc keys become refs into it.
 */
import { CALC_REF_SEP, DECISION_ACTIONS, SEGMENTER_VERSION, calcPackageProblem, calcRef, parseGraph, type CalcPackage, type DecisionAction } from "@unloaded/calc-mapper";
import type { SerializedElementGraph } from "@unloaded/element-graph";

export const PROJECT_FILE_FORMAT = "unloaded.calc-graph-project" as const;
export const PROJECT_FILE_VERSION = 2 as const;
/** Versions this reader opens (1: one calc PDF per project; 2: calc sets). */
export const PROJECT_FILE_VERSIONS_READ = [1, 2] as const;

/** The document every calc revision of a pre-set project (file version 1, or an older store record) belongs to. */
export const LEGACY_DOC_ID = "d1" as const;

/** A calc document: one logical PDF of the project, with its own revisions. */
export interface ProjectFileDocument {
  /** Stable id ("d1", "d2", ...): calc refs and revisions name it. No "#". */
  docId: string;
  name: string;
  /** Withdrawn from the set: its revisions and decisions are kept, its calcs are not mapped. */
  removed: boolean;
}

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
  /** Calc revisions: the document this is a revision of (absent on records from before calc sets: LEGACY_DOC_ID). */
  docId?: string;
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
 * The log is kept in order (oldest first). Readers give it ids that keep that order (the app's
 * auto-increment, the MCP server's 1..n): "latest decision per pair wins" depends only on the order.
 */
export interface ProjectFileDecision {
  globalId: string;
  /** A calc ref "<docId>#<key>" (version 1 files: a bare key, read as a ref into LEGACY_DOC_ID). */
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
  /** Calc documents in set order. */
  documents: ProjectFileDocument[];
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
 * ProjectFileError naming the first thing wrong. Returns a NEW object holding only the declared
 * fields, so an extra key in a hand-edited file (an `id` on a decision, say) never reaches a reader.
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
  if (!(PROJECT_FILE_VERSIONS_READ as readonly unknown[]).includes(d.version)) {
    fail(`project file version ${JSON.stringify(d.version ?? null)} is not supported (this reader reads versions ${PROJECT_FILE_VERSIONS_READ.join(", ")})`);
  }
  const v1 = d.version === 1;
  if (typeof d.exportedAt !== "string") fail("exportedAt must be a string");
  if (!isObj(d.project) || typeof d.project.name !== "string") fail("project.name must be a string");
  const project = d.project as Record<string, unknown>;
  if (typeof project.createdAt !== "string") fail("project.createdAt must be a string");
  if (!Array.isArray(d.revisions)) fail("revisions must be a list");
  if (!Array.isArray(d.decisions)) fail("decisions must be a list");

  let documents: ProjectFileDocument[] = [];
  if (!v1) {
    if (!Array.isArray(d.documents)) fail("documents must be a list");
    const seen = new Set<string>();
    documents = (d.documents as unknown[]).map((x, i): ProjectFileDocument => {
      const at = `documents[${i}]`;
      if (!isObj(x)) return fail(`${at} must be an object`);
      if (!isDocId(x.docId)) fail(`${at}.docId must be a non-empty string without "${CALC_REF_SEP}"`);
      if (seen.has(x.docId as string)) fail(`${at}: duplicate docId ${String(x.docId)}`);
      seen.add(x.docId as string);
      if (typeof x.name !== "string") fail(`${at}.name must be a string`);
      if (typeof x.removed !== "boolean") fail(`${at}.removed must be a boolean`);
      return { docId: x.docId as string, name: x.name as string, removed: x.removed as boolean };
    });
  }
  const kinds = new Map<number, RevisionKind>();
  const revisions = (d.revisions as unknown[]).map((r, i): ProjectFileRevision => {
    const at = `revisions[${i}]`;
    if (!isObj(r)) return fail(`${at} must be an object`);
    if (!isInt(r.id)) fail(`${at}.id must be an integer`);
    const id = r.id as number;
    if (kinds.has(id)) fail(`${at}: duplicate revision id ${id}`);
    if (r.kind !== "model" && r.kind !== "calcs") fail(`${at}.kind must be "model" or "calcs"`);
    const kind = r.kind as RevisionKind;
    kinds.set(id, kind);
    if (!isInt(r.seq) || r.seq < 1) fail(`${at}.seq must be a positive integer`);
    for (const k of ["label", "sourceName", "mediaType", "createdAt"] as const) {
      if (typeof r[k] !== "string") fail(`${at}.${k} must be a string`);
    }
    if (!isObj(r.meta)) fail(`${at}.meta must be an object`);
    const meta: RevisionMeta = {};
    for (const [k, v] of Object.entries(r.meta as Record<string, unknown>)) {
      if (v !== null && !["string", "number", "boolean"].includes(typeof v)) fail(`${at}.meta.${k} must be a string, number, boolean or null`);
      meta[k] = v as RevisionMeta[string];
    }
    // every revision is its original file: an empty one is a file that lost its payload
    if (typeof r.blob !== "string" || !r.blob || r.blob.length % 4 !== 0 || !BASE64.test(r.blob)) fail(`${at}.blob must be a non-empty base64 string`);
    const out: ProjectFileRevision = {
      id, kind, seq: r.seq as number, label: r.label as string, sourceName: r.sourceName as string, mediaType: r.mediaType as string,
      createdAt: r.createdAt as string, meta, blob: r.blob as string,
    };
    if (kind === "model") {
      if (r.graph === undefined) fail(`${at}: model revision ${id} has no element graph`);
      try {
        out.graph = parseGraph(r.graph);
      } catch (e) {
        fail(`${at}.graph: ${(e as Error).message}`);
      }
    } else if (r.graph !== undefined) {
      fail(`${at}: calc revision ${id} must not carry an element graph`);
    }
    if (kind === "calcs") {
      if (v1) out.docId = LEGACY_DOC_ID;
      else if (!documents.some((x) => x.docId === r.docId)) fail(`${at}.docId must name one of documents[] (calc revision ${id})`);
      else out.docId = r.docId as string;
    } else if (r.docId !== undefined) {
      fail(`${at}: model revision ${id} must not name a calc document`);
    }
    // checked against the PDF by storedExtractionFor when it is used
    if (r.extraction !== undefined) out.extraction = r.extraction;
    return out;
  });

  const decisions = (d.decisions as unknown[]).map((x, i): ProjectFileDecision => {
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
    const key = x.calcKey as string;
    if (!v1 && !key.includes(CALC_REF_SEP)) fail(`${at}.calcKey must be a calc ref "<docId>${CALC_REF_SEP}<key>"`);
    return {
      globalId: x.globalId as string, calcKey: v1 ? legacyCalcRef(key) : key, action: x.action as DecisionAction, actor: x.actor as string,
      note: x.note as string | null, at: x.at as string, modelRev: x.modelRev as number | null, calcRev: x.calcRev as number | null,
    };
  });

  if (v1) {
    const first = revisions.filter((r) => r.kind === "calcs").sort((a, b) => a.id - b.id)[0];
    if (first) documents = [{ docId: LEGACY_DOC_ID, name: documentName(first.sourceName), removed: false }];
  }
  for (const x of documents) {
    if (!revisions.some((r) => r.kind === "calcs" && r.docId === x.docId)) fail(`document ${x.docId} has no calc revision`);
  }

  return {
    format: PROJECT_FILE_FORMAT, version: PROJECT_FILE_VERSION, exportedAt: d.exportedAt as string,
    project: { name: project.name as string, createdAt: project.createdAt as string }, documents, revisions, decisions,
  };
}

const isDocId = (v: unknown): v is string => typeof v === "string" && v.length > 0 && !v.includes(CALC_REF_SEP);

/** A calc revision's document: its docId, or LEGACY_DOC_ID for a record from before calc sets. */
export function docIdOf(rev: Pick<ProjectFileRevisionFields, "docId">): string {
  return rev.docId ?? LEGACY_DOC_ID;
}

/** A decision's calc key as a ref: a bare key (written before calc sets) names a calc of LEGACY_DOC_ID. */
export function legacyCalcRef(key: string): string {
  return key.includes(CALC_REF_SEP) ? key : calcRef(LEGACY_DOC_ID, key);
}

/** A document's default name: its file name without the extension. */
export function documentName(sourceName: string): string {
  return sourceName.replace(/\.[A-Za-z0-9]{2,4}$/, "") || sourceName;
}

/**
 * The project's calc documents: the stored list, or (a project from before calc sets, which has none)
 * one LEGACY_DOC_ID document when it has calc revisions. Any calc revision naming a document the list
 * lacks gets one appended, so every revision belongs to a listed document.
 */
export function projectDocuments<R extends Pick<ProjectFileRevisionFields, "id" | "kind" | "sourceName" | "docId">>(
  stored: readonly ProjectFileDocument[] | null | undefined, revisions: readonly R[],
): ProjectFileDocument[] {
  const out = [...(stored ?? [])];
  for (const r of [...revisions].filter((x) => x.kind === "calcs").sort((a, b) => a.id - b.id)) {
    const id = docIdOf(r);
    if (!out.some((x) => x.docId === id)) out.push({ docId: id, name: documentName(r.sourceName), removed: false });
  }
  return out;
}

/** Each document that is not removed, in set order, with its head revision (the highest id). */
export function documentHeads<R extends Pick<ProjectFileRevisionFields, "id" | "kind" | "docId">>(
  documents: readonly ProjectFileDocument[], revisions: readonly R[],
): { doc: ProjectFileDocument; rev: R }[] {
  const out: { doc: ProjectFileDocument; rev: R }[] = [];
  for (const doc of documents) {
    if (doc.removed) continue;
    let best: R | null = null;
    for (const r of revisions) if (r.kind === "calcs" && docIdOf(r) === doc.docId && (!best || r.id > best.id)) best = r;
    if (best) out.push({ doc, rev: best });
  }
  return out;
}

/** The next free document id: "d<n>" one past the highest numbered one. */
export function nextDocId(documents: readonly Pick<ProjectFileDocument, "docId">[]): string {
  let n = 0;
  for (const d of documents) {
    const m = /^d(\d+)$/.exec(d.docId);
    if (m) n = Math.max(n, Number(m[1]));
  }
  return `d${n + 1}`;
}

/**
 * Whether a calc revision's stored extraction can be used as its calc package, given the sha256 of
 * the PDF it was extracted from (calc-mapper `sha256` of the stored bytes). Usable only when
 *   1. every document hash in it names a PDF (an extraction from before the provenance contract has none),
 *   2. it was segmented by the CURRENT segmenter (`segmenter` === calc-mapper `SEGMENTER_VERSION`):
 *      calc keys, pages and flags from an older segmenter would otherwise be reused forever,
 *   3. it has the full shape the engine reads (calc-mapper `calcPackageProblem`: pages with text and
 *      word boxes, calcs with unique keys, regions, title boxes, provenance), and
 *   4. every document hash names THIS PDF.
 * Otherwise `reason` says why, and the reader re-extracts from the PDF. The one rule for the app
 * (src/engine/projectService.ts) and the MCP server (packages/mcp-server/src/engine.ts).
 */
export function storedExtractionFor(extraction: unknown, pdfSha256: string): { pkg: CalcPackage; reason: null } | { pkg: null; reason: string } {
  const no = (reason: string) => ({ pkg: null, reason });
  if (extraction === undefined || extraction === null) return no("there is no stored extraction");
  if (!isObj(extraction)) return no("the stored extraction is malformed (not an object)");
  const { pages, calcs, source_sha256: src } = extraction;
  if (!Array.isArray(pages) || !pages.length || !pages.every(isObj)) return no("the stored extraction is malformed (pages must be a non-empty list of pages)");
  if (!Array.isArray(calcs) || !calcs.every(isObj)) return no("the stored extraction is malformed (calcs must be a list of calcs)");
  if (src !== undefined && src !== null && typeof src !== "string") return no("the stored extraction is malformed (source_sha256 must be a string)");
  if (!src || !pages.every((pg) => typeof pg.doc_sha256 === "string" && pg.doc_sha256)) return no("the stored extraction predates document hashes");
  const seg = extraction.segmenter;
  if (seg !== SEGMENTER_VERSION) {
    return no(`the stored extraction was segmented by ${seg ? `an older segmenter (${String(seg)})` : "a segmenter that predates versioning"}; the current one is ${SEGMENTER_VERSION}`);
  }
  const problem = calcPackageProblem(extraction);
  if (problem) return no(`the stored extraction is malformed (${problem})`);
  if (src !== pdfSha256 || !pages.every((pg) => pg.doc_sha256 === pdfSha256)) return no("the stored extraction's document hash does not match the PDF");
  return { pkg: extraction as unknown as CalcPackage, reason: null };
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
