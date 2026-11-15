/**
 * Revision diff: two serialized element graphs -> added / removed / changed elements (keyed by
 * GlobalId, changed = different content hash over ifc_type, mark, name, type_name, profile, storey,
 * params and the bbox rounded to 1 mm - the fields the reference store compared) with per-field
 * before / after, plus the load-path edges that appeared / disappeared. Port of the reference
 * Store.compare_models(); the one diff implementation for the app.
 *
 * The hash and the per-field comparison both read `diffFields` (elements.ts): params are listed by
 * key, every other field by name, and the rounded bbox as "geometry". A changed element always lists
 * at least one field, and a field is never listed for a difference the hash does not see.
 */
import { diffFields, graphElements, loadPath, type DiffFields } from "./elements.ts";
import { canonicalJson } from "./hash.ts";
import type { Compare, CompareChange, ElementRow, SerializedElementGraph } from "./types.ts";

const cmp = (p: string, q: string): number => (p < q ? -1 : p > q ? 1 : 0);
const paramJson = (p: Record<string, unknown>, k: string): string | undefined =>
  Object.hasOwn(p, k) && p[k] !== undefined ? canonicalJson(p[k]) : undefined;
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
    const fa = diffFields(ea), fb = diffFields(eb);
    const fields: Record<string, [unknown, unknown]> = {};
    const pa = fa.params, pb = fb.params;
    for (const k of [...new Set([...Object.keys(pa), ...Object.keys(pb)])].sort(cmp)) {
      // as the hash sees them: a param set to null differs from an absent one
      if (paramJson(pa, k) !== paramJson(pb, k)) fields[k] = [pa[k] ?? null, pb[k] ?? null];
    }
    for (const col of (Object.keys(fa) as (keyof DiffFields)[]).filter((c) => c !== "params").sort(cmp)) {
      if (canonicalJson(fa[col]) === canonicalJson(fb[col])) continue;
      fields[col === "bbox" ? "geometry" : col] = col === "bbox" ? ["", "moved / resized"] : [fa[col], fb[col]];
    }
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
