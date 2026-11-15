# @unloaded/element-graph

Pure TypeScript structural element graph. It has no runtime dependencies, works with any framework and has no side effects.
Elements (beams, columns, slabs, footings, ...) and **connections** are both nodes. Edges are physical
connectivity (`connects`) and the load path (`supports`).

```ts
import { buildGraph } from "@unloaded/element-graph";

const { graph, warnings } = buildGraph(modelInput);       // ModelInput from any parser
graph.loadPathDown("S1");   // Map { S1 => 0, B1 => 1, K1 => 2, C1 => 2, F1 => 3, ... }
graph.connectionsOf("B1");  // ["K1", "K2"]
```

## Data model

- **Parser contract**: `ModelInput` (`src/model/input.ts`, also exported as `@unloaded/element-graph/input`).
- **`ElementNode`**: everything from `ElementInput` (id, kind, mark, name, profile, material, levelId,
  params, geometry, source), plus `tags` (free annotations) and `links: {target, kind, data?}[]`.
  `links` is the hook for mapping to the calc graph later. Ids are the stable ids from the input. Kinds and params are open sets.
- **`GraphEdge`**: `{ id, kind, a, b, directed, evidence[] }`.

| kind       | directed | meaning                                                                           | id                 |
|------------|----------|-----------------------------------------------------------------------------------|--------------------|
| `connects` | no       | physical contact / connectivity. Endpoints are stored sorted (`a < b`).          | `connects:A\|B`    |
| `supports` | yes      | **`a` is supported by `b`**: load flows a -> b (slab -> beam -> connection -> column -> footing) | `supports:A->B` |
| `part_of`  | yes      | `a` is part of assembly `b` (e.g. bolt -> connection)                            | `part_of:A->B`     |

Other kinds are directed unless created with `directed: false`. Edge ids are deterministic.
Adding an edge that already exists merges its evidence instead of creating a duplicate.
Evidence is deduplicated, and `explicit` evidence (stated by the source file) always comes before
`inferred` evidence. Inference never adds a `supports` edge that reverses an existing one.
Instead it skips the edge and reports a warning.

## ElementGraph API

Mutations (each one is a single committed change unless it runs inside `batch`):

```ts
addNode(input: NodeInput): ElementNode            // throws on duplicate id
updateNode(id, patch: NodePatch): ElementNode     // replaces the stored object; id is immutable
removeNode(id): boolean                           // also removes incident edges
addEdge({ kind, a, b, directed?, evidence? }): GraphEdge  // throws on unknown endpoint / self-loop; merges on same id
removeEdge(id): boolean
setLevel(level) / removeLevel(id)
batch(fn): T                                      // nested batches merge; one change event at the end
```

Queries:

```ts
getNode(id) / hasNode(id) / getEdge(id) / hasEdge(id) / findEdge(kind, a, b)
nodes() / edges() / nodesByKind(kind) / kinds() / levels() / getLevel(id)
edgesOf(id, { kind?, direction?: "out" | "in" | "both" })
edgesBetween(a, b)
neighbours(id, { edgeKind?, nodeKind?, direction? })   // undirected edges match every direction
supportsOf(id)       // what id bears on
supportedBy(id)      // what bears on id
connectionsOf(memberId) / membersOf(connectionId) / partsOf(id)
loadPathDown(id) / loadPathUp(id): Map<id, depth>
subgraph(ids): ElementGraph
connectedComponents({ edgeKind? }): string[][]          // largest first, direction ignored
findCycles(edgeKind = "supports"): string[][]           // one cycle per cyclic SCC; never throws
stats(): { nodes, edges, levels, nodesByKind, edgesByKind, edgesByRule, explicitEdges, inferredOnlyEdges }
serialize(): SerializedElementGraph / static deserialize(data | json)
```

`loadPathDown` and `loadPathUp` run a BFS over `supports` edges. Connection nodes are included but
act as pass-throughs: the step into a connection counts as one, and the step out of it to a member
counts as zero. In slab -> beam -> K -> column, the connection K and the column therefore share a depth.

Serialization produces plain JSON:
`{ format: "unloaded.element-graph", version: 1, meta, levels, nodes, edges }`. The round trip is
lossless (see `serializeGraph`, `deserializeGraph`, `graphToJSON`).

## React integration contract

The graph is an external store, and the React package depends only on the members below.

- `subscribe(listener): () => void`. The listener receives a `GraphChange`:
  `{ version, nodesAdded, nodesUpdated, nodesRemoved, edgesAdded, edgesUpdated, edgesRemoved, levelsChanged }` (all ids).
- `version` increases monotonically, by exactly one per committed mutation or `batch`. A no-op does not
  increase it.
