/**
 * Move / remove a column: topological impact, screened impact, estimated utilisation change,
 * stale calcs and a health band. Port of the hackathon engine (calc-graph prototype,
 * backend/calcgraph/move_impact.py, 2026-11-14) with the same rules and thresholds, but every read
 * of the generator's design file replaced by geometry from the element graph or by values a calc
 * states (optional `CalcFact`s). See README "What changed from the hackathon engine".
 */
import { buildModel, below, dist, lineIntersect, spanOf, type End, type Member, type Model, type P2 } from "./model.ts";
import { fac, ru, solveSpan, type SpanResult, type Vec3 } from "./statics.ts";
import { healthOf } from "./health.ts";
import { normaliseFacts, utilOf, type WFact } from "./facts.ts";
import { provenance, RULES } from "./provenance.ts";
import { q, type Unit } from "@unloaded/calc-mapper";
import { phiMn, yieldFromMaterial, type FlexureSection } from "./flexure.ts";
import {
  ENGINE_VERSION,
  type Clash,
  type Estimate,
  type GeometryChange,
  type ImpactInput,
  type ImpactResult,
  type MemberGeometry,
  type ScreenedElement,
  type SectionProps,
  type StaleCalc,
  type StaleRow,
  type TopoElement,
} from "./types.ts";

/** A row is "screened stale" when its estimated demand moves by more than this (hackathon: 5 %). */
export const CHANGE = 0.05;
/** A column / footing is put on the topological path when its load moves by more than this (hackathon: 0.1 %). */
export const TOUCH = 0.001;
/** Same-plan-position tolerance for a column stack (column + pier + splices), metres. */
const STACK_TOL = 0.05;
const FT = 0.3048;

export class UnknownColumn extends Error {
  readonly column: string;
  constructor(column: string) {
    super(`not a column in this graph: ${column}`);
    this.column = column;
  }
}

type Basis = "stated loads" | "unit area load";

interface Geo {
  p1: P2;
  p2: P2;
  why: string;
  reframe?: Partial<Record<End, string>>;
  L0: number;
  L1: number;
}

function memberWeightKlf(profile: string | null): number | null {
  const m = profile ? /^W\d+(?:\.\d+)?X(\d+(?:\.\d+)?)$/i.exec(profile.trim()) : null;
  return m ? Number(m[1]) / 1000 : null;
}

