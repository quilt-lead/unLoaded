/**
 * A loaded project: one or more model revisions (the last is the current model), one or more calc
 * PDFs mapped onto the current model by the engine, and the review decisions applied. Everything is
 * computed in-process through ./engine.ts, with the calls the app makes:
 *
 *   graph = the model's element graph as calc-mapper reads it (ElementGraph.serialize + parseGraph;
 *           from a project file: the revision's stored graph)
 *   pkg   = extractPdf + segmentCalcs (from a project file: the stored extraction when
 *           storedExtractionFor accepts it, else re-extracted from the PDF in the file)
 *   run   = mapCalcs(graph, pkg)
 *   state = buildState(graph, pkg, run, decisions)    - links with decisions applied, calc edges from
 *                                                        the effective links, findings
 *
 * Several calc PDFs: calc-mapper maps ONE calc package (one PDF) per run - `packageSha256` refuses
 * pages from two documents - so the server runs it PER PDF, and page numbers always stay within their
 * own PDF. The first PDF (the main package) keeps the engine's plain calc keys, so a single-PDF
 * project is exactly the engine's output; every further PDF's keys are prefixed "<file-stem>/" (the
 * prefix is put on the package's calc keys before mapCalcs, so every record the engine makes carries
 * it). Across PDFs:
 *   - element status: the engine's `statusOf` over the element's links from every PDF;
 *   - calc edges within one PDF: that PDF's `buildState` (inferCalcEdges on its effective links);
 *   - calc edges across PDFs: `crossReferenceEdges` (inferCalcEdges with the page-reference rule
 *     switched off) on a combined view - every calc, every page with its page number offset so numbers
 *     are unique, every effective link - keeping only edges whose two calcs are in different PDFs,
 *     with evidence page numbers mapped back to their own PDF;
 *   - impact: the engine's `propagate` over the load path, every effective link and every calc edge.
 *
 * Decisions: the decisions file (calc-mapper's decision log, written by the server) and, with a
 * project file, the file's own log (read-only here) before it. Calc edges, statuses and findings are
 * recomputed from the effective links whenever the log changes.
 */
import { readFile } from "node:fs/promises";
import { basename } from "node:path";
import { userInfo } from "node:os";
import {
  ENGINE_VERSION,
  buildState,
  crossReferenceEdges,
  effectiveDecisions,
  headRevision,
  isProjectFile,
  loadModel,
  mapCalcs,
  modelFromRevision,
  parseProjectFile,
  projectFileDecisions,
  readCalcPackage,
  revisionBytes,
  statusOf,
  storedCalcPackage,
  type Calc,
  type CalcEdge,
  type CalcPackage,
  type CalcPage,
  type DecisionFields,
  type ElementRow,
  type ElementStatus,
  type Finding,
  type GroupLink,
  type Link,
  type MappingRun,
  type Model,
  type ModelNode,
  type ProjectFile,
  type ProjectState,
  type TypicalGroup,
} from "./engine.ts";
import { DecisionsFile, sha256 } from "./decisions.ts";
import type { ProjectInputs } from "./inputs.ts";

export interface ModelRev {
  /** 0-based, oldest first; the last is the current model. */
  index: number;
  /** The revision number tools take: the project file's revision id, else the --model position (1-based). */
  revision: number;
  label: string;
  /** File name (project file: the revision's source name). */
  name: string;
  path: string | null;
  /** sha256 of the model file's bytes. */
  sha256: string;
  model: Model;
  readMs: number;
}

export type ExtractionSource = "extracted" | "stored" | "re-extracted";

