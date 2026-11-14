/**
 * Geometry math: web-ifc frame conversion, bounding boxes, PCA centrelines and
 * IfcLocalPlacement evaluation. Pure functions, no web-ifc runtime calls.
 *
 * Frame facts (verified empirically against web-ifc 0.0.66, see README):
 * - Mesh vertices * flatTransformation are already in METRES (web-ifc folds the
 *   project length-unit scale into the transformation).
 * - web-ifc emits a Y-up frame: web = (X_ifc, Z_ifc, -Y_ifc). We undo it with
 *   ifc = (web.x, -web.z, web.y).
 */
import type { BBox, GeometrySummary, Vec3 } from "@unloaded/element-graph/input";

/** Round to micrometres so JSON output is stable across runs/platforms. */
export function round6(n: number): number {
  const r = Math.round(n * 1e6) / 1e6;
  return Object.is(r, -0) ? 0 : r;
}
export const roundVec = (v: Vec3): Vec3 => [round6(v[0]), round6(v[1]), round6(v[2])];

/**
 * Collects mesh vertices in IFC Z-up metres for one element.
 * `vertexData` is web-ifc's interleaved [px,py,pz,nx,ny,nz]* buffer.
 */
export class PointAccumulator {
  private chunks: Float64Array[] = [];
  count = 0;

  addWebIfcVertices(vertexData: Float32Array, m: ArrayLike<number>) {
    const n = Math.floor(vertexData.length / 6);
    const out = new Float64Array(n * 3);
    for (let i = 0; i < n; i++) {
      const x = vertexData[i * 6]!;
      const y = vertexData[i * 6 + 1]!;
      const z = vertexData[i * 6 + 2]!;
      // column-major 4x4
      const wx = m[0]! * x + m[4]! * y + m[8]! * z + m[12]!;
      const wy = m[1]! * x + m[5]! * y + m[9]! * z + m[13]!;
      const wz = m[2]! * x + m[6]! * y + m[10]! * z + m[14]!;
      out[i * 3] = wx;
      out[i * 3 + 1] = -wz;
      out[i * 3 + 2] = wy;
    }
    this.chunks.push(out);
    this.count += n;
  }

  /** Visit every point (IFC frame, metres). */
  forEach(fn: (x: number, y: number, z: number) => void) {
    for (const c of this.chunks) for (let i = 0; i < c.length; i += 3) fn(c[i]!, c[i + 1]!, c[i + 2]!);
  }
}

export function bboxOf(acc: PointAccumulator): BBox | undefined {
  if (acc.count === 0) return undefined;
  const min: Vec3 = [Infinity, Infinity, Infinity];
  const max: Vec3 = [-Infinity, -Infinity, -Infinity];
  let ok = true;
  acc.forEach((x, y, z) => {
    if (!Number.isFinite(x) || !Number.isFinite(y) || !Number.isFinite(z)) {
      ok = false;
      return;
    }
    if (x < min[0]) min[0] = x;
    if (y < min[1]) min[1] = y;
    if (z < min[2]) min[2] = z;
    if (x > max[0]) max[0] = x;
    if (y > max[1]) max[1] = y;
    if (z > max[2]) max[2] = z;
  });
  if (!ok || !Number.isFinite(min[0])) return undefined;
  return { min: roundVec(min), max: roundVec(max) };
}

type M3 = [number, number, number, number, number, number, number, number, number];

