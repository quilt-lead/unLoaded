/**
 * Uniform spatial hash over bounding boxes, used to find touching pairs in ~O(n).
 */
import type { BBox } from "../model/input.ts";
import { bboxGap } from "../geometry.ts";

export interface ContactPair {
  /** Indices into the item array, i < j. */
  i: number;
  j: number;
  gap: number;
}

/** Pick a cell size from the median element extent (clamped). */
export function autoCellSize(boxes: readonly BBox[]): number {
  if (boxes.length === 0) return 1;
  const ext = boxes
    .map((b) => Math.max(b.max[0] - b.min[0], b.max[1] - b.min[1], b.max[2] - b.min[2]))
    .sort((x, y) => x - y);
  const median = ext[Math.floor(ext.length / 2)]!;
  return Math.min(20, Math.max(0.5, median));
}

/**
 * All pairs of boxes whose distance is <= `tol`.
 * Boxes spanning more than `maxCells` cells are kept in an overflow list and
 * tested against every other box (avoids pathological memory for huge slabs).
 */
export function findContactPairs(
  boxes: readonly BBox[],
  tol: number,
  cellSize: number,
  maxCells: number,
): ContactPair[] {
  const cell = cellSize > 0 ? cellSize : autoCellSize(boxes);
  const grid = new Map<string, number[]>();
  const overflow: number[] = [];
  const ranges: [number, number, number, number, number, number][] = [];

  for (let n = 0; n < boxes.length; n++) {
    const b = boxes[n]!;
    const x0 = Math.floor((b.min[0] - tol) / cell), x1 = Math.floor((b.max[0] + tol) / cell);
    const y0 = Math.floor((b.min[1] - tol) / cell), y1 = Math.floor((b.max[1] + tol) / cell);
    const z0 = Math.floor((b.min[2] - tol) / cell), z1 = Math.floor((b.max[2] + tol) / cell);
    ranges.push([x0, x1, y0, y1, z0, z1]);
    const count = (x1 - x0 + 1) * (y1 - y0 + 1) * (z1 - z0 + 1);
    if (!(count <= maxCells)) {
      overflow.push(n);
      continue;
    }
    for (let x = x0; x <= x1; x++)
      for (let y = y0; y <= y1; y++)
        for (let z = z0; z <= z1; z++) {
          const k = `${x},${y},${z}`;
          const list = grid.get(k);
          if (list) list.push(n);
          else grid.set(k, [n]);
        }
  }

  const pairs: ContactPair[] = [];
  const stamp = new Int32Array(boxes.length).fill(-1);
  const isOverflow = new Uint8Array(boxes.length);
  for (const o of overflow) isOverflow[o] = 1;

  for (let n = 0; n < boxes.length; n++) {
    if (isOverflow[n]) continue;
    const [x0, x1, y0, y1, z0, z1] = ranges[n]!;
    const b = boxes[n]!;
    for (let x = x0; x <= x1; x++)
      for (let y = y0; y <= y1; y++)
        for (let z = z0; z <= z1; z++) {
          const list = grid.get(`${x},${y},${z}`);
          if (!list) continue;
          for (const m of list) {
            if (m <= n || stamp[m] === n) continue;
            stamp[m] = n;
            const gap = bboxGap(b, boxes[m]!);
            if (gap <= tol) pairs.push({ i: n, j: m, gap });
          }
        }
  }
  // Overflow boxes: brute force against everything.
  for (const o of overflow) {
    const b = boxes[o]!;
    for (let m = 0; m < boxes.length; m++) {
      if (m === o || (isOverflow[m] && m < o)) continue;
      const gap = bboxGap(b, boxes[m]!);
      if (gap <= tol) pairs.push(o < m ? { i: o, j: m, gap } : { i: m, j: o, gap });
    }
  }
  return pairs;
}
