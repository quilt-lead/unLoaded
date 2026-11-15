/**
 * Command-line and project-manifest inputs, validated up front with actionable messages.
 *
 *   unloaded-mcp-server --model model.ifc --calcs main.pdf [--calcs more.pdf ...]
 *                       [--decisions decisions.json] [--actor "name"] [--check] [--verbose]
 *   unloaded-mcp-server --project project.json [--decisions ...] [--actor ...] [--check]
 *
 * project.json: {"model": "...", "calcs": ["main.pdf", ...], "decisions": "...", "actor": "..."},
 * paths relative to the manifest's directory.
 */
import { closeSync, existsSync, openSync, readFileSync, readSync, statSync } from "node:fs";
import { dirname, extname, resolve } from "node:path";
import { parseArgs } from "node:util";

export class InputError extends Error {
  override name = "InputError";
}

export interface ProjectInputs {
  /** Absolute paths. */
  model: string;
  calcs: string[];
  decisions: string | null;
  actor: string | null;
  manifest: string | null;
}

export interface CliOptions {
  inputs: ProjectInputs | null;
  check: boolean;
  verbose: boolean;
  help: boolean;
  version: boolean;
}

export const USAGE = `usage:
  unloaded-mcp-server --model <model.ifc|graph.json> --calcs <main.pdf> [--calcs <more.pdf> ...]
                      [--decisions <decisions.json>] [--actor "<name>"] [--check] [--verbose]
  unloaded-mcp-server --project <project.json> [--decisions <file>] [--actor "<name>"] [--check]

Serves one structural project (an IFC model mapped to its calc-package PDFs) to your AI client over
MCP stdio. Local only: no port is opened and nothing is sent anywhere.

  --model       the model: .ifc, a serialized element graph .json, or a ModelInput .json
  --calcs       a calc-package PDF; repeat for several. The first is the main package: its calc keys are
                the engine's plain keys. Keys of every further PDF are prefixed "<file-stem>/".
  --decisions   review decisions file (JSON array, append-only). Created on the first recorded decision.
                Without it the server is read-only and record_decision explains how to enable it.
  --actor       name recorded on decisions you make through your AI (default: your OS user name)
  --project     a JSON manifest {"model", "calcs": [...], "decisions", "actor"} (paths relative to it)
  --check       load everything, print a summary to stderr, and exit (0 = ok)
  --verbose     also print web-ifc's own parser messages (suppressed by default)`;

function head(path: string, n = 1024): Uint8Array {
  const fd = openSync(path, "r");
  try {
    const buf = Buffer.alloc(n);
    const got = readSync(fd, buf, 0, n, 0);
    return new Uint8Array(buf.subarray(0, got));
  } finally {
    closeSync(fd);
  }
}

function requireFile(path: string, what: string): void {
  if (!existsSync(path)) throw new InputError(`${what} not found: ${path}`);
  const st = statSync(path);
  if (!st.isFile()) throw new InputError(`${what} is not a file: ${path}`);
  if (st.size === 0) throw new InputError(`${what} is empty: ${path}`);
}

/** A PDF starts with "%PDF-" (some writers put junk before it; the spec allows it within 1024 bytes). */
export function looksLikePdf(h: Uint8Array): boolean {
  return Buffer.from(h).toString("latin1").includes("%PDF-");
}

function validateModel(path: string): void {
  requireFile(path, "model file");
  const ext = extname(path).toLowerCase();
  const h = Buffer.from(head(path)).toString("latin1").replace(/^﻿|^ï»¿/, "").trimStart();
  if (looksLikePdf(head(path))) throw new InputError(`--model ${path} is a PDF. Pass the IFC model with --model and calc PDFs with --calcs.`);
  if (h.startsWith("ISO-10303-21")) return;
  if (h.startsWith("{")) return; // JSON: shape checked when loaded
  if (ext === ".ifc") throw new InputError(`--model ${path} has an .ifc extension but no "ISO-10303-21" STEP header: not an IFC file (or it is zipped - .ifczip is not supported, unzip it first)`);
  throw new InputError(`--model ${path} is not an IFC (STEP) file or JSON. Pass a .ifc, a serialized element graph .json or a ModelInput .json.`);
}

function validatePdf(path: string): void {
  requireFile(path, "calc PDF");
  if (!looksLikePdf(head(path))) throw new InputError(`--calcs ${path} is not a PDF (no "%PDF-" header)`);
}

function validateDecisionsPath(path: string): void {
  if (existsSync(path)) {
    if (!statSync(path).isFile()) throw new InputError(`--decisions ${path} is not a file`);
  } else if (!existsSync(dirname(path))) {
    throw new InputError(`--decisions ${path}: directory ${dirname(path)} does not exist (the file itself is created on the first decision)`);
  }
}

