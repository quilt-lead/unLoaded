import type { LevelInput, ModelMeta, RelationEvidence, RelationKind } from "../model/input.ts";
import {
  ELEMENT_GRAPH_FORMAT,
  ELEMENT_GRAPH_FORMAT_VERSION,
  type EdgeInput,
  type EdgeQuery,
  type ElementNode,
  type GraphChange,
  type GraphEdge,
  type GraphListener,
  type GraphStats,
  type NeighbourQuery,
  type NodeInput,
  type NodePatch,
  type SerializedElementGraph,
} from "../model/graph-types.ts";

type ChangeState = "added" | "updated" | "removed";

/** Kinds treated as connection nodes by connection-aware queries. */
export const CONNECTION_KIND = "connection";
const NON_MEMBER_KINDS = new Set<string>([CONNECTION_KIND, "fastener"]);

function cloneJson<T>(v: T): T {
  return v === undefined ? v : (JSON.parse(JSON.stringify(v)) as T);
}

/** Default directedness: "connects" is undirected, everything else directed. */
export function isDirectedKind(kind: RelationKind): boolean {
  return kind !== "connects";
}

/** Deterministic edge id. For undirected edges endpoints are ordered. */
export function edgeId(kind: RelationKind, a: string, b: string, directed = isDirectedKind(kind)): string {
  if (directed) return `${kind}:${a}->${b}`;
  return a <= b ? `${kind}:${a}|${b}` : `${kind}:${b}|${a}`;
}

function evidenceKey(e: RelationEvidence): string {
  return `${e.source}\u0000${e.rule}\u0000${e.detail ? JSON.stringify(e.detail) : ""}`;
}

/** Merge evidence lists: dedupe, explicit first (stable). */
function mergeEvidence(existing: RelationEvidence[], incoming: RelationEvidence[]): RelationEvidence[] {
  const seen = new Set(existing.map(evidenceKey));
  const all = existing.slice();
  for (const e of incoming) {
    const k = evidenceKey(e);
    if (!seen.has(k)) {
      seen.add(k);
      all.push(cloneJson(e));
    }
  }
  return [...all.filter((e) => e.source === "explicit"), ...all.filter((e) => e.source !== "explicit")];
}

function makeNode(input: NodeInput): ElementNode {
  const node: ElementNode = {
    id: input.id,
    kind: input.kind,
    params: { ...input.params },
    source: { ...input.source },
    tags: { ...(input.tags ?? {}) },
    links: cloneJson(input.links ?? []),
  };
  if (input.mark !== undefined) node.mark = input.mark;
  if (input.name !== undefined) node.name = input.name;
  if (input.profile !== undefined) node.profile = input.profile;
  if (input.material !== undefined) node.material = input.material;
  if (input.levelId !== undefined) node.levelId = input.levelId;
  if (input.geometry !== undefined) node.geometry = cloneJson(input.geometry);
  return node;
}

export interface ElementGraphOptions {
  meta?: ModelMeta | null;
  levels?: LevelInput[];
}

/**
 * Mutable structural element graph with change notification.
 *
 * Node / edge objects are treated as immutable: every update replaces the
 * stored object, so identity comparison works for UI memoisation.
 */
export class ElementGraph {
  meta: ModelMeta | null;

  private readonly _nodes = new Map<string, ElementNode>();
  private readonly _edges = new Map<string, GraphEdge>();
  private readonly _levels = new Map<string, LevelInput>();
  private readonly _byKind = new Map<string, Set<string>>();
  /** Edges where node is `a` (plus undirected). */
  private readonly _out = new Map<string, Set<string>>();
  /** Edges where node is `b` (plus undirected). Cached reverse adjacency. */
  private readonly _in = new Map<string, Set<string>>();

  private _version = 0;
  private _batchDepth = 0;
  private readonly _listeners = new Set<GraphListener>();
  private _pendingNodes = new Map<string, ChangeState>();
  private _pendingEdges = new Map<string, ChangeState>();
  private _pendingLevels = false;
  private _lastChange: GraphChange | null = null;

  constructor(opts: ElementGraphOptions = {}) {
    this.meta = opts.meta ? cloneJson(opts.meta) : null;
    for (const l of opts.levels ?? []) this._levels.set(l.id, { ...l });
  }

