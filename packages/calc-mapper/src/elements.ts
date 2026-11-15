/**
 * Serialized element graph -> the element rows, load path and connectivity the mapper uses.
 * The graph (packages/element-graph, `ElementGraph.serialize()`) is the one source of truth for
 * elements and topology; nothing here re-derives either.
 *
 *   global_id  node.id                (IFC GlobalId - stable across revisions)
 *   express_id node.source.nativeId
 *   ifc_type   node.source.nativeType (falls back to the node kind)
 *   cat        node.kind -> Beam / Column / Slab / Wall / Footing / Pile / Brace / Connection / Other
 *              (connections are elements; fasteners count as Connection)
 *   mark, name node.mark, node.name
 *   type_name  params["Attr.ObjectType"]
 *   profile    node.profile           (the parser's normalised section designation)
 *   storey     name of node.levelId in graph.levels ("" when the file states no storey)
 *   params     node.params
 *   geom       bbox min / max + axis start / end (p1 / p2), world metres (ModelPointM)
 * Load path = `supports` edges (a is supported by b: load flows a -> b; `gap` in metres); `connects`
 * edges are physical connectivity. A graph whose meta declares units other than metres is refused.
 */
import { modelPointM } from "./frames.ts";
import { sha1Json } from "./hash.ts";
import { canonicalUnit, q as quantity } from "./units.ts";
import type {
  ConnectivityEdge, ElementCategory, ElementRow, LoadPathEdge, SerializedElementGraph,
} from "./types.ts";

export const GRAPH_FORMAT = "unloaded.element-graph";
export const GRAPH_VERSION = 1;

const CAT: Record<string, ElementCategory> = {
  beam: "Beam", column: "Column", slab: "Slab", wall: "Wall", footing: "Footing", pile: "Pile", brace: "Brace",
  connection: "Connection", fastener: "Connection",
};

export class GraphFormatError extends Error {
  name = "GraphFormatError";
}

/** Validate (and parse, when given text) a serialized element graph. Throws GraphFormatError with the reason. */
export function parseGraph(input: string | unknown): SerializedElementGraph {
  let g: unknown = input;
  if (typeof input === "string") {
    try {
      g = JSON.parse(input);
    } catch (e) {
      throw new GraphFormatError(`graph is not valid JSON: ${(e as Error).message}`);
    }
  }
  if (!g || typeof g !== "object" || Array.isArray(g)) throw new GraphFormatError("graph must be a JSON object");
  const o = g as Record<string, unknown>;
  if (o.format !== GRAPH_FORMAT) {
    throw new GraphFormatError(`graph format must be ${JSON.stringify(GRAPH_FORMAT)} (got ${JSON.stringify(o.format ?? null)}) - send ElementGraph.serialize()`);
  }
  if (o.version !== GRAPH_VERSION) {
    throw new GraphFormatError(`graph version ${JSON.stringify(o.version ?? null)} is not supported (this engine reads version ${GRAPH_VERSION})`);
  }
  for (const k of ["levels", "nodes", "edges"]) {
    if (!Array.isArray(o[k])) throw new GraphFormatError(`graph.${k} must be a list`);
  }
  const units = (o.meta as { units?: unknown } | null | undefined)?.units;
  if (units !== undefined) {
    let u: string;
    try {
      u = canonicalUnit(String(units));
    } catch {
      throw new GraphFormatError(`graph.meta.units ${JSON.stringify(units)} is not a known unit`);
    }
    if (u !== "m") throw new GraphFormatError(`graph.meta.units must be "m" (got ${JSON.stringify(units)}): geometry is read as world metres`);
  }
  const ids = new Set<string>();
  (o.nodes as unknown[]).forEach((n, i) => {
    const r = n as { id?: unknown; kind?: unknown };
    if (!r || typeof r.id !== "string" || !r.id || typeof r.kind !== "string") {
      throw new GraphFormatError(`graph.nodes[${i}] needs a string id and kind`);
    }
    if (ids.has(r.id)) throw new GraphFormatError(`graph.nodes[${i}]: duplicate node id ${JSON.stringify(r.id)}`);
    ids.add(r.id);
  });
  (o.edges as unknown[]).forEach((e, i) => {
    const r = e as { kind?: unknown; a?: unknown; b?: unknown; id?: unknown };
    if (!r || typeof r.kind !== "string") throw new GraphFormatError(`graph.edges[${i}] needs a string kind`);
    if (!ids.has(r.a as string) || !ids.has(r.b as string)) {
      throw new GraphFormatError(`graph.edges[${i}] (${JSON.stringify(r.id ?? null)}) references a node that is not in graph.nodes`);
    }
  });
  return g as SerializedElementGraph;
}

