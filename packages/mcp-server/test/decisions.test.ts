/**
 * The decisions file: calc-mapper's decision log (Decisions made by addDecision, read back through
 * decisionFrom), validated on load, append-only atomic writes under a cross-process lock, reads and
 * appends serialised, a symlinked path written through, a malformed file served around (never
 * overwritten), external changes picked up before reads and before appending, and the write tools
 * over MCP.
 */
import { spawn } from "node:child_process";
import { chmodSync, existsSync, lstatSync, readdirSync, readFileSync, statSync, symlinkSync, writeFileSync } from "node:fs";
import { hostname } from "node:os";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import { beforeAll, describe, expect, it } from "vitest";
import { addDecision, applyDecisions, effectiveDecisions, type Decision } from "@unloaded/calc-mapper";
import { DecisionsFile, parseDecisions } from "../src/decisions.ts";
import { INSTRUCTIONS } from "../src/server.ts";
import type { Project } from "../src/project.ts";
import { checkReport } from "../src/check.ts";
import * as tools from "../src/tools.ts";
import { PDF, SUPPLEMENT, call, connect, inputs, loadProject, tempDir } from "./helpers.ts";

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

  const make = (log: readonly unknown[], actor: string): Decision =>
    addDecision(log as Decision[], { global_id: "g", calc_key: "k", action: "confirm", actor }, { at: new Date().toISOString() }).at(-1)!;

  it("a malformed file is a problem, not a crash: the last good log is kept, appends are refused, the file is never overwritten", async () => {
    const path = join(tempDir(), "d.json");
    writeFileSync(path, "{not json");
    const f = new DecisionsFile(path);
    await f.load();
    expect(f.problem).toMatch(/d.json is not valid JSON/);
    expect(f.log).toEqual([]);
    await expect(f.append((cur) => [make(cur, "me")])).rejects.toThrow(/nothing was written: the decisions file cannot be read/);
    expect(readFileSync(path, "utf8")).toBe("{not json");
    // fixed: one good entry; then broken again: the last good log (1 entry) stays in use
    writeFileSync(path, JSON.stringify([make([], "colleague")]));
    expect(await f.refresh()).toBe(true);
    expect([f.problem, f.log.length]).toEqual([null, 1]);
    writeFileSync(path, JSON.stringify([{ id: 1, global_id: "g", calc_key: "k", action: "approve", at: "2026-11-14T10:00:00Z" }]));
    await f.refresh();
    expect(f.problem).toMatch(/entry 0: "action" must be one of/);
    expect(f.log.map((d) => d.actor)).toEqual(["colleague"]);
    await expect(f.append((cur) => [make(cur, "me")])).rejects.toThrow(/nothing was written/);
    expect(readFileSync(path, "utf8")).toMatch(/approve/);
  });

  it("an empty (0-byte or whitespace) file is refused with a message, not read as an empty log", async () => {
    for (const body of ["", "  \n"]) {
      const path = join(tempDir(), "d.json");
      writeFileSync(path, body);
      const f = new DecisionsFile(path);
      await f.load();
      expect(f.problem).toMatch(/d.json is empty .* write \[\] into it, or delete it/);
      await expect(f.append((cur) => [make(cur, "me")])).rejects.toThrow(/nothing was written/);
      expect(readFileSync(path, "utf8")).toBe(body);
    }
  });

  it("two writers on one file (two DecisionsFile instances = two servers) keep every entry, with distinct ids", async () => {
    const path = join(tempDir(), "decisions.json");
    const a = new DecisionsFile(path);
    const b = new DecisionsFile(path);
    await Promise.all([a.load(), b.load()]);
    const writes: Promise<unknown>[] = [];
    for (let i = 0; i < 10; i++) {
      writes.push(a.append((cur) => [make(cur, "A")]));
      writes.push(b.append((cur) => [make(cur, "B")]));
    }
    await Promise.all(writes);
    const file = JSON.parse(readFileSync(path, "utf8")) as Decision[];
    expect(file.map((d) => d.id)).toEqual(Array.from({ length: 20 }, (_, i) => i + 1));
    expect(file.filter((d) => d.actor === "A")).toHaveLength(10);
    expect(file.filter((d) => d.actor === "B")).toHaveLength(10);
    expect(readdirSync(join(path, ".."))).toEqual(["decisions.json"]); // no lock or temp file left behind
  });

  it("two PROCESSES appending at once keep every entry, with distinct ids", { timeout: 120_000 }, async () => {
    const path = join(tempDir(), "decisions.json");
    const mod = pathToFileURL(new URL("../src/decisions.ts", import.meta.url).pathname).href;
    const script = `
      const { DecisionsFile } = await import(${JSON.stringify(mod)});
      const { addDecision } = await import("@unloaded/calc-mapper");
      const f = new DecisionsFile(process.argv[1]);
      await f.load();
      for (let i = 0; i < 15; i++) {
        await f.append((cur) => [addDecision(cur, { global_id: "g", calc_key: "k", action: "confirm", actor: process.argv[2] }, {}).at(-1)]);
      }`;
    const run = (actor: string) =>
      new Promise<void>((res, rej) => {
        const c = spawn(process.execPath, ["--input-type=module", "-e", script, path, actor], { cwd: new URL("..", import.meta.url).pathname, stdio: ["ignore", "ignore", "pipe"] });
        let err = "";
        c.stderr?.on("data", (d) => (err += d));
        c.on("exit", (code) => (code === 0 ? res() : rej(new Error(`child ${actor} exited ${code}: ${err}`))));
      });
    await Promise.all([run("P1"), run("P2")]);
    const file = JSON.parse(readFileSync(path, "utf8")) as Decision[];
    expect(file.map((d) => d.id)).toEqual(Array.from({ length: 30 }, (_, i) => i + 1));
    expect(file.filter((d) => d.actor === "P1")).toHaveLength(15);
    expect(file.filter((d) => d.actor === "P2")).toHaveLength(15);
  });

  it("waits for a live lock, gives up with the lock file named, and breaks a stale one", async () => {
    const path = join(tempDir(), "decisions.json");
    const f = new DecisionsFile(path, { lockWaitMs: 300 });
    await f.load();
    // a live writer (this process's pid, another token) holds it
    writeFileSync(`${path}.lock`, JSON.stringify({ pid: process.pid, host: hostname(), token: "someone-else", at: new Date().toISOString() }));
    await expect(f.append((cur) => [make(cur, "me")])).rejects.toThrow(/locked by another writer .* delete .*decisions\.json\.lock/);
    expect(existsSync(path)).toBe(false);
    // its owner is gone (a pid that is not running): the lock is stale and broken
    writeFileSync(`${path}.lock`, JSON.stringify({ pid: 2 ** 22 + 12345, host: hostname(), token: "crashed", at: new Date().toISOString() }));
    await f.append((cur) => [make(cur, "me")]);
    expect(JSON.parse(readFileSync(path, "utf8"))).toHaveLength(1);
    expect(existsSync(`${path}.lock`)).toBe(false);
  });

  it("serialises reads with appends: a refresh asked for during an append completes after it, never rolling the log back", async () => {
    const path = join(tempDir(), "decisions.json");
    const f = new DecisionsFile(path);
    await f.load();
    const order: string[] = [];
    let during: Promise<boolean> | null = null;
    await f
      .append((cur) => {
        during = f.refresh().then((r) => (order.push("refresh"), r));
        return [make(cur, "me")];
      })
      .then(() => order.push("append"));
    await during;
    expect(order).toEqual(["append", "refresh"]);
    expect(f.log).toHaveLength(1);
  });

  it("writes through a symlinked path to the real file, keeping the link and the file's mode", async () => {
    const dir = tempDir();
    const real = join(dir, "real.json");
    const linkPath = join(dir, "link.json");
    writeFileSync(real, "[]\n");
    chmodSync(real, 0o640);
    symlinkSync(real, linkPath);
    const f = new DecisionsFile(linkPath);
    await f.load();
    await f.append((cur) => [make(cur, "me")]);
    expect(lstatSync(linkPath).isSymbolicLink()).toBe(true);
    expect(JSON.parse(readFileSync(real, "utf8"))).toHaveLength(1);
    expect(statSync(real).mode & 0o777).toBe(0o640);
    expect(readdirSync(dir).sort()).toEqual(["link.json", "real.json"]);
  });
});