export function impact(input: ImpactInput): ImpactResult {
  const { graph, move } = input;
  const { facts, problems } = normaliseFacts(input.facts ?? []);
  const hasFacts = input.facts !== undefined;
  // every input document the result rests on: the graph, then each calc package a fact came from
  const runInputs = provenance("impact", RULES.topological, "rule", [input.graphSha256], facts.map((f) => f.source.documentSha256)).inputs;
  const links = (input.links ?? []).filter((l) => l.status !== "rejected");
  const model = buildModel(graph);
  const column = move.column;
  if (model.nodes.get(column)?.kind !== "column" || !model.columns.has(column)) throw new UnknownColumn(column);
  const remove = move.remove === true;
  const dx = move.remove ? 0 : move.dx;
  const dy = move.remove ? 0 : move.dy;
  const assumptions = [...model.assumptions, ...problems];
  const notes: string[] = [];
  const name = (id: string) => model.nodes.get(id)?.name ?? model.nodes.get(id)?.mark ?? null;
  const kindOf = (id: string) => model.nodes.get(id)?.kind ?? "unknown";

  // ---- facts by element
  const factsOf = new Map<string, WFact[]>();
  for (const f of facts) for (const e of f.elements) (factsOf.get(e) ?? factsOf.set(e, []).get(e)!).push(f);
  const factOf = (e: string, kinds: string[]) => (factsOf.get(e) ?? []).find((f) => kinds.includes(f.kind));
  const typicals = facts.filter((f) => f.kind === "typical_detail" && f.detailType && f.capacity);
  // section properties (inches) for a profile, when the caller supplies a shape table
  const sectionIn = (profile: string | null): SectionProps | null => {
    const sp = profile ? input.sections?.[profile] : undefined;
    if (!sp) return null;
    const k = sp.unit === "mm" ? 1 / 25.4 : 1;
    const pw: Partial<Record<keyof SectionProps, number>> = { d: 1, tf: 1, bf: 1, ry: 1, rts: 1, ho: 1, A: 2, Zx: 3, Sx: 3, Ix: 4, J: 4 };
    const out: SectionProps = { unit: "in" };
    for (const [key, p] of Object.entries(pw) as [keyof SectionProps, number][]) {
      const v = sp[key];
      if (typeof v === "number") (out as unknown as Record<string, number>)[key] = v * k ** p;
    }
    return out;
  };
  const flexSection = (s: SectionProps | null): FlexureSection | null =>
    s && s.Zx != null && s.Sx != null && s.bf != null && s.tf != null && s.ry != null && s.rts != null && s.ho != null && s.J != null
      ? { Zx: s.Zx, Sx: s.Sx, bf: s.bf, tf: s.tf, ry: s.ry, rts: s.rts, ho: s.ho, J: s.J }
      : null;
  // SDS >= Cs R / Ie from the braced (else any) direction's printed ELF row (hackathon _sds_lower_bound)
  const elf = facts.filter((f) => f.kind === "seismic" && f.seismic?.cs && f.seismic?.r);
  const elfRow = elf.find((f) => /braced/i.test(f.seismic!.system ?? "")) ?? elf[0];
  const sds = elfRow ? (elfRow.seismic!.cs * elfRow.seismic!.r) / (elfRow.seismic!.ie ?? 1) : null;
  // a gravity change [D, L, Lr] factored by the combination that governs the row it lands on
  const gravityIncrement = (dv: Vec3, combo: string | undefined): [number, string] => {
    const c = (combo ?? "").trim();
    if (/^LC[123]$/i.test(c)) return [fac(dv, c.toUpperCase()), c.toUpperCase()];
    if (/^(OM|S\d)$/i.test(c) || /\bE\b|Omega|Ω/i.test(c)) {
      if (sds == null) return [fac(dv, "LC2"), "LC2 (seismic combination, no SDS stated)"];
      return [(1.2 + 0.2 * sds) * dv[0] + 0.5 * dv[1] + 0.5 * dv[2], `(1.2 + 0.2 SDS) D + 0.5 L + 0.5 Lr, SDS >= ${fmt(sds, 3)}`];
    }
    const coef = (sym: string) => {
      const m = new RegExp(`([0-9.]+)\\s*${sym}(?![a-z])`, "i").exec(c);
      return m ? Number(m[1]) : new RegExp(`(^|\\+)\\s*${sym}(?![a-z])`, "i").test(c) ? 1 : 0;
    };
    if (/D/.test(c)) {
      const v: Vec3 = [coef("D"), coef("L"), coef("Lr")];
      return [v[0] * dv[0] + v[1] * dv[1] + v[2] * dv[2], c];
    }
    return [fac(dv, "LC2"), "LC2"];
  };

  // ---- topological marks
  const topo = new Map<string, TopoElement>();
  const mark = (e: string, reason: string, chain: string[]) => {
    if (!model.nodes.has(e)) return;
    let t = topo.get(e);
    if (!t)
      topo.set(e, (t = {
        element: e, kind: kindOf(e), name: name(e), reasons: [], chain: [...chain, e],
        provenance: provenance("impact", RULES.topological, "rule", runInputs),
      }));
    if (!t.reasons.includes(reason)) t.reasons.push(reason);
  };

  // the column stack: the column and everything at its plan position (pier, splices); its foundation chain
  const c0 = model.columns.get(column)!;
  const stack = [...model.columns.entries()].filter(([, p]) => dist(p, c0) <= STACK_TOL).map(([id]) => id);
  const verb = remove ? "removed" : `moved (${fmt(dx)}, ${fmt(dy)}) m`;
  const chain0 = [column];
  mark(column, `${name(column) ?? column} ${verb}: tributary area and axial load change`, []);
  const foundation = new Set<string>();
  for (const s of stack) {
    if (s !== column) mark(s, "in the moved column's stack (same plan position)", chain0);
    for (const b of below(model, s)) {
      foundation.add(b);
      mark(b, `${kindOf(b)} under the moved column${kindOf(b) === "footing" ? "; size from the new axial load" : ""}`, chain0);
    }
  }
  const movedFooting = [...foundation].find((f) => model.footings.has(f)) ?? null;
  const carriedByStack = (): [string, End][] => stack.flatMap((s) => model.carried.get(s) ?? []);

  // ---- geometry
  let geo = new Map<string, Geo>();
  const merged: { level: string | null; members: [string, string]; span: number }[] = [];
  const reframed: { member: string; end: End; onto: string }[] = [];
  if (remove) {
    const into = carriedByStack().filter(([m]) => model.members.get(m)?.kind === "beam");
    const byLevel = new Map<string | null, [string, End][]>();
    for (const x of into) {
      const lv = model.members.get(x[0])!.levelId;
      (byLevel.get(lv) ?? byLevel.set(lv, []).get(lv)!).push(x);
    }
    for (const [lv, ms] of byLevel) {
      let best: [number, string, string] | null = null;
      for (let i = 0; i < ms.length; i++)
        for (let j = i + 1; j < ms.length; j++) {
          const a = model.members.get(ms[i]![0])!;
          const b = model.members.get(ms[j]![0])!;
          const ua: P2 = [a.p2[0] - a.p1[0], a.p2[1] - a.p1[1]];
          const ub: P2 = [b.p2[0] - b.p1[0], b.p2[1] - b.p1[1]];
          const cross = Math.abs(ua[0] * ub[1] - ua[1] * ub[0]) / (Math.hypot(...ua) * Math.hypot(...ub));
          if (cross > 0.05) continue;
          const tot = spanOf(a) + spanOf(b);
          if (!best || tot < best[0]) best = [tot, a.id, b.id];
        }
      if (!best) continue;
      merged.push({ level: lv, members: [best[1], best[2]], span: best[0] });
      for (const [m, e] of ms) if (m !== best[1] && m !== best[2]) reframed.push({ member: m, end: e, onto: `${best[1]}+${best[2]}` });
    }
    for (const mg of merged) {
      for (const m of mg.members) mark(m, `merged into one transfer member spanning ${fmt(mg.span)} m (column removed)`, chain0);
      notes.push(`${mg.members.map((m) => name(m) ?? m).join(" + ")} become one ${fmt(mg.span)} m transfer member - NEW calc needed`);
    }
    for (const rf of reframed) mark(rf.member, `now frames into the transfer member ${rf.onto} instead of ${name(column) ?? column}`, chain0);
  } else {
    geo = movedGeometry(model, carriedByStack(), [c0[0] + dx, c0[1] + dy], name(column) ?? column);
    for (const [mid, v] of geo) mark(mid, `span ${fmt(v.L0)} -> ${fmt(v.L1)} m (${v.why})`, chain0);
  }

  // effective support state after re-framing
  const effSup = new Map<string, Partial<Record<End, string>>>();
  for (const m of model.members.values()) effSup.set(m.id, { ...m.sup });
  const effCarried = new Map<string, [string, End][]>();
  for (const [s, v] of model.carried) effCarried.set(s, [...v]);
  for (const [mid, v] of geo)
    for (const [end, ns] of Object.entries(v.reframe ?? {}) as [End, string][]) {
      const old = effSup.get(mid)?.[end];
      effSup.get(mid)![end] = ns;
      if (old) effCarried.set(old, (effCarried.get(old) ?? []).filter(([m, e]) => !(m === mid && e === end)));
      (effCarried.get(ns) ?? effCarried.set(ns, []).get(ns)!).push([mid, end]);
      if (old) mark(old, `${name(mid) ?? mid} no longer frames into it (re-framed onto ${name(ns) ?? ns})`, [column, mid]);
    }

  // ---- affected members: moved / merged / re-framed, plus every beam downstream of one
  const affected = new Set<string>(remove ? [...merged.flatMap((m) => m.members), ...reframed.map((r) => r.member)] : geo.keys());
  const downOf = (m: string) => Object.values(effSup.get(m) ?? {}).filter((x): x is string => !!x);
  for (const m of [...affected]) {
    const seen = new Set<string>([m]);
    const q: [string, string][] = downOf(m).map((s) => [s, m]);
    while (q.length) {
      const [s, via] = q.shift()!;
      if (seen.has(s)) continue;
      seen.add(s);
      if (model.members.get(s)?.kind === "beam" && !affected.has(s)) {
        affected.add(s);
        mark(s, `carries ${name(via) ?? via}: point load position / magnitude changes`, [column, m]);
      }
      for (const n of downOf(s)) q.push([n, s]);
    }
  }

  // ---- loads: the calc's stated line loads / reactions, or (no beam facts) a unit area load
  const beamFact = (m: string) => factOf(m, ["beam"]);
  const basis: Basis = facts.some((f) => f.kind === "beam" && f.lineLoad) ? "stated loads" : "unit area load";
  if (basis === "unit area load")
    assumptions.push(
      "no calc states beam line loads: the screen uses a unit area load on each beam's tributary width (geometry only); demands are compared as ratios, never as values",
    );
  else assumptions.push("beam self weight added from the W-shape designation's nominal weight (lb/ft) where the profile names one");
  // stated values are in working units (facts.ts: kip, klf, kip*ft): solve in feet so line loads and
  // point loads (reactions) combine consistently; geometry stays in metres everywhere else
  const ls = basis === "stated loads" ? 1 / FT : 1;
  const spanSolve = (Lm: number, w: Vec3, ptsM: [number, Vec3][], roof: boolean): SpanResult => {
    const r = solveSpan(Lm * ls, w, ptsM.map(([a, p]) => [a * ls, p] as [number, Vec3]), roof);
    return { ...r, L: Lm, lb: r.lb / ls };
  };
  const trib = new Map<string, number>();
  const tributary = (m: Member): number => {
    if (trib.has(m.id)) return trib.get(m.id)!;
    let t = 0;
    if (!(model.carried.get(m.id) ?? []).some(([c]) => model.members.get(c)?.kind === "beam")) {
      const u: P2 = [m.p2[0] - m.p1[0], m.p2[1] - m.p1[1]];
      const L = Math.hypot(...u);
      const n: P2 = [-u[1] / L, u[0] / L];
      let left = Infinity;
      let right = Infinity;
      for (const o of model.members.values()) {
        if (o.id === m.id || o.kind !== "beam" || o.levelId !== m.levelId) continue;
        const uo: P2 = [o.p2[0] - o.p1[0], o.p2[1] - o.p1[1]];
        if (Math.abs(u[0] * uo[1] - u[1] * uo[0]) / (L * Math.hypot(...uo)) > 0.087) continue; // 5 deg
        const s = (p: P2) => ((p[0] - m.p1[0]) * u[0] + (p[1] - m.p1[1]) * u[1]) / L;
        const lo = Math.min(s(o.p1), s(o.p2));
        const hi = Math.max(s(o.p1), s(o.p2));
        if (Math.min(hi, L) - Math.max(lo, 0) < 0.25 * L) continue; // must overlap along the span
        const off = (o.p1[0] - m.p1[0]) * n[0] + (o.p1[1] - m.p1[1]) * n[1];
        if (off > 1e-3) left = Math.min(left, off);
        if (off < -1e-3) right = Math.min(right, -off);
      }
      t = (Number.isFinite(left) ? left / 2 : 0) + (Number.isFinite(right) ? right / 2 : 0);
    }
    trib.set(m.id, t);
    return t;
  };
  const wOf = (m: Member): Vec3 | null => {
    if (m.kind !== "beam") return null;
    if (basis === "unit area load") return [tributary(m), 0, 0];
    const f = beamFact(m.id);
    if (!f?.lineLoad) return null;
    const sw = /klf|k\/ft|kip\/ft/i.test(f.lineLoad.unit) ? (memberWeightKlf(m.profile) ?? 0) : 0;
    return [(f.lineLoad.dead ?? 0) + sw, f.lineLoad.live ?? 0, f.lineLoad.roofLive ?? 0];
  };
  // stated reactions of a member not in the solve set (hackathon: the record's R_i / R_j)
  const baseMemo = new Map<string, SpanResult | null>();
  const baseSolve = (mid: string, depth = 0): SpanResult | null => {
    if (baseMemo.has(mid)) return baseMemo.get(mid)!;
    const m = model.members.get(mid);
    const w = m ? wOf(m) : null;
    let r: SpanResult | null = null;
    if (m && w && depth < 20) {
      const pts: [number, Vec3][] = [];
      for (const [c, ce] of model.carried.get(mid) ?? []) {
        const rv = baseReaction(c, ce, m.roof, depth + 1);
        const cm = model.members.get(c);
        if (rv && cm) pts.push([dist(m.p1, ce === "i" ? cm.p1 : cm.p2), rv]);
      }
      r = spanSolve(spanOf(m), w, pts, m.roof);
    }
    baseMemo.set(mid, r);
    return r;
  };
  const baseReaction = (c: string, end: End, carrierRoof: boolean, depth = 0): Vec3 | null => {
    if (basis === "stated loads") {
      const f = beamFact(c);
      const r = f?.reactions?.[end];
      if (!r) return null;
      const lv = r.live ?? 0;
      return carrierRoof ? [r.dead ?? 0, 0, lv + (r.roofLive ?? 0)] : [r.dead ?? 0, lv, r.roofLive ?? 0];
    }
    const s = baseSolve(c, depth);
    return s ? (end === "i" ? s.Ri : s.Rj) : null;
  };

  // carried members before their supports (topological order on the affected set)
  const order = topoOrder([...affected], (m) => downOf(m).filter((s) => affected.has(s)));
  const solve = (g: Map<string, Geo>, carried: Map<string, [string, End][]>) => {
    const out = new Map<string, SpanResult>();
    for (const mid of order) {
      const m = model.members.get(mid);
      const w = m ? wOf(m) : null;
      if (!m || !w) continue;
      const p1 = g.get(mid)?.p1 ?? m.p1;
      const p2 = g.get(mid)?.p2 ?? m.p2;
      const pts: [number, Vec3][] = [];
      for (const [c, ce] of carried.get(mid) ?? []) {
        const cm = model.members.get(c);
        if (!cm || cm.kind !== "beam") continue;
        const done = out.get(c);
        const rv = done ? (ce === "i" ? done.Ri : done.Rj) : baseReaction(c, ce, m.roof);
        if (!rv) continue;
        const cp = g.get(c)?.[ce === "i" ? "p1" : "p2"] ?? (ce === "i" ? cm.p1 : cm.p2);
        pts.push([dist(p1, cp), rv]);
      }
      out.set(mid, spanSolve(dist(p1, p2), w, pts, m.roof));
    }
    return out;
  };
  // the same local model before and after: changes come from the geometry change alone
  const before = solve(new Map(), model.carried);
  const after = solve(geo, effCarried);

  const changes = new Map<string, GeometryChange[]>();
  type RawChange = Omit<GeometryChange, "before" | "after"> & { before: number; after: number; unit: Unit };
  const addChange = (e: string, c: RawChange) => {
    const { unit, before: b0, after: a0, ...rest } = c;
    (changes.get(e) ?? changes.set(e, []).get(e)!).push({ ...rest, before: q(b0, unit), after: q(a0, unit) });
  };
  const ratio = (a: number, b: number) => (Math.abs(a) > 1e-12 ? b / a : Math.abs(b) > 1e-12 ? Infinity : 1);
  const lbasis = basis;
  // unit "1": a relative magnitude (unit area load, or deflection with EI = 1)
  const loadUnit: Unit = basis === "unit area load" ? "1" : "kip";
  const momUnit: Unit = basis === "unit area load" ? "1" : "kip*ft";
  for (const [mid, r] of after) {
    const b = before.get(mid)!;
    const m = model.members.get(mid)!;
    addChange(mid, { quantity: "moment", before: b.mu, after: r.mu, ratio: ratio(b.mu, r.mu), unit: momUnit, basis: lbasis });
    addChange(mid, { quantity: "span", before: spanOf(m), after: r.L, ratio: ratio(spanOf(m), r.L), unit: "m", basis: "geometry" });
    addChange(mid, { quantity: "shear", before: b.vu, after: r.vu, ratio: ratio(b.vu, r.vu), unit: loadUnit, basis: lbasis });
    addChange(mid, { quantity: "deflection_live", before: b.dLive, after: r.dLive, ratio: ratio(b.dLive, r.dLive), unit: "1", basis: lbasis });
    addChange(mid, { quantity: "deflection_total", before: b.dTotal, after: r.dTotal, ratio: ratio(b.dTotal, r.dTotal), unit: "1", basis: lbasis });
    addChange(mid, { quantity: "end_reaction_i", before: ru(b.Ri), after: ru(r.Ri), ratio: ratio(ru(b.Ri), ru(r.Ri)), unit: loadUnit, basis: lbasis });
    addChange(mid, { quantity: "end_reaction_j", before: ru(b.Rj), after: ru(r.Rj), ratio: ratio(ru(b.Rj), ru(r.Rj)), unit: loadUnit, basis: lbasis });
  }
  // members whose loads the screen cannot form (no stated loads) still sit on the path
  for (const m of affected) if (!after.has(m) && model.members.get(m)?.kind === "beam" && basis === "stated loads")
    notes.push(`${name(m) ?? m}: no calc states its line loads - kept on the path without a screened number`);

  const est = new Map<string, Omit<Estimate, "provenance">>();
  const frameRatio = new Map<string, number>(); // frame_girder fact -> frame moment ratio
  const resolvedIds = [...after.keys()];
  const mergedIds = merged.flatMap((mg) => mg.members);

  // ---- utilisation estimates for re-solved beams (only where a calc states a utilisation)
  for (const mid of resolvedIds) {
    const f = beamFact(mid);
    if (!f) continue;
    const ch = Object.fromEntries((changes.get(mid) ?? []).map((c) => [c.quantity, c.ratio]));
    const L0 = spanOf(model.members.get(mid)!);
    const L1 = after.get(mid)!.L;
    // flexure capacity at the new unbraced length (girders: point-load spacing), when a shape table
    // and the model's material give what AISC F2 needs; else the printed capacity is held
    const mm = model.members.get(mid)!;
    const fsec = flexSection(sectionIn(mm.profile));
    const fy = yieldFromMaterial(model.nodes.get(mid)?.material);
    const lb0 = before.get(mid)!.lb / 0.0254;
    const lb1 = after.get(mid)!.lb / 0.0254;
    const mnRatio = fsec && fy && Math.abs(lb1 - lb0) > 1e-6 ? phiMn(fsec, lb1, fy) / phiMn(fsec, lb0, fy) : 1;
    const scale: Record<string, number> = {
      flexure: (ch.moment ?? 1) / mnRatio,
      shear: ch.shear ?? 1,
      deflection_live: ((ch.deflection_live ?? 1) * L0) / (L1 || L0),
      deflection_total: ((ch.deflection_total ?? 1) * L0) / (L1 || L0),
    };
    // deflection from the stated loads and the shape table's Ix (kip, ft): the printed deflection is
    // rounded to 0.01 in, so with Ix the new deflection is computed, not scaled; the allowable (L/360,
    // L/240) scales with the span
    const absolute: Record<string, number> = {};
    const ix = sectionIn(mm.profile)?.Ix;
    if (ix && ls !== 1) {
      const EI = 29000 * 144 * (ix / 20736);
      for (const c of f.checks ?? []) {
        const cap = c.capacity?.value;
        if (!cap || (c.mode !== "deflection_live" && c.mode !== "deflection_total")) continue;
        const d = c.mode === "deflection_live" ? after.get(mid)!.dLive : after.get(mid)!.dTotal;
        absolute[c.mode] = ((d / EI) * 12) / ((cap * L1) / L0);
      }
    }
    const e = scaleChecks(
      f, scale,
      "local statics, " + basis + (mnRatio !== 1 ? `; flexure capacity x ${fmt(mnRatio, 3)} for Lb ${fmt(lb0 / 12, 2)} -> ${fmt(lb1 / 12, 2)} ft (AISC F2/F3, supplied shape table)` : "") +
        (Object.keys(absolute).length ? "; deflection from the stated loads and the supplied Ix against the printed allowable x span ratio" : ""),
      absolute,
    );
    if (e) est.set(mid, { ...e, element: mid });
    const fg = factOf(mid, ["frame_girder"]);
    if (fg && fg.utilisation != null) {
      const gr = ch.moment ?? 1;
      frameRatio.set(fg.id, gr);
      let uc = fg.utilisation * gr;
      let how = `frame utilisation x gravity moment ratio ${fmt(gr, 3)} (capacity held)`;
      const cv = fg.chevron;
      if (cv && fg.governs === "F2.3") {
        const lu = 1 / FT; // span in feet (chevron values are in kip / kip*ft, facts.ts)
        const m = (cv.unbalancedLoad.value * (L1 * lu)) / 4 + cv.gravityMoment.value * gr;
        const m0 = (cv.unbalancedLoad.value * (L0 * lu)) / 4 + cv.gravityMoment.value;
        frameRatio.set(fg.id, m0 ? m / m0 : 1);
        const pr = cv.axial.value / cv.axialCapacity.value;
        const mr = m / cv.momentCapacity.value;
        uc = cv.equation === "H1-1a" ? pr + (8 / 9) * mr : pr / 2 + mr;
        how = `AISC 341 F2.3: Pv x new span / 4 + gravity moment x ${fmt(gr, 3)}, axial held, ${cv.equation} with the printed capacities`;
      }
      const cur = est.get(mid);
      const fe = { frameUtilisationBefore: fg.utilisation, frameUtilisationAfter: round(uc, 3) };
      if (cur) est.set(mid, { ...cur, ...fe, scaledBy: `${cur.scaledBy}; frame: ${how}` });
      else
        est.set(mid, {
          element: mid, method: "estimate", scaledBy: `frame: ${how}`, utilisationBefore: null,
          utilisationAfter: round(uc, 3), governs: "frame", source: fg.source, fact: fg.id, ...fe,
        });
    }
  }

  // ---- connections at both ends of every re-solved (and merged) member
  const newRx = new Map<string, Record<End, Vec3>>();
  const oldRx = new Map<string, Record<End, Vec3>>();
  for (const mid of resolvedIds) {
    const a = after.get(mid)!;
    const b = before.get(mid)!;
    newRx.set(mid, { i: a.Ri, j: a.Rj });
    oldRx.set(mid, { i: b.Ri, j: b.Rj });
  }
  for (const mid of [...resolvedIds, ...mergedIds]) {
    const m = model.members.get(mid)!;
    for (const end of ["i", "j"] as End[]) {
      const cx = m.via[end];
      if (!cx) continue;
      mark(cx, `end reaction of ${name(mid) ?? mid} changes`, [column, mid]);
      const nr = newRx.get(mid)?.[end];
      const or = oldRx.get(mid)?.[end];
      if (!nr || !or) continue;
      const r0 = ru(or);
      const r1 = ru(nr);
      addChange(cx, { quantity: "connection_reaction", before: r0, after: r1, ratio: ratio(r0, r1), unit: loadUnit, basis: lbasis });
      const f = factOf(cx, ["connection"]);
      if (!f) continue;
      const cap = f.capacity?.value ?? null;
      let ruNew: number | null = null;
      let uc: number | null = null;
      let how = "";
      if (basis === "stated loads" && cap && utilOf(f) != null) {
        ruNew = r1;
        uc = utilOf(f)! * ratio(r0, r1);
        how = `stated utilisation x end reaction ratio ${fmt(ratio(r0, r1), 3)} (local statics, stated loads; new end reaction ${fmt(r1, 1)} vs stated capacity ${fmt(cap, 1)})`;
      } else if (basis === "stated loads" && cap) {
        ruNew = r1;
        uc = r1 / cap;
        how = `new end reaction ${fmt(r1, 1)} (local statics, stated loads) / stated capacity ${fmt(cap, 1)}`;
      } else {
        const u0 = utilOf(f);
        if (u0 == null) continue;
        uc = u0 * ratio(r0, r1);
        ruNew = f.demand ? f.demand.value * ratio(r0, r1) : null;
        how = `stated utilisation x end reaction ratio ${fmt(ratio(r0, r1), 3)} (${basis})`;
      }
      const e: Omit<Estimate, "provenance"> = {
        element: cx, method: "estimate", scaledBy: how, utilisationBefore: utilOf(f), utilisationAfter: round(uc, 3),
        governs: "connection", source: f.source, fact: f.id,
      };
      if (cap && ruNew != null && ruNew > cap && f.detailType) {
        const fam = f.detailType.replace(/\*$/, "").replace(/-[^-]*$/, "") + "-";
        const sec = sectionIn(m.profile);
        const dIn = sec?.d ?? (m.depth != null ? m.depth / 0.0254 : null);
        // T-distance bolt limit (hackathon): d - 2 (tf + 3/4") - 1", 3" pitch. Without a shape table tf
        // is unknown and taken as 0 - an upper bound on the bolts that fit (said in `why`).
        const tf = sec?.tf ?? null;
        const nmax = dIn != null ? Math.floor((dIn - 2 * ((tf ?? 0) + 0.75) - 1) / 3) : Infinity;
        const tfNote = tf != null ? `tf ${fmt(tf, 3)} in from the supplied shape table` : "flange thickness not supplied, taken as 0";
        const better = typicals
          .filter((t) => t.detailType!.startsWith(fam) && t.capacity!.value >= ruNew! && (t.bolts ?? 0) <= nmax)
          .sort((p, q) => p.capacity!.value - q.capacity!.value);
        e.nextTypical = better[0]?.detailType ?? null;
        e.special = !better.length;
        e.why = better.length
          ? `next typical ${better[0]!.detailType} (bolt row limit ${nmax}: ${tfNote})`
          : `no typical with capacity >= ${fmt(ruNew, 1)} fits a ${fmt(dIn ?? NaN, 1)} in deep web (${nmax} bolts max: ${tfNote})`;
      }
      est.set(cx, e);
    }
  }

  // ---- columns, footings, piers, base plates: reaction deltas
  const dcol = new Map<string, Vec3>();
  const addD = (c: string, d: Vec3) => {
    const v = dcol.get(c) ?? [0, 0, 0];
    dcol.set(c, [v[0] + d[0], v[1] + d[1], v[2] + d[2]]);
  };
  for (const mid of resolvedIds)
    for (const end of ["i", "j"] as End[]) {
      const s = effSup.get(mid)?.[end];
      if (s && model.columns.has(s)) {
        const o = oldRx.get(mid)![end];
        const n = newRx.get(mid)![end];
        addD(s, [n[0] - o[0], n[1] - o[1], n[2] - o[2]]);
      }
    }
  if (remove) {
    for (const mg of merged) {
      const [a, b] = mg.members.map((x) => model.members.get(x)!) as [Member, Member];
      const farEnd = (m: Member): End => (stack.includes(m.sup.j ?? "") ? "i" : "j");
      const fa = farEnd(a);
      const fb = farEnd(b);
      const pa = fa === "i" ? a.p1 : a.p2;
      const pb = fb === "i" ? b.p1 : b.p2;
      const L = dist(pa, pb);
      const wa = wOf(a);
      const wb = wOf(b);
      if (!wa || !wb) continue;
      const la = spanOf(a);
      const lb = spanOf(b);
      const w: Vec3 = [0, 1, 2].map((k) => (wa[k]! * la + wb[k]! * lb) / L) as Vec3;
      const pts: [number, Vec3][] = [];
      for (const m of [a, b])
        for (const [c, ce] of model.carried.get(m.id) ?? []) {
          const cm = model.members.get(c);
          const rv = cm?.kind === "beam" ? baseReaction(c, ce, a.roof) : null;
          if (cm && rv) pts.push([dist(pa, ce === "i" ? cm.p1 : cm.p2), rv]);
        }
      for (const rf of reframed) {
        if (model.members.get(rf.member)!.levelId !== a.levelId) continue;
        const rv = baseReaction(rf.member, rf.end, a.roof);
        if (rv) pts.push([la, rv]);
      }
      const r = spanSolve(L, w, pts, a.roof);
      const tid = `NEW:${a.id}+${b.id}`;
      // utilisation of the transfer member at the heavier member's stated flexure capacity
      const heavier = [a, b].sort((p, q) => (memberWeightKlf(q.profile) ?? 0) - (memberWeightKlf(p.profile) ?? 0))[0]!;
      const hf = beamFact(heavier.id);
      const phiMn = hf?.checks?.find((c) => c.mode === "flexure")?.capacity?.value;
      if (hf && phiMn && basis === "stated loads")
        est.set(tid, {
          element: tid, method: "estimate", utilisationBefore: null, utilisationAfter: round(r.mu / phiMn, 3), governs: "flexure",
          scaledBy: `transfer member moment ${fmt(r.mu, 1)} (local statics: both halves' stated loads + re-framed reactions) / ${name(heavier.id) ?? heavier.id}'s stated flexure capacity ${fmt(phiMn, 1)}`,
          source: hf.source, fact: hf.id,
        });
      notes.push(`${tid}: required size not estimated - no section table in the model (the hackathon sized it from the AISC table)`);
      for (const [end, m, mEnd] of [["i", a, fa], ["j", b, fb]] as [End, Member, End][]) {
        const s = m.sup[mEnd];
        const old = baseReaction(m.id, mEnd, m.roof) ?? (basis === "unit area load" ? (baseSolve(m.id)?.[mEnd === "i" ? "Ri" : "Rj"] ?? null) : null);
        if (!s || !old) continue;
        const nw = end === "i" ? r.Ri : r.Rj;
        addD(s, [nw[0] - old[0], nw[1] - old[1], nw[2] - old[2]]);
      }
    }
  }
  // unit/stated column load before: every member reaction into the stack (for the ratio)
  const colLoad0 = (c: string): number => {
    let s = 0;
    for (const [m, e] of model.carried.get(c) ?? []) {
      if (model.members.get(m)?.kind !== "beam") continue;
      const rv = basis === "stated loads" ? baseReaction(m, e, model.members.get(m)!.roof) : baseReaction(m, e, false);
      if (rv) s += fac(rv, "LC2");
    }
    return s;
  };
  for (const [c, dv] of dcol) {
    if (remove && stack.includes(c)) continue;
    const cf = factOf(c, ["column"]);
    const [dpu, comboUsed] = gravityIncrement(dv, cf?.combination);
    const pu0Stated = cf?.axial?.value ?? cf?.demand?.value ?? null;
    const statedAbs = basis === "stated loads" && pu0Stated != null;
    const pu0 = statedAbs ? pu0Stated! : colLoad0(c);
    const pu1 = pu0 + dpu;
    const r = ratio(pu0, pu1);
    addChange(c, {
      quantity: "column_load", before: pu0, after: pu1, ratio: r, unit: statedAbs ? "kip" : loadUnit,
      basis: statedAbs ? "stated loads" : lbasis,
    });
    if (Math.abs(dpu) / Math.max(Math.abs(pu0), 1e-6) > TOUCH || c === column)
      mark(c, `axial changes by ${fmt(dpu, 1)} ${statedAbs ? "kip" : "(unit load)"} (reactions of re-spanned members)`, [column]);
    if (cf && utilOf(cf) != null)
      est.set(c, {
        element: c, method: "estimate", utilisationBefore: utilOf(cf), utilisationAfter: round(utilOf(cf)! * r, 3), governs: "axial",
        scaledBy: `stated utilisation x axial ratio ${fmt(r, 3)} (${statedAbs ? `stated Pu + reaction deltas factored ${comboUsed}, stated loads` : basis}); eccentric moments held`,
        source: cf.source, fact: cf.id,
      });
    const chainBelow = below(model, c);
    // the column's base plate and pier carry its axial load: same change (the footing gets its own below)
    for (const x of chainBelow)
      if (!model.footings.has(x))
        addChange(x, { quantity: "column_load", before: pu0, after: pu1, ratio: r, unit: statedAbs ? "kip" : loadUnit, basis: statedAbs ? "stated loads" : lbasis });
    const fid = chainBelow.find((x) => model.footings.has(x));
    if (!fid) continue;
    const ff = factOf(fid, ["footing"]);
    const ds = dv[0] + dv[1] + dv[2];
    const ps0Stated = ff?.serviceLoad?.value ?? null;
    const fAbs = basis === "stated loads" && ps0Stated != null;
    let ps0: number;
    if (fAbs) ps0 = ps0Stated!;
    else {
      let s = 0;
      for (const [m, e] of model.carried.get(c) ?? []) {
        const rv = model.members.get(m)?.kind === "beam" ? baseReaction(m, e, false) : null;
        if (rv) s += rv[0] + rv[1] + rv[2];
      }
      ps0 = s;
    }
    const ps1 = ps0 + ds;
    const fr = ratio(ps0, ps1);
    addChange(fid, { quantity: "footing_load", before: ps0, after: ps1, ratio: fr, unit: fAbs ? "kip" : loadUnit, basis: fAbs ? "stated loads" : lbasis });
    if (ff) {
      const fp = model.footings.get(fid)!;
      const qa = ff.allowableBearing;
      const u0 = utilOf(ff);
      let e: Omit<Estimate, "provenance"> | null = null;
      if (fAbs && qa) {
        const B0 = Math.min(fp.bx, fp.by) / FT;
        const breq = Math.max(4.0, Math.ceil(Math.sqrt(Math.max(ps1, 0) / qa.value) * 2) / 2);
        e = {
          element: fid, method: "estimate", utilisationBefore: u0, utilisationAfter: round(ps1 / (qa.value * B0 * B0), 3), governs: "bearing",
          scaledBy: `bearing: stated service load ${fmt(ps0, 1)} + reaction deltas ${fmt(ds, 1)} kip over the model's ${fmt(B0, 2)} ft footing at the stated qa ${qa.value} ksf`,
          source: ff.source, fact: ff.id, requiredWidth: q(breq, "ft"),
        };
      } else if (u0 != null)
        e = {
          element: fid, method: "estimate", utilisationBefore: u0, utilisationAfter: round(u0 * fr, 3), governs: "bearing",
          scaledBy: `stated utilisation x service load ratio ${fmt(fr, 3)} (${basis}); no allowable bearing stated, so no required size`,
          source: ff.source, fact: ff.id,
        };
      if (e) est.set(fid, e);
    }
    if (Math.abs(ps1 - ps0) / Math.max(Math.abs(ps0), 1e-6) > TOUCH || c === column) {
      mark(fid, `column load changes by ${fmt(ds, 1)} ${fAbs ? "kip" : "(unit load)"} service`, [column, c]);
      for (const x of chainBelow) if (x !== fid) mark(x, "column load changes", [column, c]);
    }
  }

  // ---- foundations: new footing position vs neighbours and grade beams
  const clashes: Clash[] = [];
  const tied = (gb: { p1: P2; p2: P2 }, fid: string) => {
    const f = model.footings.get(fid)!;
    return [gb.p1, gb.p2].some((p) => Math.abs(p[0] - f.cx) <= f.bx / 2 + 0.3 && Math.abs(p[1] - f.cy) <= f.by / 2 + 0.3);
  };
  if (movedFooting) {
    for (const gb of model.gradeBeams.values())
      if (tied(gb, movedFooting)) mark(gb.id, `grade beam span changes: ${name(movedFooting) ?? movedFooting} ${remove ? "removed" : "moves"}`, [column, movedFooting]);
    if (!remove) {
      const f0 = model.footings.get(movedFooting)!;
      const fx = f0.cx + dx;
      const fy = f0.cy + dy;
      const req = est.get(movedFooting)?.requiredWidth;
      const breqM = req ? (req.unit === "ft" ? req.value * FT : req.value) : 0; // requiredWidth is in ft
      const B = Math.max(breqM, Math.min(f0.bx, f0.by));
      for (const o of model.footings.values()) {
        if (o.id === movedFooting) continue;
        if (Math.abs(o.cx - fx) < (o.bx + B) / 2 && Math.abs(o.cy - fy) < (o.by + B) / 2)
          clashes.push({ a: movedFooting, b: o.id, kind: "footing-footing" });
      }
      for (const gb of model.gradeBeams.values()) {
        if (tied(gb, movedFooting)) continue;
        const w = gb.width / 2;
        const [x1, y1] = gb.p1;
        const [x2, y2] = gb.p2;
        if (fx + B / 2 > Math.min(x1, x2) - w && fx - B / 2 < Math.max(x1, x2) + w && fy + B / 2 > Math.min(y1, y2) - w && fy - B / 2 < Math.max(y1, y2) + w)
          clashes.push({ a: movedFooting, b: gb.id, kind: "footing-grade_beam" });
      }
      for (const c of clashes) mark(c.b, `clashes with the moved footing ${name(movedFooting) ?? movedFooting}`, [column, movedFooting]);
    }
  }

  // ---- lateral (needs calc facts: which calcs are lateral-system calcs, and their frame line)
  const lateral: string[] = [];
  const frames = [...new Set(stack.flatMap((s) => (factsOf.get(s) ?? []).filter((f) => f.role === "lateral" && f.group).map((f) => f.group!)))].sort();
  for (const fr of frames) {
    lateral.push(`${name(column) ?? column} is in ${fr}: frame stiffness, drift and force distribution change - re-run the frame analysis`);
    for (const f of facts)
      if (f.role === "lateral" && f.group === fr) for (const e of f.elements) mark(e, `member of ${fr} - frame re-analysis`, [column]);
  }
  for (const mid of resolvedIds) {
    const braces = (model.carried.get(mid) ?? []).filter(([c]) => model.members.get(c)?.kind === "brace").map(([c]) => c);
    if (!braces.length) continue;
    const mc = (changes.get(mid) ?? []).find((c) => c.quantity === "moment");
    if (!mc || Math.abs(mc.ratio - 1) <= CHANGE) continue;
    // Brace force change (hackathon _chevron_brace_estimates): the beam and the brace pair share the
    // work-point deflection: d0 = |dM| 12 d_fac L^2 / (9.5 E Ix), R = d0 / (1/k_beam + 1/k_pair) with
    // k_beam = 48 E Ix / L^3, k_pair = 2 E A sin^2 / Lb; each brace takes R / (2 sin). d_fac =
    // (0.9 - 0.2 SDS) / 1.2 (SDS lower bound from a printed ELF row, else 0 - the conservative end).
    // The model has no section properties: with a supplied shape table (beam Ix, brace A) this is the
    // hackathon's formula; without one the brace pair is taken as rigid (k_pair -> infinity), Ix
    // cancels and R = d0 k_beam is an UPPER BOUND - a brace screened as unmoved cannot have moved more.
    const dFac = Math.max(0, 0.9 - 0.2 * (sds ?? 0)) / 1.2;
    const beamSec = sectionIn(model.members.get(mid)!.profile);
    const dM = Math.abs(mc.after.value - mc.before.value);
    const Lin = after.get(mid)!.L / 0.0254;
    const moved: string[] = [];
    for (const br of braces) {
      const bm = model.members.get(br)!;
      const len = Math.hypot(bm.b3[0] - bm.a3[0], bm.b3[1] - bm.a3[1], bm.b3[2] - bm.a3[2]);
      const sin = len ? Math.abs(bm.b3[2] - bm.a3[2]) / len : 0;
      const bf = factOf(br, ["brace"]);
      const p0 = bf?.axial?.value ?? bf?.demand?.value ?? null;
      if (basis !== "stated loads" || !bf || p0 == null || sin <= 0 || !/kip/i.test(bf.axial?.unit ?? bf.demand?.unit ?? "")) {
        mark(br, `gravity on chevron beam ${name(mid) ?? mid} changes (no brace estimate: needs the brace's stated axial and stated beam loads)`, [column, mid]);
        moved.push(br);
        continue;
      }
      const E = 29000;
      const braceSec = sectionIn(bm.profile);
      const lbIn = len / 0.0254;
      const exact = beamSec?.Ix != null && braceSec?.A != null;
      const kBeam = exact ? (48 * E * beamSec!.Ix!) / Lin ** 3 : 1;
      const kPair = exact ? (2 * E * braceSec!.A! * sin * sin) / lbIn : Infinity;
      const dF = exact
        ? ((dM * 12 * dFac * Lin * Lin) / (9.5 * E * beamSec!.Ix!) / (1 / kBeam + 1 / kPair)) / (2 * sin)
        : (dM * 12 * dFac * 48) / (9.5 * Lin * 2 * sin);
      const cap = bf.capacity?.value ?? null;
      const u0 = utilOf(bf);
      est.set(br, {
        element: br, method: "estimate", utilisationBefore: u0,
        utilisationAfter: round(cap ? (p0 + dF) / cap : (u0 ?? 0) * ((p0 + dF) / p0), 3), governs: "axial",
        scaledBy: `stated brace force ${fmt(p0, 1)} + ${exact ? "" : "upper bound "}${fmt(dF, 1)} kip of ${name(mid) ?? mid}'s gravity moment change ${fmt(dM, 1)} kip-ft reaching the work point (${exact ? "beam Ix and brace area from the supplied shape table" : "brace pair taken as rigid: no section properties supplied"}; d_fac ${fmt(dFac, 3)})`,
        source: bf.source, fact: bf.id,
      });
      addChange(br, { quantity: "brace_force", before: p0, after: p0 + dF, ratio: ratio(p0, p0 + dF), unit: "kip", basis: "stated loads" });
      mark(br, `gravity on chevron beam ${name(mid) ?? mid} reaches the brace work point`, [column, mid]);
      if (dF / Math.max(Math.abs(p0), 1e-6) > CHANGE) moved.push(br);
    }
    if (moved.length)
      lateral.push(
        `${name(mid) ?? mid} is a chevron beam: its gravity change moves brace force(s) ${moved.slice(0, 3).map((b) => name(b) ?? b).join(", ")} by > ${CHANGE * 100}% (upper-bound estimate) - brace forces change`,
      );
  }

  // ---- screened subset
  // the quantity an element's screen is decided on: the first one it has, in this order
  const GOV_ORDER = ["moment", "brace_force", "connection_reaction", "footing_load", "column_load"] as const;
  const govOf = (e: string) => {
    const cs = changes.get(e) ?? [];
    for (const gq of GOV_ORDER) {
      const c = cs.find((x) => x.quantity === gq);
      if (c) return c;
    }
    return null;
  };
  const mergedSet = new Set(mergedIds);
  const movesWithColumn = new Set<string>([...stack, ...foundation]);
  const screenedEls: ScreenedElement[] = [];
  const screenOf = new Map<string, boolean>();
  for (const t of topo.values()) {
    const cs = changes.get(t.element) ?? [];
    const gov = govOf(t.element);
    // what moves with the column (its stack and foundation chain) is always re-checked: its position,
    // tributary area and the eccentricity of every reaction on it change, not only its axial load
    const keep = mergedSet.has(t.element) || movesWithColumn.has(t.element) ? true : gov ? Math.abs(gov.ratio - 1) > CHANGE : true;
    screenOf.set(t.element, keep);
    if (keep) {
      const rule = mergedSet.has(t.element)
        ? RULES.screen.merged
        : movesWithColumn.has(t.element)
          ? RULES.screen.movesWithColumn
          : gov
            ? RULES.screen.change
            : RULES.screen.noNumber;
      screenedEls.push({
        element: t.element, kind: t.kind, name: t.name, governing: gov, changes: cs, keptWithoutEstimate: !gov && !mergedSet.has(t.element),
        provenance: provenance("impact", rule, "rule", runInputs),
      });
    }
  }

  // ---- stale rows / calcs
  let staleRows: ImpactResult["staleRows"];
  let stale: StaleCalc[] | undefined;
  if (hasFacts || links.length) {
    const rowMap = new Map<string, StaleRow>();
    const docOf = new Map<string, string>(facts.map((f) => [f.id, f.source.documentSha256]));
    for (const f of facts) {
      const on = f.elements.filter((e) => topo.has(e));
      if (!on.length) continue;
      // a frame-analysis row (drift, force distribution) is stale only when the frame's geometry changes -
      // the moved column is in it - not whenever one of its members is on the gravity path (hackathon rule)
      if (f.kind === "frame" && !(f.group && frames.includes(f.group))) continue;
      // the hackathon rule: the first element of the row with a screened number decides; none -> keep
      const decided = f.elements.find((e) => topo.has(e) && govOf(e) != null);
      const fr = frameRatio.get(f.id);
      // a braced-frame girder's frame row moves with its frame moment estimate, not the gravity re-solve
      const scr = f.elements.some((e) => mergedSet.has(e) || movesWithColumn.has(e))
        ? true
        : fr != null
          ? Math.abs(fr - 1) > CHANGE
          : decided
            ? screenOf.get(decided)!
            : true;
      rowMap.set(f.id, {
        fact: f.id, calcKey: f.source.calcKey, screened: scr, elements: on,
        provenance: provenance("impact", RULES.staleRow, "rule", [input.graphSha256, f.source.documentSha256]),
      });
    }
    if (hasFacts) staleRows = [...rowMap.values()].sort((a, b) => a.fact.localeCompare(b.fact));
    const byCalc = new Map<string, Omit<StaleCalc, "provenance">>();
    const get = (k: string) => byCalc.get(k) ?? byCalc.set(k, { calcKey: k, rows: [], elements: [], screened: false, reasons: [] }).get(k)!;
    for (const r of rowMap.values()) {
      const s = get(r.calcKey);
      s.rows.push(r.fact);
      for (const e of r.elements) if (!s.elements.includes(e)) s.elements.push(e);
      s.screened ||= r.screened;
    }
    for (const l of links) {
      if (!topo.has(l.global_id)) continue;
      const s = get(l.calc_key);
      if (!s.elements.includes(l.global_id)) s.elements.push(l.global_id);
      s.screened ||= screenOf.get(l.global_id) ?? true;
    }
    for (const s of byCalc.values()) {
      s.rows.sort();
      s.elements.sort();
      s.reasons = [...new Set(s.elements.flatMap((e) => topo.get(e)?.reasons ?? []))].slice(0, 5);
    }
    // a calc known only from links rests on the graph alone here (the link's own provenance names its PDF)
    stale = [...byCalc.values()]
      .sort((a, b) => a.calcKey.localeCompare(b.calcKey))
      .map((sc) => ({ ...sc, provenance: provenance("impact", RULES.staleCalc, "rule", [input.graphSha256], sc.rows.map((r) => docOf.get(r))) }));
  }

  const result: ImpactResult = {
    engine: ENGINE_VERSION,
    move,
    inputs: runInputs,
    topological: [...topo.values()].sort((a, b) => a.element.localeCompare(b.element)),
    screened: screenedEls.sort((a, b) => a.element.localeCompare(b.element)),
    geometry: [...geo].map(([element, v]) => {
      const m = model.members.get(element)!;
      const g: MemberGeometry = { element, before: { p1: m.p1, p2: m.p2 }, after: { p1: v.p1, p2: v.p2 }, why: v.why };
      if (v.reframe) g.reframe = v.reframe as Record<End, string>;
      return g;
    }),
    clashes,
    lateral,
    notes,
    assumptions,
    labels: {
      topological: "load path (supports through connection nodes) + re-framing + foundations + lateral system membership (from calc facts)",
      screened: `governing geometry (span / moment / column load / footing load / end reaction) changes > ${CHANGE * 100}%, from the same local statics before and after`,
      estimates: "estimate - a printed value scaled by a geometric ratio; not a recalculation",
    },
  };
  if (hasFacts) {
    const ruleOf = (e: Omit<Estimate, "provenance">): string => {
      const k = e.element.startsWith("NEW:") ? "transfer" : kindOf(e.element);
      if (k === "transfer") return RULES.estimate.transfer;
      if (k === "connection") return RULES.estimate.connection;
      if (k === "column") return RULES.estimate.column;
      if (k === "footing") return RULES.estimate.footing;
      if (k === "brace") return RULES.estimate.brace;
      return e.governs === "frame" ? RULES.estimate.frameGirder : RULES.estimate.beam;
    };
    result.estimates = Object.fromEntries(
      [...est]
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([k, e]) => [k, { ...e, provenance: provenance("impact", ruleOf(e), "estimate", [input.graphSha256, e.source.documentSha256]) }]),
    );
    result.health = {
      ...healthOf({ model, column, remove, est, facts, factsOf, staleRows: staleRows ?? [], clashes, lateral, frames, name }),
      provenance: provenance("health", RULES.health, "estimate", runInputs),
    };
  }
  if (staleRows) result.staleRows = staleRows;
  if (stale) result.stale = stale;
  return result;
}

