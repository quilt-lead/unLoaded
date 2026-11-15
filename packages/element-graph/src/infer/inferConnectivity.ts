/**
 * Format-agnostic connectivity inference. Uses only GeometrySummary
 * (bbox, axis, section) - never parser- or format-specific data.
 *
 * Every inferred edge carries evidence { rule, source: "inferred", detail: { gap_m } }.
 */
import type { BBox, Vec3 } from "../model/input.ts";
import type { ElementNode } from "../model/graph-types.ts";
import type { ElementGraph } from "../graph/ElementGraph.ts";
import { CONNECTION_KIND } from "../graph/ElementGraph.ts";
import { resolveTolerances, type Tolerances } from "../tolerances.ts";
import { axisAngleDeg, bboxCenter, memberAxis, planOverlapArea, planPointBoxDist, pointBoxDist } from "../geometry.ts";
import { findContactPairs } from "./spatial-index.ts";

export const RULE_NAMES = [
  "connectionContact",
  "slabBearing",
  "columnBase",
  "beamOnColumn",
  "beamOnGirder",
  "braceEnds",
  "bboxContact",
] as const;
export type RuleName = (typeof RULE_NAMES)[number];

/** Human-readable evidence rule strings written to edges. */
export const RULE_LABELS: Readonly<Record<RuleName, string>> = Object.freeze({
  connectionContact: "connection contact",
  slabBearing: "slab bears on support top",
  columnBase: "column bottom bears on support",
  beamOnColumn: "beam end bears on column/wall",
  beamOnGirder: "beam frames into girder",
  braceEnds: "brace end",
  bboxContact: "bbox contact",
});

export interface InferOptions {
  tolerances?: Partial<Tolerances>;
  /** false disables all rules; an object toggles individual rules (default: all on). */
  infer?: boolean | Partial<Record<RuleName, boolean>>;
}

export interface InferResult {
  warnings: string[];
  /** Number of contact pairs found by the spatial index. */
  contactPairs: number;
  /** Edges added or merged per rule. */
  edgesByRule: Record<RuleName, number>;
}

/** Load-path rank: lower ranks support higher ones. Unknown kinds are unranked. */
const RANK: Readonly<Record<string, number>> = { footing: 0, pile: 0, column: 1, wall: 1, beam: 2, slab: 3, brace: 4 };
const NON_MEMBER = new Set([CONNECTION_KIND, "fastener"]);
const COLUMN_BASE_PRIORITY: Readonly<Record<string, number>> = { column: 4, beam: 3, wall: 2, footing: 1, pile: 1 };
const BRACE_TARGET_PRIORITY: Readonly<Record<string, number>> = {
  [CONNECTION_KIND]: 5,
  column: 4,
  beam: 3,
  wall: 2,
  footing: 1,
  pile: 1,
};

export function resolveRules(infer: InferOptions["infer"]): Record<RuleName, boolean> {
  const out = {} as Record<RuleName, boolean>;
  for (const r of RULE_NAMES) {
    out[r] = infer === false ? false : infer === true || infer === undefined ? true : (infer[r] ?? true);
  }
  return out;
}

const pairKey = (a: string, b: string): string => (a < b ? `${a}\u0000${b}` : `${b}\u0000${a}`);
const round6 = (x: number): number => Math.round(x * 1e6) / 1e6;

/**
 * Infer connects / supports edges from geometry and add them to `graph`
 * (in a single batch -> one change event). Idempotent: re-running merges.
 */
