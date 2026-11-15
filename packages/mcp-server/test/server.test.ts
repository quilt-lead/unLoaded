/**
 * The MCP surface, through the official client over an in-memory transport: the tool list and its
 * read-only annotations, the JSON envelope, image content, errors as tool errors, the file never
 * written, and the per-hash cache picking up a re-saved file.
 */
import { readFileSync, statSync, utimesSync, writeFileSync } from "node:fs";
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { InMemoryTransport } from "@modelcontextprotocol/sdk/inMemory.js";
import { sha256 } from "@unloaded/calc-mapper";
import { ProjectSource } from "../src/project.ts";
import { SERVER_VERSION, TOOL_NAMES, createServer } from "../src/server.ts";
import { buildProjectFile, writeTemp } from "./fixtures.ts";

type Content = { type: string; text?: string; data?: string; mimeType?: string };

describe("MCP server", () => {
  let path: string;
  let before: string;
  let client: Client;

  beforeAll(async () => {
    path = writeTemp((await buildProjectFile()).file);
    before = await sha256(new Uint8Array(readFileSync(path)));
    const [ct, st] = InMemoryTransport.createLinkedPair();
    await createServer(new ProjectSource(path)).connect(st);
    client = new Client({ name: "test", version: "0" });
    await client.connect(ct);
  });
  afterAll(async () => {
    await client?.close();
  });

  async function call(name: string, args: Record<string, unknown> = {}) {
    const r = await client.callTool({ name, arguments: args });
    return { isError: r.isError === true, content: r.content as Content[] };
  }
  const json = (c: Content[]) => JSON.parse(c.find((x) => x.type === "text")!.text!);

  it("lists every tool, each annotated read-only and non-destructive", async () => {
    const { tools } = await client.listTools();
    expect(tools.map((t) => t.name)).toEqual([...TOOL_NAMES]);
    for (const t of tools) {
      expect(t.annotations).toMatchObject({ readOnlyHint: true, destructiveHint: false, openWorldHint: false });
      expect(t.description?.length).toBeGreaterThan(40);
    }
  });

  it("answers every tool, and never writes the project file", async () => {
    const calls: [string, Record<string, unknown>][] = [
      ["project_summary", {}], ["search_elements", { kind: "column" }], ["get_element", { id: "B-101" }],
      ["get_calc", { key: "beam-design-check", include_text: true }], ["impact_of_change", { id: "C-1", mode: "remove" }],
      ["list_revisions", {}], ["compare_revisions", {}], ["list_findings", {}], ["list_typical_groups", {}],
      ["move_column", { column: "C-2", dx: 1 }],
    ];
    for (const [name, args] of calls) {
      const r = await call(name, args);
      expect(r.isError, `${name}: ${r.content[0]?.text}`).toBe(false);
      expect(json(r.content).source).toBeTruthy();
    }
    expect(await sha256(new Uint8Array(readFileSync(path)))).toBe(before);
  });

  it("get_page_image returns PNG image content plus the frame and the PDF's hash", async () => {
    const s = json((await call("project_summary")).content);
    const r = await call("get_page_image", { page: 1, rect: [40, 40, 400, 120], highlight: [[48, 50, 200, 70]], width: 600 });
    expect(r.isError).toBe(false);
    const img = r.content.find((c) => c.type === "image")!;
    expect(img.mimeType).toBe("image/png");
    const png = Buffer.from(img.data!, "base64");
    expect(png.subarray(1, 4).toString()).toBe("PNG");
    expect(png.readUInt32BE(16)).toBe(600);
    const meta = json(r.content);
    expect(meta.area_pt).toEqual([40, 40, 400, 120]);
    expect(meta.source.pdf_sha256).toBe(s.source.calc_revision.pdf_sha256);
    expect((await call("get_page_image", { page: 9 })).content[0]!.text).toMatch(/page 9 is not in this PDF \(pages 1-2\)/);
  });

  it("bad input comes back as a tool error, not a crash", async () => {
    const r = await call("get_element", { id: "does-not-exist" });
    expect(r.isError).toBe(true);
    expect(r.content[0]!.text).toMatch(/ToolInputError: no element/);
    expect((await call("project_summary", { model_revision: 99 })).content[0]!.text).toMatch(/no revision 99/);
  });

  it("SERVER_VERSION is package.json's version", () => {
    const pkg = JSON.parse(readFileSync(new URL("../package.json", import.meta.url), "utf8")) as { version: string };
    expect(SERVER_VERSION).toBe(pkg.version);
  });
});

describe("ProjectSource (cache per file hash)", () => {
  it("reuses the loaded project while the bytes are the same, and reloads when the file changes", async () => {
    const { file } = await buildProjectFile();
    const path = writeTemp(file);
    const src = new ProjectSource(path);
    const a = await src.get();
    expect(await src.get()).toBe(a);
    // same bytes, new mtime: re-hashed, same project kept
    const t = statSync(path).mtime;
    utimesSync(path, t, new Date(t.getTime() + 5000));
    expect(await src.get()).toBe(a);
    // re-saved with different content: a new project
    writeFileSync(path, JSON.stringify({ ...file, project: { ...file.project, name: "Renamed" } }));
    const b = await src.get();
    expect(b).not.toBe(a);
    expect(b.file.project.name).toBe("Renamed");
    expect(b.sha256).not.toBe(a.sha256);
  });
});
