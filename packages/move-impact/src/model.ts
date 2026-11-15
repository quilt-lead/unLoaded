/**
 * The analytical model the screen works on, read from a serialized element graph ONLY:
 * node kind, geometry (bbox / axis, metres, Z up), level, and `supports` edges through connection
 * nodes. It never reads `params` (an uploaded model's property sets are not a contract) - a test
 * clears every param and asserts identical output.
 *
 * - columns: plan position from the axis start (bbox centre without an axis)
 * - members (beams, braces): analytical plan endpoints. The physical axis stops at the support's
 *   face, so each end is projected onto what supports it: the column centreline, or the
 *   intersection with the supporting beam's line. That gives the design span from the model.
 * - carried: support -> [(member, end)] through the graph's `supports` edges (member -> connection ->
 *   support, or member -> support); end = the member's axis end nearest the support.
 * - foundations: footings (plan box) and grade beams (beams touching a footing, below the framing).
 */
import type { ElementNode, GraphEdge, SerializedElementGraph } from "@unloaded/element-graph";

export type End = "i" | "j";
export type P2 = [number, number];

export interface Member {
  id: string;
  kind: string; // "beam" | "brace"
  levelId: string | null;
  roof: boolean;
  /** Physical axis (3D). i = axis start, j = axis end. */
  a3: [number, number, number];
  b3: [number, number, number];
  /** Analytical plan endpoints (projected onto supports). */
  p1: P2;
  p2: P2;
  /** end -> support element */
  sup: Partial<Record<End, string>>;
  /** end -> connection node between the member and that support */
  via: Partial<Record<End, string>>;
  depth: number | null;
  width: number | null;
  profile: string | null;
}

export interface Footing {
  id: string;
  cx: number;
  cy: number;
  bx: number;
  by: number;
}

export interface GradeBeam {
  id: string;
  p1: P2;
  p2: P2;
  width: number;
}

export interface Model {
  nodes: Map<string, ElementNode>;
  columns: Map<string, P2>;
  members: Map<string, Member>;
  carried: Map<string, [string, End][]>;
  footings: Map<string, Footing>;
  gradeBeams: Map<string, GradeBeam>;
  /** element -> elements directly below it on the load path (supports a -> b), connections included */
  down: Map<string, string[]>;
  up: Map<string, string[]>;
  /** connection -> members joined by it (both directions of supports) */
  connMembers: Map<string, Set<string>>;
  assumptions: string[];
}

const END_TOL = 1.0; // m: a member end within this plan distance of a support is "at" it

export function dist(a: P2, b: P2): number {
  return Math.hypot(a[0] - b[0], a[1] - b[1]);
}

/** Point where the line p + t d meets the infinite line through a, b (null when parallel). */
export function lineIntersect(p: P2, d: P2, a: P2, b: P2): P2 | null {
  const ex = b[0] - a[0];
  const ey = b[1] - a[1];
  const den = d[0] * ey - d[1] * ex;
  if (Math.abs(den) < 1e-9) return null;
  const t = ((a[0] - p[0]) * ey - (a[1] - p[1]) * ex) / den;
  return [p[0] + t * d[0], p[1] + t * d[1]];
}

export function segDist(p: P2, a: P2, b: P2): number {
  const ex = b[0] - a[0];
  const ey = b[1] - a[1];
  const l2 = ex * ex + ey * ey;
  const t = l2 > 0 ? Math.max(0, Math.min(1, ((p[0] - a[0]) * ex + (p[1] - a[1]) * ey) / l2)) : 0;
  return dist(p, [a[0] + t * ex, a[1] + t * ey]);
}

type P3 = [number, number, number];

function segDist3(p: P3, a: P3, b: P3): number {
  const e = [b[0] - a[0], b[1] - a[1], b[2] - a[2]];
  const l2 = e[0]! * e[0]! + e[1]! * e[1]! + e[2]! * e[2]!;
  const t = l2 > 0 ? Math.max(0, Math.min(1, ((p[0] - a[0]) * e[0]! + (p[1] - a[1]) * e[1]! + (p[2] - a[2]) * e[2]!) / l2)) : 0;
  return Math.hypot(p[0] - a[0] - t * e[0]!, p[1] - a[1] - t * e[1]!, p[2] - a[2] - t * e[2]!);
}