  // ---------------------------------------------------------------- change notification

  /** Monotonically increasing; incremented once per committed mutation or batch. */
  get version(): number {
    return this._version;
  }

  /** For React `useSyncExternalStore`: stable between changes. */
  getSnapshot = (): number => this._version;

  /** Last committed change, or null if none yet. */
  get lastChange(): GraphChange | null {
    return this._lastChange;
  }

  /** Subscribe to committed changes. Returns an unsubscribe function. */
  subscribe = (listener: GraphListener): (() => void) => {
    this._listeners.add(listener);
    return () => {
      this._listeners.delete(listener);
    };
  };

  /**
   * Run several mutations and emit a single change event. Nested batches are
   * merged into the outermost one. Not transactional: if `fn` throws, mutations
   * already applied are kept and still emitted, then the error is rethrown.
   */
  batch<T>(fn: (graph: this) => T): T {
    this._batchDepth++;
    try {
      return fn(this);
    } finally {
      this._batchDepth--;
      if (this._batchDepth === 0) this._commit();
    }
  }

  private _mutate<T>(fn: () => T): T {
    return this.batch(() => fn());
  }

  private _markNode(id: string, s: ChangeState): void {
    mark(this._pendingNodes, id, s);
  }
  private _markEdge(id: string, s: ChangeState): void {
    mark(this._pendingEdges, id, s);
  }

  private _commit(): void {
    if (this._pendingNodes.size === 0 && this._pendingEdges.size === 0 && !this._pendingLevels) return;
    const change: GraphChange = {
      version: ++this._version,
      nodesAdded: [],
      nodesUpdated: [],
      nodesRemoved: [],
      edgesAdded: [],
      edgesUpdated: [],
      edgesRemoved: [],
      levelsChanged: this._pendingLevels,
    };
    for (const [id, s] of this._pendingNodes) {
      (s === "added" ? change.nodesAdded : s === "updated" ? change.nodesUpdated : change.nodesRemoved).push(id);
    }
    for (const [id, s] of this._pendingEdges) {
      (s === "added" ? change.edgesAdded : s === "updated" ? change.edgesUpdated : change.edgesRemoved).push(id);
    }
    this._pendingNodes = new Map();
    this._pendingEdges = new Map();
    this._pendingLevels = false;
    this._lastChange = change;
    let firstError: unknown;
    for (const l of [...this._listeners]) {
      try {
        l(change);
      } catch (err) {
        firstError ??= err;
      }
    }
    if (firstError !== undefined) throw firstError;
  }

  // ---------------------------------------------------------------- levels

  setLevel(level: LevelInput): void {
    this._mutate(() => {
      this._levels.set(level.id, { ...level });
      this._pendingLevels = true;
    });
  }

  removeLevel(id: string): boolean {
    return this._mutate(() => {
      const had = this._levels.delete(id);
      if (had) this._pendingLevels = true;
      return had;
    });
  }

  getLevel(id: string): LevelInput | undefined {
    return this._levels.get(id);
  }

  /** Levels sorted by elevation. */
  levels(): LevelInput[] {
    return [...this._levels.values()].sort((x, y) => x.elevation - y.elevation);
  }

  // ---------------------------------------------------------------- node mutations

  addNode(input: NodeInput): ElementNode {
    if (!input || typeof input.id !== "string" || input.id === "") throw new Error("addNode: node id is required");
    if (this._nodes.has(input.id)) throw new Error(`addNode: duplicate node id "${input.id}"`);
    return this._mutate(() => {
      const node = makeNode(input);
      this._nodes.set(node.id, node);
      this._indexKind(node.id, node.kind);
      this._out.set(node.id, new Set());
      this._in.set(node.id, new Set());
      this._markNode(node.id, "added");
      return node;
    });
  }

  updateNode(id: string, patch: NodePatch): ElementNode {
    const prev = this._nodes.get(id);
    if (!prev) throw new Error(`updateNode: unknown node "${id}"`);
    if ("id" in patch && (patch as { id?: unknown }).id !== id) throw new Error("updateNode: id cannot be changed");
    return this._mutate(() => {
      const next = makeNode({ ...prev, ...patch, id });
      if (next.kind !== prev.kind) {
        this._unindexKind(id, prev.kind);
        this._indexKind(id, next.kind);
      }
      this._nodes.set(id, next);
      this._markNode(id, "updated");
      return next;
    });
  }

