/**
 * Scores a drawing-parser ModelInput against the synthetic v2 generator's answer key.
 *
 *   node packages/drawing-parser/scripts/score.ts --model model.json \
 *     --truth <dir>/registry_truth.json --design <dir>/design.json \
 *     [--out score.json] [--baseline packages/drawing-parser/eval/baseline.json --gate]
 *
 * Synthetic data only (the generator's fictional building): never point it at a real set.
 * Truth: registry_truth.json (every element and where it is printed) + design.json (coordinates, ft).
 *
 * Elements are matched to truth per class by plan position (greedy, nearest first, within
 * --match-ft, default 3 ft; beams and braces also by level), so the metrics below are about what
 * was read, not about ids. Columns: the parser emits one element per storey segment
 * (`column:1/A:level-1..level-2`), the truth one full-height column per intersection, so a column's
 * segments (same Drawing.Grid) are scored as one stack: matched by its plan position, size-correct only
 * if every segment's size is the truth size, its occurrences the union of the segments', and in the
 * load-path pairs every segment stands for the stack (segment-on-segment pairs are dropped).
 *   recall / precision          per class; recall_drawn counts only truth elements printed with text
 *   size_accuracy               normalised profile = truth size (matched)
 *   level_accuracy              element level elevation = truth level (beams, braces)
 *   placement_within_tol        plan position error <= --tol-ft (default 0.5 ft); mean / max error
 *   mark_accuracy               footing / pier / grade-beam mark = the mark printed on the plan
 *   callout_recall              truth detail callouts (sheet + bubble) read as a connection occurrence
 *   callout_attribution         ... attributed to the same member and end as the truth connection
 *   callout_wrong_flagged       share of the wrong attributions the parser flagged as ambiguous
 *   base_plate_recall           truth base plates found (column schedule)
 *   occ_recall / occ_precision  printed occurrences (plan / elevation tags, schedule rows) of matched elements
 *   frames_into / bears_on      load-path pairs of the element graph built from the model vs truth
 * --misses prints the load-path pairs missed / extra.
 * --gate fails (exit 1) when any metric in the baseline is lower (higher for *_mean_err / *_max_err).
 */
import { readFileSync, writeFileSync } from "node:fs";
import { parseArgs } from "node:util";
import { buildGraph } from "@unloaded/element-graph";
import type { ElementInput, ModelInput } from "@unloaded/element-graph/input";
import { normaliseProfile } from "@unloaded/ifc-parser";

const { values } = parseArgs({
  options: {
    model: { type: "string" }, truth: { type: "string" }, design: { type: "string" }, out: { type: "string" },
    baseline: { type: "string" }, gate: { type: "boolean" }, misses: { type: "boolean" }, "match-ft": { type: "string" }, "tol-ft": { type: "string" },
  },
});
if (!values.model || !values.truth || !values.design) {
  console.error("usage: score.ts --model model.json --truth registry_truth.json --design design.json [--out s.json] [--baseline b.json --gate]");
  process.exit(2);
}
const MATCH_FT = Number(values["match-ft"] ?? 3);
const TOL_FT = Number(values["tol-ft"] ?? 0.5);
const FT = 0.3048;

type Rect = [number, number, number, number];
interface TruthOcc { doc: string; how: string; page?: number; bbox?: Rect; sheet?: string; text?: string }
interface TruthNode { id: string; kind: string; type: string; attrs: Record<string, unknown>; occurrences: TruthOcc[] }
interface DesignEl { id: string; type: string; level?: string; size?: string; p1?: number[]; p2?: number[]; x?: number; y?: number; member?: string; end?: string; conn_type?: string; grid?: string }
interface MyOcc { sheet: string; page: number; rect: Rect; how: string; text: string }

