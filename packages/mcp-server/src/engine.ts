/**
 * The engine boundary. This is the ONLY module in the server that imports the unLoaded engine
 * packages: @unloaded/ifc-parser and @unloaded/element-graph (model -> element graph, connectivity,
 * load path), @unloaded/calc-mapper (calc PDFs -> calcs, mapping, calc graph, review state, export,
 * impact, revision diff, decision log), @unloaded/project-file (the app's *.calcgraph.json) and
 * @unloaded/move-impact (move / remove a column). Everything else in src/ talks to the narrow
 * interface below (functions + the types re-exported here), so the server can be re-pointed to
 * another port of the engine by rewriting this one file.
 *
 * No logic of its own lives here: every function is a direct call into the engine packages, made
 * the way the app makes it (src/loaders/parsers.ts for models, src/engine/projectService.ts and
 * src/engine/ops.ts for calc packages, calc sets, runs and decisions). One thin composition,
 * documented where it is: `projectFileDecisions` (the project file's log as DecisionFields, numbered
 * in file order).
 */
import { parseIfc, hasStepHeader } from "@unloaded/ifc-parser";
import {
  buildGraph,
  ElementGraph,
  ELEMENT_GRAPH_FORMAT,
  type ElementNode,
  type GraphEdge,
  type GraphStats,
  type LevelInput,
  type ModelInput,
  type SerializedElementGraph,
} from "@unloaded/element-graph";
import * as cm from "@unloaded/calc-mapper";
import * as pf from "@unloaded/project-file";
import * as mi from "@unloaded/move-impact";

// ------------------------------------------------------------------ re-exported data types

export type {
  Rect,
  WordBox,
  Calc,
  CalcPage,
  CalcPackage,
  CalcSet,
  CalcSetDocument,
  CalcEdge,
  CalcEdgeEvidence,
  Link,
  LinkReview,
  Tier,
  Snippet,
  Decision,
  DecisionFields,
  DecisionAction,
  ElementRow,
  ElementStatus,
  Finding,
  TypicalGroup,
  GroupLink,
  Impact,
  ImpactMode,
  Compare,
  Export,
  ExportInfo,
  LoadPathEdge,
  ConnectivityEdge,
  MappingRun,
  ProjectState,
  Provenance,
} from "@unloaded/calc-mapper";
export type { ProjectFile, ProjectFileDocument, ProjectFileRevision } from "@unloaded/project-file";
export type { Move, ImpactResult as MoveResult } from "@unloaded/move-impact";
/** An element-graph node (elements and connections are both nodes). */
export type ModelNode = ElementNode;
/** An element-graph edge: `connects` (undirected), `supports` (a is supported by b), `part_of`. */
export type ModelEdge = GraphEdge;
export type ModelLevel = LevelInput;
export type ModelStats = GraphStats;
export type ModelGraph = SerializedElementGraph;

/** The mapping engine's version (calc-mapper `ENGINE_VERSION`: matcher + segmenter), stamped on every result. */
export const ENGINE_VERSION: string = cm.ENGINE_VERSION;
/** Producer strings of the engine packages the server runs. */
export const ENGINE_PRODUCERS = {
  calc_mapper: `${cm.PACKAGE_NAME}@${cm.PACKAGE_VERSION}`,
  move_impact: `${mi.PACKAGE_NAME}@${mi.PACKAGE_VERSION}`,
} as const;
/** The engine's confidence bands (high >= 0.75, medium >= 0.5). */
export const CONFIDENCE_BANDS: Readonly<{ high: number; medium: number }> = cm.BANDS;
/** The decision actions the engine accepts. */
export const DECISION_ACTIONS: readonly cm.DecisionAction[] = cm.DECISION_ACTIONS;

/** Bad input the engine refuses (wrong format, malformed JSON...). The message is user-facing. */
export class EngineInputError extends Error {
  override name = "EngineInputError";
}

// ------------------------------------------------------------------ model

export type ModelFormat = "ifc" | "element-graph-json" | "model-input-json" | "project-file";

/**
 * A loaded model revision: the element graph (for connectivity and load-path queries) plus the
 * serialized graph calc-mapper reads (`ElementGraph.serialize()`, validated by `parseGraph`, exactly
 * what the app stores per model revision) and its sha256. Read-only.
 */
