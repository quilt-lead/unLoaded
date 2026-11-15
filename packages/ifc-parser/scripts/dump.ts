/**
 * Prints a summary of a parsed IFC file.
 *
 *   node packages/ifc-parser/scripts/dump.ts [file.ifc]      (Node >= 22.18 / 23.6 type stripping)
 *   npx tsx packages/ifc-parser/scripts/dump.ts [file.ifc]
 *
 * Defaults to the buildingSMART sample in data/. The same summary is
 * printed by the vitest suite (test/sample.test.ts).
 */
import type { ModelInput } from "@unloaded/element-graph/input";

export function summariseModel(m: ModelInput, samples = 3): string {
  const lines: string[] = [];
  const count = (xs: string[]) =>
    Object.entries(xs.reduce<Record<string, number>>((a, k) => ((a[k] = (a[k] ?? 0) + 1), a), {})).sort();
  lines.push(`schema=${m.meta.schema ?? "?"} project=${m.meta.project ?? "?"} file=${m.meta.source.file ?? "?"}`);
  lines.push(`elements: ${m.elements.length}`);
  for (const [k, n] of count(m.elements.map((e) => String(e.kind)))) lines.push(`  ${k.padEnd(12)} ${n}`);
  lines.push(`native types: ${count(m.elements.map((e) => e.source.nativeType ?? "?")).map(([k, n]) => `${k}=${n}`).join(", ")}`);
  lines.push(`relations: ${m.relations.length}`);
  for (const [k, n] of count(m.relations.map((r) => `${r.kind} (${r.evidence.rule})`))) lines.push(`  ${k.padEnd(40)} ${n}`);
  lines.push(`levels: ${m.levels.length}`);
  for (const l of m.levels) lines.push(`  ${l.name} @ ${l.elevation} m  (${l.id})`);
  lines.push(`warnings: ${m.warnings.length}`);
  for (const w of m.warnings) lines.push(`  - ${w}`);
  lines.push(`sample elements:`);
  const picks = [...new Map(m.elements.map((e) => [e.kind, e])).values()].slice(0, samples);
  for (const e of picks) lines.push(JSON.stringify(e, null, 2).replace(/^/gm, "  "));
  return lines.join("\n");
}

const isMain = typeof process !== "undefined" && process.argv[1] !== undefined && /dump\.ts$/.test(process.argv[1]);
if (isMain) {
  const { readFile } = await import("node:fs/promises");
  const { fileURLToPath } = await import("node:url");
  const { parseIfc } = await import("../src/index.ts");
  const file = process.argv[2] ?? fileURLToPath(new URL("../../../data/Building-Structural-IFC4.ifc", import.meta.url));
  const data = new Uint8Array(await readFile(file));
  const model = await parseIfc(data, { fileName: file.split(/[\\/]/).pop() });
  console.log(summariseModel(model));
}