export interface PdfDoc {
  /** 0 = main package. */
  index: number;
  path: string | null;
  name: string;
  sha256: string;
  /** "" for the main PDF, "<stem>/" for the others. */
  prefix: string;
  bytes: Uint8Array;
  title: string;
  /** The calc package, calc keys prefixed. */
  pkg: CalcPackage;
  /** mapCalcs on the current model (keys prefixed). */
  run: MappingRun;
  pages: CalcPage[];
  calcs: Calc[];
  /** Pages with no text layer (pages of the calcs the engine marked `scanned`). */
  noTextPages: number[];
  /** Offset of this PDF's pages in the combined view used for cross-PDF edges. */
  offset: number;
  /** How the package was obtained: extracted from the PDF, or a project file's stored extraction. */
  extraction: ExtractionSource;
  extractionNote: string | null;
  /** Project file: the calc revision's id and label. */
  revision: { id: number; label: string } | null;
  readMs: number;
  mapMs: number;
}

export interface CalcEdgeView extends CalcEdge {
  cross_pdf: boolean;
}

/** Deterministic file-stem slug used as the calc-key prefix of a non-main PDF. */
export function stemSlug(fileName: string): string {
  const stem = basename(fileName).replace(/\.[^.]+$/, "");
  const s = stem.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
  return s || "pdf";
}

const pairKey = (gid: string, key: string) => `${gid}\u0000${key}`;

export class ProjectError extends Error {
  override name = "ProjectError";
}

export interface ProjectFileInfo {
  path: string;
  name: string;
  sha256: string;
  project: string;
  exportedAt: string;
  file: ProjectFile;
}

export class Project {
  readonly inputs: ProjectInputs;
  readonly actor: string;
  /** Every model revision, oldest first. */
  readonly models: ModelRev[];
  /** The current model revision (the last). */
  readonly current: ModelRev;
  readonly graph: Model;
  readonly elements: ElementRow[];
  readonly elementById: Map<string, ElementRow>;
  readonly gids: Set<string>;
  readonly pdfs: PdfDoc[];
  readonly calcs: Calc[];
  readonly calcByKey: Map<string, Calc>;
  readonly pdfOfCalc: Map<string, PdfDoc>;
  readonly calcKeys: Set<string>;
  /** The engine's automatic links of every PDF (status "auto"). */
  readonly rawLinks: Link[];
  /** Typical groups (the engine's, from the element rows: the same in every run). */
  readonly groups: TypicalGroup[];
  readonly projectFile: ProjectFileInfo | null;
  /** The project file's decision log (read-only here), oldest first. */
  readonly baseLog: DecisionFields[];
  readonly decisions: DecisionsFile | null;
  readonly warnings: string[];
  readonly timings: Record<string, number>;

  // derived from the decisions (recompute)
  states: ProjectState[] = [];
  links: Link[] = [];
  linksByElement = new Map<string, Link[]>();
  linksByCalc = new Map<string, Link[]>();
  status = new Map<string, ElementStatus>();
  counts: Record<ElementStatus, number> = { confirmed: 0, review: 0, unmapped: 0 };
  calcEdges: CalcEdgeView[] = [];
  findings: Finding[] = [];
  groupLinks: GroupLink[] = [];
  effective = new Map<string, DecisionFields>();
  /** Decisions whose element or calc is not in this project (carried, but not applied). */
  unappliedDecisions = 0;
  /** The decisions file log the derived state was computed from (identity), to tell when it is stale. */
  computedLog: readonly DecisionFields[] | null = null;

  constructor(init: {
    inputs: ProjectInputs;
    models: ModelRev[];
    pdfs: PdfDoc[];
    projectFile: ProjectFileInfo | null;
    baseLog: DecisionFields[];
    decisions: DecisionsFile | null;
    warnings: string[];
    timings: Record<string, number>;
  }) {
    this.inputs = init.inputs;
    this.actor = init.inputs.actor ?? safeUser();
    this.models = init.models;
    this.current = init.models.at(-1)!;
    this.graph = this.current.model;
    this.elements = this.graph.elements();
    this.elementById = new Map(this.elements.map((e) => [e.global_id, e]));
    this.gids = new Set(this.elementById.keys());
    this.pdfs = init.pdfs;
    this.calcs = init.pdfs.flatMap((p) => p.calcs);
    this.calcByKey = new Map(this.calcs.map((c) => [c.key, c]));
    this.pdfOfCalc = new Map(init.pdfs.flatMap((p) => p.calcs.map((c) => [c.key, p] as const)));
    this.calcKeys = new Set(this.calcByKey.keys());
    this.rawLinks = init.pdfs.flatMap((p) => p.run.links);
    const groups = new Map<string, TypicalGroup>();
    for (const p of init.pdfs) for (const g of p.run.groups) if (!groups.has(g.id)) groups.set(g.id, g);
    this.groups = [...groups.values()];
    this.projectFile = init.projectFile;
    this.baseLog = init.baseLog;
    this.decisions = init.decisions;
    this.warnings = init.warnings;
    this.timings = init.timings;
    this.recompute();
  }