/** Jacobi eigen-decomposition of a symmetric 3x3 matrix (row-major). */
export function symmetricEigen3(a: M3): { values: Vec3; vectors: [Vec3, Vec3, Vec3] } {
  const A = [
    [a[0], a[1], a[2]],
    [a[3], a[4], a[5]],
    [a[6], a[7], a[8]],
  ];
  const V = [
    [1, 0, 0],
    [0, 1, 0],
    [0, 0, 1],
  ];
  for (let sweep = 0; sweep < 50; sweep++) {
    const off = Math.abs(A[0]![1]!) + Math.abs(A[0]![2]!) + Math.abs(A[1]![2]!);
    if (off < 1e-15) break;
    for (const [p, q] of [
      [0, 1],
      [0, 2],
      [1, 2],
    ] as const) {
      const apq = A[p]![q]!;
      if (Math.abs(apq) < 1e-18) continue;
      const theta = (A[q]![q]! - A[p]![p]!) / (2 * apq);
      const t = Math.sign(theta || 1) / (Math.abs(theta) + Math.sqrt(theta * theta + 1));
      const c = 1 / Math.sqrt(t * t + 1);
      const s = t * c;
      for (let k = 0; k < 3; k++) {
        const akp = A[k]![p]!;
        const akq = A[k]![q]!;
        A[k]![p] = c * akp - s * akq;
        A[k]![q] = s * akp + c * akq;
      }
      for (let k = 0; k < 3; k++) {
        const apk = A[p]![k]!;
        const aqk = A[q]![k]!;
        A[p]![k] = c * apk - s * aqk;
        A[q]![k] = s * apk + c * aqk;
      }
      for (let k = 0; k < 3; k++) {
        const vkp = V[k]![p]!;
        const vkq = V[k]![q]!;
        V[k]![p] = c * vkp - s * vkq;
        V[k]![q] = s * vkp + c * vkq;
      }
    }
  }
  const order = [0, 1, 2].sort((i, j) => A[j]![j]! - A[i]![i]!);
  const values = order.map((i) => A[i]![i]!) as Vec3;
  const vectors = order.map((i) => [V[0]![i]!, V[1]![i]!, V[2]![i]!] as Vec3) as [Vec3, Vec3, Vec3];
  return { values, vectors };
}

const dot = (a: Vec3, b: Vec3) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
/** PCA directions within this angle of a world axis are snapped to it. */
const SNAP_DEG = 3;
const SNAP_COS = Math.cos((SNAP_DEG * Math.PI) / 180);

/** Make a direction's sign deterministic: largest-magnitude component positive. */
function canonical(v: Vec3): Vec3 {
  let k = 0;
  for (let i = 1; i < 3; i++) if (Math.abs(v[i]!) > Math.abs(v[k]!)) k = i;
  return v[k]! < 0 ? [-v[0], -v[1], -v[2]] : v;
}

export interface AxisResult {
  axis: { start: Vec3; end: Vec3 };
  /** Cross-section extents along the two minor principal axes. */
  crossVertical: number;
  crossHorizontal: number;
  length: number;
  inclinationDeg: number;
}

/**
 * Principal axis (centreline) via PCA of the vertex cloud. The axis runs
 * through the centre of the cross-section extents, between the extreme
 * projections along the major principal direction.
 */
export function principalAxis(acc: PointAccumulator, lowerStart: boolean): AxisResult | undefined {
  if (acc.count < 2) return undefined;
  let n = 0;
  const mean: Vec3 = [0, 0, 0];
  acc.forEach((x, y, z) => {
    n++;
    mean[0] += x;
    mean[1] += y;
    mean[2] += z;
  });
  mean[0] /= n;
  mean[1] /= n;
  mean[2] /= n;
  const c: M3 = [0, 0, 0, 0, 0, 0, 0, 0, 0];
  acc.forEach((x, y, z) => {
    const d = [x - mean[0], y - mean[1], z - mean[2]];
    for (let i = 0; i < 3; i++) for (let j = 0; j < 3; j++) c[i * 3 + j] = c[i * 3 + j]! + d[i]! * d[j]!;
  });
  const { vectors } = symmetricEigen3(c);
  const e = vectors.map(canonical) as [Vec3, Vec3, Vec3];
  // Vertex-cloud PCA is biased on short / coarsely tessellated members. If the
  // major direction is within SNAP_DEG of a world axis, snap to it exactly and
  // re-orthogonalise the minor axes.
  for (let k = 0; k < 3; k++) {
    if (Math.abs(e[0][k]!) >= SNAP_COS) {
      const w: Vec3 = [0, 0, 0];
      w[k] = 1;
      e[0] = w;
      const d1 = dot(e[1], w);
      e[1] = norm([e[1][0] - d1 * w[0], e[1][1] - d1 * w[1], e[1][2] - d1 * w[2]]);
      e[2] = cross(e[0], e[1]);
      break;
    }
  }
  const lo: Vec3 = [Infinity, Infinity, Infinity];
  const hi: Vec3 = [-Infinity, -Infinity, -Infinity];
  acc.forEach((x, y, z) => {
    const d: Vec3 = [x - mean[0], y - mean[1], z - mean[2]];
    for (let k = 0; k < 3; k++) {
      const t = dot(d, e[k]!);
      if (t < lo[k]!) lo[k] = t;
      if (t > hi[k]!) hi[k] = t;
    }
  });
  const mid1 = (lo[1] + hi[1]) / 2;
  const mid2 = (lo[2] + hi[2]) / 2;
  const centre = [0, 1, 2].map((i) => mean[i]! + e[1][i]! * mid1 + e[2][i]! * mid2) as Vec3;
  let start: Vec3 = [0, 1, 2].map((i) => centre[i]! + e[0][i]! * lo[0]) as Vec3;
  let end: Vec3 = [0, 1, 2].map((i) => centre[i]! + e[0][i]! * hi[0]) as Vec3;
  if (lowerStart && start[2] > end[2]) [start, end] = [end, start];
  const length = hi[0] - lo[0];
  if (!(length > 0) || !Number.isFinite(length)) return undefined;
  const inclinationDeg = (Math.asin(Math.min(1, Math.abs(end[2] - start[2]) / length)) * 180) / Math.PI;
  // Cross extents: the minor axis closer to world Z is "vertical" (depth for beams).
  const v1 = Math.abs(e[1][2]);
  const v2 = Math.abs(e[2][2]);
  const ext1 = hi[1] - lo[1];
  const ext2 = hi[2] - lo[2];
  const [crossVertical, crossHorizontal] = v1 >= v2 ? [ext1, ext2] : [ext2, ext1];
  return {
    axis: { start: roundVec(start), end: roundVec(end) },
    crossVertical: round6(crossVertical),
    crossHorizontal: round6(crossHorizontal),
    length: round6(length),
    inclinationDeg: Math.round(inclinationDeg * 100) / 100,
  };
}

