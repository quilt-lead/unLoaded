/**
 * Core element-graph types. Pure data (JSON-serialisable), no rendering types.
 */
import type {
  ElementInput,
  LevelInput,
  ModelMeta,
  ParamValue,
  RelationEvidence,
  RelationKind,
} from "./input.ts";

/** Open hook for mapping an element to other graphs (e.g. the calc graph). */
export interface NodeLink {
  /** Target id in the other system (e.g. calc node id). */
  target: string;
  /** Link kind, e.g. "calc". Open set. */
  kind: string;
  data?: Record<string, ParamValue>;
}

/** A node in the element graph. Connections are nodes too (kind "connection"). */
export interface ElementNode extends ElementInput {
  /** Free user / app annotations (not from the source file). */
  tags: Record<string, ParamValue>;
  links: NodeLink[];
}

/** What `addNode` accepts: an ElementInput with optional tags / links. */
export type NodeInput = ElementInput & Partial<Pick<ElementNode, "tags" | "links">>;

/** Patch accepted by `updateNode`. `id` cannot change. */
export type NodePatch = Partial<Omit<ElementNode, "id">>;

/**
 * An edge.
 * - "connects": undirected; endpoints stored with a < b (lexicographic).
 * - "supports": directed; `a` is SUPPORTED BY `b` (load flows a -> b).
 * - "part_of":  directed; `a` is part of assembly `b`.
 * Other kinds are directed unless created with `directed: false`.
 */
export interface GraphEdge {
  /** Deterministic: `${kind}:${a}->${b}` (directed) or `${kind}:${a}|${b}` (undirected). */
  id: string;
  kind: RelationKind;
  a: string;
  b: string;
  directed: boolean;
  /** Explicit evidence always ordered before inferred evidence. */
  evidence: RelationEvidence[];
}

export interface EdgeInput {
  kind: RelationKind;
  a: string;
  b: string;
  /** Default: false for "connects", true otherwise. */
  directed?: boolean;
  evidence?: RelationEvidence | RelationEvidence[];
}

/** Ids touched by one committed mutation or batch. */
export interface GraphChange {
  /** Graph version after this change (monotonically increasing). */
  version: number;
  nodesAdded: string[];
  nodesUpdated: string[];
  nodesRemoved: string[];
  edgesAdded: string[];
  edgesUpdated: string[];
  edgesRemoved: string[];
  levelsChanged: boolean;
}

export type GraphListener = (change: GraphChange) => void;

export type Direction = "out" | "in" | "both";

export interface EdgeQuery {
  kind?: RelationKind;
  /** For directed edges: "out" = node is `a`, "in" = node is `b`. Undirected edges match any direction. Default "both". */
  direction?: Direction;
}

export interface NeighbourQuery {
  edgeKind?: RelationKind;
  nodeKind?: string;
  direction?: Direction;
}

export interface GraphStats {
  nodes: number;
  edges: number;
  levels: number;
  nodesByKind: Record<string, number>;
  edgesByKind: Record<string, number>;
  /** Number of edges carrying at least one evidence entry with this rule. */
  edgesByRule: Record<string, number>;
  /** Edges with any explicit evidence vs. edges with only inferred evidence. */
  explicitEdges: number;
  inferredOnlyEdges: number;
}

export const ELEMENT_GRAPH_FORMAT = "unloaded.element-graph" as const;
export const ELEMENT_GRAPH_FORMAT_VERSION = 1 as const;

export interface SerializedElementGraph {
  format: typeof ELEMENT_GRAPH_FORMAT;
  version: typeof ELEMENT_GRAPH_FORMAT_VERSION;
  meta: ModelMeta | null;
  levels: LevelInput[];
  nodes: ElementNode[];
  edges: GraphEdge[];
}