  /** The decisions file's entries, as stored. */
  get fileLog(): readonly DecisionFields[] {
    return this.decisions?.log ?? [];
  }

  /**
   * The log the engine applies: the project file's decisions (ids 1..n), then the decisions file's,
   * ids shifted past them so they come later (an id only orders decisions; the latest per pair wins).
   */
  get log(): DecisionFields[] {
    const n = this.baseLog.length;
    if (!n) return [...this.fileLog];
    return [...this.baseLog, ...this.fileLog.map((d) => ({ ...d, id: d.id + n }))];
  }

  /** Apply the decision log: per-PDF state, statuses, calc edges, findings. */
  recompute(): void {
    this.computedLog = this.fileLog;
    const log = this.log;
    this.states = this.pdfs.map((pdf) => buildState(this.graph.graph, pdf.pkg, pdf.run, log));
    this.links = this.states.flatMap((s) => s.links);
    this.linksByElement = new Map();
    this.linksByCalc = new Map();
    for (const l of this.links) {
      push(this.linksByElement, l.global_id, l);
      push(this.linksByCalc, l.calc_key, l);
    }
    this.status = new Map();
    this.counts = { confirmed: 0, review: 0, unmapped: 0 };
    for (const e of this.elements) {
      const s = statusOf(this.linksByElement.get(e.global_id) ?? []);
      this.status.set(e.global_id, s);
      this.counts[s] += 1;
    }
    this.findings = this.states.flatMap((s) => s.findings);
    this.groupLinks = this.states.flatMap((s) => s.group_links);
    this.effective = effectiveDecisions(log);
    this.unappliedDecisions = log.filter((d) => !this.gids.has(d.global_id) || !this.calcKeys.has(d.calc_key)).length;

    const edges: CalcEdgeView[] = this.states.flatMap((s) => s.calc_edges.map((e) => ({ ...e, cross_pdf: false })));
    if (this.pdfs.length > 1) {
      // combined view: page numbers offset per PDF so they are unique; links' pages offset to match
      const pages = this.pdfs.flatMap((p) => p.pages.map((pg) => ({ ...pg, n: pg.n + p.offset })));
      const links = this.links.map((l) => {
        const p = this.pdfOfCalc.get(l.calc_key)!;
        return l.page === null ? l : { ...l, page: l.page + p.offset };
      });
      for (const e of crossReferenceEdges(this.calcs, pages, links)) {
        const a = this.pdfOfCalc.get(e.src);
        const b = this.pdfOfCalc.get(e.dst);
        if (!a || !b || a === b) continue;
        edges.push({
          ...e,
          evidence: e.evidence.map((ev) => {
            const p = this.pdfOfCalc.get(ev.calc);
            return { ...ev, page: p ? ev.page - p.offset : ev.page };
          }),
          cross_pdf: true,
        });
      }
    }
    this.calcEdges = edges;
  }

  /** Pick up decisions written by someone else since the last read. */
  async refresh(): Promise<boolean> {
    if (this.decisions && (await this.decisions.refresh())) {
      this.recompute();
      return true;
    }
    return false;
  }

  node(gid: string): ModelNode | undefined {
    return this.graph.node(gid);
  }

  decisionFor(gid: string, key: string): DecisionFields | undefined {
    return this.effective.get(pairKey(gid, key));
  }

