/**
 * The engine boundary. This is the ONLY module in the server that imports @unloaded/ifc-parser,
 * @unloaded/element-graph and @unloaded/calc-parser. Everything else in src/ talks to the narrow
 * interface below (functions + the types re-exported here), so the server can be re-pointed to
 * another port of the same engine by rewriting this one file.
 *
 * No logic of its own lives here: every function is a direct call into the engine packages,
 * made the way the app makes it (src/loaders/parsers.ts for models; calc-parser's README and tests
 * for PDFs). The one composition is `crossReferenceDeps`, which calls `inferCalcDeps` on a view with
 * the page-reference rule switched off (see its comment).
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
import * as cp from "@unloaded/calc-parser";

// ------------------------------------------------------------------ re-exported data types

export type {
  Rect,
  WordBox,
  Calc,
  CalcPage,
  CalcLink,
  CalcEdge,
  CalcEdgeEvidence,
  LinkTier,
  LinkStatus,
  Snippet,
  Decision,
  DecisionAction,
  ImpactMode,
  ImpactResult,
  LoadEdge,
  MappingStatus,
} from "@unloaded/calc-parser";
/** The element record the matcher reasons about (GlobalId, category, mark, profile, storey, name). */
export type EngineElement = cp.CalcElement;
/** An element-graph node (elements and connections are both nodes). */
export type ModelNode = ElementNode;
/** An element-graph edge: `connects` (undirected), `supports` (a is supported by b), `part_of`. */
export type ModelEdge = GraphEdge;
export type ModelLevel = LevelInput;
export type ModelStats = GraphStats;

/** Engine version stamped on every result. */
export const ENGINE_VERSION: string = cp.ENGINE_VERSION;

/** Bad input the engine refuses (wrong format, malformed JSON...). The message is user-facing. */
export class EngineInputError extends Error {
  override name = "EngineInputError";
}

// ------------------------------------------------------------------ model

export type ModelFormat = "ifc" | "element-graph-json" | "model-input-json";