export interface Model {
  format: ModelFormat;
  project: string | null;
  schema: string | null;
  /** Parser + graph-build warnings, prefixed with their origin (as the app does). */
  warnings: string[];
  /** The serialized graph calc-mapper and move-impact read. */
  graph: SerializedElementGraph;
  /** sha256 of the graph's canonical JSON (calc-mapper `sha256Json`): the graph input of every run. */
  graphSha256: string;
  nodes(): ModelNode[];
  node(id: string): ModelNode | undefined;
  levels(): ModelLevel[];
  edges(): ModelEdge[];
  stats(): ModelStats;
  /** calc-mapper element rows (`graphElements`), sorted by GlobalId. */
  elements(): cm.ElementRow[];
  /** calc-mapper `loadPath`: the `supports` edges (src is supported by dst), with rule and gap. */
  loadEdges(): cm.LoadPathEdge[];
  /** calc-mapper `connectivity`: the `connects` edges. */
  connectivity(): cm.ConnectivityEdge[];
  /** Edges incident to a node, optionally of one kind. */
  edgesOf(id: string, kind?: string): ModelEdge[];
  edgesBetween(a: string, b: string): ModelEdge[];
  supportsOf(id: string): string[];
  supportedBy(id: string): string[];
  connectionsOf(id: string): string[];
  membersOf(id: string): string[];
  partsOf(id: string): string[];
  /** Neighbours over `connects` edges. */
  connected(id: string): string[];
  loadPathDown(id: string): Map<string, number>;
  loadPathUp(id: string): Map<string, number>;
}

async function wrapGraph(
  eg: ElementGraph,
  format: ModelFormat,
  project: string | null,
  schema: string | null,
  warnings: string[],
  fileName: string,
  serialized?: SerializedElementGraph,
): Promise<Model> {
  let graph: SerializedElementGraph;
  try {
    // what the app stores (ElementGraph.serialize) as calc-mapper reads it back (parseGraph)
    graph = serialized ?? cm.parseGraph(eg.serialize());
  } catch (e) {
    throw new EngineInputError(`${fileName}: the calc engine cannot read this model's element graph: ${(e as Error).message}`);
  }
  const graphSha256 = await cm.sha256Json(graph);
  let elements: cm.ElementRow[] | null = null;
  let loadEdges: cm.LoadPathEdge[] | null = null;
  let connectivity: cm.ConnectivityEdge[] | null = null;
  return {
    format,
    project,
    schema,
    warnings,
    graph,
    graphSha256,
    nodes: () => eg.nodes(),
    node: (id) => eg.getNode(id),
    levels: () => eg.levels(),
    edges: () => eg.edges(),
    stats: () => eg.stats(),
    elements: () => (elements ??= cm.graphElements(graph)),
    loadEdges: () => (loadEdges ??= cm.loadPath(graph)),
    connectivity: () => (connectivity ??= cm.connectivity(graph)),
    edgesOf: (id, kind) => eg.edgesOf(id, kind === undefined ? {} : { kind }),
    edgesBetween: (a, b) => eg.edgesBetween(a, b),
    supportsOf: (id) => eg.supportsOf(id),
    supportedBy: (id) => eg.supportedBy(id),
    connectionsOf: (id) => eg.connectionsOf(id),
    membersOf: (id) => eg.membersOf(id),
    partsOf: (id) => eg.partsOf(id),
    connected: (id) => eg.neighbours(id, { edgeKind: "connects" }),
    loadPathDown: (id) => eg.loadPathDown(id),
    loadPathUp: (id) => eg.loadPathUp(id),
  };
}

/** Does the file start like an IFC (STEP) file? */
export function looksLikeIfc(head: Uint8Array): boolean {
  return hasStepHeader(head);
}

function isSerializedGraph(d: unknown): d is SerializedElementGraph {
  return typeof d === "object" && d !== null && (d as { format?: unknown }).format === ELEMENT_GRAPH_FORMAT;
}

function isModelInput(d: unknown): d is ModelInput {
  if (typeof d !== "object" || d === null) return false;
  const m = d as Partial<ModelInput>;
  return Array.isArray(m.elements) && typeof m.meta === "object" && m.meta !== null;
}

