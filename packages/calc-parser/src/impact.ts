/**
 * Impact propagation over the element graph and the calc graph. Port of impact.py.
 *
 * change  - the element itself changes: everything downstream on the load path is hit
 * remove  - the element is removed: what it supported is re-framed (direct upstream
 *           neighbours, through a connection node to the member on the other side), the
 *           connection nodes that only served it go too, anything downstream that loses
 *           all its supports is orphaned (removed), then the re-framed members propagate
 *           downstream like a change.
 * Then: every calc linked to a hit or removed element is stale, and every calc
 * downstream of a stale calc in the calc graph is stale too.
 */
import { cmpStr } from './pyre.ts';
import type { CalcEdge, CalcElement, CalcLink, ImpactMode, ImpactResult, LoadEdge } from './types.ts';

type ElementInfo = Pick<CalcElement, 'cat' | 'mark'> & { name?: string };

export function propagateImpact(
  gid: string,
  mode: ImpactMode,
  edges: readonly LoadEdge[],
  links: ReadonlyArray<Pick<CalcLink, 'global_id' | 'calc_key' | 'status'>>,
  calcEdges: ReadonlyArray<Pick<CalcEdge, 'src' | 'dst'>>,
  elements: ReadonlyMap<string, ElementInfo> | Record<string, ElementInfo>,
): ImpactResult {
  const get = (g: string): ElementInfo | undefined =>
    elements instanceof Map ? elements.get(g) : (elements as Record<string, ElementInfo>)[g];
  const down = new Map<string, string[]>();
  const up = new Map<string, string[]>();
  for (const e of edges) {
    (down.get(e.src) ?? down.set(e.src, []).get(e.src)!).push(e.dst);
    (up.get(e.dst) ?? up.set(e.dst, []).get(e.dst)!).push(e.src);
  }

  const removed = new Set<string>();
  let seeds: string[] = [];
  const why: Record<string, string> = {};
  const mark = (g: string) => get(g)?.mark || get(g)?.name || g;

  if (mode === 'remove') {
    removed.add(gid);
    for (const u of up.get(gid) ?? []) {
      if (get(u)?.cat === 'Connection' && (down.get(u) ?? []).every((d) => removed.has(d))) {
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
    why[gid] = 'changed';
  }

  const hit: Record<string, number> = {};
  const hitSet = new Set<string>();
  let wave = [...new Set(seeds)].filter((s) => !removed.has(s));
  for (const s of wave) {
    hit[s] = 0;
    hitSet.add(s);
  }
  let w = 0;
  while (wave.length) {
    w += 1;
    const nxt: string[] = [];
    for (const x of wave) {
      for (const d of down.get(x) ?? []) {
        if (!removed.has(d) && !hitSet.has(d)) {
          hit[d] = w;
          hitSet.add(d);
          nxt.push(d);
        }
      }
    }
    wave = nxt;
  }

  const stale: Record<string, string> = {};
  const byCalc = new Map<string, string[]>();
  for (const l of links) {
    if (l.status === 'rejected') continue;
    if (hitSet.has(l.global_id) || removed.has(l.global_id)) {
      (byCalc.get(l.calc_key) ?? byCalc.set(l.calc_key, []).get(l.calc_key)!).push(l.global_id);
    }
  }
  for (const [k, gs] of byCalc) {
    const names = [...new Set(gs.map(mark))].sort(cmpStr);
    stale[k] = `covers ${names.slice(0, 6).join(', ')}${names.length > 6 ? ` +${names.length - 6} more` : ''}`;
  }
  const kdown = new Map<string, string[]>();
  for (const e of calcEdges) (kdown.get(e.src) ?? kdown.set(e.src, []).get(e.src)!).push(e.dst);
  // insertion order (Object.keys would put integer-like keys first)
  const q = [...byCalc.keys()];
  while (q.length) {
    const k = q.shift()!;
    for (const d of kdown.get(k) ?? []) {
      if (!Object.hasOwn(stale, d)) {
        stale[d] = `input from ${k}`;
        q.push(d);
      }
    }
  }
  return {
    global_id: gid,
    mode,
    removed: [...removed].sort(cmpStr),
    hit,
    why,
    stale,
    waves: Math.max(0, ...Object.values(hit)),
  };
}