// ------------------------------------------------------------------ helpers

function movedGeometry(model: Model, carriedByCol: [string, End][], newc: P2, colName: string): Map<string, Geo> {
  const geo = new Map<string, Geo>();
  for (const [mid, end] of carriedByCol) {
    const m = model.members.get(mid);
    if (!m) continue;
    const p1: P2 = end === "i" ? [...newc] : [...m.p1];
    const p2: P2 = end === "j" ? [...newc] : [...m.p2];
    geo.set(mid, { p1, p2, why: `frames into ${colName} (end ${end})`, L0: 0, L1: 0 });
  }
  let frontier = [...geo.keys()];
  while (frontier.length) {
    const nxt: string[] = [];
    for (const sup of frontier) {
      const a = geo.get(sup)!.p1;
      const b = geo.get(sup)!.p2;
      for (const [mid, end] of model.carried.get(sup) ?? []) {
        const m = model.members.get(mid)!;
        const cur = geo.get(mid) ?? { p1: [...m.p1] as P2, p2: [...m.p2] as P2 };
        let p1: P2 = [...cur.p1];
        let p2: P2 = [...cur.p2];
        const other = end === "i" ? p2 : p1;
        const d: P2 = [m.p2[0] - m.p1[0], m.p2[1] - m.p1[1]];
        let hit = lineIntersect(other, d, a, b);
        if (!hit) continue;
        let newSup: string | null = null;
        const seg = dist(a, b);
        const t = ((hit[0] - a[0]) * (b[0] - a[0]) + (hit[1] - a[1]) * (b[1] - a[1])) / Math.max(seg * seg, 1e-9);
        if (t < -1e-6 || t > 1 + 1e-6) {
          // the support no longer spans past this member: it re-frames onto the collinear member on the
          // other side of the moved column (the one whose new span covers it)
          for (const [sib, sv] of geo) {
            if (sib === sup || model.members.get(sib)!.levelId !== model.members.get(sup)!.levelId) continue;
            const hit2 = lineIntersect(other, d, sv.p1, sv.p2);
            if (!hit2) continue;
            const sl = dist(sv.p1, sv.p2);
            const t2 = ((hit2[0] - sv.p1[0]) * (sv.p2[0] - sv.p1[0]) + (hit2[1] - sv.p1[1]) * (sv.p2[1] - sv.p1[1])) / Math.max(sl * sl, 1e-9);
            const ua: P2 = [b[0] - a[0], b[1] - a[1]];
            const ub: P2 = [sv.p2[0] - sv.p1[0], sv.p2[1] - sv.p1[1]];
            if (t2 >= -1e-6 && t2 <= 1 + 1e-6 && Math.abs(ua[0] * ub[1] - ua[1] * ub[0]) / Math.max(seg * sl, 1e-9) < 0.2) {
              newSup = sib;
              hit = hit2;
              break;
            }
          }
        }
        if (end === "i") p1 = [...hit];
        else p2 = [...hit];
        const old = end === "i" ? m.p1 : m.p2;
        if (dist(old, hit) < 1e-6 && !newSup) continue;
        const prev = geo.get(mid);
        const g: Geo = { ...(prev ?? { L0: 0, L1: 0 }), p1, p2, why: `frames into ${model.nodes.get(sup)?.name ?? sup}, which moved with ${colName}` };
        if (newSup) {
          g.reframe = { ...(prev?.reframe ?? {}), [end]: newSup };
          g.why = `re-frames from ${model.nodes.get(sup)?.name ?? sup} onto ${model.nodes.get(newSup)?.name ?? newSup} (moved support no longer spans past it)`;
        }
        geo.set(mid, g);
        nxt.push(mid);
      }
    }
    frontier = nxt;
  }
  for (const [mid, v] of geo) {
    const m = model.members.get(mid)!;
    v.L0 = dist(m.p1, m.p2);
    v.L1 = dist(v.p1, v.p2);
  }
  return geo;
}

