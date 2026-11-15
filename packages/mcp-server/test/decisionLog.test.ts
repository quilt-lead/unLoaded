import { describe, expect, it } from "vitest";
import type { ProjectFile } from "@unloaded/project-file";
import { decisionsOf } from "../src/decisionLog.ts";

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

describe("decision log as the engine reads it", () => {
  it("ids 1..n in file order, engine field names, revisions kept", () => {
    const d = decisionsOf(file());
    expect(d.map((x) => [x.id, x.global_id, x.calc_key, x.action, x.model_rev])).toEqual([[1, "G", "k", "confirm", 1], [2, "G", "k", "reject", 4]]);
    expect(d[1]!.note).toBe("no");
  });
});
