/**
 * Revision diff: two serialized element graphs -> added / removed / changed elements (keyed by
 * GlobalId, changed = different content hash over ifc_type, mark, name, type_name, profile, storey,
 * params and the bbox rounded to 1 mm - the fields the reference store compared) with per-field
 * before / after, plus the load-path edges that appeared / disappeared. Port of the reference
 * Store.compare_models(); the one diff implementation for the app.
 */
import { graphElements, loadPath } from "./elements.ts";
import { canonicalJson } from "./hash.ts";
import type { Compare, CompareChange, ElementRow, SerializedElementGraph } from "./types.ts";

const cmp = (p: string, q: string): number => (p < q ? -1 : p > q ? 1 : 0);
const pairCmp = (p: [string, string], q: [string, string]): number => cmp(p[0], q[0]) || cmp(p[1], q[1]);

export function diffElements(
  a: ElementRow[], b: ElementRow[], edgesA: { src: string; dst: string }[], edgesB: { src: string; dst: string }[],
  labels: { a?: string | number; b?: string | number } = {},
): Compare {
  const ha = new Map(a.map((e) => [e.global_id, e]));
  const hb = new Map(b.map((e) => [e.global_id, e]));
  const changed: CompareChange[] = [];
  for (const g of [...ha.keys()].filter((k) => hb.has(k)).sort(cmp)) {
    const ea = ha.get(g)!, eb = hb.get(g)!;
    if (ea.content_hash === eb.content_hash) continue;
    const fields: Record<string, [unknown, unknown]> = {};
    const pa = ea.params, pb = eb.params;
    for (const k of [...new Set([...Object.keys(pa), ...Object.keys(pb)])].sort(cmp)) {
      if (canonicalJson(pa[k] ?? null) !== canonicalJson(pb[k] ?? null)) fields[k] = [pa[k] ?? null, pb[k] ?? null];
    }
    for (const col of ["mark", "profile", "storey", "type_name"] as const) {
      if (ea[col] !== eb[col]) fields[col] = [ea[col], eb[col]];
    }
    if (canonicalJson(ea.geom) !== canonicalJson(eb.geom)) fields.geometry = ["", "moved / resized"];
    changed.push({ global_id: g, mark: eb.mark, fields });
  }
  const key = (e: { src: string; dst: string }) => `${e.src}\u0000${e.dst}`;
  const ka = new Set(edgesA.map(key));
  const kb = new Set(edgesB.map(key));
  const pairs = (s: Set<string>, minus: Set<string>) =>
    [...s].filter((k) => !minus.has(k)).map((k) => k.split("\u0000") as [string, string]).sort(pairCmp);
  const brief = (e: ElementRow) => ({ global_id: e.global_id, mark: e.mark, cat: e.cat });
  return {
    a: labels.a ?? "a", b: labels.b ?? "b",
    removed: [...ha.keys()].filter((k) => !hb.has(k)).sort(cmp).map((k) => brief(ha.get(k)!)),
    added: [...hb.keys()].filter((k) => !ha.has(k)).sort(cmp).map((k) => brief(hb.get(k)!)),
    changed, edges_removed: pairs(ka, kb), edges_added: pairs(kb, ka),
  };
}

/** Diff two revisions of a model, each given as its serialized element graph. */
export function diffGraphs(
  a: SerializedElementGraph, b: SerializedElementGraph, labels: { a?: string | number; b?: string | number } = {},
): Compare {
  return diffElements(graphElements(a), graphElements(b), loadPath(a), loadPath(b), labels);
}
