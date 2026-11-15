/** Shared test setup: the calc-parser fixture (already on prod, referenced in place), temp dirs, an in-memory MCP client. */
import { copyFileSync, mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { InMemoryTransport } from "@modelcontextprotocol/sdk/inMemory.js";
import { loadProject, type Project } from "../src/project.ts";
import { createServer } from "../src/server.ts";
import type { ProjectInputs } from "../src/inputs.ts";

export const MODEL = fileURLToPath(new URL("../../calc-parser/test/fixtures/model_rev1.ifc", import.meta.url));
export const PDF = fileURLToPath(new URL("../../calc-parser/test/fixtures/calc_package.pdf", import.meta.url));

export const tempDir = () => mkdtempSync(join(tmpdir(), "unloaded-mcp-test-"));

export function inputs(over: Partial<ProjectInputs> = {}): ProjectInputs {
  return { model: MODEL, calcs: [PDF], decisions: null, actor: "tester", manifest: null, ...over };
}

/** The fixture PDF copied twice under two names (main + a supplement), in a fresh temp dir. */
export function twoPdfs(): { dir: string; main: string; supplement: string } {
  const dir = tempDir();
  const main = join(dir, "main-package.pdf");
  const supplement = join(dir, "Supplement A.pdf");
  copyFileSync(PDF, main);
  copyFileSync(PDF, supplement);
  return { dir, main, supplement };
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

export { loadProject };
