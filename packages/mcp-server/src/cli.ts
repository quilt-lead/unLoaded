/**
 * unloaded-mcp-server <project.calcgraph.json>
 *
 * Serves one project file over MCP on stdio to the AI client that launched it (Claude Desktop,
 * Claude Code, Cursor...). Local only: the server opens no port and makes no network request; it
 * reads the file and answers on stdin/stdout. stdout is the protocol channel, so every log line
 * (including pdf.js's own console output) goes to stderr.
 *
 *   --check   load the file, run the engine on the head revisions, print a summary to stderr, exit
 */
import { resolve } from "node:path";
import { parseArgs } from "node:util";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { ProjectSource } from "./project.ts";
import { SERVER_NAME, SERVER_VERSION, createServer } from "./server.ts";
import { projectSummary } from "./tools.ts";

// stdout carries JSON-RPC only: route console output (ours and libraries') to stderr
for (const k of ["log", "info", "warn", "debug"] as const) console[k] = (...a: unknown[]) => console.error(...a);

const USAGE = `usage: unloaded-mcp-server <project.calcgraph.json> [--check]

Serves a calc-graph project file (saved from the app with "Save project") to your AI client over
MCP stdio. Read-only, local: nothing leaves this machine except what your AI client sends.`;

const { values, positionals } = parseArgs({
  allowPositionals: true,
  options: { check: { type: "boolean" }, help: { type: "boolean", short: "h" }, version: { type: "boolean", short: "v" } },
});
if (values.help) {
  console.error(USAGE);
  process.exit(0);
}
if (values.version) {
  console.error(`${SERVER_NAME} ${SERVER_VERSION}`);
  process.exit(0);
}
const file = positionals[0] ?? process.env.UNLOADED_PROJECT_FILE;
if (!file || positionals.length > 1) {
  console.error(USAGE);
  process.exit(2);
}

const source = new ProjectSource(resolve(file));
try {
  const p = await source.get();
  if (values.check) {
    const s = await projectSummary(p);
    console.error(JSON.stringify({ project: s.project, counts: s.counts, source: s.source }, null, 2));
    process.exit(0);
  }
  console.error(`${SERVER_NAME} ${SERVER_VERSION}: serving ${p.file.project.name} (${file}, sha256 ${p.sha256.slice(0, 12)}...) on stdio`);
} catch (e) {
  console.error(`${SERVER_NAME}: cannot read ${file}: ${(e as Error).message}`);
  process.exit(1);
}
await createServer(source).connect(new StdioServerTransport());