/** The loaded model: the element graph plus the matcher's element records. Read-only. */
export interface Model {
  format: ModelFormat;
  project: string | null;
  schema: string | null;
  /** Parser + graph-build warnings, prefixed with their origin (as the app does). */
  warnings: string[];
  nodes(): ModelNode[];
  node(id: string): ModelNode | undefined;
  levels(): ModelLevel[];
  edges(): ModelEdge[];
  stats(): ModelStats;
  /** Matcher records for every node (`toCalcElements` over the graph nodes, storey from the level). */
  elements(): EngineElement[];
  /** `supports` edges as calc-parser LoadEdges (src is supported by dst: load flows src -> dst), with the first evidence rule. */
  loadEdges(): Array<{ src: string; dst: string; rule: string }>;
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

function wrapGraph(graph: ElementGraph, format: ModelFormat, project: string | null, schema: string | null, warnings: string[]): Model {
  let elements: EngineElement[] | null = null;
  let loadEdges: Array<{ src: string; dst: string; rule: string }> | null = null;
  return {
    format,
    project,
    schema,
    warnings,
    nodes: () => graph.nodes(),
    node: (id) => graph.getNode(id),
    levels: () => graph.levels(),
    edges: () => graph.edges(),
    stats: () => graph.stats(),
    elements: () =>
      (elements ??= cp.toCalcElements(graph.nodes(), new Map(graph.levels().map((l) => [l.id, l.name])))),
    loadEdges: () =>
      (loadEdges ??= graph
        .edges()
        .filter((e) => e.kind === "supports")
        .map((e) => ({ src: e.a, dst: e.b, rule: e.evidence[0]?.rule ?? "" }))),
    edgesOf: (id, kind) => graph.edgesOf(id, kind === undefined ? {} : { kind }),
    edgesBetween: (a, b) => graph.edgesBetween(a, b),
    supportsOf: (id) => graph.supportsOf(id),
    supportedBy: (id) => graph.supportedBy(id),
    connectionsOf: (id) => graph.connectionsOf(id),
    membersOf: (id) => graph.membersOf(id),
    partsOf: (id) => graph.partsOf(id),
    connected: (id) => graph.neighbours(id, { edgeKind: "connects" }),
    loadPathDown: (id) => graph.loadPathDown(id),
    loadPathUp: (id) => graph.loadPathUp(id),
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
 * GlobalIds and is refused.
 */
export async function loadModel(bytes: Uint8Array, fileName: string): Promise<Model> {
  const head = bytes.subarray(0, 1024);
  if (hasStepHeader(head)) {
    const input = await parseIfc(bytes, { fileName });
    const { graph, warnings } = buildGraph(input);
    return wrapGraph(graph, "ifc", input.meta.project ?? null, input.meta.schema ?? null, [
      ...(input.warnings ?? []).map((w) => `parser: ${w}`),
      ...warnings.map((w) => `graph: ${w}`),
    ]);
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
    return wrapGraph(graph, "element-graph-json", data.meta?.project ?? null, data.meta?.schema ?? null, []);
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
    ]);
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

// ------------------------------------------------------------------ calc PDFs

let pdfjsPromise: Promise<cp.PdfjsLike> | null = null;
/** pdf.js legacy build: what pdf.js documents for Node and what calc-parser's tests use. */
function nodePdfjs(): Promise<cp.PdfjsLike> {
  return (pdfjsPromise ??= import("pdfjs-dist/legacy/build/pdf.mjs") as unknown as Promise<cp.PdfjsLike>);
}

export interface PdfText {
  pages: cp.CalcPage[];
  meta: { page_count: number; title: string };
}

/** PDF bytes -> pages of text with word boxes (`readPdf`). */
export async function readPdf(bytes: Uint8Array): Promise<PdfText> {
  return cp.readPdf(bytes, await nodePdfjs());
}

/** Segment one PDF's pages into calcs, map elements to them, infer calc dependencies (`mapCalcs`). */
export function mapCalcs(elements: readonly EngineElement[], pages: readonly cp.CalcPage[]): cp.CalcMapping {
  return cp.mapCalcs(elements, pages);
}

/** Calc -> calc edges of one package, from page references and cross-references (`inferCalcDeps`). */
export function calcDependencies(
  calcs: ReadonlyArray<Pick<cp.Calc, "key" | "pages" | "front" | "scanned">>,
  pages: ReadonlyArray<Pick<cp.CalcPage, "n" | "text" | "words">>,
  links: readonly cp.CalcLink[],
): cp.CalcEdge[] {
  return cp.inferCalcDeps(calcs, pages, links);
}

/**
 * Only the cross-reference rule of `inferCalcDeps`, on any view of calcs / pages / links.
 * The page-reference rule walks each calc's `pages`; passing calcs with no pages switches it off,
 * while the cross-reference rule (which reads `pages` only to find the cue word on the link's line)
 * still runs. Used to find calc edges between two PDFs without resolving "page N" across files.
 */
export function crossReferenceDeps(
  calcs: ReadonlyArray<Pick<cp.Calc, "key" | "front" | "scanned">>,
  pages: ReadonlyArray<Pick<cp.CalcPage, "n" | "text" | "words">>,
  links: readonly cp.CalcLink[],
): cp.CalcEdge[] {
  return cp.inferCalcDeps(
    calcs.map((c) => ({ key: c.key, front: c.front, scanned: c.scanned, pages: [] })),
    pages,
    links,
  );
}

/** Highlight boxes of the words overlapping [start, end) of a page's text. */
export function rectsForSpan(page: Pick<cp.CalcPage, "words">, start: number, end: number): cp.Rect[] {
  return cp.rectsForSpan(page, start, end);
}

// ------------------------------------------------------------------ review, impact, export

export function effectiveDecisions(log: readonly cp.Decision[]): Map<string, cp.Decision> {
  return cp.effectiveDecisions(log);
}

export function effectiveLinks(
  links: readonly cp.CalcLink[],
  log: readonly cp.Decision[],
  gids: ReadonlySet<string>,
  calcKeys: ReadonlySet<string>,
): cp.CalcLink[] {
  return cp.effectiveLinks(links, log, gids, calcKeys);
}

export function mappingStatuses(
  elements: readonly EngineElement[],
  links: readonly cp.CalcLink[],
): { byElement: Map<string, cp.MappingStatus>; counts: Record<cp.MappingStatus, number> } {
  return cp.mappingStatuses(elements, links);
}

export function statusOf(links: ReadonlyArray<Pick<cp.CalcLink, "status" | "conf">>): cp.MappingStatus {
  return cp.statusOf(links);
}

export function propagateImpact(
  gid: string,
  mode: cp.ImpactMode,
  edges: readonly cp.LoadEdge[],
  links: ReadonlyArray<Pick<cp.CalcLink, "global_id" | "calc_key" | "status">>,
  calcEdges: ReadonlyArray<Pick<cp.CalcEdge, "src" | "dst">>,
  elements: ReadonlyMap<string, Pick<EngineElement, "cat" | "mark" | "name">>,
): cp.ImpactResult {
  return cp.propagateImpact(gid, mode, edges, links, calcEdges, elements);
}

export type ExportInput = cp.ExportInput;
export type MappingExport = ReturnType<typeof cp.exportMapping>;

export function exportMapping(input: ExportInput): MappingExport {
  return cp.exportMapping(input);
}
