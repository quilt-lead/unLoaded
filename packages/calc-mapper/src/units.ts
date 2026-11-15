/**
 * Units: every physical quantity the engine reports carries its unit. Port of the reference
 * schema's units.py (prototyping/calc-graph backend/calcgraph/schema/units.py, which sat on pint):
 * the same CLOSED vocabulary of structural units with the same canonical spellings, the same
 * source aliases, and the same refusals -
 *   - an unknown unit string throws UnknownUnit (and is a type error where the unit is a literal);
 *     nothing is ever converted silently
 *   - converting across dimensions throws UnitMismatch (kip -> ft)
 *   - angle is its own dimension, so rad / deg convert only among themselves
 *   - a dimensionless value says so with unit "1"
 * Factors are to SI base (m, N, rad). The foot, inch, yard and pound-force are the exact
 * international definitions pint uses, so every conversion matches the reference to float precision.
 *
 * Identifiers are not quantities: a section designation ("W18X35") stays a string.
 */

/** (length, force, angle) exponents. */
export type Dim = readonly [number, number, number];

const FT = 0.3048;
const IN = 0.0254;
const YD = 0.9144;
const LBF = 4.4482216152605;
const KIP = 1000 * LBF;

/** canonical name -> [dimension, factor to SI base]. Mirrors units.py `UNITS` key for key. */
const TABLE = {
  "1": [[0, 0, 0], 1], percent: [[0, 0, 0], 0.01],
  // length
  m: [[1, 0, 0], 1], mm: [[1, 0, 0], 1e-3], cm: [[1, 0, 0], 1e-2], ft: [[1, 0, 0], FT], in: [[1, 0, 0], IN],
  pt: [[1, 0, 0], IN / 72], // PDF point as a paper length (a sheet rect is still its own frame type: frames.ts)
  // area / volume
  m2: [[2, 0, 0], 1], ft2: [[2, 0, 0], FT ** 2], in2: [[2, 0, 0], IN ** 2],
  m3: [[3, 0, 0], 1], ft3: [[3, 0, 0], FT ** 3], yd3: [[3, 0, 0], YD ** 3], in3: [[3, 0, 0], IN ** 3],
  mm2: [[2, 0, 0], 1e-6], mm3: [[3, 0, 0], 1e-9], cm2: [[2, 0, 0], 1e-4], cm3: [[3, 0, 0], 1e-6],
  // section properties: second moment of area / torsion constant (L^4), warping constant (L^6)
  m4: [[4, 0, 0], 1], mm4: [[4, 0, 0], 1e-12], cm4: [[4, 0, 0], 1e-8], in4: [[4, 0, 0], IN ** 4], ft4: [[4, 0, 0], FT ** 4],
  m6: [[6, 0, 0], 1], mm6: [[6, 0, 0], 1e-18], in6: [[6, 0, 0], IN ** 6],
  // force
  N: [[0, 1, 0], 1], kN: [[0, 1, 0], 1e3], lbf: [[0, 1, 0], LBF], kip: [[0, 1, 0], KIP],
  // moment
  "N*m": [[1, 1, 0], 1], "kN*m": [[1, 1, 0], 1e3], "kip*ft": [[1, 1, 0], KIP * FT], "kip*in": [[1, 1, 0], KIP * IN],
  "lbf*ft": [[1, 1, 0], LBF * FT],
  // line load / translational spring stiffness (force / length)
  "N/m": [[-1, 1, 0], 1], "kN/m": [[-1, 1, 0], 1e3], plf: [[-1, 1, 0], LBF / FT], klf: [[-1, 1, 0], KIP / FT],
  "kip/in": [[-1, 1, 0], KIP / IN], "lbf/in": [[-1, 1, 0], LBF / IN],
  // rotational spring stiffness (moment / angle)
  "N*m/rad": [[1, 1, -1], 1], "kN*m/rad": [[1, 1, -1], 1e3], "kip*in/rad": [[1, 1, -1], KIP * IN],
  "kip*ft/rad": [[1, 1, -1], KIP * FT],
  // pressure / stress
  Pa: [[-2, 1, 0], 1], kPa: [[-2, 1, 0], 1e3], MPa: [[-2, 1, 0], 1e6],
  psf: [[-2, 1, 0], LBF / FT ** 2], ksf: [[-2, 1, 0], KIP / FT ** 2], psi: [[-2, 1, 0], LBF / IN ** 2],
  ksi: [[-2, 1, 0], KIP / IN ** 2],
  // density (force / volume)
  pcf: [[-3, 1, 0], LBF / FT ** 3], "kN/m3": [[-3, 1, 0], 1e3],
  // angle (own dimension)
  rad: [[0, 0, 1], 1], deg: [[0, 0, 1], Math.PI / 180],
} as const satisfies Record<string, readonly [Dim, number]>;

/** A canonical unit name: the fixed set. Any other string is not a Unit. */
export type Unit = keyof typeof TABLE;
export const UNITS = Object.freeze(Object.keys(TABLE) as Unit[]);

