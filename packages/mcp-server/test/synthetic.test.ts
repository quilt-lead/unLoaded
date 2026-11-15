/**
 * The synthetic package (tools/calcgraph-reference: `uv run python -m synth.generate`, then
 * scripts/build_graph.mjs for the two graphs) as a project file: rev 1 graph, the calc package, rev 2
 * graph (column C8 removed). Those files are generated, never committed, so this suite is skipped
 * where they have not been built. When present, the server's answers equal calc-mapper's on them,
 * and the numbers the decision log records for the browser smoke hold (D15 / D24).
 */
import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { buildExport, diffGraphs, impactOf, mapCalcs, parseGraph, type CalcPackage } from "@unloaded/calc-mapper";
import { makeProjectFile } from "../src/makeProjectFile.ts";
import { loadProject } from "../src/project.ts";
import { decisionsOf } from "../src/decisionLog.ts";
import * as tools from "../src/tools.ts";
import { writeTemp } from "./fixtures.ts";

const dir = fileURLToPath(new URL("../../../tools/calcgraph-reference/data/synthetic/", import.meta.url));
const files = ["model_rev1.graph.json", "calc_package.pdf", "model_rev2.graph.json"];
const present = files.every((f) => existsSync(dir + f));

describe.skipIf(!present)("synthetic package as a project file", () => {
  it("summary, element links, impact and compare equal calc-mapper", { timeout: 120_000 }, async () => {
    const read = (f: string) => new Uint8Array(readFileSync(dir + f));
    const file = await makeProjectFile({
      name: "Sample Office Building",
      revisions: [
        { kind: "model", name: files[0]!, bytes: read(files[0]!) },
        { kind: "calcs", name: files[1]!, bytes: read(files[1]!) },
        { kind: "model", name: files[2]!, bytes: read(files[2]!) },
      ],
    });
    const p = await loadProject(writeTemp(file, "sample.calcgraph.json"));
    const g1 = parseGraph(file.revisions[0]!.graph), g2 = parseGraph(file.revisions[2]!.graph);
    const pkg = file.revisions[1]!.extraction as CalcPackage;
    const run = await mapCalcs(g2, pkg);
    const exp = buildExport(g2, pkg, run, decisionsOf(file), { model: files[2], model_revision: 3, calc_package: files[1], calc_revision: 2 });

    const s = await tools.projectSummary(p);
    expect([s.counts.elements, s.counts.calcs, s.counts.calc_edges, s.counts.findings]).toEqual([exp.elements.length, exp.calcs.length, exp.calc_edges.length, exp.findings.length]);
    expect(s.counts.calcs).toBe(12);

    const withLinks = exp.elements.filter((e) => e.calcs.length).slice(0, 25);
    for (const e of withLinks) {
      expect(JSON.parse(JSON.stringify((await tools.getElement(p, { id: e.global_id })).calcs))).toEqual(JSON.parse(JSON.stringify(e.calcs)));
    }

    const cmp = await tools.compareRevisions(p, { a: 1, b: 3 });
    expect(JSON.parse(JSON.stringify(cmp.compare))).toEqual(JSON.parse(JSON.stringify(diffGraphs(g1, g2, { a: 1, b: 3 }))));
    // rev 1 -> rev 2 ground truth: 15 removed, 12 changed (decision log D15 / D24)
    expect([cmp.summary.removed, cmp.summary.changed]).toEqual([15, 12]);

    const col = exp.elements.find((e) => e.ifc_type === "IfcColumn")!;
    const imp = await tools.impactOfChange(p, { id: col.global_id, mode: "remove" });
    expect(JSON.parse(JSON.stringify(imp.impact))).toEqual(JSON.parse(JSON.stringify(await impactOf(g2, pkg, run, [], col.global_id, "remove"))));
  });
});
