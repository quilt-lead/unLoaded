/**
 * The decisions file: calc-parser's Decision format, validated on load, append-only atomic writes,
 * external changes picked up before reads and before appending, and the write tools over MCP.
 */
import { existsSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { beforeAll, describe, expect, it } from "vitest";
import { DecisionsFile, parseDecisions } from "../src/decisions.ts";
import type { Project } from "../src/project.ts";
import { call, connect, inputs, loadProject, tempDir } from "./helpers.ts";

describe("parseDecisions", () => {
  it("accepts calc-parser Decisions and names the bad entry and field", () => {
    expect(parseDecisions([{ global_id: "g", calc_key: "k", action: "confirm", at: "2026-11-14T10:00:00Z", actor: null }], "d.json")).toHaveLength(1);
    expect(() => parseDecisions({}, "d.json")).toThrow(/must be a JSON array/);
    expect(() => parseDecisions([{ global_id: "g", calc_key: "k", action: "approve", at: "2026-11-14" }], "d.json")).toThrow(/entry 0: "action" must be one of confirm, reject, manual, undo/);
    expect(() => parseDecisions([{ global_id: "g", calc_key: "k", action: "confirm", at: "yesterday" }], "d.json")).toThrow(/entry 0: "at" must be an ISO date-time/);
    expect(() => parseDecisions([{ calc_key: "k", action: "confirm", at: "2026-11-14" }], "d.json")).toThrow(/entry 0: "global_id"/);
  });
});

describe("DecisionsFile", () => {
  it("creates the file on the first append, writes atomically, never drops entries written by someone else", async () => {
    const dir = tempDir();
    const path = join(dir, "decisions.json");
    const f = new DecisionsFile(path);
    await f.load();
    expect(f.exists).toBe(false);
    const d = (action: "confirm" | "reject", actor: string) => ({ global_id: "g", calc_key: "k", action, at: new Date().toISOString(), actor, note: null });
    await f.append(() => [d("confirm", "me")]);
    expect(JSON.parse(readFileSync(path, "utf8"))).toHaveLength(1);
    expect(readdirSync(dir)).toEqual(["decisions.json"]); // no temp file left behind
    // someone else appends meanwhile
    writeFileSync(path, JSON.stringify([...JSON.parse(readFileSync(path, "utf8")), d("reject", "other")]));
    const r = await f.append((cur) => (expect(cur).toHaveLength(2), [d("confirm", "me")]));
    expect(r.reloaded).toBe(true);
    expect(JSON.parse(readFileSync(path, "utf8")).map((x: { actor: string }) => x.actor)).toEqual(["me", "other", "me"]);
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

  it("appends a Decision, recomputes status, and reports before / after", async () => {
    const client = await connect(p);
    const el = p.elements.find((e) => p.status.get(e.global_id) === "review")!;
    const l = p.links.filter((x) => x.global_id === el.global_id).sort((a, b) => b.conf - a.conf)[0]!;
    const r = await call(client, "record_decision", { global_id: el.global_id, calc_key: l.calc_key, action: "confirm", note: "checked page" });
    expect(r.isError).toBe(false);
    expect(r.json.recorded[0]).toMatchObject({ status_before: "review", status_after: "confirmed", link_after: { status: "confirmed", decided_by: "Jane Engineer" } });
    const file = JSON.parse(readFileSync(path, "utf8"));
    expect(file).toEqual([{ global_id: el.global_id, calc_key: l.calc_key, action: "confirm", at: file[0].at, actor: "Jane Engineer", note: "checked page" }]);
    const ge = await call(client, "get_element", { id: el.global_id });
    expect(ge.json.links.find((x: { calc_key: string }) => x.calc_key === l.calc_key).decision).toMatchObject({ action: "confirm", decided_by: "Jane Engineer", note: "checked page" });
    expect(ge.json.source.decisions.sha256).toMatch(/^[0-9a-f]{64}$/);
    await client.close();
  });

  it("writes nothing when any batch entry is invalid, and lists every problem", async () => {
    const client = await connect(p);
    const before = readFileSync(path, "utf8");
    const el = p.elements[0]!;
    const r = await call(client, "record_decisions", {
      decisions: [
        { global_id: el.global_id, calc_key: "no-such-calc", action: "manual" },
        { global_id: "NOPE", calc_key: p.calcs[0]!.key, action: "confirm" },
        { global_id: el.global_id, calc_key: p.calcs[3]!.key, action: "undo" },
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

  it("points a mark at its GlobalId, and refuses confirm where there is no automatic link", async () => {
    const client = await connect(p);
    const el = p.elements.find((e) => e.mark && p.elements.filter((x) => x.mark === e.mark).length === 1)!;
    const r = await call(client, "record_decision", { global_id: el.mark, calc_key: p.calcs[2]!.key, action: "manual" });
    expect(r.text).toMatch(new RegExp(`is a mark; its GlobalId is ${el.global_id.replace(/\$/g, "\\$")}`));
    const unlinked = p.calcs.find((c) => !p.rawLinks.some((l) => l.global_id === el.global_id && l.calc_key === c.key))!;
    const r2 = await call(client, "record_decision", { global_id: el.global_id, calc_key: unlinked.key, action: "reject" });
    expect(r2.text).toMatch(/no automatic link .* use manual to link them by hand/);
    await client.close();
  });

  it("picks up a decision written to the file by someone else before answering", async () => {
    const client = await connect(p);
    const l = p.rawLinks.find((x) => x.tier === "exact")!;
    const cur = JSON.parse(readFileSync(path, "utf8"));
    writeFileSync(path, JSON.stringify([...cur, { global_id: l.global_id, calc_key: l.calc_key, action: "reject", at: new Date().toISOString(), actor: "colleague", note: null }]));
    const ge = await call(client, "get_element", { id: l.global_id });
    expect(ge.json.links.find((x: { calc_key: string }) => x.calc_key === l.calc_key).status).toBe("rejected");
    await client.close();
  });
});

describe("read-only server", () => {
  it("explains how to enable writes when started without --decisions", async () => {
    const p = await loadProject(inputs());
    const client = await connect(p);
    const r = await call(client, "record_decision", { global_id: p.elements[0]!.global_id, calc_key: p.calcs[0]!.key, action: "manual" });
    expect(r.isError).toBe(true);
    expect(r.text).toMatch(/started without --decisions/);
    expect(existsSync(join(process.cwd(), "decisions.json"))).toBe(false);
    await client.close();
  }, 120_000);
});
