/**
 * A loaded project: one or more model revisions (the last is the current model), one or more calc
 * PDFs mapped onto the current model by the engine, and the review decisions applied. Everything is
 * computed in-process through ./engine.ts, with the calls the app makes (src/engine/projectService.ts,
 * src/engine/ops.ts):
 *
 *   graph = the model's element graph as calc-mapper reads it (ElementGraph.serialize + parseGraph;
 *           from a project file: the revision's stored graph)
 *   pkg   = per PDF: extractPdf + segmentCalcs (from a project file: the stored extraction when
 *           storedExtractionFor accepts it, else re-extracted from the PDF in the file)
 *   set   = buildCalcSet(every PDF as a document)     - the calc SET, as the app maps it
 *   run   = mapCalcs(graph, set)
 *   state = buildState(graph, set, run, decisions)    - links with decisions applied, element status,
 *                                                        calc edges from the effective links, findings
 *
 * Calc sets (calc-mapper calcset.ts): every PDF is a document with a doc id ("d1", "d2", ... in
 * --calcs order; from a project file, its documents and their head revisions, withdrawn documents
 * left out). Calc keys are calc refs "<doc_id>#<key>", the keys the app and the project file's
 * decision log use, so a decision made here means the same calc in the app. The engine numbers pages
 * across the set (document page + page_offset); this module turns every page number in the engine's
 * records back into the page of the record's own PDF, so a page number in any tool result is a page of
 * the PDF the result names (and get_page_image takes it as is).
 *
 * Decisions: the decisions file (calc-mapper's decision log, written by the server) and, with a
 * project file, the file's own log (read-only here) before it. Calc edges, statuses and findings are
 * recomputed from the effective links whenever the log changes. Decision ids are per origin (see
 * `DecisionRef`): the engine is handed one log with the decisions file's ids shifted past the project
 * file's, but no tool ever shows a shifted id.
 */