const model: ModelInput = JSON.parse(readFileSync(values.model, "utf8"));
const truth: { nodes: TruthNode[]; relations: Array<{ src: string; dst: string; kind: string; via?: string }> } = JSON.parse(readFileSync(values.truth, "utf8"));
const design: { elements: DesignEl[]; building: { levels: Array<{ key: string; elev_ft: number; name: string }> } } = JSON.parse(readFileSync(values.design, "utf8"));
const dEl = new Map(design.elements.map((e) => [e.id, e]));
const levelFt = new Map<string, number>([["L1", 0], ...design.building.levels.map((l) => [l.key, l.elev_ft] as [string, number])]);
const myLevelFt = new Map(model.levels.map((l) => [l.id, l.elevation / FT]));
const occsOf = (e: ElementInput): MyOcc[] => JSON.parse(String(e.params["Drawing.Occurrences"] ?? "[]"));

// ------------------------------------------------------------------ classes
type Cls = "beam" | "grade_beam" | "column" | "pier" | "brace" | "footing" | "slab";
const truthCls: Record<string, Cls> = { beam: "beam", girder: "beam", grade_beam: "grade_beam", column: "column", pier: "pier", brace: "brace", footing: "footing", deck: "slab" };
function myCls(e: ElementInput): Cls | undefined {
  const role = e.params["Drawing.Role"];
  if (e.kind === "beam") return role === "grade_beam" ? "grade_beam" : "beam";
  if (e.kind === "column") return role === "pier" ? "pier" : "column";
  if (e.kind === "brace" || e.kind === "footing" || e.kind === "slab") return e.kind as Cls;
  return undefined;
}

/** Plan geometry in ft: segment (linear) or point. */
function myGeom(e: ElementInput): { a: number[]; b: number[] } | undefined {
  const g = e.geometry;
  if (!g) return undefined;
  if (g.axis && (e.kind === "beam" || e.kind === "brace")) return { a: g.axis.start.map((v) => v / FT), b: g.axis.end.map((v) => v / FT) };
  const c = [0, 1, 2].map((k) => (g.bbox.min[k]! + g.bbox.max[k]!) / 2 / FT);
  return { a: c, b: c };
}
function truthGeom(id: string): { a: number[]; b: number[] } | undefined {
  const d = dEl.get(id);
  if (!d) return undefined;
  if (d.p1 && d.p2) return { a: d.p1, b: d.p2 };
  if (d.x !== undefined && d.y !== undefined) return { a: [d.x, d.y], b: [d.x, d.y] };
  return undefined;
}
const d2 = (p: number[], q: number[]) => Math.hypot(p[0]! - q[0]!, p[1]! - q[1]!);
function segDist(t: { a: number[]; b: number[] }, m: { a: number[]; b: number[] }): number {
  return Math.min(Math.max(d2(t.a, m.a), d2(t.b, m.b)), Math.max(d2(t.a, m.b), d2(t.b, m.a)));
}
const truthLevelFt = (n: TruthNode) => (typeof n.attrs.level === "string" ? levelFt.get(n.attrs.level) : undefined);

const metrics: Record<string, number> = {};
const truthEls = truth.nodes.filter((n) => n.kind === "element" && truthCls[n.type]);
// column stacks: the storey segments of one column (same Drawing.Grid); the lowest stands for the stack
const segmentsOf = new Map<string, ElementInput[]>(); // representative id -> its segments
const stackOf = new Map<string, string>(); // any column segment id -> representative id
{
  const byGrid = new Map<string, ElementInput[]>();
  for (const e of model.elements.filter((x) => myCls(x) === "column")) {
    const k = String(e.params["Drawing.Grid"] ?? e.id);
    byGrid.set(k, [...(byGrid.get(k) ?? []), e]);
  }
  for (const group of byGrid.values()) {
    group.sort((a, b) => (a.geometry?.bbox.min[2] ?? 0) - (b.geometry?.bbox.min[2] ?? 0) || (a.id < b.id ? -1 : 1));
    segmentsOf.set(group[0]!.id, group);
    for (const e of group) stackOf.set(e.id, group[0]!.id);
  }
}
const canon = (id: string) => stackOf.get(id) ?? id;
const segs = (e: ElementInput) => segmentsOf.get(e.id) ?? [e];
const mine = model.elements.filter((e) => myCls(e) && (myCls(e) !== "column" || segmentsOf.has(e.id)));
metrics.column_segments_found = stackOf.size;
const match = new Map<string, ElementInput>(); // truth id -> mine
const matchedMine = new Map<string, string>(); // my id -> truth id
const textOcc = (o: TruthOcc) => o.doc === "drawings" && ["plan_tag", "elevation_tag", "schedule_row"].includes(o.how) && !!o.text;