function topoOrder(ids: string[], deps: (id: string) => string[]): string[] {
  // carried first: an edge m -> s (m is supported by s) means m comes before s
  const set = new Set(ids);
  const indeg = new Map(ids.map((i) => [i, 0]));
  const out = new Map<string, string[]>();
  for (const m of ids)
    for (const s of deps(m)) {
      if (!set.has(s)) continue;
      indeg.set(s, indeg.get(s)! + 1);
      (out.get(m) ?? out.set(m, []).get(m)!).push(s);
    }
  const ready = ids.filter((i) => indeg.get(i) === 0).sort();
  const res: string[] = [];
  while (ready.length) {
    const x = ready.shift()!;
    res.push(x);
    for (const s of out.get(x) ?? []) {
      indeg.set(s, indeg.get(s)! - 1);
      if (indeg.get(s) === 0) {
        ready.push(s);
        ready.sort();
      }
    }
  }
  // a cycle in the support graph: append the rest in id order (said by the order, never dropped)
  for (const i of [...ids].sort()) if (!res.includes(i)) res.push(i);
  return res;
}

/** Scale each stated check by its geometric ratio; the governing one is the largest. */
function scaleChecks(
  f: WFact,
  scale: Record<string, number>,
  basis: string,
  absolute: Record<string, number> = {},
): Omit<Estimate, "element" | "provenance"> | null {
  const u0 = utilOf(f);
  const parts: [string, number, number][] = [];
  for (const c of f.checks ?? []) {
    const u = c.utilisation ?? (c.demand && c.capacity && c.capacity.value ? c.demand.value / c.capacity.value : null);
    const s = scale[c.mode];
    if (u == null || s == null) continue;
    parts.push([c.mode, u, absolute[c.mode] ?? u * s]);
  }
  if (parts.length) {
    const g = parts.reduce((p, q) => (q[2] > p[2] ? q : p));
    return {
      method: "estimate", utilisationBefore: u0, utilisationAfter: round(g[2], 3), governs: g[0], source: f.source, fact: f.id,
      scaledBy: parts.map(([m, u, v]) => `${m} ${fmt(u, 3)} x ${fmt(v / u || 1, 3)}`).join("; ") + ` (${basis}; capacities held at the printed values)`,
    };
  }
  if (u0 == null) return null;
  const mode = f.governs && scale[f.governs] != null ? f.governs : "flexure";
  return {
    method: "estimate", utilisationBefore: u0, utilisationAfter: round(u0 * scale[mode]!, 3), governs: mode, source: f.source, fact: f.id,
    scaledBy: `utilisation x ${mode} ratio ${fmt(scale[mode]!, 3)} (${basis}; ${f.governs ? "printed governing check" : "governing check not printed, flexure assumed"})`,
  };
}

export function round(x: number, n: number): number {
  const p = 10 ** n;
  return Math.round(x * p) / p;
}

function fmt(x: number, n = 2): string {
  return Number.isFinite(x) ? (Math.round(x * 10 ** n) / 10 ** n).toString() : String(x);
}