  pdfByName(name: string | undefined | null): PdfDoc {
    if (name === undefined || name === null || name === "") return this.pdfs[0]!;
    const n = name.replace(/\/$/, "");
    const hit =
      this.pdfs.find((p) => p.name === name) ??
      this.pdfs.find((p) => p.name.toLowerCase() === name.toLowerCase()) ??
      this.pdfs.find((p) => p.prefix && p.prefix.slice(0, -1) === n) ??
      this.pdfs.find((p) => p.sha256 === name);
    if (!hit) {
      throw new ProjectError(`no calc PDF "${name}" in this project (PDFs: ${this.pdfs.map((p) => p.name).join(", ")})`);
    }
    return hit;
  }

  /** A model revision by its revision number (project_summary.model_revisions) or file name. */
  modelRevision(ref: string | number): ModelRev {
    const s = String(ref).trim();
    const hit =
      this.models.find((m) => String(m.revision) === s) ??
      this.models.find((m) => m.name === s) ??
      this.models.find((m) => m.name.toLowerCase() === s.toLowerCase() || m.label.toLowerCase() === s.toLowerCase());
    if (!hit) {
      throw new ProjectError(
        `no model revision "${s}" (revisions: ${this.models.map((m) => `${m.revision} = ${m.name}`).join(", ")})`,
      );
    }
    return hit;
  }

  /** The decisions context of a calc: the revision labels and documents a decision is recorded against. */
  decisionContext(calcKey: string): { model_rev: string | number; calc_rev: string | number | null; inputs: string[] } {
    const pdf = this.pdfOfCalc.get(calcKey);
    return {
      model_rev: this.projectFile ? this.current.revision : this.current.name,
      calc_rev: pdf ? (pdf.revision?.id ?? pdf.name) : null,
      inputs: [this.graph.graphSha256, ...(pdf ? [pdf.sha256] : [])],
    };
  }

  /** The `source` block every result carries. */
  source(opts: { pdfs?: Iterable<PdfDoc> | "all"; decisions?: boolean } = {}): Record<string, unknown> {
    const pdfs = opts.pdfs === "all" || opts.pdfs === undefined ? this.pdfs : [...new Set(opts.pdfs)].sort((a, b) => a.index - b.index);
    return {
      ...(this.projectFile ? { project_file: { file: this.projectFile.name, sha256: this.projectFile.sha256 } } : {}),
      model: {
        file: this.current.name,
        sha256: this.current.sha256,
        graph_sha256: this.graph.graphSha256,
        revision: this.current.revision,
      },
      calc_pdfs: pdfs.map((p) => ({ file: p.name, sha256: p.sha256, key_prefix: p.prefix })),
      ...(opts.decisions
        ? {
            decisions: this.decisions
              ? { file: this.decisions.name, sha256: this.decisions.sha256, entries: this.decisions.log.length, exists: this.decisions.exists }
              : null,
            ...(this.projectFile ? { project_file_decisions: this.baseLog.length } : {}),
          }
        : {}),
      engine: ENGINE_VERSION,
    };
  }
}

function push<K, V>(m: Map<K, V[]>, k: K, v: V): void {
  const a = m.get(k);
  if (a) a.push(v);
  else m.set(k, [v]);
}

function safeUser(): string {
  try {
    return userInfo().username;
  } catch {
    return "unknown";
  }
}

/** Put a prefix on every calc key of a package (before mapping, so every record the engine makes carries it). */
function prefixPackage(pkg: CalcPackage, prefix: string): CalcPackage {
  return prefix ? { ...pkg, calcs: pkg.calcs.map((c) => ({ ...c, key: `${prefix}${c.key}` })) } : pkg;
}

interface PdfSource {
  name: string;
  path: string | null;
  bytes: Uint8Array;
  /** A project file's stored extraction (checked with storedExtractionFor). */
  stored?: { extraction: unknown; revision: { id: number; label: string } };
}