/**
 * Model bytes -> element graph, dispatched like the app's importers (src/loaders/parsers.ts):
 * IFC -> parseIfc -> buildGraph (connectivity inferred); serialized element graph JSON ->
 * ElementGraph.deserialize; ModelInput JSON -> buildGraph. Legacy `{nodes, links}` BIM JSON has no
 * GlobalIds and is refused; a project file belongs in --project.
 */
export async function loadModel(bytes: Uint8Array, fileName: string): Promise<Model> {
  const head = bytes.subarray(0, 1024);
  if (hasStepHeader(head)) {
    const input = await parseIfc(bytes, { fileName });
    const { graph, warnings } = buildGraph(input);
    return wrapGraph(graph, "ifc", input.meta.project ?? null, input.meta.schema ?? null, [
      ...(input.warnings ?? []).map((w) => `parser: ${w}`),
      ...warnings.map((w) => `graph: ${w}`),
    ], fileName);
  }
  let data: unknown;
  try {
    data = JSON.parse(new TextDecoder().decode(bytes).replace(/^﻿/, ""));
  } catch (e) {
    throw new EngineInputError(
      `${fileName} is neither an IFC file (no "ISO-10303-21" STEP header) nor valid JSON (${(e as Error).message}). ` +
        `Pass the model as .ifc, a serialized element graph (.json) or a ModelInput (.json).`,
    );
  }
  if (isSerializedGraph(data)) {
    let graph: ElementGraph;
    try {
      graph = ElementGraph.deserialize(data);
    } catch (e) {
      throw new EngineInputError(`${fileName}: element graph JSON could not be loaded: ${(e as Error).message}`);
    }
    return wrapGraph(graph, "element-graph-json", data.meta?.project ?? null, data.meta?.schema ?? null, [], fileName);
  }
  if (isModelInput(data)) {
    let built: ReturnType<typeof buildGraph>;
    try {
      built = buildGraph(data);
    } catch (e) {
      throw new EngineInputError(`${fileName}: ModelInput JSON could not be built into a graph: ${(e as Error).message}`);
    }
    return wrapGraph(built.graph, "model-input-json", data.meta.project ?? null, data.meta.schema ?? null, [
      ...(data.warnings ?? []).map((w) => `parser: ${w}`),
      ...built.warnings.map((w) => `graph: ${w}`),
    ], fileName);
  }
  if (pf.isProjectFileFormat(data)) {
    throw new EngineInputError(`${fileName} is a calc-graph project file: pass it with --project, not --model.`);
  }
  if (typeof data === "object" && data !== null && Array.isArray((data as { nodes?: unknown }).nodes)) {
    throw new EngineInputError(
      `${fileName} is a legacy BIM graph JSON ({nodes, links}). It has no IFC GlobalIds, so calcs and review ` +
        `decisions cannot be keyed to its elements. Use the source .ifc, or save the element graph from the app.`,
    );
  }
  throw new EngineInputError(
    `${fileName}: JSON is not an element graph (format "${ELEMENT_GRAPH_FORMAT}") or a ModelInput ({meta, elements, relations}).`,
  );
}

/** A project file's model revision: its stored element graph (never re-parsed from the IFC, as in the app). */
export async function modelFromRevision(rev: pf.ProjectFileRevision, fileName: string): Promise<Model> {
  if (!rev.graph) throw new EngineInputError(`${fileName}: model revision ${rev.id} (${rev.sourceName}) has no element graph`);
  let graph: SerializedElementGraph;
  try {
    graph = cm.parseGraph(rev.graph);
  } catch (e) {
    throw new EngineInputError(`${fileName}: model revision ${rev.id} (${rev.sourceName}): ${(e as Error).message}`);
  }
  const meta = rev.meta ?? {};
  return wrapGraph(
    ElementGraph.deserialize(graph),
    "project-file",
    typeof meta.project === "string" ? meta.project : (graph.meta?.project ?? null),
    graph.meta?.schema ?? null,
    [],
    fileName,
    graph,
  );
}

// ------------------------------------------------------------------ project file (*.calcgraph.json)

/** Does this parsed JSON claim to be a calc-graph project file? (routing only) */
export function isProjectFile(data: unknown): boolean {
  return pf.isProjectFileFormat(data);
}