  /** Removes the node and all incident edges. Returns false if the node did not exist. */
  removeNode(id: string): boolean {
    const node = this._nodes.get(id);
    if (!node) return false;
    this._mutate(() => {
      for (const eid of [...this._incident(id)]) this._removeEdgeInternal(eid);
      this._nodes.delete(id);
      this._unindexKind(id, node.kind);
      this._out.delete(id);
      this._in.delete(id);
      this._markNode(id, "removed");
    });
    return true;
  }

  private _indexKind(id: string, kind: string): void {
    let s = this._byKind.get(kind);
    if (!s) this._byKind.set(kind, (s = new Set()));
    s.add(id);
  }
  private _unindexKind(id: string, kind: string): void {
    const s = this._byKind.get(kind);
    if (!s) return;
    s.delete(id);
    if (s.size === 0) this._byKind.delete(kind);
  }

  // ---------------------------------------------------------------- edge mutations

  /**
   * Add an edge, or merge evidence into the existing edge with the same id.
   * Throws on unknown endpoints or self-loops.
   */
  addEdge(input: EdgeInput): GraphEdge {
    const { kind } = input;
    if (!this._nodes.has(input.a)) throw new Error(`addEdge: unknown endpoint "${input.a}"`);
    if (!this._nodes.has(input.b)) throw new Error(`addEdge: unknown endpoint "${input.b}"`);
    if (input.a === input.b) throw new Error(`addEdge: self-loop on "${input.a}"`);
    const directed = input.directed ?? isDirectedKind(kind);
    const [a, b] = directed || input.a <= input.b ? [input.a, input.b] : [input.b, input.a];
    const id = edgeId(kind, a, b, directed);
    const incoming = input.evidence === undefined ? [] : Array.isArray(input.evidence) ? input.evidence : [input.evidence];
    return this._mutate(() => {
      const prev = this._edges.get(id);
      if (prev) {
        const evidence = mergeEvidence(prev.evidence, incoming);
        if (evidence.length === prev.evidence.length) return prev;
        const next: GraphEdge = { ...prev, evidence };
        this._edges.set(id, next);
        this._markEdge(id, "updated");
        return next;
      }
      const edge: GraphEdge = { id, kind, a, b, directed, evidence: mergeEvidence([], incoming) };
      this._insertEdge(edge);
      this._markEdge(id, "added");
      return edge;
    });
  }

  removeEdge(id: string): boolean {
    if (!this._edges.has(id)) return false;
    this._mutate(() => this._removeEdgeInternal(id));
    return true;
  }

  private _insertEdge(edge: GraphEdge): void {
    this._edges.set(edge.id, edge);
    this._out.get(edge.a)!.add(edge.id);
    this._in.get(edge.b)!.add(edge.id);
    if (!edge.directed) {
      this._out.get(edge.b)!.add(edge.id);
      this._in.get(edge.a)!.add(edge.id);
    }
  }

  private _removeEdgeInternal(id: string): void {
    const e = this._edges.get(id);
    if (!e) return;
    this._edges.delete(id);
    for (const n of [e.a, e.b]) {
      this._out.get(n)?.delete(id);
      this._in.get(n)?.delete(id);
    }
    this._markEdge(id, "removed");
  }

  private _incident(id: string): Set<string> {
    const s = new Set(this._out.get(id));
    for (const e of this._in.get(id) ?? []) s.add(e);
    return s;
  }

  // ---------------------------------------------------------------- basic queries

  get nodeCount(): number {
    return this._nodes.size;
  }
  get edgeCount(): number {
    return this._edges.size;
  }

  getNode(id: string): ElementNode | undefined {
    return this._nodes.get(id);
  }
  hasNode(id: string): boolean {
    return this._nodes.has(id);
  }
  getEdge(id: string): GraphEdge | undefined {
    return this._edges.get(id);
  }
  hasEdge(id: string): boolean {
    return this._edges.has(id);
  }