function bboxGap(a: ElementNode, b: ElementNode): number {
  const A = a.geometry?.bbox;
  const B = b.geometry?.bbox;
  if (!A || !B) return Infinity;
  let g = 0;
  for (let k = 0; k < 3; k++) {
    const d = Math.max(A.min[k]! - B.max[k]!, B.min[k]! - A.max[k]!, 0);
    g = Math.max(g, d);
  }
  return g;
}

export function buildModel(graph: SerializedElementGraph): Model {
  const nodes = new Map(graph.nodes.map((n) => [n.id, n]));
  const assumptions: string[] = [];
  const levelElev = new Map(graph.levels.map((l) => [l.id, l.elevation]));
  const down = new Map<string, string[]>();
  const up = new Map<string, string[]>();
  const supEdges: GraphEdge[] = graph.edges.filter((e) => e.kind === "supports");
  const isSlab = (id: string) => nodes.get(id)?.kind === "slab";
  for (const e of supEdges) {
    if (isSlab(e.a) || isSlab(e.b)) continue; // slabs are a load source, not a member on the path
    if (!down.has(e.a)) down.set(e.a, []);
    down.get(e.a)!.push(e.b);
    if (!up.has(e.b)) up.set(e.b, []);
    up.get(e.b)!.push(e.a);
  }
  const connMembers = new Map<string, Set<string>>();
  for (const e of supEdges) {
    for (const [c, m] of [
      [e.a, e.b],
      [e.b, e.a],
    ] as const) {
      if (nodes.get(c)?.kind === "connection" && !isSlab(m)) {
        if (!connMembers.has(c)) connMembers.set(c, new Set());
        connMembers.get(c)!.add(m);
      }
    }
  }

  const columns = new Map<string, P2>();
  for (const n of graph.nodes) {
    if (n.kind !== "column" || !n.geometry) continue;
    const ax = n.geometry.axis;
    if (ax) columns.set(n.id, [ax.start[0], ax.start[1]]);
    else {
      const b = n.geometry.bbox;
      columns.set(n.id, [(b.min[0] + b.max[0]) / 2, (b.min[1] + b.max[1]) / 2]);
    }
  }

  const footings = new Map<string, Footing>();
  for (const n of graph.nodes) {
    if (n.kind !== "footing" || !n.geometry) continue;
    const b = n.geometry.bbox;
    footings.set(n.id, {
      id: n.id,
      cx: (b.min[0] + b.max[0]) / 2,
      cy: (b.min[1] + b.max[1]) / 2,
      bx: b.max[0] - b.min[0],
      by: b.max[1] - b.min[1],
    });
  }

  // grade beams: beams that touch a footing (embedded into it) and carry / sit on no framing
  const gradeBeams = new Map<string, GradeBeam>();
  const footingNodes = graph.nodes.filter((n) => n.kind === "footing");
  for (const n of graph.nodes) {
    if (n.kind !== "beam" || !n.geometry?.axis) continue;
    if (down.has(n.id) || up.has(n.id)) continue;
    if (!footingNodes.some((f) => bboxGap(n, f) <= 0.05)) continue;
    const ax = n.geometry.axis;
    const b = n.geometry.bbox;
    const horizX = Math.abs(ax.end[0] - ax.start[0]) >= Math.abs(ax.end[1] - ax.start[1]);
    gradeBeams.set(n.id, {
      id: n.id,
      p1: [ax.start[0], ax.start[1]],
      p2: [ax.end[0], ax.end[1]],
      width: n.geometry.section?.width ?? (horizX ? b.max[1] - b.min[1] : b.max[0] - b.min[0]),
    });
  }

  const topElev = Math.max(...graph.levels.map((l) => l.elevation));
  const members = new Map<string, Member>();
  for (const n of graph.nodes) {
    if ((n.kind !== "beam" && n.kind !== "brace") || !n.geometry?.axis || gradeBeams.has(n.id)) continue;
    const ax = n.geometry.axis;
    const lv = n.levelId ?? null;
    members.set(n.id, {
      id: n.id,
      kind: n.kind,
      levelId: lv,
      roof: lv != null && levelElev.get(lv) === topElev,
      a3: [...ax.start] as [number, number, number],
      b3: [...ax.end] as [number, number, number],
      p1: [ax.start[0], ax.start[1]],
      p2: [ax.end[0], ax.end[1]],
      sup: {},
      via: {},
      depth: n.geometry.section?.depth ?? null,
      width: n.geometry.section?.width ?? null,
      profile: n.profile ?? null,
    });
  }

  // supports of each member, through connection nodes; end = nearest axis end (plan)
  const supCand = (m: Member): { s: string; via: string | null }[] => {
    const out: { s: string; via: string | null }[] = [];
    for (const x of down.get(m.id) ?? []) {
      const xn = nodes.get(x);
      if (!xn) continue;
      if (xn.kind === "connection") {
        for (const s of down.get(x) ?? []) if (s !== m.id) out.push({ s, via: x });
      } else out.push({ s: x, via: null });
    }
    return out;
  };
  // 3D distance from a member end to the support's axis: a brace's lower end lies on the girder's
  // line in plan but not in elevation
  const axisOf = (s: string): [P3, P3] | null => {
    const ax = nodes.get(s)?.geometry?.axis;
    return ax ? [ax.start as P3, ax.end as P3] : null;
  };
  const supDist = (p: P3, s: string): number => {
    const ax = axisOf(s);
    return ax ? segDist3(p, ax[0], ax[1]) : Infinity;
  };
  for (const m of members.values()) {
    const ends: Record<End, P3> = { i: m.a3, j: m.b3 };
    const best: Partial<Record<End, { s: string; via: string | null; d: number }>> = {};
    for (const { s, via } of supCand(m)) {
      if (!columns.has(s) && !members.has(s)) continue;
      const di = supDist(ends.i, s);
      const dj = supDist(ends.j, s);
      const end: End = di <= dj ? "i" : "j";
      const d = Math.min(di, dj);
      if (d > END_TOL) continue;
      const cur = best[end];
      // prefer the connection that belongs to this member (fewest members joined) on a tie
      if (!cur || d < cur.d - 1e-6) best[end] = { s, via, d };
    }
    for (const end of ["i", "j"] as End[]) {
      const b = best[end];
      if (!b) continue;
      m.sup[end] = b.s;
      if (b.via) m.via[end] = b.via;
    }
  }
  // own connection per end: the connection node touching this member closest to that end
  for (const m of members.values()) {
    for (const end of ["i", "j"] as End[]) {
      const p3 = end === "i" ? m.a3 : m.b3;
      let bestC: string | null = null;
      let bd = Infinity;
      for (const x of down.get(m.id) ?? []) {
        const xn = nodes.get(x);
        if (xn?.kind !== "connection" || !xn.geometry) continue;
        const b = xn.geometry.bbox;
        const c: P2 = [(b.min[0] + b.max[0]) / 2, (b.min[1] + b.max[1]) / 2];
        const d = dist(c, [p3[0], p3[1]]);
        if (d < bd) {
          bd = d;
          bestC = x;
        }
      }
      if (bestC && bd < END_TOL) m.via[end] = bestC;
    }
  }
  // analytical endpoints: project onto the support
  for (const m of members.values()) {
    const d: P2 = [m.b3[0] - m.a3[0], m.b3[1] - m.a3[1]];
    for (const end of ["i", "j"] as End[]) {
      const s = m.sup[end];
      if (!s) continue;
      const c = columns.get(s);
      let p: P2 | null = null;
      if (c) p = [c[0], c[1]];
      else {
        const sm = members.get(s);
        if (sm) p = lineIntersect([m.a3[0], m.a3[1]], d, [sm.a3[0], sm.a3[1]], [sm.b3[0], sm.b3[1]]);
      }
      if (!p) continue;
      if (end === "i") m.p1 = p;
      else m.p2 = p;
    }
  }
  // supporting beams' own analytical lines are needed for the second pass (a beam framing into a
  // girder that itself was projected): recompute intersections against analytical lines
  for (const m of members.values()) {
    const d: P2 = [m.b3[0] - m.a3[0], m.b3[1] - m.a3[1]];
    for (const end of ["i", "j"] as End[]) {
      const sm = m.sup[end] ? members.get(m.sup[end]!) : undefined;
      if (!sm) continue;
      const p = lineIntersect([m.a3[0], m.a3[1]], d, sm.p1, sm.p2);
      if (!p) continue;
      if (end === "i") m.p1 = p;
      else m.p2 = p;
    }
  }

  const carried = new Map<string, [string, End][]>();
  for (const m of members.values()) {
    for (const end of ["i", "j"] as End[]) {
      const s = m.sup[end];
      if (!s) continue;
      if (!carried.has(s)) carried.set(s, []);
      carried.get(s)!.push([m.id, end]);
    }
  }
  const unsupported = [...members.values()].filter((m) => m.kind === "beam" && (!m.sup.i || !m.sup.j)).length;
  if (unsupported)
    assumptions.push(
      `${unsupported} beam(s) have a support resolved at only one end (or none) in the graph; their span is the physical axis at the unresolved end`,
    );
  return { nodes, columns, members, carried, footings, gradeBeams, down, up, connMembers, assumptions };
}

