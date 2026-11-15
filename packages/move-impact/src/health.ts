/**
 * Health band of a move - the hackathon's categories and rules (move_impact.health_of), judged on
 * the ESTIMATES only (never a re-run). Design health only: the hackathon's construction-status
 * adjustment came from mock platform data and is not part of this package.
 *
 *   easy        demand changes only - recalc
 *   moderate    a beam / girder or typical connection needs the next size, a footing grows
 *   hard        column over capacity, foundation clash, connection beyond the typicals, removal,
 *               lateral system touched (the column is in a frame, or a chevron brace is reached)
 *   do-not-move a frame column whose frame members are at / over capacity (estimate), or the frame's
 *               drift is already within 5 % of its limit
 */
import type { Model } from "./model.ts";
import { BANDS, type Band, type Clash, type Estimate, type Health } from "./types.ts";
import type { WFact } from "./facts.ts";
import { utilOf } from "./facts.ts";

export interface HealthInput {
  model: Model;
  column: string;
  remove: boolean;
  est: Map<string, Omit<Estimate, "provenance">>;
  facts: WFact[];
  factsOf: Map<string, WFact[]>;
  staleRows: { fact: string }[];
  clashes: Clash[];
  lateral: string[];
  frames: string[];
  name: (id: string) => string | null;
}

export function healthOf(h: HealthInput): Omit<Health, "provenance"> {
  const { model, est, factsOf, frames, name } = h;
  const reasons: [number, string, string][] = [];
  const kind = (id: string) => model.nodes.get(id)?.kind;
  const sfrs = (id: string) => (factsOf.get(id) ?? []).some((f) => f.role === "lateral");
  const nm = (ids: string[]) => ids.slice(0, 3).map((i) => name(i) ?? i).join(", ");
  const over = [...est.values()].filter((v) => v.utilisationAfter > 1.0).map((v) => v.element);
  const memOver = over.filter((k) => kind(k) === "beam" || k.startsWith("NEW:"));
  const colOver = over.filter((k) => kind(k) === "column");
  const ftgOver = over.filter((k) => kind(k) === "footing");
  const cxOver = over.filter((k) => kind(k) === "connection");
  const special = cxOver.filter((k) => est.get(k)!.special);
  let sfrsOver = new Set<string>([
    ...over.filter(sfrs),
    ...[...est.values()].filter((v) => sfrs(v.element) && (v.frameUtilisationAfter ?? 0) > 1.0).map((v) => v.element),
  ]);
  if (frames.length) {
    reasons.push([2, `part of the lateral system (${frames.join(", ")}): moving it changes frame geometry - frame re-analysis and re-detailing`, "SFRS role"]);
    // the screen does not re-run the frame analysis, so a frame member within 5 % of its capacity is
    // treated as having no reserve for the geometry change (a member with an in-frame estimate is
    // judged on that estimate against 1.0 above)
    const near = [...est.values()].filter((v) => sfrs(v.element) && v.frameUtilisationAfter == null && v.utilisationAfter > 0.95).map((v) => v.element);
    sfrsOver = new Set([...sfrsOver, ...near]);
    if (sfrsOver.size) reasons.push([3, `frame member(s) ${nm([...sfrsOver].sort())} at or over capacity at current size (estimate) - frame must be re-designed`, "SFRS reserve"]);
    else {
      const fr = h.facts.filter((f) => f.kind === "frame" && f.group && frames.includes(f.group)).map(utilOf).filter((u): u is number => u != null);
      if (fr.length && Math.max(...fr) > 0.95)
        reasons.push([3, `frame drift already at ${Math.max(...fr).toFixed(2)} of the limit - no reserve for a geometry change`, "SFRS reserve"]);
    }
  }
  if (h.remove) reasons.push([2, "column removed: transfer member over two bays, neighbouring columns and footings pick up its load", "removal"]);
  if (colOver.length) reasons.push([2, `column(s) ${nm(colOver)} over capacity at current size (estimate)`, "reserve"]);
  if (h.clashes.length) reasons.push([2, "footing clash: " + h.clashes.slice(0, 3).map((c) => `${name(c.a) ?? c.a} vs ${name(c.b) ?? c.b}`).join(", "), "foundation clash"]);
  if (special.length) reasons.push([2, `${special.length} connection(s) beyond the largest typical detail - special detail`, "connection headroom"]);
  if (h.lateral.some((l) => l.includes("chevron") || l.includes("brace")) && !frames.length)
    reasons.push([2, "gravity change reaches the chevron braces - lateral analysis changes", "lateral"]);
  if (memOver.length)
    reasons.push([1, `${memOver.length} beam/girder(s) over capacity at current size - next size up (estimate, worst UC ${Math.max(...memOver.map((k) => est.get(k)!.utilisationAfter)).toFixed(2)})`, "reserve"]);
  if (cxOver.length && !special.length) reasons.push([1, `${cxOver.length} connection(s) exceed their typical detail - next typical`, "connection headroom"]);
  if (ftgOver.length) reasons.push([1, `footing(s) ${nm(ftgOver)} must grow (bearing, estimate)`, "foundation"]);
  const worst = Math.max(0, ...[...est.values()].map((v) => v.utilisationAfter));
  const nStale = h.staleRows.length;
  reasons.push([0, `${nStale} calc rows to redo`, "fan-out"]);
  reasons.push([0, `worst estimated UC at current sizes ${worst.toFixed(2)}`, "reserve"]);
  const band = Math.max(0, ...reasons.map((r) => r[0]));
  const score = Math.min(100, Math.floor(25 * band + Math.min(15, nStale / 10) + Math.max(0, Math.min(10, (worst - 0.8) * 25))));
  return {
    band: BANDS[band] as Band,
    score,
    reasons: [...reasons].sort((a, b) => b[0] - a[0]).slice(0, 10).map(([b, reason, factor]) => ({ band: BANDS[b]!, reason, factor })),
    worstUtilisation: est.size ? Math.round(worst * 1000) / 1000 : null,
    method: "estimate",
  };
}