async function loadPdfs(sources: PdfSource[], model: Model, warnings: string[], timings: Record<string, number>): Promise<PdfDoc[]> {
  // prefixes: main = "", others = "<stem>/" (must be unique)
  const prefixes = sources.map((s, i) => (i === 0 ? "" : `${stemSlug(s.name)}/`));
  const dup = prefixes.find((p, i) => p && prefixes.indexOf(p) !== i);
  if (dup) {
    const who = sources.filter((_, i) => prefixes[i] === dup).map((s) => s.name);
    throw new ProjectError(`calc PDFs ${who.join(" and ")} give the same calc-key prefix "${dup}". Rename one of them (the prefix is the file stem).`);
  }
  const pdfs: PdfDoc[] = [];
  let offset = 0;
  for (const [i, src] of sources.entries()) {
    const hash = sha256(src.bytes);
    const twin = pdfs.find((p) => p.sha256 === hash);
    if (twin) warnings.push(`calcs: ${src.name} has the same content as ${twin.name} (sha256 ${hash.slice(0, 12)})`);
    const t1 = performance.now();
    let pkg: CalcPackage;
    let title = "";
    let extraction: ExtractionSource = "extracted";
    let extractionNote: string | null = null;
    const stored = src.stored ? storedCalcPackage(src.stored.extraction, hash) : null;
    if (stored?.pkg) {
      pkg = stored.pkg;
      extraction = "stored";
    } else {
      try {
        ({ pkg, title } = await readCalcPackage(src.bytes, src.name));
      } catch (e) {
        throw new ProjectError(`calc PDF ${src.name} could not be read: ${(e as Error).message}`);
      }
      if (stored) {
        extraction = "re-extracted";
        extractionNote = stored.reason;
      }
    }
    const readMs = Math.round(performance.now() - t1);
    const prefix = prefixes[i]!;
    pkg = prefixPackage(pkg, prefix);
    const t2 = performance.now();
    const run = await mapCalcs(model.graph, pkg);
    const mapMs = Math.round(performance.now() - t2);
    // the engine's own scanned rule (segment): pages of calcs it flagged as having no text layer
    const noTextPages = [...new Set(pkg.calcs.filter((c) => c.scanned).flatMap((c) => c.pages))].sort((a, b) => a - b);
    if (noTextPages.length === pkg.pages.length) {
      warnings.push(`calcs: ${src.name} has NO text layer on any of its ${pkg.pages.length} page(s) (scanned?). Nothing in it can be mapped: OCR it first.`);
    } else if (noTextPages.length) {
      warnings.push(`calcs: ${src.name} page(s) ${compactRanges(noTextPages)} have no text layer (scanned / handwritten); calcs on them are never mapped`);
    }
    pdfs.push({
      index: i, path: src.path, name: src.name, sha256: hash, prefix, bytes: src.bytes, title, pkg, run,
      pages: pkg.pages, calcs: pkg.calcs, noTextPages, offset, extraction, extractionNote,
      revision: src.stored?.revision ?? null, readMs, mapMs,
    });
    offset += Math.max(pkg.pages.length, ...pkg.pages.map((p) => p.n), 0);
    timings[`pdf_${i}_read_ms`] = readMs;
    timings[`pdf_${i}_map_ms`] = mapMs;
  }
  return pdfs;
}

function modelWarnings(m: ModelRev, warnings: string[], current: boolean): void {
  const tag = current ? "model" : `model revision ${m.revision}`;
  warnings.push(...m.model.warnings.map((w) => `${tag}: ${w}`));
  if (!current) return;
  const elements = m.model.elements();
  if (!elements.length) warnings.push(`model: ${m.name} has no structural elements; nothing can be mapped`);
  else if (!elements.some((e) => e.mark)) warnings.push(`model: no element in ${m.name} has a mark, so only size / type tiers can link calcs`);
}

