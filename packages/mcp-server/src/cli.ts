/**
 * unloaded-mcp-server: serve one project over MCP stdio to the AI client that launched it (Claude
 * Desktop, Claude Code, Cursor...). Local only: no port, no network. stdout is the protocol channel,
 * so every log line goes to stderr (bin/unloaded-mcp-server.mjs routes console output before this
 * module loads). See inputs.ts for the arguments.
 */
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { checkReport } from "./check.ts";
import { InputError, USAGE, parseCli } from "./inputs.ts";
import { loadProject } from "./project.ts";
import { SERVER_NAME, SERVER_VERSION, createServer } from "./server.ts";
import { routeConsoleToStderr, suppressedPdfjsWarnings, suppressedWebIfcMessages } from "./stdio.ts";

// idempotent when the bin shim already did it; covers `node src/cli.ts`
routeConsoleToStderr({ verbose: process.argv.includes("--verbose") });

const log = (s: string) => process.stderr.write(s.endsWith("\n") ? s : s + "\n");

let opts: ReturnType<typeof parseCli>;
try {
  opts = parseCli(process.argv.slice(2));
} catch (e) {
  log(`${SERVER_NAME}: ${(e as Error).message}`);
  process.exit(2);
}
if (opts.help) {
  log(USAGE);
  process.exit(0);
}
if (opts.version) {
  log(`${SERVER_NAME} ${SERVER_VERSION}`);
  process.exit(0);
}

let project: Awaited<ReturnType<typeof loadProject>>;
try {
  project = await loadProject(opts.inputs!);
} catch (e) {
  const err = e as Error;
  log(`${SERVER_NAME}: cannot load the project: ${err.message}`);
  if (!(e instanceof InputError) && process.env.UNLOADED_DEBUG) log(err.stack ?? "");
  process.exit(1);
}

if (opts.check) {
  log(checkReport(project, { serverName: SERVER_NAME, version: SERVER_VERSION, suppressedWebIfc: suppressedWebIfcMessages(), suppressedPdfjs: suppressedPdfjsWarnings() }));
  process.exit(0);
}

const c = project.counts;
log(
  `${SERVER_NAME} ${SERVER_VERSION}: serving ${project.projectFile ? `${project.projectFile.name}: ` : ""}${project.current.name}` +
    `${project.models.length > 1 ? ` (+${project.models.length - 1} older revision(s))` : ""} + ${project.pdfs.map((p) => p.name).join(", ")} ` +
    `(${project.elements.length} elements, ${project.calcs.length} calcs; confirmed ${c.confirmed}, review ${c.review}, unmapped ${c.unmapped}); ` +
    (project.decisions ? `decisions -> ${project.decisions.path} as "${project.actor}"` : "read-only (no --decisions)") +
    " on stdio",
);
for (const w of project.warnings) log(`warning: ${w}`);
await createServer(project).connect(new StdioServerTransport());
