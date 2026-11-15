/**
 * Calc facts in the engine's working units. Every stated `Quantity` is converted ONCE, here, with
 * calc-mapper's `convert()` (closed unit set; a wrong dimension throws UnitMismatch, an unknown unit
 * UnknownUnit) to kip / kip*ft / klf / ksf / ft, deflections to in. A value whose unit cannot be
 * converted is dropped and reported in `problems` - never used as if it were in another unit.
 */
import { convert, dimensionOf } from "@unloaded/calc-mapper";
import type { CalcFact, CalcSource, CheckMode, FactKind, LoadComponents, Quantity } from "./types.ts";

/** A number in a known working unit. */
export interface W {
  value: number;
  unit: string;
}
export interface WComponents {
  dead?: number;
  live?: number;
  roofLive?: number;
  unit: "klf" | "kip";
}
export interface WCheck {
  mode: CheckMode;
  demand?: W;
  capacity?: W;
  utilisation?: number;
}

/** A calc fact in working units (internal). Same field names as `CalcFact`. */
export interface WFact {
  id: string;
  kind: FactKind;
  elements: string[];
  source: CalcSource;
  role?: "gravity" | "lateral";
  group?: string;
  utilisation?: number;
  demand?: W;
  capacity?: W;
  governs?: CheckMode;
  checks?: WCheck[];
  span?: W;
  lineLoad?: WComponents;
  reactions?: { i?: WComponents; j?: WComponents; factoredI?: W; factoredJ?: W };
  axial?: W;
  serviceLoad?: W;
  allowableBearing?: W;
  width?: W;
  detailType?: string;
  bolts?: number;
  combination?: string;
  seismic?: CalcFact["seismic"];
  chevron?: { unbalancedLoad: W; gravityMoment: W; axial: W; axialCapacity: W; momentCapacity: W; equation: "H1-1a" | "H1-1b" };
}

/** Working unit for a dimension: force kip, moment kip*ft, line load klf, pressure ksf, length ft. */
const WORKING: Record<string, string> = {
  "0,1,0": "kip",
  "1,1,0": "kip*ft",
  "-1,1,0": "klf",
  "-2,1,0": "ksf",
  "1,0,0": "ft",
  "0,0,0": "1",
};

export function normaliseFacts(facts: CalcFact[]): { facts: WFact[]; problems: string[] } {
  const problems: string[] = [];
  const conv = (x: Quantity | undefined, to: string | null, what: string): W | undefined => {
    if (!x) return undefined;
    try {
      const unit = to ?? WORKING[dimensionOf(x.unit).join()];
      if (!unit) throw new Error(`no working unit for ${x.unit}`);
      return { value: convert(x.value, x.unit, unit), unit };
    } catch (e) {
      problems.push(`${what}: ${(e as Error).message} - value not used`);
      return undefined;
    }
  };
  const comps = (c: LoadComponents | undefined, unit: "klf" | "kip", what: string): WComponents | undefined => {
    if (!c) return undefined;
    const out: WComponents = { unit };
    for (const k of ["dead", "live", "roofLive"] as const) {
      const v = conv(c[k], unit, `${what}.${k}`);
      if (v) out[k] = v.value;
    }
    return out;
  };
  const out = facts.map((f): WFact => {
    const id = f.id;
    const w: WFact = { id, kind: f.kind, elements: f.elements, source: f.source };
    if (f.role) w.role = f.role;
    if (f.group) w.group = f.group;
    if (f.utilisation != null) w.utilisation = f.utilisation;
    const set = <K extends keyof WFact>(k: K, v: WFact[K] | undefined) => {
      if (v !== undefined) w[k] = v;
    };
    // demand and capacity of one row share a dimension: capacity is expressed in demand's working unit
    const dem = conv(f.demand, null, `${id}.demand`);
    set("demand", dem);
    set("capacity", conv(f.capacity, dem?.unit ?? null, `${id}.capacity`));
    set("governs", f.governs);
    if (f.checks)
      w.checks = f.checks.map((c) => {
        const to = c.mode === "deflection_live" || c.mode === "deflection_total" ? "in" : null;
        const d = conv(c.demand, to, `${id}.${c.mode}.demand`);
        const wc: WCheck = { mode: c.mode };
        if (d) wc.demand = d;
        const cap = conv(c.capacity, d?.unit ?? to, `${id}.${c.mode}.capacity`);
        if (cap) wc.capacity = cap;
        if (c.utilisation != null) wc.utilisation = c.utilisation;
        return wc;
      });
    set("span", conv(f.span, "ft", `${id}.span`));
    set("lineLoad", comps(f.lineLoad, "klf", `${id}.lineLoad`));
    if (f.reactions) {
      const r: NonNullable<WFact["reactions"]> = {};
      const ri = comps(f.reactions.i, "kip", `${id}.reactions.i`);
      const rj = comps(f.reactions.j, "kip", `${id}.reactions.j`);
      const fi = conv(f.reactions.factoredI, "kip", `${id}.reactions.factoredI`);
      const fj = conv(f.reactions.factoredJ, "kip", `${id}.reactions.factoredJ`);
      if (ri) r.i = ri;
      if (rj) r.j = rj;
      if (fi) r.factoredI = fi;
      if (fj) r.factoredJ = fj;
      w.reactions = r;
    }
    set("axial", conv(f.axial, "kip", `${id}.axial`));
    set("serviceLoad", conv(f.serviceLoad, "kip", `${id}.serviceLoad`));
    set("allowableBearing", conv(f.allowableBearing, "ksf", `${id}.allowableBearing`));
    set("width", conv(f.width, "ft", `${id}.width`));
    set("detailType", f.detailType);
    set("bolts", f.bolts);
    set("combination", f.combination);
    set("seismic", f.seismic);
    if (f.chevron) {
      const c = f.chevron;
      const parts = {
        unbalancedLoad: conv(c.unbalancedLoad, "kip", `${id}.chevron.unbalancedLoad`),
        gravityMoment: conv(c.gravityMoment, "kip*ft", `${id}.chevron.gravityMoment`),
        axial: conv(c.axial, "kip", `${id}.chevron.axial`),
        axialCapacity: conv(c.axialCapacity, "kip", `${id}.chevron.axialCapacity`),
        momentCapacity: conv(c.momentCapacity, "kip*ft", `${id}.chevron.momentCapacity`),
      };
      if (parts.unbalancedLoad && parts.gravityMoment && parts.axial && parts.axialCapacity && parts.momentCapacity)
        w.chevron = { ...(parts as { [K in keyof typeof parts]: W }), equation: c.equation };
    }
    return w;
  });
  return { facts: out, problems };
}

/** The utilisation a row states: the printed ratio, else demand / capacity; null when neither is printed. */
export function utilOf(f: { utilisation?: number; demand?: W | Quantity; capacity?: W | Quantity }): number | null {
  if (f.utilisation != null) return f.utilisation;
  if (f.demand && f.capacity && f.capacity.value) return f.demand.value / f.capacity.value;
  return null;
}
