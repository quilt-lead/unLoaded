/**
 * Impact propagation over the element graph's load path and the calc graph. Port of the reference
 * impact.propagate() (itself a port of the 2D prototype's propagate()):
 *
 * change  - the element itself changes: everything downstream on the load path is hit
 * remove  - the element is removed: what it supported is re-framed (direct upstream neighbours,
 *           through a connection node to the member on the other side), the connection nodes
 *           that only served it go too, anything downstream that loses all its supports is
 *           orphaned (removed), then the re-framed members propagate downstream like a change.
 * Then: every calc linked to a hit or removed element is stale, and every calc downstream of a
 * stale calc in the calc graph is stale too.
 *
 * `edges` are the graph's `supports` edges (src is supported by dst). Waves count steps the way
 * packages/element-graph's loadPathDown counts depth: the step into a connection node counts, the
 * step out of it to a member does not, so the engine and the UI report the same depth.
 *
 * `inputs`: sha256 of the documents the answer rests on (the element graph; the calc PDF when calcs
 * are linked) - the result's provenance (rule `impact.propagate.<mode>`).
 */
import { RULES, ruleProvenance } from "./provenance.ts";
import type { CalcEdge, ElementRow, Impact, ImpactMode, Link, LoadPathEdge } from "./types.ts";

type Lite = Pick<ElementRow, "cat" | "mark" | "name">;

export function propagate(
  gid: string, mode: ImpactMode, edges: Pick<LoadPathEdge, "src" | "dst">[], links: Link[], calcEdges: CalcEdge[],
  elements: Map<string, Lite> | Record<string, Lite>, inputs: readonly string[],
): Impact {
  const get = (g: string): Lite | undefined => (elements instanceof Map ? elements.get(g) : elements[g]);
  const down = new Map<string, string[]>();
  const up = new Map<string, string[]>();
  for (const e of edges) {
    (down.get(e.src) ?? down.set(e.src, []).get(e.src)!).push(e.dst);
    (up.get(e.dst) ?? up.set(e.dst, []).get(e.dst)!).push(e.src);
  }
  const removed = new Set<string>();
  let seeds: string[] = [];
  const why: Record<string, string> = {};
  const mark = (g: string): string => get(g)?.mark || get(g)?.name || g;

  if (mode === "remove") {
    removed.add(gid);
    for (const u of up.get(gid) ?? []) {
      if (get(u)?.cat === "Connection" && (down.get(u) ?? []).every((d) => removed.has(d))) {
        removed.add(u);
        for (const uu of up.get(u) ?? []) {
          seeds.push(uu);
          why[uu] = `lost its support at ${mark(gid)} (via connection) - re-frame / re-span`;
        }
      } else {
        seeds.push(u);
        why[u] = `lost its support at ${mark(gid)} - re-frame / re-span`;
      }
    }
    // orphans: downstream nodes whose every support is removed
    const stack = [...(down.get(gid) ?? [])];
    while (stack.length) {
      const d = stack.pop()!;
      if (removed.has(d)) continue;
      if ((up.get(d) ?? []).every((s) => removed.has(s))) {
        removed.add(d);
        why[d] = `only carried load from ${mark(gid)} - now orphaned`;
        stack.push(...(down.get(d) ?? []));
      }
    }
  } else {
    seeds = [gid];
    why[gid] = "changed";
  }

  const hit: Record<string, number> = {};
  const q: string[] = [];
  for (const s of new Set(seeds)) {
    if (!removed.has(s)) {
      hit[s] = 0;
      q.push(s);
    }
  }
  while (q.length) { // 0-1 BFS: leaving a connection node costs 0, every other step 1
    const x = q.shift()!;
    const step = get(x)?.cat === "Connection" ? 0 : 1;
    for (const d of down.get(x) ?? []) {
      if (removed.has(d) || (d in hit && hit[d]! <= hit[x]! + step)) continue;
      hit[d] = hit[x]! + step;
      if (step === 0) q.unshift(d);
      else q.push(d);
    }
  }

  const stale: Record<string, string> = {};
  const byCalc = new Map<string, string[]>();
  for (const l of links) {
    if (l.status === "rejected") continue;
    if (l.global_id in hit || removed.has(l.global_id)) {
      (byCalc.get(l.calc_key) ?? byCalc.set(l.calc_key, []).get(l.calc_key)!).push(l.global_id);
    }
  }
  for (const [k, gs] of byCalc) {
    const names = [...new Set(gs.map(mark))].sort();
    stale[k] = `covers ${names.slice(0, 6).join(", ")}${names.length > 6 ? ` +${names.length - 6} more` : ""}`;
  }
  const kdown = new Map<string, string[]>();
  for (const e of calcEdges) (kdown.get(e.src) ?? kdown.set(e.src, []).get(e.src)!).push(e.dst);
  const cq = Object.keys(stale);
  while (cq.length) {
    const k = cq.shift()!;
    for (const d of kdown.get(k) ?? []) {
      if (!(d in stale)) {
        stale[d] = `input from ${k}`;
        cq.push(d);
      }
    }
  }
  return {
    global_id: gid, mode, removed: [...removed].sort(), hit, why, stale,
    waves: Math.max(0, ...Object.values(hit)),
    provenance: ruleProvenance("impact", RULES.impact.propagate(mode), inputs),
  };
}