/**
 * How the column screen walks down a load path from a column: through connections (splice, base
 * plate) and foundations; never through a member (beam / brace: what bears on it is its own load
 * path); and a wall ends the walk - a column on a wall spreads its load along the wall, which the
 * screen does not model, so the change is never copied to every footing under the wall.
 */
function downStep(kind: string | undefined): "skip" | "stop" | "through" {
  if (kind === "beam" || kind === "brace") return "skip";
  if (kind === "wall") return "stop";
  return "through";
}

/** Elements below `id` on the load path (BFS over supports, connections included; a wall is listed, not passed). */
export function below(model: Model, id: string): string[] {
  const seen = new Set<string>([id]);
  const out: string[] = [];
  const q = [id];
  while (q.length) {
    const x = q.shift()!;
    for (const y of model.down.get(x) ?? []) {
      if (seen.has(y)) continue;
      // stop at another member: only the column's own foundation chain moves with it
      const step = downStep(model.nodes.get(y)?.kind);
      if (step === "skip") continue;
      seen.add(y);
      out.push(y);
      if (step === "through") q.push(y);
    }
  }
  return out;
}

/**
 * One step down a column's load path: the next column(s) below `id` (an upper storey's column bears
 * on the one below it; a column on its pier), the elements met before reaching one (splice or base
 * plate connection, footing) and the walls it ends on (`downStep`). Never passes through a beam or
 * brace, a wall, or past a column: what is below that column belongs to its own step. Following
 * `columns` repeatedly walks the whole stack.
 */
export function nextBelow(model: Model, id: string): { columns: string[]; between: string[]; walls: string[] } {
  const seen = new Set<string>([id]);
  const columns: string[] = [];
  const between: string[] = [];
  const walls: string[] = [];
  const q = [id];
  while (q.length) {
    const x = q.shift()!;
    for (const y of model.down.get(x) ?? []) {
      if (seen.has(y)) continue;
      seen.add(y);
      const k = model.nodes.get(y)?.kind;
      const step = downStep(k);
      if (step === "skip") continue;
      if (step === "stop") {
        walls.push(y);
        continue;
      }
      if (k === "column") {
        columns.push(y);
        continue;
      }
      between.push(y);
      q.push(y);
    }
  }
  return { columns, between, walls };
}

export function spanOf(m: { p1: P2; p2: P2 }): number {
  return dist(m.p1, m.p2);
}
