import { describe, expect, it } from "vitest";
import { ProjectFileError, decisionsOf, headOf, parseProjectFile, type ProjectFile } from "../src/projectFile.ts";

const base = (): ProjectFile => ({
  format: "unloaded.calc-graph-project", version: 1, exportedAt: "2026-11-14T21:00:00-05:00",
  project: { name: "P", createdAt: "2026-11-14T21:00:00-05:00" },
  revisions: [
    { id: 4, kind: "model", seq: 2, label: "b", sourceName: "b.ifc", mediaType: "application/x-step", createdAt: "", meta: {}, blob: "" },
    { id: 1, kind: "model", seq: 1, label: "a", sourceName: "a.ifc", mediaType: "application/x-step", createdAt: "", meta: {}, blob: "" },
    { id: 2, kind: "calcs", seq: 1, label: "c", sourceName: "c.pdf", mediaType: "application/pdf", createdAt: "", meta: {}, blob: "" },
  ],
  decisions: [
    { globalId: "G", calcKey: "k", action: "confirm", actor: "r", note: null, at: "t1", modelRev: 1, calcRev: 2 },
    { globalId: "G", calcKey: "k", action: "reject", actor: "r", note: "no", at: "t2", modelRev: 4, calcRev: 2 },
  ],
});

describe("project file (the app's exportProject format)", () => {
  it("accepts the app's format and rejects anything else with the reason", () => {
    expect(parseProjectFile(base()).project.name).toBe("P");
    expect(() => parseProjectFile({ ...base(), format: "unloaded.calc-graph-export" })).toThrow(/not a calc-graph project file/);
    expect(() => parseProjectFile({ ...base(), version: 2 })).toThrow(/version 2 is not supported/);
    expect(() => parseProjectFile([])).toThrow(ProjectFileError);
    const dup = base();
    dup.revisions[1]!.id = 4;
    expect(() => parseProjectFile(dup)).toThrow(/duplicate revision id 4/);
    const badKind = base() as unknown as { revisions: { kind: string }[] };
    badKind.revisions[0]!.kind = "drawings";
    expect(() => parseProjectFile(badKind)).toThrow(/kind must be/);
  });

  it("head of a kind = highest id (what the app's importer leaves as head)", () => {
    const f = base();
    expect(headOf(f.revisions, "model")?.id).toBe(4);
    expect(headOf(f.revisions, "calcs")?.id).toBe(2);
    expect(headOf([], "calcs")).toBeNull();
  });

  it("decision log: ids 1..n in file order, engine field names, revisions kept", () => {
    const d = decisionsOf(base());
    expect(d.map((x) => [x.id, x.global_id, x.calc_key, x.action, x.model_rev])).toEqual([[1, "G", "k", "confirm", 1], [2, "G", "k", "reject", 4]]);
    expect(d[1]!.note).toBe("no");
  });
});
