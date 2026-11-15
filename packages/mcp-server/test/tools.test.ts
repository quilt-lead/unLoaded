/**
 * Parity: every tool's records and numbers equal what @unloaded/calc-mapper (and
 * @unloaded/move-impact) return when called directly on the same inputs - the graph and the
 * extraction stored in the project file, and its decision log.
 */
import { beforeAll, describe, expect, it } from "vitest";
import {
  buildExport, buildState, diffGraphs, impactOf, mapCalcs, sha256, sha256Json,
  type CalcPackage, type DecisionFields, type Export, type MappingRun, type ProjectState, type SerializedElementGraph,
} from "@unloaded/calc-mapper";
import { impact as moveImpact } from "@unloaded/move-impact";
import { loadProject, type LoadedProject } from "../src/project.ts";
import type { ProjectFile } from "@unloaded/project-file";
import { decisionsOf } from "../src/decisionLog.ts";
import * as tools from "../src/tools.ts";
import { buildProjectFile, writeTemp } from "./fixtures.ts";

/** JSON round trip: what a client receives. */
const wire = <T>(v: T): T => JSON.parse(JSON.stringify(v)) as T;

interface Direct {
  graph: SerializedElementGraph;
  pkg: CalcPackage;
  run: MappingRun;
  decisions: DecisionFields[];
  state: ProjectState;
  exp: Export;
}

async function direct(file: ProjectFile): Promise<Direct> {
  const m = file.revisions.find((r) => r.id === 3)!, c = file.revisions.find((r) => r.id === 2)!;
  const graph = m.graph!, pkg = c.extraction as CalcPackage;
  const decisions = decisionsOf(file);
  const run = await mapCalcs(graph, pkg);
  return {
    graph, pkg, run, decisions, state: buildState(graph, pkg, run, decisions),
    exp: buildExport(graph, pkg, run, decisions, { model: m.sourceName, model_revision: 3, calc_package: c.sourceName, calc_revision: 2 }),
  };
}

