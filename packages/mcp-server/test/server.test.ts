/** The MCP surface and the package's own invariants. */
import { readdirSync, readFileSync } from "node:fs";
import { beforeAll, describe, expect, it } from "vitest";
import type { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { SERVER_VERSION, TOOL_NAMES, WRITE_TOOLS } from "../src/server.ts";
import { call, connect, inputs, loadProject } from "./helpers.ts";

describe("MCP server", () => {
  let client: Client;
  beforeAll(async () => {
    client = await connect(await loadProject(inputs()));
  }, 120_000);

  it("lists every tool with annotations: reads read-only, writes not read-only and not idempotent", async () => {
    const { tools } = await client.listTools();
    expect(tools.map((t) => t.name)).toEqual([...TOOL_NAMES]);
    for (const t of tools) {
      const write = (WRITE_TOOLS as readonly string[]).includes(t.name);
      expect(t.annotations).toMatchObject(write ? { readOnlyHint: false, idempotentHint: false, destructiveHint: false } : { readOnlyHint: true });
      expect(t.description!.length).toBeGreaterThan(60);
    }
  });

  it("answers every read tool with a source block", async () => {
    const calls: [string, Record<string, unknown>][] = [
      ["project_summary", {}], ["search_elements", { category: "Column" }], ["get_element", { id: "C5" }], ["list_calcs", {}],
      ["get_calc", { key: "column-design-ram-structural-system", include_text: true }], ["search_calc_text", { query: "W12X53" }],
      ["trace_load_path", { id: "C5" }], ["calc_dependencies", {}], ["impact_of_change", { id: "C5", mode: "remove" }],
      ["review_status", {}], ["export_mapping", { element_limit: 5 }],
    ];
    for (const [name, args] of calls) {
      const r = await call(client, name, args);
      expect(r.isError, `${name}: ${r.text}`).toBe(false);
      expect(r.json.source.engine).toBeTruthy();
      expect(r.json.source.model.sha256).toMatch(/^[0-9a-f]{64}$/);
    }
  });

  it("get_page_image returns PNG image content and its frame", async () => {
    const r = await client.callTool({ name: "get_page_image", arguments: { page: 13, width: 600, crop: false } });
    const content = r.content as { type: string; data?: string; mimeType?: string; text?: string }[];
    const img = content.find((c) => c.type === "image")!;
    expect(img.mimeType).toBe("image/png");
    expect(Buffer.from(img.data!, "base64").readUInt32BE(16)).toBe(600);
    expect(JSON.parse(content.find((c) => c.type === "text")!.text!).source.calc_pdfs[0].file).toBe("calc_package.pdf");
  });

  it("exposes the summary and decisions as resources", async () => {
    const { resources } = await client.listResources();
    expect(resources.map((r) => r.uri).sort()).toEqual(["unloaded://project/decisions", "unloaded://project/summary"]);
    const s = await client.readResource({ uri: "unloaded://project/summary" });
    expect(JSON.parse((s.contents[0] as { text: string }).text).model.elements).toBe(459);
  });

  it("SERVER_VERSION is package.json's version", () => {
    const pkg = JSON.parse(readFileSync(new URL("../package.json", import.meta.url), "utf8")) as { version: string };
    expect(SERVER_VERSION).toBe(pkg.version);
  });
});

describe("engine boundary", () => {
  it("only src/engine.ts imports the engine packages", () => {
    const dir = new URL("../src/", import.meta.url);
    const offenders = readdirSync(dir)
      .filter((f) => f.endsWith(".ts") && f !== "engine.ts")
      .filter((f) => /from\s+["']@unloaded\/(calc-parser|ifc-parser|element-graph|calc-mapper)/.test(readFileSync(new URL(f, dir), "utf8")));
    expect(offenders).toEqual([]);
  });
});
