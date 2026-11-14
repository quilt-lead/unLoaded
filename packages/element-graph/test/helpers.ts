import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import type { ElementInput, ModelInput, Vec3 } from "../src/index.ts";

export type FixtureInput = ModelInput & {
  _expected: { supports: [string, string][]; notSupports: [string, string][] };
};

export function loadSimpleFrame(): FixtureInput {
  const path = fileURLToPath(new URL("../../../fixtures/simple-frame.json", import.meta.url));
  return JSON.parse(readFileSync(path, "utf8")) as FixtureInput;
}

const src = { format: "synthetic" };
const el = (id: string, kind: string, min: Vec3, max: Vec3, axis?: { start: Vec3; end: Vec3 }): ElementInput => ({
  id,
  kind,
  params: {},
  source: src,
  geometry: axis ? { bbox: { min, max }, axis } : { bbox: { min, max } },
});

/**
 * Regular steel frame: (bx+1)*(by+1) column lines, `storeys` storeys,
 * pad footings, beams in X and Y at each storey top with a shear-tab
 * connection node at every beam end, one slab per bay per storey.
 */
export function gridFrame(bx: number, by: number, storeys: number, bay = 6, h = 3.5): ModelInput {
  const elements: ElementInput[] = [];
  const c = 0.13; // column half width
  const bw = 0.07; // beam half width
  const d = 0.4; // beam depth
  for (let i = 0; i <= bx; i++)
    for (let j = 0; j <= by; j++) {
      const x = i * bay, y = j * bay;
      elements.push(el(`F_${i}_${j}`, "footing", [x - 0.75, y - 0.75, -0.6], [x + 0.75, y + 0.75, 0]));
      for (let s = 0; s < storeys; s++) {
        elements.push(
          el(`C_${i}_${j}_${s}`, "column", [x - c, y - c, s * h], [x + c, y + c, (s + 1) * h], {
            start: [x, y, s * h],
            end: [x, y, (s + 1) * h],
          }),
        );
      }
    }
  for (let s = 0; s < storeys; s++) {
    const top = (s + 1) * h;
    const zc = top - d / 2;
    for (let i = 0; i <= bx; i++)
      for (let j = 0; j <= by; j++) {
        const x = i * bay, y = j * bay;
        if (i < bx) {
          const id = `BX_${i}_${j}_${s}`;
          const x0 = x + c + 0.01, x1 = x + bay - c - 0.01;
          elements.push(el(id, "beam", [x0, y - bw, top - d], [x1, y + bw, top], { start: [x0, y, zc], end: [x1, y, zc] }));
          elements.push(el(`K_${id}_0`, "connection", [x + c, y + bw, top - 0.35], [x + c + 0.12, y + bw + 0.01, top - 0.05]));
          elements.push(
            el(`K_${id}_1`, "connection", [x + bay - c - 0.12, y + bw, top - 0.35], [x + bay - c, y + bw + 0.01, top - 0.05]),
          );
        }
        if (j < by) {
          const id = `BY_${i}_${j}_${s}`;
          const y0 = y + c + 0.01, y1 = y + bay - c - 0.01;
          elements.push(el(id, "beam", [x - bw, y0, top - d], [x + bw, y1, top], { start: [x, y0, zc], end: [x, y1, zc] }));
          elements.push(el(`K_${id}_0`, "connection", [x + bw, y + c, top - 0.35], [x + bw + 0.01, y + c + 0.12, top - 0.05]));
          elements.push(
            el(`K_${id}_1`, "connection", [x + bw, y + bay - c - 0.12, top - 0.35], [x + bw + 0.01, y + bay - c, top - 0.05]),
          );
        }
        if (i < bx && j < by) {
          elements.push(el(`S_${i}_${j}_${s}`, "slab", [x, y, top], [x + bay, y + bay, top + 0.2]));
        }
      }
  }
  return {
    meta: { version: 1, units: "m", source: src },
    levels: Array.from({ length: storeys + 1 }, (_, s) => ({ id: `L${s}`, name: `Level ${s}`, elevation: s * h })),
    elements,
    relations: [],
    warnings: [],
  };
}