for (const cls of ["beam", "grade_beam", "column", "pier", "brace", "footing", "slab"] as Cls[]) {
  const T = truthEls.filter((n) => truthCls[n.type] === cls);
  const M = mine.filter((e) => myCls(e) === cls);
  const pairs: Array<{ t: TruthNode; m: ElementInput; d: number }> = [];
  for (const t of T) {
    const tg = truthGeom(t.id);
    for (const m of M) {
      if (cls === "slab") {
        if (Math.abs((truthLevelFt(t) ?? NaN) - (myLevelFt.get(m.levelId ?? "") ?? NaN)) < 0.01) pairs.push({ t, m, d: 0 });
        continue;
      }
      const mg = myGeom(m);
      if (!tg || !mg) continue;
      if ((cls === "beam" || cls === "brace") && Math.abs((truthLevelFt(t) ?? NaN) - (myLevelFt.get(m.levelId ?? "") ?? NaN)) > 0.01) continue;
      const d = segDist(tg, mg);
      if (d <= MATCH_FT) pairs.push({ t, m, d });
    }
  }
  pairs.sort((p, q) => p.d - q.d || (p.t.id < q.t.id ? -1 : 1));
  const errs: number[] = [];
  for (const p of pairs) {
    if (match.has(p.t.id) || matchedMine.has(p.m.id)) continue;
    match.set(p.t.id, p.m);
    matchedMine.set(p.m.id, p.t.id);
    errs.push(p.d);
  }
  const drawn = T.filter((t) => t.occurrences.some(textOcc));
  const hit = T.filter((t) => match.has(t.id));
  const k = (s: string) => `${cls}_${s}`;
  metrics[k("truth")] = T.length;
  metrics[k("found")] = M.length;
  metrics[k("recall")] = T.length ? hit.length / T.length : 1;
  metrics[k("recall_drawn")] = drawn.length ? drawn.filter((t) => match.has(t.id)).length / drawn.length : 1;
  metrics[k("precision")] = M.length ? hit.length / M.length : 1;
  if (cls !== "slab" && hit.length) {
    metrics[k("placement_within_tol")] = errs.filter((e) => e <= TOL_FT).length / errs.length;
    metrics[k("placement_mean_err_ft")] = errs.reduce((s, e) => s + e, 0) / errs.length;
    metrics[k("placement_max_err_ft")] = Math.max(...errs);
  }
  const sized = hit.filter((t) => typeof t.attrs.size === "string");
  if (sized.length) metrics[k("size_accuracy")] = sized.filter((t) => segs(match.get(t.id)!).every((e) => e.profile === normaliseProfile(String(t.attrs.size)))).length / sized.length;
  const lev = hit.filter((t) => truthLevelFt(t) !== undefined);
  if (lev.length && (cls === "beam" || cls === "brace")) {
    metrics[k("level_accuracy")] = lev.filter((t) => Math.abs(truthLevelFt(t)! - (myLevelFt.get(match.get(t.id)!.levelId ?? "") ?? NaN)) < 0.01).length / lev.length;
  }
  if (cls === "footing" || cls === "pier" || cls === "grade_beam") {
    const marked = hit.filter((t) => t.occurrences.some((o) => o.how === "plan_tag" && o.text));
    if (marked.length) metrics[k("mark_accuracy")] = marked.filter((t) => match.get(t.id)!.mark === t.occurrences.find((o) => o.how === "plan_tag" && o.text)!.text).length / marked.length;
  }
}