type Edge = SerializedElementGraph["edges"][number];
const firstRule = (e: Edge): string => e.evidence?.[0]?.rule ?? "";
const gapOf = (e: Edge): number | null => {
  for (const ev of e.evidence ?? []) {
    const g = ev.detail?.gap_m;
    if (typeof g === "number") return g;
  }
  return null;
};
const byId = (p: string, q: string): number => (p < q ? -1 : p > q ? 1 : 0);

/** The fields a revision diff compares, hashed (see diff.ts). */
export function elementContentHash(e: Omit<ElementRow, "content_hash">): string {
  const g = e.geom;
  return sha1Json({
    ifc_type: e.ifc_type, mark: e.mark, name: e.name, type_name: e.type_name, profile: e.profile, storey: e.storey,
    params: e.params, bbox: g ? [g.min.map((v) => Math.round(v * 1000) / 1000), g.max.map((v) => Math.round(v * 1000) / 1000)] : null,
  });
}

/** Element rows of a graph, sorted by global_id (the order the reference engine read them in). */
export function graphElements(g: SerializedElementGraph): ElementRow[] {
  const levels = new Map(g.levels.map((l) => [l.id, l.name ?? ""]));
  return g.nodes
    .map((n) => {
      const params = n.params ?? {};
      const bb = n.geometry?.bbox;
      const ax = n.geometry?.axis;
      const geom = bb
        ? { min: modelPointM(bb.min), max: modelPointM(bb.max), ...(ax ? { p1: modelPointM(ax.start), p2: modelPointM(ax.end) } : {}) }
        : null;
      const row: Omit<ElementRow, "content_hash"> = {
        global_id: n.id, express_id: n.source?.nativeId ?? null, ifc_type: n.source?.nativeType || n.kind,
        cat: CAT[n.kind] ?? "Other", mark: n.mark || "", name: n.name || "",
        type_name: String(params["Attr.ObjectType"] ?? ""), profile: n.profile || "",
        storey: (n.levelId && levels.get(n.levelId)) || "", params, geom,
      };
      return { ...row, content_hash: elementContentHash(row) };
    })
    .sort((p, q) => byId(p.global_id, q.global_id));
}

/** The graph's `supports` edges, src -> dst = a -> b, sorted by (src, dst). */
export function loadPath(g: SerializedElementGraph): LoadPathEdge[] {
  return g.edges
    .filter((e) => e.kind === "supports")
    .map((e): LoadPathEdge => {
      const gap = gapOf(e);
      return { src: e.a, dst: e.b, kind: "supports", rule: firstRule(e), gap_m: gap, gap: gap === null ? null : quantity(gap, "m") };
    })
    .sort((p, q) => byId(p.src, q.src) || byId(p.dst, q.dst));
}

/** The graph's `connects` edges (a < b as the graph stores them), sorted by (a, b). */
export function connectivity(g: SerializedElementGraph): ConnectivityEdge[] {
  return g.edges
    .filter((e) => e.kind === "connects")
    .map((e) => ({ a: e.a, b: e.b, rule: firstRule(e), explicit: (e.evidence ?? []).some((v) => v.source === "explicit") }))
    .sort((p, q) => byId(p.a, q.a) || byId(p.b, q.b));
}