  /** Look up an edge by kind and endpoints (order normalised for undirected kinds). */
  findEdge(kind: RelationKind, a: string, b: string, directed = isDirectedKind(kind)): GraphEdge | undefined {
    return this._edges.get(edgeId(kind, a, b, directed));
  }

  nodes(): ElementNode[] {
    return [...this._nodes.values()];
  }
  edges(): GraphEdge[] {
    return [...this._edges.values()];
  }

  nodesByKind(kind: string): ElementNode[] {
    const ids = this._byKind.get(kind);
    return ids ? [...ids].map((id) => this._nodes.get(id)!) : [];
  }

  kinds(): string[] {
    return [...this._byKind.keys()];
  }

  edgesOf(id: string, q: EdgeQuery = {}): GraphEdge[] {
    const dir = q.direction ?? "both";
    const ids = dir === "out" ? this._out.get(id) : dir === "in" ? this._in.get(id) : this._incident(id);
    const out: GraphEdge[] = [];
    for (const eid of ids ?? []) {
      const e = this._edges.get(eid)!;
      if (q.kind === undefined || e.kind === q.kind) out.push(e);
    }
    return out;
  }

  /** Edges between two nodes, any kind / direction. */
  edgesBetween(a: string, b: string): GraphEdge[] {
    return this.edgesOf(a).filter((e) => e.a === b || e.b === b);
  }

  /** Neighbour ids (deduplicated, in edge insertion order). */
  neighbours(id: string, q: NeighbourQuery = {}): string[] {
    const edgeQ: EdgeQuery = { direction: q.direction ?? "both" };
    if (q.edgeKind !== undefined) edgeQ.kind = q.edgeKind;
    const seen = new Set<string>();
    for (const e of this.edgesOf(id, edgeQ)) {
      const other = e.a === id ? e.b : e.a;
      if (q.nodeKind !== undefined && this._nodes.get(other)?.kind !== q.nodeKind) continue;
      seen.add(other);
    }
    return [...seen];
  }

  /** Nodes that `id` bears on (supports edges out of id). */
  supportsOf(id: string): string[] {
    return this.neighbours(id, { edgeKind: "supports", direction: "out" });
  }

  /** Nodes that bear on `id` (supports edges into id). */
  supportedBy(id: string): string[] {
    return this.neighbours(id, { edgeKind: "supports", direction: "in" });
  }

  /** Connection nodes adjacent to a member (any edge kind). */
  connectionsOf(memberId: string): string[] {
    return this.neighbours(memberId, { nodeKind: CONNECTION_KIND });
  }

  /** Members (non-connection, non-fastener nodes) adjacent to a connection. */
  membersOf(connectionId: string): string[] {
    return this.neighbours(connectionId).filter((n) => !NON_MEMBER_KINDS.has(this._nodes.get(n)!.kind));
  }

  /** Parts (part_of edges into the node), e.g. fasteners of a connection. */
  partsOf(id: string): string[] {
    return this.neighbours(id, { edgeKind: "part_of", direction: "in" });
  }

  // ---------------------------------------------------------------- traversal

  /**
   * Everything `id` bears on, transitively (follows supports edges a -> b).
   * Returns Map<id, depth>, start at depth 0. Connection nodes are included
   * but pass-through: crossing a connection costs one step in total, so in
   * slab -> beam -> connection -> column the column and the connection share a depth.
   */
  loadPathDown(id: string): Map<string, number> {
    return this._loadPath(id, "out");
  }

  /** Everything that bears on `id`, transitively. Same depth semantics as loadPathDown. */
  loadPathUp(id: string): Map<string, number> {
    return this._loadPath(id, "in");
  }