// ------------------------------------------------------------------ occurrences (drawing-side evidence)
const inside = (r: Rect, t: Rect, pad = 2) => {
  const cx = (r[0] + r[2]) / 2, cy = (r[1] + r[3]) / 2;
  return cx >= t[0] - pad && cx <= t[2] + pad && cy >= t[1] - pad && cy <= t[3] + pad;
};
let occT = 0, occHit = 0, occM = 0, occMHit = 0;
for (const [tid, m] of match) {
  const t = truthEls.find((n) => n.id === tid)!;
  const to = t.occurrences.filter(textOcc);
  const mo = segs(m).flatMap(occsOf).filter((o) => ["plan_tag", "elevation_tag", "schedule_row"].includes(o.how));
  occT += to.length;
  occHit += to.filter((o) => mo.some((x) => x.page === o.page && inside(x.rect, o.bbox!))).length;
  occM += mo.length;
  occMHit += mo.filter((x) => to.some((o) => x.page === o.page && inside(x.rect, o.bbox!))).length;
}
metrics.occ_recall = occT ? occHit / occT : 1;
metrics.occ_precision = occM ? occMHit / occM : 1;

// ------------------------------------------------------------------ connections: callouts and base plates
const conns = model.elements.filter((e) => e.kind === "connection");
const truthConn = truth.nodes.filter((n) => n.kind === "element" && n.type === "connection");
let calloutT = 0, calloutHit = 0, calloutAttr = 0, wrong = 0, wrongFlagged = 0;
for (const t of truthConn) {
  for (const o of t.occurrences.filter((x) => x.doc === "drawings" && x.how === "detail_callout")) {
    calloutT++;
    const found = conns.find((c) => occsOf(c).some((x) => x.how === "detail_callout" && x.page === o.page && inside(x.rect, o.bbox!)));
    if (!found) continue;
    calloutHit++;
    const de = dEl.get(t.id);
    if (!de) continue;
    if (t.id.startsWith("BP-")) {
      if (found.id === `connection:base:${de.grid ?? String(t.attrs.grid ?? "")}` || found.id === `connection:base:${t.id.slice(3, -1)}/${t.id.slice(-1)}`) calloutAttr++;
      continue;
    }
    const mm = match.get(de.member ?? "");
    // end: the truth end (i = p1) is the member end nearer the connection's position
    const tg = truthGeom(de.member ?? ""), cg = myGeom(found);
    const right = !!mm && found.params["Drawing.Member"] === mm.id && !!tg && !!cg &&
      d2(cg.a, de.end === "i" ? tg.a : tg.b) < d2(cg.a, de.end === "i" ? tg.b : tg.a);
    if (right) calloutAttr++;
    else {
      wrong++;
      if (found.params["Drawing.CalloutAmbiguous"] === true) wrongFlagged++;
    }
  }
}
metrics.callout_truth = calloutT;
metrics.callout_recall = calloutT ? calloutHit / calloutT : 1;
metrics.callout_attribution = calloutHit ? calloutAttr / calloutHit : 1;
// of the wrong attributions, how many the parser flagged as ambiguous (Drawing.CalloutAmbiguous)
metrics.callout_wrong_flagged = wrong ? wrongFlagged / wrong : 1;
const bpT = truthConn.filter((t) => t.id.startsWith("BP-"));
metrics.base_plate_recall = bpT.length ? bpT.filter((t) => conns.some((c) => c.id === `connection:base:${t.id.slice(3, -1)}/${t.id.slice(-1)}`)).length / bpT.length : 1;
metrics.connection_found = conns.length;

