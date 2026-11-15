/**
 * Shared test setup: the byte-built fixture project (test/fixtures.ts: two element-graph revisions and
 * two calc PDFs written in the test, nothing generated or committed as binary), temp dirs and an
 * in-memory MCP client.
 */
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { InMemoryTransport } from "@modelcontextprotocol/sdk/inMemory.js";
import { loadProject, type Project } from "../src/project.ts";
import { createServer } from "../src/server.ts";
import type { ProjectInputs } from "../src/inputs.ts";
import { writeFixtureFiles } from "./fixtures.ts";

/** The fixture files, written once per test file. */
export const FIX = writeFixtureFiles();
/** Model rev 1 (a serialized element graph) and the main calc PDF. */
export const MODEL = FIX.rev1;
export const MODEL_REV2 = FIX.rev2;
export const PDF = FIX.main;
export const SUPPLEMENT = FIX.supplement;
/** The cross-PDF pair (fixtures.ts CROSS_*): B-101 designed in both, a "see page 2" and a "carried to" across PDFs. */
export const CROSS_MAIN = FIX.crossMain;
export const CROSS_SUPPLEMENT = FIX.crossSupplement;

export const tempDir = () => mkdtempSync(join(tmpdir(), "unloaded-mcp-test-"));

export function inputs(over: Partial<ProjectInputs> = {}): ProjectInputs {
  return { models: [MODEL], calcs: [PDF], projectFile: null, decisions: null, actor: "tester", manifest: null, ...over };
}

export async function connect(project: Project): Promise<Client> {
  const [ct, st] = InMemoryTransport.createLinkedPair();
  await createServer(project).connect(st);
  const client = new Client({ name: "test", version: "0" });
  await client.connect(ct);
  return client;
}

export type Content = { type: string; text?: string; data?: string; mimeType?: string };

export async function call(client: Client, name: string, args: Record<string, unknown> = {}) {
  const r = await client.callTool({ name, arguments: args });
  const content = r.content as Content[];
  const text = content.find((c) => c.type === "text")?.text ?? "";
  return { isError: r.isError === true, content, text, json: r.isError ? null : JSON.parse(text) };
}

/** Plain JSON (drops undefined, as the MCP channel does). */
export const plain = <T>(v: T): T => JSON.parse(JSON.stringify(v)) as T;

export { loadProject };