function readManifest(path: string): { model: string; calcs: string[]; decisions: string | null; actor: string | null } {
  requireFile(path, "project manifest");
  let data: unknown;
  try {
    data = JSON.parse(readFileSync(path, "utf8").replace(/^﻿/, ""));
  } catch (e) {
    throw new InputError(`project manifest ${path} is not valid JSON: ${(e as Error).message}`);
  }
  if (typeof data !== "object" || data === null || Array.isArray(data)) {
    throw new InputError(`project manifest ${path} must be an object {"model", "calcs": [...], "decisions"?, "actor"?}`);
  }
  const o = data as Record<string, unknown>;
  const known = new Set(["model", "calcs", "decisions", "actor"]);
  const unknown = Object.keys(o).filter((k) => !known.has(k));
  if (unknown.length) throw new InputError(`project manifest ${path}: unknown key(s) ${unknown.join(", ")} (allowed: model, calcs, decisions, actor)`);
  if (typeof o.model !== "string" || !o.model) throw new InputError(`project manifest ${path}: "model" must be a path string`);
  const calcs = typeof o.calcs === "string" ? [o.calcs] : o.calcs;
  if (!Array.isArray(calcs) || !calcs.length || calcs.some((c) => typeof c !== "string" || !c)) {
    throw new InputError(`project manifest ${path}: "calcs" must be a non-empty array of PDF paths (the first is the main package)`);
  }
  for (const k of ["decisions", "actor"] as const) {
    if (o[k] !== undefined && o[k] !== null && typeof o[k] !== "string") throw new InputError(`project manifest ${path}: "${k}" must be a string`);
  }
  const base = dirname(path);
  return {
    model: resolve(base, o.model),
    calcs: (calcs as string[]).map((c) => resolve(base, c)),
    decisions: typeof o.decisions === "string" && o.decisions ? resolve(base, o.decisions) : null,
    actor: typeof o.actor === "string" && o.actor ? o.actor : null,
  };
}

/** Validate a set of inputs (files exist and look like what they claim to be). */
export function validateInputs(inp: ProjectInputs): ProjectInputs {
  validateModel(inp.model);
  if (!inp.calcs.length) throw new InputError("at least one --calcs PDF is required (the calc package the model is mapped to)");
  const seen = new Map<string, number>();
  inp.calcs.forEach((c, i) => {
    validatePdf(c);
    const prev = seen.get(c);
    if (prev !== undefined) throw new InputError(`--calcs ${c} is given twice (positions ${prev + 1} and ${i + 1})`);
    seen.set(c, i);
  });
  if (inp.decisions) validateDecisionsPath(inp.decisions);
  return inp;
}

export function parseCli(argv: string[], cwd = process.cwd()): CliOptions {
  let values: Record<string, string | string[] | boolean | undefined>;
  let positionals: string[];
  try {
    ({ values, positionals } = parseArgs({
      args: argv,
      allowPositionals: true,
      options: {
        model: { type: "string" },
        calcs: { type: "string", multiple: true },
        decisions: { type: "string" },
        actor: { type: "string" },
        project: { type: "string" },
        check: { type: "boolean" },
        verbose: { type: "boolean" },
        help: { type: "boolean", short: "h" },
        version: { type: "boolean", short: "v" },
      },
    }));
  } catch (e) {
    throw new InputError(`${(e as Error).message}\n\n${USAGE}`);
  }
  const base = { check: !!values.check, verbose: !!values.verbose, help: !!values.help, version: !!values.version };
  if (base.help || base.version) return { ...base, inputs: null };
  if (positionals.length) throw new InputError(`unexpected argument(s): ${positionals.join(" ")}\n\n${USAGE}`);
  const str = (k: string) => (typeof values[k] === "string" && values[k] ? resolve(cwd, values[k] as string) : null);
  let inputs: ProjectInputs;
  if (values.project) {
    if (values.model || values.calcs) throw new InputError("use either --project or --model/--calcs, not both");
    const manifest = resolve(cwd, values.project as string);
    const m = readManifest(manifest);
    inputs = {
      model: m.model,
      calcs: m.calcs,
      decisions: str("decisions") ?? m.decisions,
      actor: (values.actor as string | undefined) || m.actor,
      manifest,
    };
  } else {
    if (!values.model) throw new InputError(`--model is required (or --project)\n\n${USAGE}`);
    const calcs = (values.calcs as string[] | undefined) ?? [];
    if (!calcs.length) throw new InputError(`at least one --calcs PDF is required\n\n${USAGE}`);
    inputs = {
      model: str("model")!,
      calcs: calcs.map((c) => resolve(cwd, c)),
      decisions: str("decisions"),
      actor: (values.actor as string | undefined) || null,
      manifest: null,
    };
  }
  return { ...base, inputs: validateInputs(inputs) };
}