  private _loadPath(start: string, direction: "out" | "in"): Map<string, number> {
    const depth = new Map<string, number>();
    if (!this._nodes.has(start)) return depth;
    depth.set(start, 0);
    // 0-1 BFS: stepping from a connection to a member costs 0.
    const deque: string[] = [start];
    let head = 0;
    const front: string[] = [];
    while (front.length > 0 || head < deque.length) {
      const cur = front.length > 0 ? front.pop()! : deque[head++]!;
      const d = depth.get(cur)!;
      const curIsConn = this._nodes.get(cur)!.kind === CONNECTION_KIND;
      for (const eid of (direction === "out" ? this._out : this._in).get(cur) ?? []) {
        const e = this._edges.get(eid)!;
        if (e.kind !== "supports" || !e.directed) continue;
        const next = direction === "out" ? e.b : e.a;
        const nextIsConn = this._nodes.get(next)!.kind === CONNECTION_KIND;
        const cost = curIsConn && !nextIsConn ? 0 : 1;
        const nd = d + cost;
        const old = depth.get(next);
        if (old === undefined || nd < old) {
          depth.set(next, nd);
          if (cost === 0) front.push(next);
          else deque.push(next);
        }
      }
    }
    return depth;
  }

  /** New graph containing the given nodes and the edges among them (deep copies). */
  subgraph(ids: Iterable<string>): ElementGraph {
    const keep = new Set<string>();
    for (const id of ids) if (this._nodes.has(id)) keep.add(id);
    const g = new ElementGraph({ meta: this.meta, levels: [...this._levels.values()] });
    for (const id of keep) g._loadNode(cloneJson(this._nodes.get(id)!));
    for (const e of this._edges.values()) {
      if (keep.has(e.a) && keep.has(e.b)) g._insertEdge(cloneJson(e));
    }
    return g;
  }

  /** Weakly connected components (edge direction ignored), largest first. */
  connectedComponents(opts: { edgeKind?: RelationKind } = {}): string[][] {
    const seen = new Set<string>();
    const comps: string[][] = [];
    for (const start of this._nodes.keys()) {
      if (seen.has(start)) continue;
      const comp: string[] = [];
      const stack = [start];
      seen.add(start);
      while (stack.length) {
        const cur = stack.pop()!;
        comp.push(cur);
        for (const eid of this._incident(cur)) {
          const e = this._edges.get(eid)!;
          if (opts.edgeKind !== undefined && e.kind !== opts.edgeKind) continue;
          const o = e.a === cur ? e.b : e.a;
          if (!seen.has(o)) {
            seen.add(o);
            stack.push(o);
          }
        }
      }
      comps.push(comp);
    }
    return comps.sort((x, y) => y.length - x.length);
  }

  /**
   * Directed cycles over edges of `edgeKind` (undirected edges ignored).
   * Returns one representative cycle (node ids in order, first node not
   * repeated) per strongly connected component that contains a cycle. Never throws.
   */
  findCycles(edgeKind: RelationKind = "supports"): string[][] {
    const succ = (n: string): string[] => {
      const out: string[] = [];
      for (const eid of this._out.get(n) ?? []) {
        const e = this._edges.get(eid)!;
        if (e.directed && e.kind === edgeKind && e.a === n) out.push(e.b);
      }
      return out;
    };
    // Iterative Tarjan SCC.
    let index = 0;
    const idx = new Map<string, number>();
    const low = new Map<string, number>();
    const onStack = new Set<string>();
    const stack: string[] = [];
    const sccs: string[][] = [];
    for (const root of this._nodes.keys()) {
      if (idx.has(root)) continue;
      const work: { n: string; it: string[]; i: number }[] = [];
      const push = (n: string) => {
        idx.set(n, index);
        low.set(n, index);
        index++;
        stack.push(n);
        onStack.add(n);
        work.push({ n, it: succ(n), i: 0 });
      };
      push(root);
      while (work.length) {
        const frame = work[work.length - 1]!;
        if (frame.i < frame.it.length) {
          const w = frame.it[frame.i++]!;
          if (!idx.has(w)) push(w);
          else if (onStack.has(w)) low.set(frame.n, Math.min(low.get(frame.n)!, idx.get(w)!));
          continue;
        }
        work.pop();
        const parent = work[work.length - 1];
        if (parent) low.set(parent.n, Math.min(low.get(parent.n)!, low.get(frame.n)!));
        if (low.get(frame.n) === idx.get(frame.n)) {
          const comp: string[] = [];
          let w: string;
          do {
            w = stack.pop()!;
            onStack.delete(w);
            comp.push(w);
          } while (w !== frame.n);
          if (comp.length > 1) sccs.push(comp);
        }
      }
    }
    // Representative cycle per SCC: BFS from first node back to itself within the SCC.
    const cycles: string[][] = [];
    for (const comp of sccs) {
      const inComp = new Set(comp);
      const start = [...comp].sort()[0]!;
      const prev = new Map<string, string>();
      const queue = [start];
      let found: string | undefined;
      for (let h = 0; h < queue.length && found === undefined; h++) {
        const cur = queue[h]!;
        for (const nx of succ(cur)) {
          if (!inComp.has(nx)) continue;
          if (nx === start) {
            found = cur;
            break;
          }
          if (!prev.has(nx)) {
            prev.set(nx, cur);
            queue.push(nx);
          }
        }
      }
      if (found === undefined) {
        cycles.push(comp.reverse());
        continue;
      }
      const path: string[] = [];
      for (let c: string | undefined = found; c !== undefined && c !== start; c = prev.get(c)) path.push(c);
      path.push(start);
      cycles.push(path.reverse());
    }
    return cycles;
  }