import { readFile } from "node:fs/promises";
import { basename } from "node:path";
import { userInfo } from "node:os";
import {
  CALC_REF_SEP,
  LEGACY_DOC_ID,
  ENGINE_VERSION,
  buildCalcSet,
  buildState,
  calcDocIdOf,
  calcDocumentHeads,
  effectiveDecisions,
  isProjectFile,
  legacyCalcRef,
  loadModel,
  mapCalcs,
  modelFromRevision,
  parseProjectFile,
  projectFileDecisions,
  readCalcPackage,
  revisionBytes,
  storedCalcPackage,
  type Calc,
  type CalcEdge,
  type CalcPackage,
  type CalcPage,
  type CalcSet,
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

/** One calc PDF: a document of the calc set. */
export interface PdfDoc {
  /** Position in the set (0 = first). */
  index: number;
  /** The calc-set document id ("d1", ...); calc refs are "<docId>#<key>". */
  docId: string;
  /** Document name (project file: the document's name; else the file name). */
  docName: string;
  path: string | null;
  /** File name of the PDF. */
  name: string;
  sha256: string;
  /** "<docId>#": every calc key of this PDF starts with it. */
  prefix: string;
  bytes: Uint8Array;
  title: string;
  /** The PDF's own calc package (bare keys, its own page numbers). */
  pkg: CalcPackage;
  /** Its pages (its own page numbers). */
  pages: CalcPage[];
  /** Its calcs, keyed by calc ref, with its own page numbers. */
  calcs: Calc[];
  /** Pages with no text layer (pages of the calcs the engine marked `scanned`). */
  noTextPages: number[];
  /** The engine's set page of this PDF's page n is n + offset. */
  offset: number;
  /** How the package was obtained: extracted from the PDF, or a project file's stored extraction. */
  extraction: ExtractionSource;
  extractionNote: string | null;
  /** Project file: the calc revision's id and label. */
  revision: { id: number; label: string } | null;
  readMs: number;
}

export interface CalcEdgeView extends CalcEdge {
  /** The two calcs are in different PDFs. */
  cross_pdf: boolean;
}

/**
 * Where a decision is recorded, and its id THERE: "decisions_file" = the --decisions file (its own
 * ids, the ids record_decision returns), "project_file" = the project file's decision log (numbered
 * 1..n in file order). Every tool and the decisions resource name decisions this way.
 */
export type DecisionOrigin = "decisions_file" | "project_file";
export interface DecisionRef {
  origin: DecisionOrigin;
  id: number;
}

/** The largest of `xs` (and `init`), without spreading them into Math.max's arguments (a RangeError past ~100k). */
export function maxOf(xs: Iterable<number>, init = -Infinity): number {
  let m = init;
  for (const x of xs) if (x > m) m = x;
  return m;
}
/** The smallest of `xs` (and `init`), without spreading. */
export function minOf(xs: Iterable<number>, init = Infinity): number {
  let m = init;
  for (const x of xs) if (x < m) m = x;
  return m;
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
  /** The calc set the engine maps (set page numbers). */
  readonly set: CalcSet;
  /** mapCalcs(graph, set): the engine's run (set page numbers). */
  readonly run: MappingRun;
  readonly calcs: Calc[];
  readonly calcByKey: Map<string, Calc>;
  readonly pdfOfCalc: Map<string, PdfDoc>;
  readonly calcKeys: Set<string>;
  /** The engine's automatic links (status "auto"), pages per PDF. */
  readonly rawLinks: Link[];
  /** Typical groups (the engine's, from the element rows). */
  readonly groups: TypicalGroup[];
  readonly projectFile: ProjectFileInfo | null;
  /** The project file's decision log (read-only here), oldest first. */
  readonly baseLog: DecisionFields[];
  readonly decisions: DecisionsFile | null;
  readonly warnings: string[];
  readonly timings: Record<string, number>;

  // derived from the decisions (recompute)
  /** buildState(graph, set, run, log), as the engine returns it (set page numbers). */
  state!: ProjectState;
  links: Link[] = [];
  linksByElement = new Map<string, Link[]>();
  linksByCalc = new Map<string, Link[]>();
  status = new Map<string, ElementStatus>();
  counts: Record<ElementStatus, number> = { confirmed: 0, review: 0, unmapped: 0 };
  calcEdges: CalcEdgeView[] = [];
  findings: Finding[] = [];
  groupLinks: GroupLink[] = [];
  effective = new Map<string, DecisionFields>();
  /**
   * The log the engine applies: the project file's decisions (ids 1..n), then the decisions file's,
   * ids shifted past them.
   */
  log: DecisionFields[] = [];
  /** Each entry of `log` -> its origin and its id there. */
  private refs = new Map<DecisionFields, DecisionRef>();
  /** Decisions-file entries written with a bare calc key (resolved to d1), so a warning can say so only for those. */
  private readonly bareKeyed = new WeakSet<DecisionFields>();
  /** Decisions whose element or calc is not in this project (carried, but not applied). */
  unappliedDecisions = 0;
  /** Warnings about the decision logs as they stand (recomputed with them). */
  decisionWarnings: string[] = [];
  /**
   * The decisions file log the derived state was computed from (identity: DecisionsFile keeps the same
   * array while the file is unchanged), to tell when it is stale.
   */
  computedLog: readonly DecisionFields[] | null = null;

  constructor(init: {
    inputs: ProjectInputs;
    models: ModelRev[];
    pdfs: PdfDoc[];
    set: CalcSet;
    run: MappingRun;
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
    this.set = init.set;
    this.run = init.run;
    this.calcs = init.pdfs.flatMap((p) => p.calcs);
    this.calcByKey = new Map(this.calcs.map((c) => [c.key, c]));
    this.pdfOfCalc = new Map(init.pdfs.flatMap((p) => p.calcs.map((c) => [c.key, p] as const)));
    this.calcKeys = new Set(this.calcByKey.keys());
    this.rawLinks = init.run.links.map((l) => this.linkPages(l));
    this.groups = init.run.groups;
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

  /** A decision of `log` (or of `effective`) as its origin and its id there. */
  decisionRef(d: DecisionFields): DecisionRef {
    const r = this.refs.get(d);
    if (!r) throw new ProjectError(`internal: decision ${d.id} is not in the applied log`);
    return r;
  }

  /** Every warning as things stand: the load-time ones, then the decision logs' (they change when the files do). */
  get allWarnings(): string[] {
    return [...this.warnings, ...this.decisionWarnings, ...(this.decisions?.problem ? [`decisions: ${this.decisions.problem}`] : [])];
  }

  /**
   * Build the log the engine applies: the project file's decisions (ids 1..n), then the decisions
   * file's, ids shifted past them so they come later (an id only orders decisions; the latest per
   * pair wins). A bare calc key (no "<docId>#") names a calc of the first document, as in the app.
   * The shifted ids live only here: `decisionRef` maps every entry back.
   */
  private combinedLog(fileLog: readonly DecisionFields[], ref?: (e: DecisionFields, r: DecisionRef) => void): DecisionFields[] {
    const n = this.baseLog.length;
    const log: DecisionFields[] = [];
    for (const d of this.baseLog) {
      log.push(d);
      ref?.(d, { origin: "project_file", id: d.id });
    }
    for (const d of fileLog) {
      const calc_key = legacyCalcRef(d.calc_key);
      const e = n || calc_key !== d.calc_key ? { ...d, id: d.id + n, calc_key } : d;
      if (calc_key !== d.calc_key) this.bareKeyed.add(e); // written as a bare key, read as a calc of d1
      log.push(e);
      ref?.(e, { origin: "decisions_file", id: d.id });
    }
    return log;
  }

  private buildLog(fileLog: readonly DecisionFields[]): void {
    this.refs = new Map();
    this.log = this.combinedLog(fileLog, (e, r) => this.refs.set(e, r));
  }

  /**
   * The effective decision per (global_id, calc_key) over the project file's log + `fileLog`, without
   * applying anything (no buildState): cheap enough to run under the decisions file's lock.
   */
  effectiveOver(fileLog: readonly DecisionFields[]): Map<string, DecisionFields> {
    return effectiveDecisions(this.combinedLog(fileLog));
  }

  /** A set page of a calc's record -> the page of that calc's own PDF. */
  private docPage(calcKey: string, page: number): number {
    const pdf = this.pdfOfCalc.get(calcKey);
    return pdf ? page - pdf.offset : page;
  }

  private linkPages<T extends Link | GroupLink>(l: T): T {
    const pg = (n: number | null) => (n === null ? null : this.docPage(l.calc_key, n));
    return { ...l, page: pg(l.page), evidence: l.evidence.map((e) => ({ ...e, page: pg(e.page) })) };
  }

  /**
   * Apply the decision log: one buildState on the set, then page numbers per PDF. `fileLog` is the
   * decisions file's log to apply (default: as last read).
   */
  recompute(fileLog: readonly DecisionFields[] = this.fileLog): void {
    this.computedLog = fileLog;
    this.buildLog(fileLog);
    const log = this.log;
    this.state = buildState(this.graph.graph, this.set, this.run, log);
    this.links = this.state.links.map((l) => this.linkPages(l));
    this.linksByElement = new Map();
    this.linksByCalc = new Map();
    for (const l of this.links) {
      push(this.linksByElement, l.global_id, l);
      push(this.linksByCalc, l.calc_key, l);
    }
    this.status = new Map(this.state.elements.map((e) => [e.global_id, e.status]));
    this.counts = { ...this.state.counts };
    this.findings = this.state.findings.map((f) => ({ ...f, page: this.docPage(f.calc_key, f.page) }));
    this.groupLinks = this.state.group_links.map((g) => this.linkPages(g));
    this.effective = effectiveDecisions(log);
    this.unappliedDecisions = log.filter((d) => !this.gids.has(d.global_id) || !this.calcKeys.has(d.calc_key)).length;
    this.decisionWarnings = this.checkDecisionKeys();
    this.calcEdges = this.state.calc_edges.map((e) => ({
      ...e,
      evidence: e.evidence.map((ev) => ({ ...ev, page: this.docPage(ev.calc, ev.page) })),
      cross_pdf: this.pdfOfCalc.get(e.src) !== this.pdfOfCalc.get(e.dst),
    }));
  }

  /**
   * Decisions that name a calc or element this project does not have: kept, not applied, and said
   * loudly with the likely cause (a calc ref names a document of the calc set: d1, d2, ... in --calcs
   * order, or the project file's documents).
   */
  private checkDecisionKeys(): string[] {
    const out: string[] = [];
    const missing = new Map<string, number>();
    const bare = new Set<string>(); // refs that some entry wrote as a bare key
    for (const d of this.log) {
      if (this.calcKeys.has(d.calc_key)) continue;
      missing.set(d.calc_key, (missing.get(d.calc_key) ?? 0) + 1);
      if (this.bareKeyed.has(d)) bare.add(d.calc_key);
    }
    const order = this.projectFile ? "the project file's documents" : "the --calcs order";
    if (missing.size) {
      const docs = this.pdfs.map((p) => `${p.docId} = ${p.name}`).join(", ");
      const lines = [...missing].sort((a, b) => (a[0] < b[0] ? -1 : 1)).slice(0, 20).map(([ref, n]) => {
        const sep = ref.indexOf(CALC_REF_SEP);
        const docId = sep >= 0 ? ref.slice(0, sep) : "";
        const key = sep >= 0 ? ref.slice(sep + 1) : ref;
        const pdf = this.pdfs.find((p) => p.docId === docId);
        const elsewhere = this.pdfs.filter((p) => p !== pdf && this.calcKeys.has(`${p.prefix}${key}`)).map((p) => `${p.prefix}${key}`);
        let why: string;
        if (!pdf) {
          why = `no loaded calc document is "${docId}" (documents: ${docs}): was a PDF dropped, or did ${order} change?`;
        } else {
          why = `${pdf.name} (${pdf.docId}) has no calc "${key}": did that PDF change (calcs renamed, split or reordered), or ${order}?`;
        }
        if (elsewhere.length) {
          why += ` A calc with this key is in ${elsewhere.join(", ")}` + (bare.has(ref) ? ` (the decision names a bare key, which is read as a calc of ${LEGACY_DOC_ID}).` : ".");
        }
        return `"${ref}" (${n} decision${n === 1 ? "" : "s"}): ${why}`;
      });
      out.push(
        `decisions: ${[...missing.values()].reduce((a, b) => a + b, 0)} decision(s) name ${missing.size} calc ref(s) that are not in this project; they are kept but NOT applied. ` +
          lines.join("; ") + (missing.size > 20 ? `; and ${missing.size - 20} more` : ""),
      );
    }
    const noEl = this.log.filter((d) => this.calcKeys.has(d.calc_key) && !this.gids.has(d.global_id)).length;
    if (noEl) out.push(`decisions: ${noEl} decision(s) name an element that is not in the current model; they are kept but not applied`);
    return out;
  }

  /** Pick up decisions written by someone else since the last read. */
  async refresh(): Promise<boolean> {
    // also when the file turned malformed (the warnings change), and whenever the log is not the one
    // last applied (e.g. an append re-read the file but then wrote nothing)
    if (this.decisions && ((await this.decisions.refresh()) || this.computedLog !== this.fileLog)) {
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

  /** A calc PDF by file name, document name, doc id ("d2" or "d2#") or sha256; the first PDF when none is named. */
  pdfByName(name: string | undefined | null): PdfDoc {
    if (name === undefined || name === null || name === "") return this.pdfs[0]!;
    const n = name.endsWith(CALC_REF_SEP) ? name.slice(0, -1) : name;
    const hit =
      this.pdfs.find((p) => p.name === name) ??
      this.pdfs.find((p) => p.name.toLowerCase() === name.toLowerCase()) ??
      this.pdfs.find((p) => p.docId === n) ??
      this.pdfs.find((p) => p.docName.toLowerCase() === name.toLowerCase()) ??
      this.pdfs.find((p) => p.sha256 === name);
    if (!hit) {
      throw new ProjectError(`no calc PDF "${name}" in this project (PDFs: ${this.pdfs.map((p) => `${p.docId} = ${p.name}`).join(", ")})`);
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

  /**
   * The decisions context of a calc: the revisions and documents a decision is recorded against. As
   * in the app, the calc revision is the head revision of the calc's own document.
   */
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
      calc_pdfs: pdfs.map((p) => ({ file: p.name, sha256: p.sha256, doc_id: p.docId, key_prefix: p.prefix })),
      ...(this.decisions?.problem ? { decisions_warning: this.decisions.problem } : {}),
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

interface PdfSource {
  docId: string;
  docName: string;
  name: string;
  path: string | null;
  bytes: Uint8Array;
  /** A project file's stored extraction (checked with storedExtractionFor). */
  stored?: { extraction: unknown; revision: { id: number; label: string } };
}

/** Read every PDF into a calc package, then combine them into the calc set and map it once. */
async function loadPdfs(
  sources: PdfSource[], model: Model, warnings: string[], timings: Record<string, number>,
): Promise<{ pdfs: PdfDoc[]; set: CalcSet; run: MappingRun }> {
  const read: Omit<PdfDoc, "index" | "offset">[] = [];
  for (const [i, src] of sources.entries()) {
    const hash = sha256(src.bytes);
    const twin = read.find((p) => p.sha256 === hash);
    if (twin) {
      // a calc set holds a PDF once (buildCalcSet refuses the same PDF twice; the app does not add it again)
      warnings.push(`calcs: ${src.name} has the same content as ${twin.name} (sha256 ${hash.slice(0, 12)}); it is left out`);
      continue;
    }
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
    const prefix = `${src.docId}${CALC_REF_SEP}`;
    // the engine's own scanned rule (segment): pages of calcs it flagged as having no text layer
    const noTextPages = [...new Set(pkg.calcs.filter((c) => c.scanned).flatMap((c) => c.pages))].sort((a, b) => a - b);
    if (noTextPages.length === pkg.pages.length) {
      warnings.push(`calcs: ${src.name} has NO text layer on any of its ${pkg.pages.length} page(s) (scanned?). Nothing in it can be mapped: OCR it first.`);
    } else if (noTextPages.length) {
      warnings.push(`calcs: ${src.name} page(s) ${compactRanges(noTextPages)} have no text layer (scanned / handwritten); calcs on them are never mapped`);
    }
    read.push({
      docId: src.docId, docName: src.docName, path: src.path, name: src.name, sha256: hash, prefix, bytes: src.bytes, title, pkg,
      pages: pkg.pages, calcs: pkg.calcs.map((c) => ({ ...c, key: `${prefix}${c.key}` })), noTextPages, extraction, extractionNote,
      revision: src.stored?.revision ?? null, readMs,
    });
    timings[`pdf_${i}_read_ms`] = readMs;
  }
  const set = buildCalcSet(read.map((d) => ({ doc_id: d.docId, name: d.docName, revision: d.revision?.id ?? null, package: d.pkg })));
  const pdfs: PdfDoc[] = read.map((d, i) => ({ ...d, index: i, offset: set.docs[i]!.page_offset }));
  const t2 = performance.now();
  const run = await mapCalcs(model.graph, set);
  timings.map_ms = Math.round(performance.now() - t2);
  return { pdfs, set, run };
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
    // the calc set the app maps: each live document's head revision, in document order
    const heads = calcDocumentHeads(file);
    if (!heads.length) throw new ProjectError(`${name} has no calc package yet (add a calc PDF in the app, then save the project again)`);
    const headIds = new Set(heads.map((h) => h.rev.id));
    const older = revs.filter((r) => r.kind === "calcs" && !headIds.has(r.id));
    if (older.length) {
      warnings.push(`project file: serving the head revision of each calc document (${heads.map((h) => `${h.doc.docId}: revision ${h.rev.id}, ${h.rev.sourceName}`).join("; ")}); ${older.length} older or withdrawn calc revision(s) are not mapped`);
    }
    sources = heads.map(({ doc, rev }) => ({
      docId: calcDocIdOf(rev), docName: doc.name, name: rev.sourceName, path: null, bytes: revisionBytes(rev),
      stored: { extraction: rev.extraction, revision: { id: rev.id, label: rev.label } },
    }));
    baseLog = projectFileDecisions(file);
  } else {
    for (const [i, path] of inputs.models.entries()) {
      const t = performance.now();
      const bytes = new Uint8Array(await readFile(path));
      const name = basename(path);
      const model = await loadModel(bytes, name);
      models.push({ index: i, revision: i + 1, label: name, name, path, sha256: sha256(bytes), model, readMs: Math.round(performance.now() - t) });
    }
    // documents d1, d2, ... in --calcs order (the ids the app gives documents as they are added)
    sources = [];
    for (const [i, path] of inputs.calcs.entries()) {
      const name = basename(path);
      sources.push({ docId: `d${i + 1}`, docName: name.replace(/\.[A-Za-z0-9]{2,4}$/, "") || name, name, path, bytes: new Uint8Array(await readFile(path)) });
    }
  }
  const current = models.at(-1)!;
  for (const m of models) modelWarnings(m, warnings, m === current);
  timings.model_ms = models.reduce((s, m) => s + m.readMs, 0);

  const { pdfs, set, run } = await loadPdfs(sources, current.model, warnings, timings);
  for (const p of pdfs) {
    if (p.extraction === "re-extracted") warnings.push(`project file: ${p.name}: the stored extraction was not used (${p.extractionNote}); re-read from the PDF in the file`);
  }

  let decisions: DecisionsFile | null = null;
  if (inputs.decisions) {
    decisions = new DecisionsFile(inputs.decisions);
    await decisions.load();
  }
  const t3 = performance.now();
  const project = new Project({ inputs, models, pdfs, set, run, projectFile, baseLog, decisions, warnings, timings });
  timings.review_ms = Math.round(performance.now() - t3);
  timings.total_ms = Math.round(performance.now() - t0);
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
