/**
 * Simple-span statics for the local re-solve (the hackathon used a PyNite simple span with the
 * same load cases; for a pinned-roller beam statics is exact, so no FE solver is needed).
 *
 * Loads are [D, L, Lr] components: a uniform line load and point loads at distances from end i.
 * Combinations are the hackathon's (ASCE 7-16 LRFD): LC1 1.4D, LC2 1.2D + 1.6L + 0.5Lr,
 * LC3 1.2D + 0.5L + 1.6Lr; deflection "live" = L (Lr at the roof), "total" = D + L + Lr.
 * Deflections are for EI = 1: the screen only ever uses before/after ratios of the SAME member,
 * so EI cancels and no section table is needed.
 */
export type Vec3 = [number, number, number];

export const COMBOS: Record<string, Vec3> = {
  LC1: [1.4, 0, 0],
  LC2: [1.2, 1.6, 0.5],
  LC3: [1.2, 0.5, 1.6],
};

export function fac(v: Vec3, c: keyof typeof COMBOS | string = "LC2"): number {
  const f = COMBOS[c]!;
  return v[0] * f[0] + v[1] * f[1] + v[2] * f[2];
}

/** Max factored value over the combinations. */
export function ru(v: Vec3): number {
  return Math.max(...Object.keys(COMBOS).map((c) => fac(v, c)));
}

export interface SpanResult {
  L: number;
  /** Unbraced length for flexure: the largest gap between point loads (framing members brace the
   * member there) when it carries any, else 0 (deck-braced) - the hackathon's rule. Same length unit as L. */
  lb: number;
  mu: number;
  vu: number;
  dLive: number;
  dTotal: number;
  Ri: Vec3;
  Rj: Vec3;
}

/** Simple-span reactions per component - statics, exact. */
export function reactions(L: number, w: Vec3, pts: [number, Vec3][]): [Vec3, Vec3] {
  // Per component: half the UDL to each end, point loads split by lever arm (half each on a zero span).
  const end = (k: 0 | 1 | 2, atI: boolean): number => {
    let r = (w[k] * L) / 2;
    for (const [a0, p] of pts) {
      const a = Math.min(Math.max(a0, 0), L);
      r += L > 0 ? (p[k] * (atI ? L - a : a)) / L : p[k] / 2;
    }
    return r;
  };
  const ri: Vec3 = [end(0, true), end(1, true), end(2, true)];
  const rj: Vec3 = [end(0, false), end(1, false), end(2, false)];
  return [ri, rj];
}

/** Moment at x for a load vector already combined to one scalar per load. */
function momentAt(x: number, L: number, w: number, pts: [number, number][], ri: number): number {
  let m = ri * x - (w * x * x) / 2;
  for (const [a, p] of pts) if (a < x) m -= p * (x - a);
  return m;
}

function maxDeflection(L: number, w: number, pts: [number, number][], ri: number, n = 400): number {
  if (L <= 0) return 0;
  // y'' = -M (EI = 1); y(0) = y(L) = 0. Trapezoid twice, then remove the linear term.
  const h = L / n;
  const m: number[] = [];
  for (let k = 0; k <= n; k++) m.push(momentAt(k * h, L, w, pts, ri));
  const slope: number[] = [0];
  for (let k = 1; k <= n; k++) slope.push(slope[k - 1]! - ((m[k - 1]! + m[k]!) / 2) * h);
  const y: number[] = [0];
  for (let k = 1; k <= n; k++) y.push(y[k - 1]! + ((slope[k - 1]! + slope[k]!) / 2) * h);
  const yL = y[n]!;
  let best = 0;
  for (let k = 0; k <= n; k++) best = Math.max(best, Math.abs(y[k]! - (yL * k) / n));
  return best;
}

export function solveSpan(L: number, w: Vec3, pts: [number, Vec3][], roof: boolean): SpanResult {
  const P = pts.map(([a, p]) => [Math.min(Math.max(a, 0), L), p] as [number, Vec3]);
  const [Ri, Rj] = reactions(L, w, P);
  const comb = (f: Vec3) => {
    const ws = w[0] * f[0] + w[1] * f[1] + w[2] * f[2];
    const ps = P.map(([a, p]) => [a, p[0] * f[0] + p[1] * f[1] + p[2] * f[2]] as [number, number]);
    const ri = Ri[0] * f[0] + Ri[1] * f[1] + Ri[2] * f[2];
    const rj = Rj[0] * f[0] + Rj[1] * f[1] + Rj[2] * f[2];
    return { ws, ps, ri, rj };
  };
  let mu = 0;
  let vu = 0;
  for (const f of Object.values(COMBOS)) {
    const { ws, ps, ri, rj } = comb(f);
    vu = Math.max(vu, Math.abs(ri), Math.abs(rj));
    // max moment: at point loads, ends, and where the shear crosses zero inside each segment
    const xs = [0, L, ...ps.map(([a]) => a)];
    const stops = [...new Set(xs)].sort((a, b) => a - b);
    for (let s = 0; s + 1 < stops.length; s++) {
      const x0 = stops[s]!;
      const x1 = stops[s + 1]!;
      // shear just right of x0
      let v = ri - ws * x0;
      for (const [a, p] of ps) if (a <= x0) v -= p;
      if (ws > 0) {
        const xz = x0 + v / ws;
        if (xz > x0 && xz < x1) xs.push(xz);
      }
    }
    for (const x of xs) mu = Math.max(mu, Math.abs(momentAt(x, L, ws, ps, ri)));
  }
  const live: Vec3 = roof ? [0, 0, 1] : [0, 1, 0];
  const lv = comb(live);
  const tv = comb([1, 1, 1]);
  const stops = [...new Set([0, L, ...P.map(([a]) => a)])].sort((a, b) => a - b);
  const lb = P.length ? Math.max(...stops.slice(1).map((x, k) => x - stops[k]!)) : 0;
  return {
    L,
    lb,
    mu,
    vu,
    dLive: maxDeflection(L, lv.ws, lv.ps, lv.ri),
    dTotal: maxDeflection(L, tv.ws, tv.ps, tv.ri),
    Ri,
    Rj,
  };
}
