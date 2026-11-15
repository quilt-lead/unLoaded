/**
 * The decisions file: calc-mapper's decision log (Decisions made by addDecision, read back through
 * decisionFrom), validated on load, append-only atomic writes, external changes picked up before
 * reads and before appending, and the write tools over MCP.
 */
import { existsSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { beforeAll, describe, expect, it } from "vitest";
import { addDecision, applyDecisions, type Decision } from "@unloaded/calc-mapper";
import { DecisionsFile, parseDecisions } from "../src/decisions.ts";
import type { Project } from "../src/project.ts";
import { call, connect, inputs, loadProject, tempDir } from "./helpers.ts";

const at = "2026-11-14T10:00:00Z";

describe("parseDecisions", () => {
  it("accepts calc-mapper Decisions (with or without provenance) and names the bad entry and field", () => {
    const made = addDecision([], { global_id: "g", calc_key: "k", action: "confirm", actor: "me" }, { at });
    expect(parseDecisions(JSON.parse(JSON.stringify(made)), "d.json")).toEqual(JSON.parse(JSON.stringify(made)));
    expect(parseDecisions([{ id: 1, global_id: "g", calc_key: "k", action: "confirm", at, actor: null, note: null }], "d.json")).toHaveLength(1);
    expect(() => parseDecisions({}, "d.json")).toThrow(/must be a JSON array/);
    expect(() => parseDecisions([{ global_id: "g", calc_key: "k", action: "confirm", at }], "d.json")).toThrow(/entry 0: "id" must be a positive integer/);
    expect(() => parseDecisions([{ id: 1, global_id: "g", calc_key: "k", action: "confirm", at }, { id: 1, global_id: "g", calc_key: "k", action: "undo", at }], "d.json"))
      .toThrow(/entry 1: "id" 1 is also the id of entry 0/);
    expect(() => parseDecisions([{ id: 1, global_id: "g", calc_key: "k", action: "approve", at }], "d.json")).toThrow(/entry 0: "action" must be one of confirm, reject, manual, undo/);
    expect(() => parseDecisions([{ id: 1, global_id: "g", calc_key: "k", action: "confirm", at: "yesterday" }], "d.json")).toThrow(/entry 0: "at" must be an ISO date-time/);
    expect(() => parseDecisions([{ id: 1, calc_key: "k", action: "confirm", at }], "d.json")).toThrow(/entry 0: "global_id"/);
  });
});

describe("DecisionsFile", () => {
  it("creates the file on the first append, writes atomically, never drops or rewrites entries written by someone else", async () => {
    const dir = tempDir();
    const path = join(dir, "decisions.json");
    const f = new DecisionsFile(path);
    await f.load();
    expect(f.exists).toBe(false);
    const next = (log: readonly unknown[], action: "confirm" | "reject", actor: string): Decision =>
      addDecision(log as Decision[], { global_id: "g", calc_key: "k", action, actor }, { at: new Date().toISOString() }).at(-1)!;
    await f.append((cur) => [next(cur, "confirm", "me")]);
    expect(JSON.parse(readFileSync(path, "utf8"))).toHaveLength(1);
    expect(readdirSync(dir)).toEqual(["decisions.json"]); // no temp file left behind
    // someone else appends meanwhile, without provenance
    const other = { id: 2, global_id: "g", calc_key: "k", action: "reject", at: new Date().toISOString(), actor: "other", note: null };
    writeFileSync(path, JSON.stringify([...JSON.parse(readFileSync(path, "utf8")), other]));
    const r = await f.append((cur) => (expect(cur).toHaveLength(2), [next(cur, "confirm", "me")]));
    expect(r.reloaded).toBe(true);
    const file = JSON.parse(readFileSync(path, "utf8"));
    expect(file.map((x: { actor: string; id: number }) => [x.id, x.actor])).toEqual([[1, "me"], [2, "other"], [3, "me"]]);
    expect(file[1]).toEqual(other); // kept exactly as written: no provenance added
  });

  it("rejects a malformed file with the reason", async () => {
    const path = join(tempDir(), "d.json");
    writeFileSync(path, "{not json");
    await expect(new DecisionsFile(path).load()).rejects.toThrow(/d.json is not valid JSON/);
  });
});

describe("record_decision / record_decisions over MCP", () => {
  let p: Project;
  let path: string;
  beforeAll(async () => {
    path = join(tempDir(), "decisions.json");
    p = await loadProject(inputs({ decisions: path, actor: "Jane Engineer" }));
  }, 120_000);

  it("appends a calc-mapper Decision (id, revisions, human provenance), recomputes status, and reports before / after", async () => {
    const client = await connect(p);
    const r = await call(client, "record_decision", { global_id: "B1", calc_key: "beam-design-check", action: "reject", note: "wrong calc" });
    expect(r.isError, r.text).toBe(false);
    expect(r.json.recorded[0]).toMatchObject({ status_before: "confirmed", status_after: "unmapped", link_after: { status: "rejected", decided_by: "Jane Engineer" } });
    const file = JSON.parse(readFileSync(path, "utf8"));
    expect(file).toHaveLength(1);
    expect(file[0]).toMatchObject({
      id: 1, global_id: "B1", calc_key: "d1#beam-design-check", action: "reject", actor: "Jane Engineer", note: "wrong calc",
      model_rev: "test_rev1.graph.json", calc_rev: "test_calcs.pdf",
      provenance: { method: "human", rule: "decision.reject", actor: "Jane Engineer", at: file[0].at },
    });
    expect([...file[0].provenance.inputs].sort()).toEqual([p.graph.graphSha256, p.pdfs[0]!.sha256].sort());
    // the engine applies the file as written
    const applied = applyDecisions(p.rawLinks, file, p.gids, p.calcKeys).find((l) => l.global_id === "B1" && l.calc_key === "d1#beam-design-check");
    expect(applied?.status).toBe("rejected");
    const ge = await call(client, "get_element", { id: "B1" });
    expect(ge.json.links.find((x: { calc_key: string }) => x.calc_key === "d1#beam-design-check").decision).toMatchObject({ action: "reject", decided_by: "Jane Engineer", note: "wrong calc" });
    expect(ge.json.source.decisions.sha256).toMatch(/^[0-9a-f]{64}$/);
    // findings on a rejected link are left out (buildState)
    const c2 = await call(client, "record_decision", { global_id: "C2", calc_key: "column-design-check", action: "reject" });
    expect(c2.isError).toBe(false);
    expect((await call(client, "list_findings")).json.total).toBe(0);
    await call(client, "record_decision", { global_id: "C2", calc_key: "column-design-check", action: "undo" });
    expect((await call(client, "list_findings")).json.total).toBe(1);
    expect(JSON.parse(readFileSync(path, "utf8")).map((d: { id: number }) => d.id)).toEqual([1, 2, 3]);
    await client.close();
  });

  it("writes nothing when any batch entry is invalid, and lists every problem", async () => {
    const client = await connect(p);
    const before = readFileSync(path, "utf8");
    const r = await call(client, "record_decisions", {
      decisions: [
        { global_id: "C1", calc_key: "no-such-calc", action: "manual" },
        { global_id: "NOPE", calc_key: "beam-design-check", action: "confirm" },
        { global_id: "F1", calc_key: "beam-design-check", action: "undo" },
      ],
    });
    expect(r.isError).toBe(true);
    expect(r.text).toMatch(/nothing was written/);
    expect(r.text).toMatch(/decision 0: no calc "no-such-calc"/);
    expect(r.text).toMatch(/decision 1: no element with GlobalId "NOPE"/);
    expect(r.text).toMatch(/decision 2: there is no decision .* to undo/);
    expect(readFileSync(path, "utf8")).toBe(before);
    await client.close();
  });

  it("points a mark at its GlobalId, refuses confirm where there is no automatic link, and links by hand", async () => {
    const client = await connect(p);
    const r = await call(client, "record_decision", { global_id: "C-1", calc_key: "beam-design-check", action: "manual" });
    expect(r.text).toMatch(/"C-1" is a mark; its GlobalId is C1/);
    const r2 = await call(client, "record_decision", { global_id: "F1", calc_key: "beam-design-check", action: "reject" });
    expect(r2.text).toMatch(/no automatic link .* use manual to link them by hand/);
    const r3 = await call(client, "record_decision", { global_id: "F1", calc_key: "column-design-check", action: "manual" });
    expect(r3.json.recorded[0]).toMatchObject({ status_before: "unmapped", status_after: "confirmed", link_after: { tier: "manual", role: "design" } });
    await client.close();
  });

  it("picks up a decision written to the file by someone else before answering", async () => {
    const client = await connect(p);
    const cur = JSON.parse(readFileSync(path, "utf8"));
    const id = Math.max(...cur.map((d: { id: number }) => d.id)) + 1;
    writeFileSync(path, JSON.stringify([...cur, { id, global_id: "C1", calc_key: "column-design-check", action: "reject", at: new Date().toISOString(), actor: "colleague", note: null }]));
    // a bare key (written by hand, or before calc sets) names a calc of the first document, as in the app
    const ge = await call(client, "get_element", { id: "C1" });
    expect(ge.json.links.find((x: { calc_key: string }) => x.calc_key === "d1#column-design-check").status).toBe("rejected");
    await client.close();
  });
});

describe("read-only server", () => {
  it("explains how to enable writes when started without --decisions", async () => {
    const p = await loadProject(inputs());
    const client = await connect(p);
    const r = await call(client, "record_decision", { global_id: "C1", calc_key: "beam-design-check", action: "manual" });
    expect(r.isError).toBe(true);
    expect(r.text).toMatch(/started without --decisions/);
    expect(existsSync(join(process.cwd(), "decisions.json"))).toBe(false);
    await client.close();
  }, 120_000);
});