/** Spellings found in sources -> canonical (units.py `ALIASES`; matched lower-cased). */
export const ALIASES: Readonly<Record<string, Unit>> = {
  k: "kip", kips: "kip", kip: "kip", lb: "lbf", lbs: "lbf", "#": "lbf",
  feet: "ft", foot: "ft", "'": "ft", inch: "in", inches: "in", '"': "in",
  "k-ft": "kip*ft", kft: "kip*ft", "k*ft": "kip*ft", "kip-ft": "kip*ft", "ft-k": "kip*ft", "ft*k": "kip*ft",
  "k-in": "kip*in", "kip-in": "kip*in", "in-k": "kip*in", "lb-ft": "lbf*ft", "ft-lb": "lbf*ft",
  "kn-m": "kN*m", knm: "kN*m", nm: "N*m",
  "k/ft": "klf", "kip/ft": "klf", "lb/ft": "plf", "#/ft": "plf",
  "k/ft2": "ksf", "k/ft^2": "ksf", "lb/ft2": "psf", "lb/ft^2": "psf", "#/ft2": "psf",
  "k/in2": "ksi", "lb/in2": "psi", sf: "ft2", sqft: "ft2", "sq ft": "ft2", cy: "yd3",
  "k/in": "kip/in", "kip/inch": "kip/in", "lb/in": "lbf/in", "#/in": "lbf/in",
  "k-in/rad": "kip*in/rad", "k-ft/rad": "kip*ft/rad", "kn-m/rad": "kN*m/rad", "nm/rad": "N*m/rad",
  "mm^2": "mm2", "mm^4": "mm4", "in^4": "in4", "in^6": "in6", "m^4": "m4",
  degrees: "deg", degree: "deg", "°": "deg", "%": "percent", "": "1", "-": "1",
};

export class UnknownUnit extends Error {
  name = "UnknownUnit";
}
export class UnitMismatch extends Error {
  name = "UnitMismatch";
}

/** A number with its unit. JSON: `{ "value": 0.004, "unit": "m" }`. */
export interface Quantity<U extends Unit = Unit> {
  value: number;
  unit: U;
}

const isUnit = (u: string): u is Unit => Object.prototype.hasOwnProperty.call(TABLE, u);

/** Canonical spelling of a unit string (exact, alias, or case-insensitive match); throws UnknownUnit. */
export function canonicalUnit(unit: string): Unit {
  if (typeof unit !== "string") throw new UnknownUnit(`unknown unit ${JSON.stringify(unit)}`);
  if (isUnit(unit)) return unit;
  const u = unit.trim();
  if (isUnit(u)) return u;
  const low = u.toLowerCase();
  const alias = Object.prototype.hasOwnProperty.call(ALIASES, low) ? ALIASES[low] : undefined;
  if (alias) return alias;
  const ci = UNITS.find((n) => n.toLowerCase() === low);
  if (ci) return ci;
  throw new UnknownUnit(`unknown unit ${JSON.stringify(unit)}`);
}

const DIM_NAMES: Record<string, string> = {
  "1,0,0": "length", "2,0,0": "area", "3,0,0": "volume", "0,1,0": "force", "1,1,0": "moment", "-1,1,0": "line load",
  "-2,1,0": "pressure", "-3,1,0": "density", "0,0,1": "angle", "0,0,0": "dimensionless",
};
const dimName = (d: Dim): string => DIM_NAMES[d.join()] ?? `(${d.join(", ")})`;

/** (length, force, angle) exponents of a unit; throws UnknownUnit. */
export function dimensionOf(unit: string): Dim {
  return TABLE[canonicalUnit(unit)][0];
}

/** Convert a value between units of one dimension. Unknown unit: UnknownUnit. Different dimensions: UnitMismatch. */
export function convert(value: number, from: string, to: string): number {
  const s = canonicalUnit(from), d = canonicalUnit(to);
  if (s === d) return value;
  const [ds, fs] = TABLE[s], [dd, fd] = TABLE[d];
  if (ds.join() !== dd.join()) throw new UnitMismatch(`cannot convert ${s} (${dimName(ds)}) to ${d} (${dimName(dd)})`);
  return (value * fs) / fd;
}

/** A Quantity; throws UnknownUnit on a unit outside the vocabulary and TypeError on a non-finite value. */
export function q<U extends Unit>(value: number, unit: U): Quantity<U> {
  if (!Number.isFinite(value)) throw new TypeError(`quantity value must be a finite number, got ${value}`);
  return { value, unit: canonicalUnit(unit) as U };
}

/** Express a quantity in another unit (same dimension, else UnitMismatch). */
export function to<U extends Unit>(x: Quantity, unit: U): Quantity<U> {
  return { value: convert(x.value, x.unit, unit), unit: canonicalUnit(unit) as U };
}

const HEADER = /\[([^\]]+)\]\s*$/;
const SUFFIX: Readonly<Record<string, Unit>> = {
  k: "kip", kip: "kip", kips: "kip", ft: "ft", in: "in", m: "m", mm: "mm", ksf: "ksf", psf: "psf", psi: "psi",
  ksi: "ksi", plf: "plf", klf: "klf", kft: "kip*ft", deg: "deg", pt: "pt", uc: "1", ratio: "1", pcf: "pcf", sf: "ft2",
  ft2: "ft2",
};

/**
 * The unit a field name or a table header DECLARES, else null (never a guess):
 * "PreDL[ksf]" -> ksf; "Magnitude[k,k-ft]" -> null (two units); "max_reaction_k" -> kip; "gap_m" -> m; "size" -> null.
 */
export function unitFromKey(key: string): Unit | null {
  const m = HEADER.exec(key);
  if (m) {
    const inner = m[1]!.trim();
    if (inner.includes(",")) return null;
    try {
      return canonicalUnit(inner);
    } catch {
      return null;
    }
  }
  const k = key.trim().toLowerCase();
  if (k === "uc") return "1";
  const tok = k.split(/[_.\s]/).pop() ?? "";
  return Object.prototype.hasOwnProperty.call(SUFFIX, tok) ? SUFFIX[tok]! : null;
}