- `getSnapshot()` returns `version`, a number, so it stays stable between changes.
  `subscribe` and `getSnapshot` are pre-bound arrow properties.
- Stored node and edge objects are never mutated in place. An update swaps in a new object, so
  identity comparison works for memoization.

```ts
const version = useSyncExternalStore(graph.subscribe, graph.getSnapshot);
const beams = useMemo(() => graph.nodesByKind("beam"), [graph, version]);
```

A listener that throws does not prevent the other listeners from running. The first error is rethrown
after all listeners are called. `batch` is not transactional: if `fn` throws, the mutations it already
applied are kept and emitted.

## buildGraph and inference

```ts
buildGraph(input: ModelInput, opts?: {
  tolerances?: Partial<Tolerances>;
  infer?: boolean | Partial<Record<RuleName, boolean>>;
}): { graph: ElementGraph; warnings: string[] }

inferConnectivity(graph, opts?): { warnings, contactPairs, edgesByRule }
```

1. Adds levels and nodes, then the explicit relations. A relation with an unknown endpoint or a
   duplicate element produces a warning and is skipped.
2. Runs `inferConnectivity` unless `infer: false`. It is format-agnostic, uses only
   `GeometrySummary` (bbox, axis, section), and emits everything in one batch. A uniform spatial hash
   finds touching bbox pairs (`gap <= contact`) in ~O(n). Very large elements go to an overflow list.
3. Runs `findCycles("supports")` and reports any cycles as warnings.

Every inferred edge has evidence `{ rule, source: "inferred", detail: { gap_m } }`. The rules run in
this order (`RuleName` -> evidence `rule`):

| RuleName            | evidence rule                    | emits |
|---------------------|----------------------------------|-------|
| `connectionContact` | connection contact               | `connects` between the connection and each touching member. For 2 or more ranked members, the members are ordered by rank: footing/pile < column/wall < beam < slab < brace. Between two beams, the one whose **end** is at the connection is the supported one. Ties go to the lower element, and level ties stay ambiguous with no `supports` edge. Each supported member gets `supports` member -> connection, and the connection gets `supports` connection -> supporting member. Every member pair touching the connection is recorded as *joined via connection*. |
| `slabBearing`       | slab bears on support top        | Slab underside is within `contact` of a beam or wall top, and the plan overlap is at least `minPlanOverlap`. Emits connects and slab supports-> beam/wall. |
| `columnBase`        | column bottom bears on support   | Column (or wall) bottom is on a column > beam > wall > footing/pile. Columns take the best candidate only; walls take every top-priority candidate. |
| `footingOnPile`     | footing bears on pile            | A footing (pile cap) touches a pile whose head is at the footing underside or embedded in it (within `contact`), the pile extends below the footing, and the head lies inside the footing in plan. Emits connects and footing supports-> pile, for every pile of a group. |
| `beamOnColumn`      | beam end bears on column/wall    | A beam end lies against a column or wall within `endZone` and inside its height, or the beam sits on its top. |
| `beamOnGirder`      | beam frames into girder          | A beam end touches another beam whose ends are not there. Parallel beams and beams that both end at the same point are skipped. Crossing beams stacked on each other: the upper one is supported by the lower one. |
| `braceEnds`         | brace end                        | Connects to touching columns, beams, walls, footings and connections. The lower end supports-> the element it lands on (priority connection > column > beam > wall > footing). |
| `bboxContact`       | bbox contact                     | Fallback: any other touching pair with no edge yet gets `connects` only. |

The direct rules (slabBearing, columnBase, footingOnPile, beamOnColumn, beamOnGirder, braceEnds, bboxContact) skip
any pair that is *joined via connection*. A beam that is shear-tabbed to a column therefore gives
beam -> K -> column, never a direct beam -> column.

Not inferred: slab on column top (flat plate). That pair gets `connects` from the bbox fallback only.

### Tolerances (`src/tolerances.ts`, `DEFAULT_TOLERANCES`)

| key                  | default | meaning |
|----------------------|---------|---------|
| `contact`            | 0.025 m | max bbox gap that counts as touching / bearing |
| `endZone`            | 0.3 m   | max distance from an axis end for that end to count as "at" another element |
| `minPlanOverlap`     | 0.01 m² | min plan overlap for slab bearing |
| `parallelAngleDeg`   | 5       | axes closer than this angle are parallel |
| `gridCellSize`       | 0       | spatial hash cell size (0 = auto from the median element size, clamped 0.5-20 m) |
| `maxCellsPerElement` | 4096    | elements spanning more cells than this are brute-forced instead of hashed |

## Scripts

```
npx tsc -p packages/element-graph/tsconfig.json
npx vitest run --root packages/element-graph
```
