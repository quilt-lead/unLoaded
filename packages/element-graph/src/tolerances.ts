/**
 * Single source of geometric tolerances used by connectivity inference.
 * All lengths in metres. Override per call via `buildGraph(input, { tolerances })`.
 */
export interface Tolerances {
  /** Max bbox-to-bbox distance for two elements to count as touching. */
  contact: number;
  /** Max distance from a member's axis end to another element for that end to be "at" it. */
  endZone: number;
  /** Min plan (XY) overlap area, m^2, for bearing rules (slab on beam, ...). */
  minPlanOverlap: number;
  /** Two members whose axes differ by less than this angle (degrees) are parallel. */
  parallelAngleDeg: number;
  /** Spatial-hash cell size; 0 = automatic (derived from element sizes). */
  gridCellSize: number;
  /** Elements spanning more cells than this are tested against everything instead of hashed. */
  maxCellsPerElement: number;
}

export const DEFAULT_TOLERANCES: Readonly<Tolerances> = Object.freeze({
  contact: 0.025,
  endZone: 0.3,
  minPlanOverlap: 0.01,
  parallelAngleDeg: 5,
  gridCellSize: 0,
  maxCellsPerElement: 4096,
});

export function resolveTolerances(overrides?: Partial<Tolerances>): Tolerances {
  const out: Tolerances = { ...DEFAULT_TOLERANCES };
  if (overrides) {
    for (const key of Object.keys(overrides) as (keyof Tolerances)[]) {
      const v = overrides[key];
      if (typeof v === "number" && Number.isFinite(v)) out[key] = v;
    }
  }
  return out;
}