export function summarise(acc: PointAccumulator, linear: boolean, isColumn: boolean) {
  const bbox = bboxOf(acc);
  if (!bbox) return undefined;
  const g: GeometrySummary = { bbox };
  const ax = linear ? principalAxis(acc, isColumn) : undefined;
  if (ax) g.axis = ax.axis;
  return { geometry: g, axis: ax };
}

// ---------------------------------------------------------------------------
// IfcLocalPlacement evaluation (file units, IFC frame). Used for storey
// elevations so they are expressed in the same frame as the meshes.

/** Column-major 4x4. */
export type Mat4 = number[];

export const IDENTITY: Mat4 = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1];

export function mul(a: Mat4, b: Mat4): Mat4 {
  const o = new Array<number>(16).fill(0);
  for (let c = 0; c < 4; c++)
    for (let r = 0; r < 4; r++) {
      let s = 0;
      for (let k = 0; k < 4; k++) s += a[k * 4 + r]! * b[c * 4 + k]!;
      o[c * 4 + r] = s;
    }
  return o;
}

function norm(v: Vec3): Vec3 {
  const l = Math.hypot(v[0], v[1], v[2]);
  return l > 0 ? [v[0] / l, v[1] / l, v[2] / l] : v;
}
const cross = (a: Vec3, b: Vec3): Vec3 => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];

/** Matrix of an IfcAxis2Placement3D given its location / axis / refDirection. */
export function axis2Placement(loc: number[], axis?: number[], refDir?: number[]): Mat4 {
  const z = norm(axis && axis.length >= 3 ? [axis[0]!, axis[1]!, axis[2]!] : [0, 0, 1]);
  const xr: Vec3 = refDir && refDir.length >= 2 ? [refDir[0]!, refDir[1]!, refDir[2] ?? 0] : [1, 0, 0];
  let x = norm([xr[0] - dot(xr, z) * z[0], xr[1] - dot(xr, z) * z[1], xr[2] - dot(xr, z) * z[2]]);
  if (!Number.isFinite(x[0]) || Math.hypot(...x) < 1e-9) x = Math.abs(z[0]) < 0.9 ? norm(cross([0, 1, 0], z)) : norm(cross(z, [0, 0, 1]));
  const y = cross(z, x);
  return [x[0], x[1], x[2], 0, y[0], y[1], y[2], 0, z[0], z[1], z[2], 0, loc[0] ?? 0, loc[1] ?? 0, loc[2] ?? 0, 1];
}
