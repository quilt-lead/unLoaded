import type { CalcFact } from "./types.ts";

/** The utilisation a row states: the printed ratio, else demand / capacity; null when neither is printed. */
export function utilOf(f: CalcFact): number | null {
  if (f.utilisation != null) return f.utilisation;
  if (f.demand && f.capacity && f.capacity.value) return f.demand.value / f.capacity.value;
  return null;
}