/** Validate a parsed project file (`parseProjectFile`); errors name the field at fault. */
export function parseProjectFile(data: unknown): pf.ProjectFile {
  try {
    return pf.parseProjectFile(data);
  } catch (e) {
    throw new EngineInputError(`project file: ${(e as Error).message}`);
  }
}

/** The head revision of a kind: the highest id (what the app shows after importing). */
export function headRevision(file: pf.ProjectFile, kind: "model" | "calcs"): pf.ProjectFileRevision | null {
  return pf.headOf(file.revisions, kind);
}

/**
 * The calc set the app maps (`documentHeads`): every calc document that is not withdrawn, in set
 * order, with its head revision (the highest id of that document).
 */
export function calcDocumentHeads(file: pf.ProjectFile): { doc: pf.ProjectFileDocument; rev: pf.ProjectFileRevision }[] {
  return pf.documentHeads(file.documents, file.revisions);
}

/** A calc revision's document id (`docIdOf`: LEGACY_DOC_ID for a revision from before calc sets). */
export function calcDocIdOf(rev: pf.ProjectFileRevision): string {
  return pf.docIdOf(rev);
}

/** The document a bare calc key (no "<docId>#") names (`LEGACY_DOC_ID`: the first document). */
export const LEGACY_DOC_ID: string = pf.LEGACY_DOC_ID;

/** A calc key as a calc ref (`legacyCalcRef`): a bare key names a calc of the first document (LEGACY_DOC_ID). */
export function legacyCalcRef(key: string): string {
  return pf.legacyCalcRef(key);
}

/** A revision's original file (base64 in the project file). */
export function revisionBytes(rev: pf.ProjectFileRevision): Uint8Array {
  return pf.decodeBase64(rev.blob);
}

/**
 * The project file's decision log as calc-mapper DecisionFields, oldest first, numbered 1..n in file
 * order. The file keeps the log in order and without ids (the app's store ids are an auto-increment
 * across projects); order is all the engine reads from an id (`effectiveDecisions`: latest per pair
 * wins). The engine states each decision's provenance from these fields (`decisionFrom`).
 */
export function projectFileDecisions(file: pf.ProjectFile): cm.DecisionFields[] {
  return file.decisions.map((d, i) => ({
    id: i + 1,
    global_id: d.globalId,
    calc_key: d.calcKey,
    action: d.action,
    actor: d.actor,
    note: d.note,
    at: d.at,
    model_rev: d.modelRev,
    calc_rev: d.calcRev,
  }));
}

/**
 * A calc revision's stored extraction, when the app's rule (`storedExtractionFor`) accepts it for this
 * PDF's sha256; otherwise the reason it must be re-extracted.
 */
export function storedCalcPackage(extraction: unknown, pdfSha256: string): { pkg: cm.CalcPackage; reason: null } | { pkg: null; reason: string } {
  return pf.storedExtractionFor(extraction, pdfSha256);
}

// ------------------------------------------------------------------ calc PDFs

let pdfjsPromise: Promise<cm.PdfjsLike> | null = null;
/** pdf.js legacy build: what pdf.js documents for Node and what calc-mapper's own Node CLI uses. */
function nodePdfjs(): Promise<cm.PdfjsLike> {
  return (pdfjsPromise ??= import("pdfjs-dist/legacy/build/pdf.mjs") as unknown as Promise<cm.PdfjsLike>);
}

/** PDF bytes -> a segmented calc package (`extractPdf` + `segmentCalcs`, as the app's worker does) and the PDF title. */
export async function readCalcPackage(bytes: Uint8Array, sourceName: string): Promise<{ pkg: cm.CalcPackage; title: string }> {
  const text = await cm.extractPdf(bytes, { pdfjs: await nodePdfjs() });
  return { pkg: cm.segmentCalcs(text.pages, sourceName), title: text.meta.title };
}

/**
 * Combine calc PDFs into one calc set (`buildCalcSet`), as the app's worker does: calc keys become
 * calc refs "<doc_id>#<key>" and pages get SET page numbers (document page + page_offset). Throws on
 * a duplicate doc_id or the same PDF twice.
 */
export function buildCalcSet(documents: readonly cm.CalcSetDocument[]): cm.CalcSet {
  return cm.buildCalcSet(documents);
}