for (const variant of ["no decisions", "with decisions"] as const) {
  describe(`tools = calc-mapper on the same project (${variant})`, () => {
    let file: ProjectFile;
    let p: LoadedProject;
    let d: Direct;

    beforeAll(async () => {
      file = (await buildProjectFile(variant === "with decisions" ? {
        decisions: [
          { globalId: "B1", calcKey: "column-design-check", action: "reject", actor: "reviewer", note: "loads only" },
          { globalId: "C2", calcKey: "column-design-check", action: "confirm", actor: "reviewer", note: null },
        ],
      } : {})).file;
      p = await loadProject(writeTemp(file));
      d = await direct(file);
    });

    it("the fixture is not vacuous: calcs, links, a finding, calc edges", () => {
      expect(d.exp.calcs.length).toBe(2);
      expect(d.state.links.length).toBeGreaterThan(0);
      expect(d.run.calc_edges.length).toBeGreaterThan(0);
      expect(d.run.findings.length).toBe(1);
    });

    it("project_summary counts and producers", async () => {
      const s = await tools.projectSummary(p);
      expect(s.counts.elements).toBe(d.state.elements.length);
      expect(s.counts.element_status).toEqual(d.state.counts);
      expect(s.counts.calcs).toBe(d.exp.calcs.length);
      expect(s.counts.links).toBe(d.state.links.length);
      expect(s.counts.calc_edges).toBe(d.exp.calc_edges.length);
      expect(s.counts.load_path_edges).toBe(d.exp.load_path.length);
      expect(s.counts.connectivity_edges).toBe(d.exp.connectivity.length);
      expect([s.counts.typical_groups, s.counts.group_links, s.counts.findings]).toEqual([d.exp.groups.length, d.exp.group_links.length, d.exp.findings.length]);
      expect(s.counts.decisions).toBe(d.decisions.length);
      expect(wire(s.source.producers)).toEqual(wire(d.exp.producers));
      expect((s.source.model_revision as { graph_sha256: string }).graph_sha256).toBe(await sha256Json(d.graph));
      expect((s.source.calc_revision as { extraction: string }).extraction).toBe("stored");
      expect(s.calcs.map((c) => c.key)).toEqual(d.exp.calcs.map((c) => c.key));
    });

    it("search_elements filters", async () => {
      expect((await tools.searchElements(p, { kind: "column" })).count).toBe(d.state.elements.filter((e) => e.cat === "Column").length);
      expect((await tools.searchElements(p, { size: "w12 x65" })).elements.map((e) => e.global_id)).toEqual(["C2"]);
      expect((await tools.searchElements(p, { grid: "a/1" })).elements.map((e) => e.global_id)).toEqual(["C1"]);
      expect((await tools.searchElements(p, { storey: "level 2", kind: "beam" })).elements.map((e) => e.mark)).toEqual(["B-101"]);
      for (const status of ["confirmed", "review", "unmapped"] as const) {
        expect((await tools.searchElements(p, { status })).count).toBe(d.state.counts[status]);
      }
      const b = (await tools.searchElements(p, { mark: "b-101" })).elements[0]!;
      const exportLinks = d.exp.elements.find((e) => e.global_id === "B1")!.calcs.filter((l) => l.review !== "rejected");
      expect(b.calcs.map((l) => [l.calc, l.confidence, l.band, l.role, l.review])).toEqual(exportLinks.map((l) => [l.calc, l.confidence, l.band, l.role, l.review]));
    });

    it("get_element: links pass through untouched, load path and connectivity are the graph's", async () => {
      for (const e of d.exp.elements) {
        const g = await tools.getElement(p, { id: e.global_id });
        expect(wire(g.calcs)).toEqual(wire(e.calcs));
        expect(g.element.status).toBe(e.status);
        expect(g.load_path.bears_on.map((x) => x.global_id)).toEqual(d.state.edges.filter((x) => x.src === e.global_id).map((x) => x.dst));
        expect(g.load_path.carries.map((x) => x.global_id)).toEqual(d.state.edges.filter((x) => x.dst === e.global_id).map((x) => x.src));
        expect(g.connectivity.length).toBe(d.exp.connectivity.filter((c) => c.a === e.global_id || c.b === e.global_id).length);
        expect(wire(g.findings)).toEqual(wire(d.exp.findings.filter((f) => f.global_id === e.global_id)));
      }
      // every link carries the engine's provenance, resting on the graph and the PDF
      const b = await tools.getElement(p, { id: "B-101" });
      for (const l of b.calcs) expect(l.provenance.inputs).toEqual(d.run.inputs);
      // a mark resolves; an unknown one is a clear error
      expect((await tools.getElement(p, { id: "c-2" })).element.global_id).toBe("C2");
      await expect(tools.getElement(p, { id: "NOPE" })).rejects.toThrow(/no element with GlobalId or mark/);
    });

    it("get_calc: the calc record, its linked elements, edges and text", async () => {
      for (const c of d.exp.calcs) {
        const g = await tools.getCalc(p, { key: c.key, include_text: true });
        expect(wire(g.calc)).toEqual(wire(c));
        const linked = d.exp.elements.flatMap((e) => e.calcs.filter((l) => l.calc === c.key).map((l) => [e.global_id, l.confidence, l.provenance]));
        expect(wire(g.linked_elements.map((l) => [l.global_id, l.confidence, l.provenance]))).toEqual(wire(linked).sort((x, y) => (y[1] as number) - (x[1] as number)));
        expect(wire(g.calc_edges.feeds.map(({ dst_title: _t, ...e }) => e))).toEqual(wire(d.exp.calc_edges.filter((e) => e.src === c.key)));
        expect(wire(g.calc_edges.fed_by.map(({ src_title: _t, ...e }) => e))).toEqual(wire(d.exp.calc_edges.filter((e) => e.dst === c.key)));
        expect(g.text?.text).toContain(c.title);
      }
      await expect(tools.getCalc(p, { key: "nope" })).rejects.toThrow(/no calc "nope"/);
    });

    it("impact_of_change = impactOf", async () => {
      for (const id of ["C1", "C2", "B1"]) {
        for (const mode of ["change", "remove"] as const) {
          const r = await tools.impactOfChange(p, { id, mode });
          expect(wire(r.impact)).toEqual(wire(await impactOf(d.graph, d.pkg, d.run, d.decisions, id, mode)));
          expect(r.hit_elements.length).toBe(Object.keys(r.impact.hit).length);
          expect(r.stale_calcs.map((s) => s.calc).sort()).toEqual(Object.keys(r.impact.stale).sort());
        }
      }
    });

    it("list_revisions and compare_revisions = diffGraphs", async () => {
      const l = await tools.listRevisions(p);
      expect(l.head).toEqual({ model: 3, calcs: 2 });
      expect(l.revisions.model.map((r) => r.id)).toEqual([1, 3]);
      const c = await tools.compareRevisions(p, {});
      const g1 = file.revisions.find((r) => r.id === 1)!.graph!;
      expect(wire(c.compare)).toEqual(wire(diffGraphs(g1, d.graph, { a: 1, b: 3 })));
      expect(c.summary).toEqual({ removed: 1, added: 0, changed: 1, edges_removed: 1, edges_added: 0 });
      await expect(tools.compareRevisions(p, { a: 2, b: 3 })).rejects.toThrow(/not a model revision/);
    });

    it("list_findings and list_typical_groups pass the engine's records through", async () => {
      const f = await tools.listFindings(p);
      expect(wire(f.findings)).toEqual(wire(d.exp.findings));
      const g = await tools.listTypicalGroups(p);
      expect(wire(g.groups.map((x) => x.group))).toEqual(wire(d.exp.groups));
      expect(g.groups.flatMap((x) => x.links).length).toBe(d.exp.group_links.length);
    });

    it("move_column = move-impact on the same graph and links", async () => {
      const r = await tools.moveColumn(p, { column: "C-2", dx: 1, dy: 0 });
      const want = moveImpact({ graph: d.graph, graphSha256: await sha256Json(d.graph), move: { column: "C2", dx: 1, dy: 0 }, links: d.state.links });
      expect(wire(r.result)).toEqual(wire(want));
      await expect(tools.moveColumn(p, { column: "B-101", dx: 1 })).rejects.toThrow(/not a column/);
      await expect(tools.moveColumn(p, { column: "C-1" })).rejects.toThrow(/give dx/);
    });
  });
}