/** Read, validate and map everything. Throws with a user-facing message on bad input. */
export async function loadProject(inputs: ProjectInputs): Promise<Project> {
  const timings: Record<string, number> = {};
  const warnings: string[] = [];
  const t0 = performance.now();
  const models: ModelRev[] = [];
  let sources: PdfSource[];
  let projectFile: ProjectFileInfo | null = null;
  let baseLog: DecisionFields[] = [];

  if (inputs.projectFile) {
    const raw = new Uint8Array(await readFile(inputs.projectFile));
    const name = basename(inputs.projectFile);
    let data: unknown;
    try {
      data = JSON.parse(new TextDecoder().decode(raw));
    } catch (e) {
      throw new ProjectError(`${name} is not valid JSON: ${(e as Error).message}`);
    }
    if (!isProjectFile(data)) throw new ProjectError(`${name} is not a calc-graph project file (format "unloaded.calc-graph-project")`);
    const file = parseProjectFile(data);
    projectFile = { path: inputs.projectFile, name, sha256: sha256(raw), project: file.project.name, exportedAt: file.exportedAt, file };
    const revs = [...file.revisions].sort((a, b) => a.id - b.id);
    for (const rev of revs.filter((r) => r.kind === "model")) {
      const t = performance.now();
      const bytes = revisionBytes(rev);
      const model = await modelFromRevision(rev, name);
      models.push({ index: models.length, revision: rev.id, label: rev.label, name: rev.sourceName, path: null, sha256: sha256(bytes), model, readMs: Math.round(performance.now() - t) });
    }
    if (!models.length) throw new ProjectError(`${name} has no model revision yet (add an IFC in the app, then save the project again)`);
    const head = headRevision(file, "calcs");
    if (!head) throw new ProjectError(`${name} has no calc package yet (add a calc PDF in the app, then save the project again)`);
    const older = revs.filter((r) => r.kind === "calcs" && r.id !== head.id);
    if (older.length) {
      warnings.push(`project file: serving the head calc package (revision ${head.id}, ${head.sourceName}); ${older.length} older calc revision(s) are not mapped`);
    }
    sources = [{ name: head.sourceName, path: null, bytes: revisionBytes(head), stored: { extraction: head.extraction, revision: { id: head.id, label: head.label } } }];
    baseLog = projectFileDecisions(file);
  } else {
    for (const [i, path] of inputs.models.entries()) {
      const t = performance.now();
      const bytes = new Uint8Array(await readFile(path));
      const name = basename(path);
      const model = await loadModel(bytes, name);
      models.push({ index: i, revision: i + 1, label: name, name, path, sha256: sha256(bytes), model, readMs: Math.round(performance.now() - t) });
    }
    sources = [];
    for (const path of inputs.calcs) sources.push({ name: basename(path), path, bytes: new Uint8Array(await readFile(path)) });
  }
  const current = models.at(-1)!;
  for (const m of models) modelWarnings(m, warnings, m === current);
  timings.model_ms = models.reduce((s, m) => s + m.readMs, 0);

  const pdfs = await loadPdfs(sources, current.model, warnings, timings);
  for (const p of pdfs) {
    if (p.extraction === "re-extracted") warnings.push(`project file: ${p.name}: the stored extraction was not used (${p.extractionNote}); re-read from the PDF in the file`);
  }

  let decisions: DecisionsFile | null = null;
  if (inputs.decisions) {
    decisions = new DecisionsFile(inputs.decisions);
    await decisions.load();
  }
  const t3 = performance.now();
  const project = new Project({ inputs, models, pdfs, projectFile, baseLog, decisions, warnings, timings });
  timings.review_ms = Math.round(performance.now() - t3);
  timings.total_ms = Math.round(performance.now() - t0);
  if (project.unappliedDecisions) {
    warnings.push(
      `decisions: ${project.unappliedDecisions} decision(s) name an element or calc that is not in this project; they are kept but not applied`,
    );
  }
  return project;
}

export function compactRanges(ns: number[]): string {
  const out: string[] = [];
  const s = [...ns].sort((a, b) => a - b);
  for (let i = 0; i < s.length; ) {
    let j = i;
    while (j + 1 < s.length && s[j + 1] === s[j]! + 1) j++;
    out.push(i === j ? `${s[i]}` : `${s[i]}-${s[j]}`);
    i = j + 1;
  }
  return out.join(", ");
}
