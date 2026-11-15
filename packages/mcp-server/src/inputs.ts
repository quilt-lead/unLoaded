/**
 * Command-line and project-manifest inputs, validated up front with actionable messages.
 *
 *   unloaded-mcp-server --model model.ifc [--model newer.ifc ...] --calcs main.pdf [--calcs more.pdf ...]
 *                       [--decisions decisions.json] [--actor "name"] [--check] [--verbose]
 *   unloaded-mcp-server --project project.json|project.calcgraph.json [--decisions ...] [--actor ...] [--check]
 *
 * project.json (a manifest): {"model": "..." | ["older", "current"], "calcs": ["main.pdf", ...],
 * "decisions": "...", "actor": "..."}, paths relative to the manifest's directory.
 * project.calcgraph.json: the app's saved project file (format "unloaded.calc-graph-project").
 */
import { closeSync, existsSync, openSync, readFileSync, readSync, statSync } from "node:fs";
import { dirname, extname, resolve } from "node:path";
import { parseArgs } from "node:util";
import { isProjectFile } from "./engine.ts";

export class InputError extends Error {
  override name = "InputError";
}

export interface ProjectInputs {
  /**
   * Model revisions, absolute paths, oldest first. The LAST is the current model: the one the calcs
   * are mapped onto. Earlier ones are older revisions for compare_revisions (as in a project file,
   * where the head is the highest revision id). Empty with a project file.
   */
  models: string[];
  /** Calc PDFs, absolute paths; the first is the main package. Empty with a project file. */
  calcs: string[];
  /** A *.calcgraph.json project file (the app's Save project), instead of models + calcs. */
  projectFile: string | null;
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
  unloaded-mcp-server --model <model.ifc|graph.json> [--model <newer revision> ...]
                      --calcs <main.pdf> [--calcs <more.pdf> ...]
                      [--decisions <decisions.json>] [--actor "<name>"] [--check] [--verbose]
  unloaded-mcp-server --project <project.json | project.calcgraph.json>
                      [--decisions <file>] [--actor "<name>"] [--check] [--verbose]

Serves one structural project (an IFC model mapped to its calc-package PDFs) to your AI client over
MCP stdio. Local only: no port is opened and nothing is sent anywhere.

  --model       the model: .ifc, a serialized element graph .json, or a ModelInput .json. Repeat it to
                give older revisions too, oldest first: the LAST --model is the current model (the calcs
                are mapped onto it); compare_revisions diffs any two of them.
  --calcs       a calc-package PDF; repeat for several. All of them are mapped as ONE calc set; calcs are
                named by calc ref "<doc>#<key>", the doc being d1, d2, ... in --calcs order (keep the
                order stable: decisions name calcs by these refs).
  --decisions   review decisions file (calc-mapper decision log, JSON array, append-only). Created on the
                first recorded decision. Without it the server is read-only and record_decision explains
                how to enable it.
  --actor       name recorded on decisions you make through your AI (default: your OS user name)
  --project     the app's saved project file (*.calcgraph.json: every model revision, the head calc
                package, the decision log), or a JSON manifest {"model", "calcs": [...], "decisions",
                "actor"} with paths relative to it
  --check       load everything, print a summary to stderr, and exit (0 = ok)
  --verbose     also print web-ifc's parser messages and pdf.js warnings (counted and hidden by default)`;

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

/** A Git LFS pointer file (the repo keeps PDFs in LFS): the PDF itself was never downloaded. */
export function isLfsPointer(h: Uint8Array): boolean {
  return Buffer.from(h).toString("latin1").startsWith("version https://git-lfs.github.com/spec/");
}

function validatePdf(path: string): void {
  requireFile(path, "calc PDF");
  const h = head(path);
  if (isLfsPointer(h)) throw new InputError(`--calcs ${path} is a Git LFS pointer, not the PDF: run \`git lfs install && git lfs pull\` in the repo first`);
  if (!looksLikePdf(h)) throw new InputError(`--calcs ${path} is not a PDF (no "%PDF-" header)`);
}

function validateDecisionsPath(path: string): void {
  if (existsSync(path)) {
    if (!statSync(path).isFile()) throw new InputError(`--decisions ${path} is not a file`);
  } else if (!existsSync(dirname(path))) {
    throw new InputError(`--decisions ${path}: directory ${dirname(path)} does not exist (the file itself is created on the first decision)`);
  }
}