describe("undo, as the engine applies it", () => {
  it("clears the pair back to its automatic state: an earlier decision on the pair is not restored", () => {
    const log = [
      { id: 1, global_id: "g", calc_key: "k", action: "confirm" as const, actor: null, note: null, at },
      { id: 2, global_id: "g", calc_key: "k", action: "reject" as const, actor: null, note: null, at },
      { id: 3, global_id: "g", calc_key: "k", action: "undo" as const, actor: null, note: null, at },
    ];
    expect(effectiveDecisions(log).size).toBe(0); // not the confirm (id 1)
    expect(INSTRUCTIONS).toMatch(/earlier decisions on that pair are NOT restored/);
    expect(INSTRUCTIONS).not.toMatch(/latest decision on/);
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
      id: 1, global_id: "B1", calc_key: "beam-design-check", action: "reject", actor: "Jane Engineer", note: "wrong calc",
      model_rev: "test_rev1.graph.json", calc_rev: "test_calcs.pdf",
      provenance: { method: "human", rule: "decision.reject", actor: "Jane Engineer", at: file[0].at },
    });
    expect([...file[0].provenance.inputs].sort()).toEqual([p.graph.graphSha256, p.pdfs[0]!.sha256].sort());
    // the engine applies the file as written
    const applied = applyDecisions(p.rawLinks, file, p.gids, p.calcKeys).find((l) => l.global_id === "B1" && l.calc_key === "beam-design-check");
    expect(applied?.status).toBe("rejected");
    const ge = await call(client, "get_element", { id: "B1" });
    expect(ge.json.links.find((x: { calc_key: string }) => x.calc_key === "beam-design-check").decision).toMatchObject({ action: "reject", decided_by: "Jane Engineer", note: "wrong calc" });
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
    const ge = await call(client, "get_element", { id: "C1" });
    expect(ge.json.links.find((x: { calc_key: string }) => x.calc_key === "column-design-check").status).toBe("rejected");
    await client.close();
  });
});