/** The calc-ref separator ("#"): a calc ref is "<doc_id>#<key>". */
export const CALC_REF_SEP: string = cm.CALC_REF_SEP;

/** Map a calc package or set onto a graph: auto links, calc edges, typical groups, group links, findings (`mapCalcs`). */
export function mapCalcs(graph: SerializedElementGraph, calcs: cm.CalcPackage | cm.CalcSet): Promise<cm.MappingRun> {
  return cm.mapCalcs(graph, calcs);
}

/** Elements with status, links with decisions applied, calc edges from the effective links, findings (`buildState`). */
export function buildState(
  graph: SerializedElementGraph,
  pkg: cm.CalcPackage | cm.CalcSet,
  run: cm.MappingRun,
  decisions: readonly cm.DecisionFields[],
): cm.ProjectState {
  return cm.buildState(graph, pkg, run, decisions);
}

/** The engine's export of one (graph, calc package or set) pair (`buildExport`). */
export function buildExport(
  graph: SerializedElementGraph,
  pkg: cm.CalcPackage | cm.CalcSet,
  run: cm.MappingRun,
  decisions: readonly cm.DecisionFields[],
  info: cm.ExportInfo,
): cm.Export {
  return cm.buildExport(graph, pkg, run, decisions, info);
}

/** The [start, end) regions of a page's text that belong to a calc (`calcRegions`: its spans, else its whole pages). */
export function calcRegions(calc: cm.Calc, pages: cm.CalcPage[]): { page: number; start: number; end: number }[] {
  return cm.calcRegions(calc, pages);
}

/** Element status from its links (design links only; `statusOf`). */
export function statusOf(links: cm.Link[]): cm.ElementStatus {
  return cm.statusOf(links);
}

/** Highlight boxes of the words overlapping [start, end) of a page's text. */
export function rectsForSpan(page: Pick<cm.CalcPage, "words">, start: number, end: number): cm.Rect[] {
  return cm.rectsForSpan(page, start, end);
}

// ------------------------------------------------------------------ impact, diff, move

/**
 * What a change to / removal of one element hits on the load path and which calcs go stale
 * (`propagate`, the core of `impactOf`). `inputs`: sha256 of the documents the answer rests on.
 */
export function propagateImpact(
  gid: string,
  mode: cm.ImpactMode,
  edges: Pick<cm.LoadPathEdge, "src" | "dst">[],
  links: cm.Link[],
  calcEdges: cm.CalcEdge[],
  elements: Map<string, Pick<cm.ElementRow, "cat" | "mark" | "name">>,
  inputs: readonly string[],
): cm.Impact {
  return cm.propagate(gid, mode, edges, links, calcEdges, elements, inputs);
}

/** Diff two model revisions (`diffGraphs`): removed / added / changed elements and load-path edges. */
export function diffGraphs(a: SerializedElementGraph, b: SerializedElementGraph, labels: { a?: string | number; b?: string | number }): cm.Compare {
  return cm.diffGraphs(a, b, labels);
}

/** Move or remove a column (`@unloaded/move-impact` `impact`), on the graph and the reviewed links. */
export function moveColumn(input: { graph: SerializedElementGraph; graphSha256: string; move: mi.Move; links: cm.Link[] }): mi.ImpactResult {
  return mi.impact(input);
}

// ------------------------------------------------------------------ decisions (append-only log)

/**
 * The decision `addDecision` appends to a log (next id, human provenance), alone. The log may hold
 * entries read back from a file without provenance: addDecision reads only their ids.
 */
export function nextDecision(
  log: readonly cm.DecisionFields[],
  d: cm.DecisionIn,
  ctx: { at?: string; model_rev?: string | number | null; calc_rev?: string | number | null; inputs?: readonly string[] },
): cm.Decision {
  return cm.addDecision(log as readonly cm.Decision[], d, ctx).at(-1)!;
}

/** A Decision from stored fields (`decisionFrom`; throws on an unknown action). */
export function decisionFrom(d: cm.DecisionFields): cm.Decision {
  return cm.decisionFrom(d);
}

/** Latest decision per (global_id, calc_key), undone pairs dropped (`effectiveDecisions`). */
export function effectiveDecisions<D extends cm.DecisionFields>(log: readonly D[]): Map<string, D> {
  return cm.effectiveDecisions(log);
}