// ------------------------------------------------------------------ load path through the graph built from the model
const { graph } = buildGraph(model);
const isConn = (id: string) => graph.getNode(id)?.kind === "connection";
const pairsOut = new Set<string>();
for (const e of graph.edges()) {
  if (e.kind !== "supports") continue;
  if (isConn(e.a)) continue;
  const targets = isConn(e.b) ? graph.edgesOf(e.b, { kind: "supports", direction: "out" }).map((x) => x.b).filter((b) => !isConn(b) && b !== e.a) : [e.b];
  for (const b of targets) if (canon(e.a) !== canon(b)) pairsOut.add(`${canon(e.a)}|${canon(b)}`);
}
// grade beam -> footing is split out: the element graph has no "beam end bears on footing" rule, so
// those pairs measure the graph, not the parser
const gradeBeam = (id: string) => dEl.get(id)?.type === "grade_beam";
for (const [kind, name, keep] of [
  ["frames-into", "frames_into", (r: { src: string }) => !gradeBeam(r.src)],
  ["frames-into", "frames_into_grade_beam", (r: { src: string }) => gradeBeam(r.src)],
  ["bears-on", "bears_on", (_r: { src: string }) => true],
] as const) {
  const rels = truth.relations.filter((r) => r.kind === kind && keep(r) && match.has(r.src) && match.has(r.dst));
  const truthPairs = new Set(rels.map((r) => `${match.get(r.src)!.id}|${match.get(r.dst)!.id}`));
  const scope = new Set([...truthPairs].flatMap((p) => p.split("|")));
  const pred = [...pairsOut].filter((p) => p.split("|").every((x) => scope.has(x)) && (kind === "bears-on"
    ? ["column", "footing", "slab"].includes(graph.getNode(p.split("|")[0]!)!.kind)
    : ["beam", "brace"].includes(graph.getNode(p.split("|")[0]!)!.kind)));
  const k = name;
  if (values.misses) {
    for (const p of truthPairs) if (!pairsOut.has(p)) {
      const [a, b] = p.split("|") as [string, string];
      console.log(`miss ${name}: ${p}  ${graph.edgesBetween(a, b).map((e) => `${e.kind} ${e.a}->${e.b} (${e.evidence.map((v) => v.rule).join(", ")})`).join("; ")}`);
    }
    for (const p of pred) if (!truthPairs.has(p)) console.log(`extra ${name}: ${p}`);
  }
  metrics[`${k}_truth`] = truthPairs.size;
  metrics[`${k}_recall`] = truthPairs.size ? [...truthPairs].filter((p) => pairsOut.has(p)).length / truthPairs.size : 1;
  metrics[`${k}_precision`] = pred.length ? pred.filter((p) => truthPairs.has(p)).length / pred.length : 1;
}

// ------------------------------------------------------------------ levels
const tLevels = [{ key: "L1", elev_ft: 0 }, ...design.building.levels];
metrics.levels_found = tLevels.filter((l) => model.levels.some((m) => Math.abs(m.elevation / FT - l.elev_ft) < 0.01)).length / tLevels.length;

const rounded = Object.fromEntries(Object.entries(metrics).sort(([a], [b]) => a.localeCompare(b)).map(([k, v]) => [k, Math.round(v * 10000) / 10000]));
const report = { about: "drawing-parser vs synthetic v2 answer key (numbers only)", match_ft: MATCH_FT, tol_ft: TOL_FT, metrics: rounded };
if (values.out) writeFileSync(values.out, JSON.stringify(report, null, 1) + "\n");
for (const [k, v] of Object.entries(rounded)) console.log(`${k.padEnd(36)} ${v}`);

if (values.baseline) {
  const base: { metrics: Record<string, number> } = JSON.parse(readFileSync(values.baseline, "utf8"));
  const worse = Object.entries(base.metrics).filter(([k, v]) => {
    const now = rounded[k];
    if (now === undefined) return true;
    return /_(mean|max)_err_ft$/.test(k) ? now > v + 1e-9 : now < v - 1e-9;
  });
  if (worse.length) {
    console.error(`\nWORSE than baseline: ${worse.map(([k, v]) => `${k} ${rounded[k]} (baseline ${v})`).join("; ")}`);
    if (values.gate) process.exit(1);
  } else console.log("\nbaseline: no metric worse");
}
