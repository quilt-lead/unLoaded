/**
 * A *.calcgraph.json project file (the app's Save project, @unloaded/project-file) as input: every
 * model revision (the head is the current model), the calc set the app maps (each calc document's head
 * revision) from the stored extractions when storedExtractionFor accepts them, the file's decision log
 * applied before the decisions file. Fixture: model rev 1 (id 1), the calc PDF (id 2, document d1),
 * model rev 2 (id 3), optionally the supplement PDF (id 4, document d2).
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { buildCalcSet, buildState, diffGraphs, mapCalcs, parseGraph, type CalcPackage } from "@unloaded/calc-mapper";
import type { ProjectFile } from "@unloaded/project-file";
import { projectFileDecisions } from "../src/engine.ts";
import * as tools from "../src/tools.ts";
import { buildProjectFile, writeTemp } from "./fixtures.ts";
import { call, connect, inputs, loadProject, plain, tempDir } from "./helpers.ts";

const open = (path: string, decisions: string | null = null) => loadProject(inputs({ models: [], calcs: [], projectFile: path, decisions }));

describe("project file", () => {
  it("serves the head model with the stored extraction: the engine's output on the head pair", { timeout: 120_000 }, async () => {
    const { file } = await buildProjectFile();
    const path = writeTemp(file);
    const p = await open(path);
    expect(p.models.map((m) => [m.revision, m.name])).toEqual([[1, "test_rev1.graph.json"], [3, "test_rev2.graph.json"]]);
    expect(p.current.revision).toBe(3);
    expect(p.pdfs[0]).toMatchObject({ name: "test_calcs.pdf", extraction: "stored", revision: { id: 2, label: "calcs" } });
    const g2 = parseGraph(file.revisions[2]!.graph);
    const pkg = file.revisions[1]!.extraction as CalcPackage;
    const set = buildCalcSet([{ doc_id: "d1", name: "test_calcs", revision: 2, package: pkg }]);
    const run = await mapCalcs(g2, set);
    const state = buildState(g2, set, run, []);
    expect(plain(p.links)).toEqual(plain(state.links));
    expect(p.counts).toEqual(state.counts);
    const s = tools.projectSummary(p);
    expect(s.source).toMatchObject({ project_file: { file: "test.calcgraph.json" }, model: { file: "test_rev2.graph.json", revision: 3 } });
    expect((s.source as { project_file: { sha256: string } }).project_file.sha256).toMatch(/^[0-9a-f]{64}$/);
    // compare: labels are the revision ids, as the app passes them
    const cmp = tools.compareRevisions(p, {});
    expect(plain(cmp.compare)).toEqual(plain(diffGraphs(parseGraph(file.revisions[0]!.graph), g2, { a: 1, b: 3 })));
    expect([cmp.counts.removed, cmp.counts.changed]).toEqual([1, 1]);
  });

  it("maps every calc document's head as one calc set, as the app does", { timeout: 120_000 }, async () => {
    const { file } = await buildProjectFile({ supplement: true });
    const p = await open(writeTemp(file));
    expect(p.pdfs.map((d) => [d.docId, d.name, d.revision?.id, d.extraction])).toEqual([
      ["d1", "test_calcs.pdf", 2, "stored"],
      ["d2", "Supplement A.pdf", 4, "stored"],
    ]);
    const g2 = parseGraph(file.revisions[2]!.graph);
    const set = buildCalcSet([
      { doc_id: "d1", name: "test_calcs", revision: 2, package: file.revisions[1]!.extraction as CalcPackage },
      { doc_id: "d2", name: "Supplement A", revision: 4, package: file.revisions[3]!.extraction as CalcPackage },
    ]);
    const run = await mapCalcs(g2, set);
    const state = buildState(g2, set, run, []);
    expect(p.calcs.map((c) => c.key)).toEqual(set.combined.calcs.map((c) => c.key));
    expect(p.counts).toEqual(state.counts);
    // the same links, each with its page in its own PDF (set page - page_offset)
    const off = new Map(set.docs.map((d) => [d.doc_id, d.page_offset]));
    const docPage = (key: string, n: number | null) => (n === null ? null : n - off.get(key.split("#")[0]!)!);
    expect(p.links.map((l) => [l.global_id, l.calc_key, l.conf, l.page])).toEqual(
      state.links.map((l) => [l.global_id, l.calc_key, l.conf, docPage(l.calc_key, l.page)]),
    );
    expect(p.calcEdges.filter((e) => e.cross_pdf).map((e) => [e.src, e.dst])).toEqual([["d1#beam-design-check", "d2#connection-design-check"]]);
    expect(tools.projectSummary(p).warnings.some((w) => /older or withdrawn/.test(w))).toBe(false);
  });

  it("leaves a withdrawn calc document out of the set", { timeout: 120_000 }, async () => {
    const { file } = await buildProjectFile({ supplement: true });
    file.documents = file.documents.map((d) => (d.docId === "d2" ? { ...d, removed: true } : d));
    const p = await open(writeTemp(file));
    expect(p.pdfs.map((d) => d.docId)).toEqual(["d1"]);
    expect(p.warnings.some((w) => /1 older or withdrawn calc revision/.test(w))).toBe(true);
  });

  it("re-extracts the PDF when the stored extraction is unusable, and says why", { timeout: 120_000 }, async () => {
    const { file } = await buildProjectFile({ stripExtraction: true });
    const p = await open(writeTemp(file));
    expect(p.pdfs[0]!.extraction).toBe("re-extracted");
    expect(p.pdfs[0]!.extractionNote).toBeTruthy();
    expect(p.warnings.some((w) => /stored extraction was not used/.test(w))).toBe(true);
  });

  it("applies the file's decision log first, then the decisions file (a later decision wins)", { timeout: 120_000 }, async () => {
    const { file } = await buildProjectFile({ decisions: [{ globalId: "B1", calcKey: "beam-design-check", action: "reject", note: "no" }] });
    const dec = join(tempDir(), "decisions.json");
    const p = await open(writeTemp(file), dec);
    expect(p.baseLog).toHaveLength(1);
    expect(p.status.get("B1")).toBe("unmapped");
    const client = await connect(p);
    const r = await call(client, "record_decision", { global_id: "B1", calc_key: "beam-design-check", action: "undo" });
    expect(r.isError, r.text).toBe(false);
    expect(r.json.recorded[0]).toMatchObject({ status_before: "unmapped", status_after: "confirmed" });
    // the decisions file is its own calc-mapper log (ids from 1), recorded against the revision ids
    const written = JSON.parse(readFileSync(dec, "utf8"));
    expect(written).toMatchObject([{ id: 1, global_id: "B1", calc_key: "d1#beam-design-check", action: "undo", model_rev: 3, calc_rev: 2 }]);
    // the project file itself is never written
    expect(readFileSync(p.projectFile!.path, "utf8")).toBe(JSON.stringify(file));
    // one id scheme everywhere: origin + the id in that origin (never the engine's shifted id)
    expect(r.json.recorded[0].decision).toMatchObject({ origin: "decisions_file", id: 1 });
    const log = (await call(client, "get_element", { id: "B1" })).json.decisions;
    expect(log.map((d: { origin: string; id: number; action: string }) => [d.origin, d.id, d.action])).toEqual([["project_file", 1, "reject"], ["decisions_file", 1, "undo"]]);
    const res = JSON.parse(((await client.readResource({ uri: "unloaded://project/decisions" })).contents[0] as { text: string }).text);
    expect(res.entries.map((d: { id: number }) => d.id)).toEqual([1]);
    expect(res.project_file_entries.map((d: { id: number }) => d.id)).toEqual([1]);
    // a decision a link shows is named the same way
    await call(client, "record_decision", { global_id: "B1", calc_key: "beam-design-check", action: "confirm" });
    const link = (await call(client, "get_element", { id: "B1" })).json.links.find((l: { calc_key: string }) => l.calc_key === "d1#beam-design-check");
    expect(link.decision).toMatchObject({ origin: "decisions_file", id: 2, action: "confirm" });
    await client.close();
  });
});

describe("projectFileDecisions", () => {
  const file = (): ProjectFile => ({
    format: "unloaded.calc-graph-project", version: 2, exportedAt: "2026-11-14T21:00:00-05:00",
    project: { name: "P", createdAt: "2026-11-14T21:00:00-05:00" },
    documents: [],
    revisions: [],
    decisions: [
      { globalId: "G", calcKey: "k", action: "confirm", actor: "r", note: null, at: "t1", modelRev: 1, calcRev: 2 },
      { globalId: "G", calcKey: "k", action: "reject", actor: "r", note: "no", at: "t2", modelRev: 4, calcRev: 2 },
    ],
  });
  it("numbers the log 1..n in file order, with the engine's field names and the revisions kept", () => {
    const d = projectFileDecisions(file());
    expect(d.map((x) => [x.id, x.global_id, x.calc_key, x.action, x.model_rev])).toEqual([[1, "G", "k", "confirm", 1], [2, "G", "k", "reject", 4]]);
    expect(d[1]!.note).toBe("no");
  });
});