function readProjectArg(path: string): { projectFile: string } | { models: string[]; calcs: string[]; decisions: string | null; actor: string | null } {
  requireFile(path, "--project file");
  let data: unknown;
  try {
    data = JSON.parse(readFileSync(path, "utf8").replace(/^\uFEFF/, ""));
  } catch (e) {
    throw new InputError(`--project ${path} is not valid JSON: ${(e as Error).message} (pass a *.calcgraph.json project file or a JSON manifest)`);
  }
  if (isProjectFile(data)) return { projectFile: path };
  if (typeof data !== "object" || data === null || Array.isArray(data)) {
    throw new InputError(`project manifest ${path} must be an object {"model", "calcs": [...], "decisions"?, "actor"?}, or a *.calcgraph.json project file`);
  }
  const o = data as Record<string, unknown>;
  const known = new Set(["model", "calcs", "decisions", "actor"]);
  const unknown = Object.keys(o).filter((k) => !known.has(k));
  if (unknown.length) throw new InputError(`project manifest ${path}: unknown key(s) ${unknown.join(", ")} (allowed: model, calcs, decisions, actor)`);
  const models = typeof o.model === "string" ? [o.model] : o.model;
  if (!Array.isArray(models) || !models.length || models.some((m) => typeof m !== "string" || !m)) {
    throw new InputError(`project manifest ${path}: "model" must be a path, or an array of paths oldest first (the last is the current model)`);
  }
  const calcs = typeof o.calcs === "string" ? [o.calcs] : o.calcs;
  if (!Array.isArray(calcs) || !calcs.length || calcs.some((c) => typeof c !== "string" || !c)) {
    throw new InputError(`project manifest ${path}: "calcs" must be a non-empty array of PDF paths (the first is the main package)`);
  }
  for (const k of ["decisions", "actor"] as const) {
    if (o[k] !== undefined && o[k] !== null && typeof o[k] !== "string") throw new InputError(`project manifest ${path}: "${k}" must be a string`);
  }
  const base = dirname(path);
  return {
    models: (models as string[]).map((m) => resolve(base, m)),
    calcs: (calcs as string[]).map((c) => resolve(base, c)),
    decisions: typeof o.decisions === "string" && o.decisions ? resolve(base, o.decisions) : null,
    actor: typeof o.actor === "string" && o.actor ? o.actor : null,
  };
}

/** Validate a set of inputs (files exist and look like what they claim to be). */
export function validateInputs(inp: ProjectInputs): ProjectInputs {
  if (inp.projectFile) {
    requireFile(inp.projectFile, "project file");
    if (inp.decisions) validateDecisionsPath(inp.decisions);
    return inp;
  }
  if (!inp.models.length) throw new InputError("--model is required (or --project)");
  const seenModels = new Map<string, number>();
  inp.models.forEach((m, i) => {
    validateModel(m);
    const prev = seenModels.get(m);
    if (prev !== undefined) throw new InputError(`--model ${m} is given twice (positions ${prev + 1} and ${i + 1})`);
    seenModels.set(m, i);
  });
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
        model: { type: "string", multiple: true },
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
    const path = resolve(cwd, values.project as string);
    const m = readProjectArg(path);
    inputs = "projectFile" in m
      ? {
          models: [],
          calcs: [],
          projectFile: m.projectFile,
          decisions: str("decisions"),
          actor: (values.actor as string | undefined) || null,
          manifest: null,
        }
      : {
          models: m.models,
          calcs: m.calcs,
          projectFile: null,
          decisions: str("decisions") ?? m.decisions,
          actor: (values.actor as string | undefined) || m.actor,
          manifest: path,
        };
  } else {
    const models = (values.model as string[] | undefined) ?? [];
    if (!models.length) throw new InputError(`--model is required (or --project)\n\n${USAGE}`);
    const calcs = (values.calcs as string[] | undefined) ?? [];
    if (!calcs.length) throw new InputError(`at least one --calcs PDF is required\n\n${USAGE}`);
    inputs = {
      models: models.map((m) => resolve(cwd, m)),
      calcs: calcs.map((c) => resolve(cwd, c)),
      projectFile: null,
      decisions: str("decisions"),
      actor: (values.actor as string | undefined) || null,
      manifest: null,
    };
  }
  return { ...base, inputs: validateInputs(inputs) };
}