export function inferConnectivity(graph: ElementGraph, opts: InferOptions = {}): InferResult {
  const tol = resolveTolerances(opts.tolerances);
  const rules = resolveRules(opts.infer);
  const warnings: string[] = [];
  const edgesByRule = Object.fromEntries(RULE_NAMES.map((r) => [r, 0])) as Record<RuleName, number>;
  const result: InferResult = { warnings, contactPairs: 0, edgesByRule };
  if (!RULE_NAMES.some((r) => rules[r])) return result;

  // ---- spatial contact pairs
  const items: ElementNode[] = [];
  let noGeom = 0;
  for (const n of graph.nodes()) {
    if (n.geometry?.bbox) items.push(n);
    else noGeom++;
  }
  if (noGeom > 0) warnings.push(`${noGeom} element(s) without geometry skipped by connectivity inference`);
  const boxes = items.map((n) => n.geometry!.bbox);
  const pairs = findContactPairs(boxes, tol.contact, tol.gridCellSize, tol.maxCellsPerElement);
  result.contactPairs = pairs.length;

  const touching = new Map<string, Map<string, number>>();
  for (const n of items) touching.set(n.id, new Map());
  for (const p of pairs) {
    const a = items[p.i]!.id;
    const b = items[p.j]!.id;
    touching.get(a)!.set(b, p.gap);
    touching.get(b)!.set(a, p.gap);
  }
  const byId = new Map(items.map((n) => [n.id, n]));
  const box = (id: string): BBox => byId.get(id)!.geometry!.bbox;
  const touchingOf = (id: string): [ElementNode, number][] =>
    [...(touching.get(id) ?? [])].map(([o, gap]) => [byId.get(o)!, gap]);
  const ofKind = (...kinds: string[]): ElementNode[] => kinds.flatMap((k) => graph.nodesByKind(k)).filter((n) => byId.has(n.id));

  /** Member pairs joined through a connection node: direct rules skip them. */
  const joined = new Set<string>();
  const isJoined = (a: string, b: string) => joined.has(pairKey(a, b));

  const evidence = (rule: RuleName, gap: number) => ({
    rule: RULE_LABELS[rule],
    source: "inferred" as const,
    detail: { gap_m: round6(gap) },
  });
  const connects = (a: string, b: string, rule: RuleName, gap: number) => {
    graph.addEdge({ kind: "connects", a, b, evidence: evidence(rule, gap) });
    edgesByRule[rule]++;
  };
  /** a is supported by b. Never overrides / contradicts an existing reverse supports edge. */
  const supports = (a: string, b: string, rule: RuleName, gap: number): boolean => {
    const reverse = graph.findEdge("supports", b, a);
    if (reverse) {
      const src = reverse.evidence.some((e) => e.source === "explicit") ? "explicit" : "inferred";
      warnings.push(`${RULE_LABELS[rule]}: skipped ${a} supported-by ${b}; conflicts with ${src} edge ${reverse.id}`);
      return false;
    }
    graph.addEdge({ kind: "supports", a, b, evidence: evidence(rule, gap) });
    edgesByRule[rule]++;
    return true;
  };
  const gapOf = (a: string, b: string): number => touching.get(a)?.get(b) ?? 0;

  graph.batch(() => {
    // ---- 1. connection contact (always computes `joined`, emits only if enabled)
    for (const conn of ofKind(CONNECTION_KIND)) {
      const members = touchingOf(conn.id).filter(([m]) => !NON_MEMBER.has(m.kind));
      if (rules.connectionContact) for (const [m, gap] of members) connects(m.id, conn.id, "connectionContact", gap);
      if (members.length < 2) continue;
      for (let i = 0; i < members.length; i++)
        for (let j = i + 1; j < members.length; j++) joined.add(pairKey(members[i]![0].id, members[j]![0].id));
      if (!rules.connectionContact) continue;

      const ranked = members.filter(([m]) => RANK[m.kind] !== undefined).map(([m]) => m);
      if (ranked.length < 2) continue;
      const cbox = conn.geometry!.bbox;
      const eff = (m: ElementNode): number => {
        let r = RANK[m.kind]! * 2;
        // Between beams: the one whose END is at the connection is supported.
        if (m.kind === "beam" && endNear(m, cbox, tol.endZone)) r += 1;
        return r;
      };
      const minR = Math.min(...ranked.map(eff));
      let lows = ranked.filter((m) => eff(m) === minR);
      if (lows.length > 1) {
        // Tie (e.g. column splice): the lowest element supports. Ambiguous if level.
        lows.sort((x, y) => bboxCenter(box(x.id))[2] - bboxCenter(box(y.id))[2]);
        const z0 = bboxCenter(box(lows[0]!.id))[2];
        const z1 = bboxCenter(box(lows[1]!.id))[2];
        if (z1 - z0 <= tol.contact) continue;
        lows = [lows[0]!];
      }
      const supporting = lows[0]!;
      let any = false;
      for (const m of ranked) {
        if (m === supporting) continue;
        any = supports(m.id, conn.id, "connectionContact", gapOf(m.id, conn.id)) || any;
      }
      if (any) supports(conn.id, supporting.id, "connectionContact", gapOf(conn.id, supporting.id));
    }

    // ---- 2. slab bears on beam / wall top
    if (rules.slabBearing) {
      for (const slab of ofKind("slab")) {
        const sb = box(slab.id);
        for (const [t, gap] of touchingOf(slab.id)) {
          if ((t.kind !== "beam" && t.kind !== "wall") || isJoined(slab.id, t.id)) continue;
          const tb = box(t.id);
          if (Math.abs(sb.min[2] - tb.max[2]) > tol.contact) continue;
          if (planOverlapArea(sb, tb) < tol.minPlanOverlap) continue;
          connects(slab.id, t.id, "slabBearing", gap);
          supports(slab.id, t.id, "slabBearing", gap);
        }
      }
    }

    // ---- 3. column / wall bottom bears on column > beam > wall > footing/pile
    if (rules.columnBase) {
      for (const v of ofKind("column", "wall")) {
        const vb = box(v.id);
        const axis = memberAxis(v);
        const bottomZ = vb.min[2];
        const p: Vec3 = axis ? [axis.start[0], axis.start[1], bottomZ] : [...bboxCenter(vb).slice(0, 2), bottomZ] as Vec3;
        const cands: { t: ElementNode; gap: number; pri: number }[] = [];
        for (const [t, gap] of touchingOf(v.id)) {
          const pri = COLUMN_BASE_PRIORITY[t.kind];
          if (pri === undefined || isJoined(v.id, t.id)) continue;
          const tb = box(t.id);
          if (Math.abs(tb.max[2] - bottomZ) > tol.contact || tb.max[2] >= vb.max[2]) continue;
          const inPlan = v.kind === "wall" ? planOverlapArea(vb, tb) > 0 : planPointBoxDist(p, tb) <= tol.contact;
          if (inPlan) cands.push({ t, gap, pri });
        }
        if (cands.length === 0) continue;
        const best = Math.max(...cands.map((c) => c.pri));
        let chosen = cands.filter((c) => c.pri === best).sort((x, y) => x.gap - y.gap);
        if (v.kind !== "wall") chosen = chosen.slice(0, 1);
        for (const c of chosen) {
          connects(v.id, c.t.id, "columnBase", c.gap);
          supports(v.id, c.t.id, "columnBase", c.gap);
        }
      }
    }

    // ---- 4. beam end bears directly on column / wall (not via a connection)
    if (rules.beamOnColumn) {
      for (const beam of ofKind("beam")) {
        const axis = memberAxis(beam);
        const bb = box(beam.id);
        for (const [t, gap] of touchingOf(beam.id)) {
          if ((t.kind !== "column" && t.kind !== "wall") || isJoined(beam.id, t.id)) continue;
          const tb = box(t.id);
          const endBears =
            !!axis &&
            [axis.start, axis.end].some(
              (pt) =>
                pt[2] >= tb.min[2] - tol.contact &&
                pt[2] <= tb.max[2] + tol.contact &&
                planPointBoxDist(pt, tb) <= tol.endZone,
            );
          const sitsOnTop = Math.abs(bb.min[2] - tb.max[2]) <= tol.contact && planOverlapArea(bb, tb) > 0;
          if (!endBears && !sitsOnTop) continue;
          connects(beam.id, t.id, "beamOnColumn", gap);
          supports(beam.id, t.id, "beamOnColumn", gap);
        }
      }
    }

    // ---- 5. beam end frames into mid-span of another beam (girder), or beam sits on beam
    if (rules.beamOnGirder) {
      for (const b1 of ofKind("beam")) {
        for (const [b2, gap] of touchingOf(b1.id)) {
          if (b2.kind !== "beam" || b1.id >= b2.id || isJoined(b1.id, b2.id)) continue;
          const a1 = memberAxis(b1);
          const a2 = memberAxis(b2);
          if (!a1 || !a2 || axisAngleDeg(a1, a2) < tol.parallelAngleDeg) continue;
          const bb1 = box(b1.id);
          const bb2 = box(b2.id);
          const e1 = endNear(b1, bb2, tol.endZone);
          const e2 = endNear(b2, bb1, tol.endZone);
          let pair: [string, string] | undefined;
          if (e1 && !e2) pair = [b1.id, b2.id];
          else if (e2 && !e1) pair = [b2.id, b1.id];
          else if (!e1 && !e2) {
            // Crossing beams stacked one on the other.
            if (Math.abs(bb1.min[2] - bb2.max[2]) <= tol.contact) pair = [b1.id, b2.id];
            else if (Math.abs(bb2.min[2] - bb1.max[2]) <= tol.contact) pair = [b2.id, b1.id];
          }
          // e1 && e2: both beams end at the same point -> ambiguous, skip.
          if (!pair) continue;
          connects(pair[0], pair[1], "beamOnGirder", gap);
          supports(pair[0], pair[1], "beamOnGirder", gap);
        }
      }
    }

    // ---- 6. brace ends
    if (rules.braceEnds) {
      for (const brace of ofKind("brace")) {
        const targets = touchingOf(brace.id).filter(
          ([t]) => BRACE_TARGET_PRIORITY[t.kind] !== undefined && !isJoined(brace.id, t.id),
        );
        for (const [t, gap] of targets) connects(brace.id, t.id, "braceEnds", gap);
        const axis = memberAxis(brace);
        if (!axis || Math.abs(axis.start[2] - axis.end[2]) <= tol.contact) continue;
        const lower = axis.start[2] < axis.end[2] ? axis.start : axis.end;
        const near = targets
          .map(([t, gap]) => ({ t, gap, d: pointBoxDist(lower, box(t.id)), pri: BRACE_TARGET_PRIORITY[t.kind]! }))
          .filter((c) => c.d <= tol.endZone)
          .sort((x, y) => y.pri - x.pri || x.d - y.d);
        const target = near[0];
        if (target) supports(brace.id, target.t.id, "braceEnds", target.gap);
      }
    }

    // ---- 7. fallback: any other contact -> connects only
    if (rules.bboxContact) {
      for (const p of pairs) {
        const a = items[p.i]!.id;
        const b = items[p.j]!.id;
        if (isJoined(a, b) || graph.edgesBetween(a, b).length > 0) continue;
        connects(a, b, "bboxContact", p.gap);
      }
    }
  });

  return result;
}

/** True when one of the member's axis ends lies within `zone` of the box. */
function endNear(member: ElementNode, target: BBox, zone: number): boolean {
  const axis = memberAxis(member);
  if (!axis) return false;
  return pointBoxDist(axis.start, target) <= zone || pointBoxDist(axis.end, target) <= zone;
}