  stats(): GraphStats {
    const nodesByKind: Record<string, number> = {};
    for (const [k, s] of this._byKind) nodesByKind[k] = s.size;
    const edgesByKind: Record<string, number> = {};
    const edgesByRule: Record<string, number> = {};
    let explicitEdges = 0;
    for (const e of this._edges.values()) {
      edgesByKind[e.kind] = (edgesByKind[e.kind] ?? 0) + 1;
      const rules = new Set(e.evidence.map((ev) => ev.rule));
      for (const r of rules) edgesByRule[r] = (edgesByRule[r] ?? 0) + 1;
      if (e.evidence.some((ev) => ev.source === "explicit")) explicitEdges++;
    }
    return {
      nodes: this._nodes.size,
      edges: this._edges.size,
      levels: this._levels.size,
      nodesByKind,
      edgesByKind,
      edgesByRule,
      explicitEdges,
      inferredOnlyEdges: this._edges.size - explicitEdges,
    };
  }

  // ---------------------------------------------------------------- serialisation

  serialize(): SerializedElementGraph {
    return cloneJson({
      format: ELEMENT_GRAPH_FORMAT,
      version: ELEMENT_GRAPH_FORMAT_VERSION,
      meta: this.meta,
      levels: [...this._levels.values()],
      nodes: [...this._nodes.values()],
      edges: [...this._edges.values()],
    });
  }

  static deserialize(data: SerializedElementGraph | string): ElementGraph {
    const d = (typeof data === "string" ? JSON.parse(data) : data) as SerializedElementGraph;
    if (!d || d.format !== ELEMENT_GRAPH_FORMAT) throw new Error("deserialize: not an unloaded.element-graph document");
    if (d.version !== ELEMENT_GRAPH_FORMAT_VERSION) throw new Error(`deserialize: unsupported version ${String(d.version)}`);
    const g = new ElementGraph({ meta: d.meta ?? null, levels: d.levels ?? [] });
    for (const n of d.nodes ?? []) {
      if (g._nodes.has(n.id)) throw new Error(`deserialize: duplicate node id "${n.id}"`);
      g._loadNode(makeNode(n));
    }
    for (const e of d.edges ?? []) {
      if (!g._nodes.has(e.a) || !g._nodes.has(e.b)) throw new Error(`deserialize: edge "${e.id}" has unknown endpoint`);
      if (g._edges.has(e.id)) throw new Error(`deserialize: duplicate edge id "${e.id}"`);
      g._insertEdge({ id: e.id, kind: e.kind, a: e.a, b: e.b, directed: e.directed, evidence: cloneJson(e.evidence) });
    }
    return g;
  }

  /** Insert a node without emitting (used by deserialize / subgraph on fresh graphs). */
  private _loadNode(node: ElementNode): void {
    this._nodes.set(node.id, node);
    this._indexKind(node.id, node.kind);
    this._out.set(node.id, new Set());
    this._in.set(node.id, new Set());
  }
}

function mark(m: Map<string, ChangeState>, id: string, s: ChangeState): void {
  const prev = m.get(id);
  if (s === "added") m.set(id, prev === "removed" ? "updated" : "added");
  else if (s === "updated") m.set(id, prev === "added" ? "added" : "updated");
  else if (prev === "added") m.delete(id);
  else m.set(id, "removed");
}