describe("the decisions file over MCP: external writers, a malformed file, calc keys that are gone", () => {
  it("a write reports and keeps a decision someone else appended since this server last read the file", async () => {
    const path = join(tempDir(), "decisions.json");
    const p = await loadProject(inputs({ decisions: path }));
    const client = await connect(p);
    const r1 = await call(client, "record_decision", { global_id: "C1", calc_key: "column-design-check", action: "confirm" });
    expect([r1.isError, r1.json.reloaded_external_changes, r1.json.recorded[0].decision]).toEqual([false, false, expect.objectContaining({ origin: "decisions_file", id: 1 })]);
    // a colleague appends, formatted as the server writes; NO read in between
    const ext = { id: 2, global_id: "C1", calc_key: "column-design-check", action: "reject", at: new Date().toISOString(), actor: "colleague", note: null };
    const before = JSON.stringify([...JSON.parse(readFileSync(path, "utf8")), ext], null, 2) + "\n";
    writeFileSync(path, before);
    const r2 = await call(client, "record_decision", { global_id: "B1", calc_key: "beam-design-check", action: "confirm" });
    expect(r2.isError, r2.text).toBe(false);
    expect(r2.json.reloaded_external_changes).toBe(true);
    expect(r2.json.recorded[0].decision).toMatchObject({ origin: "decisions_file", id: 3 });
    const after = readFileSync(path, "utf8");
    // every earlier entry written back byte for byte: the old file minus its closing bracket is a prefix of the new one
    expect(after.startsWith(before.slice(0, before.lastIndexOf("\n]")))).toBe(true);
    expect(JSON.parse(after)[1]).toEqual(ext);
    expect((await call(client, "get_element", { id: "C1" })).json.links.find((l: { calc_key: string }) => l.calc_key === "column-design-check").status).toBe("rejected");
    await client.close();
  }, 120_000);

  it("reads keep working on the last good log with a warning when the file turns malformed; writes are refused; the file is never overwritten", async () => {
    const path = join(tempDir(), "decisions.json");
    const p = await loadProject(inputs({ decisions: path }));
    const client = await connect(p);
    await call(client, "record_decision", { global_id: "B1", calc_key: "beam-design-check", action: "reject" });
    writeFileSync(path, '[{"id": 1, "global_id": "B1"'); // a half-written edit
    const s = await call(client, "project_summary");
    expect(s.isError, s.text).toBe(false);
    expect(s.json.decisions.problem).toMatch(/not valid JSON/);
    expect(s.json.warnings.some((w: string) => /decisions file cannot be read/.test(w))).toBe(true);
    const ge = await call(client, "get_element", { id: "B1" });
    expect(ge.isError).toBe(false);
    expect(ge.json.source.decisions_warning).toMatch(/last good copy of the log \(1 entry\)/);
    expect(ge.json.links.find((l: { calc_key: string }) => l.calc_key === "beam-design-check").status).toBe("rejected"); // the last good log
    const w = await call(client, "record_decision", { global_id: "C1", calc_key: "column-design-check", action: "confirm" });
    expect(w.isError).toBe(true);
    expect(w.text).toMatch(/nothing was written: the decisions file cannot be read/);
    expect(readFileSync(path, "utf8")).toBe('[{"id": 1, "global_id": "B1"');
    // fixed: the warning goes, writes work again
    writeFileSync(path, "[]");
    const s2 = await call(client, "project_summary");
    expect([s2.json.decisions.problem, s2.json.source.decisions_warning]).toEqual([null, undefined]);
    expect((await call(client, "record_decision", { global_id: "C1", calc_key: "column-design-check", action: "confirm" })).isError).toBe(false);
    await client.close();
  }, 120_000);

  it("starts on a malformed file (no good log yet) and says so in --check terms", async () => {
    const path = join(tempDir(), "decisions.json");
    writeFileSync(path, "");
    const p = await loadProject(inputs({ decisions: path }));
    expect(p.decisions!.problem).toMatch(/is empty/);
    expect(checkReport(p, { serverName: "unloaded", version: "0" })).toMatch(/NOT READY: the decisions file cannot be read/);
  }, 120_000);

  it("warns loudly when decisions name calc keys this project does not have, naming the likely cause", async () => {
    const path = join(tempDir(), "decisions.json");
    const d = (id: number, calc_key: string) => ({ id, global_id: "B1", calc_key, action: "confirm", at, actor: "x", note: null });
    writeFileSync(path, JSON.stringify([d(1, "supplement-a/connection-design-check"), d(2, "beam-design-chek"), d(3, "beam-design-check")]));
    const p = await loadProject(inputs({ decisions: path })); // one PDF: Supplement A is not loaded
    const w = tools.projectSummary(p).warnings.join("\n");
    expect(w).toMatch(/2 decision\(s\) name 2 calc key\(s\) that are not in this project; they are kept but NOT applied/);
    expect(w).toMatch(/"supplement-a\/connection-design-check" .* no loaded calc PDF has the key prefix "supplement-a\/"/);
    expect(w).toMatch(/"beam-design-chek" .* the main PDF \(test_calcs\.pdf.* has no calc with this key: was the --calcs order changed/);
    expect(checkReport(p, { serverName: "unloaded", version: "0" })).toMatch(/no loaded calc PDF has the key prefix/);
    // loaded with the supplement, that key applies and its warning goes
    const p2 = await loadProject(inputs({ decisions: path, calcs: [PDF, SUPPLEMENT] }));
    expect(tools.projectSummary(p2).warnings.join("\n")).not.toMatch(/supplement-a\/connection-design-check/);
  }, 120_000);
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