describe("calc package source", () => {
  it("an extraction without document hashes is re-extracted from the PDF in the file, with the same calcs", async () => {
    const { file, pdf } = await buildProjectFile({ stripExtraction: true });
    const p = await loadProject(writeTemp(file));
    const s = await tools.projectSummary(p);
    const cr = s.source.calc_revision as { extraction: string; pdf_sha256: string; extraction_note: string };
    expect(cr.extraction).toBe("re-extracted");
    expect(cr.extraction_note).toMatch(/predates document hashes/);
    expect(cr.pdf_sha256).toBe(await sha256(pdf));
    const stored = await loadProject(writeTemp((await buildProjectFile()).file));
    expect((await tools.projectSummary(stored)).calcs).toEqual(s.calcs);
  });

  it("an extraction whose hash does not match the PDF is not trusted", async () => {
    const { file, pdf } = await buildProjectFile();
    const c = file.revisions.find((r) => r.kind === "calcs")!;
    const pkg = c.extraction as CalcPackage;
    const other = "e".repeat(64);
    c.extraction = { ...pkg, source_sha256: other, pages: pkg.pages.map((pg) => ({ ...pg, doc_sha256: other })) };
    const p = await loadProject(writeTemp(file));
    const v = await p.view();
    expect(v.calcs?.extraction).toBe("re-extracted");
    expect(v.run?.producers.calc_package.sha256).toBe(await sha256(pdf));
  });

  it("revision arguments select other revisions; a project with no calcs still answers model questions", async () => {
    const { file } = await buildProjectFile();
    const p = await loadProject(writeTemp(file));
    const s1 = await tools.projectSummary(p, { model_revision: 1 });
    expect(s1.counts.elements).toBe(7);
    const noCalcs = await loadProject(writeTemp({ ...file, revisions: file.revisions.filter((r) => r.kind === "model") }));
    const s = await tools.projectSummary(noCalcs);
    expect([s.counts.elements, s.counts.calcs, s.counts.links, s.source.calc_revision]).toEqual([6, 0, 0, null]);
    await expect(tools.getCalc(noCalcs, { key: "x" })).rejects.toThrow(/no calc package/);
  });
});
