/**
 * A loaded project: the model's element graph and one or more calc PDFs, mapped by the engine,
 * with the review decisions applied. Everything is computed in-process through ./engine.ts.
 *
 * Multiple PDFs: `mapCalcs` runs PER PDF, so page numbers always stay within their own PDF. The first
 * PDF (the main package) keeps the engine's plain calc keys, so a single-PDF decisions file is
 * exactly calc-parser's format; every further PDF's keys are prefixed "<file-stem>/". Calc edges:
 *   - within one PDF: `calcDependencies` (inferCalcDeps) on that PDF's calcs, pages and effective links,
 *     exactly what the engine computes for that PDF alone;
 *   - across PDFs: `crossReferenceDeps` on a combined view (all calcs, all pages with page numbers
 *     offset so they are unique, all effective links), keeping only edges whose two calcs are in
 *     different PDFs, with evidence page numbers mapped back to their own PDF. Only the engine's
 *     cross-reference rule can produce them ("page 7" is never resolved across files).
 * Like the Python reference (pipeline.state), calc edges are computed from the EFFECTIVE links,
 * so a rejected cross-reference stops feeding an edge and a manual link counts as a designer.
 */
import { readFile } from "node:fs/promises";
import { basename } from "node:path";
import { userInfo } from "node:os";
import {
  ENGINE_VERSION,
  calcDependencies,
  crossReferenceDeps,
  effectiveDecisions,
  effectiveLinks,
  loadModel,
  mapCalcs,
  mappingStatuses,
  readPdf,
  type Calc,
  type CalcEdge,
  type CalcLink,
  type CalcPage,
  type Decision,
  type EngineElement,
  type MappingStatus,
  type Model,
  type ModelNode,
} from "./engine.ts";
import { DecisionsFile, sha256 } from "./decisions.ts";
import type { ProjectInputs } from "./inputs.ts";

export interface PdfDoc {
  /** 0 = main package. */
  index: number;
  path: string;
  name: string;
  sha256: string;
  /** "" for the main PDF, "<stem>/" for the others. */
  prefix: string;
  bytes: Uint8Array;
  pages: CalcPage[];
  title: string;
  /** Calcs with prefixed keys; `pages` are page numbers within this PDF. */
  calcs: Calc[];
  /** Raw (automatic) links with prefixed calc keys; `page` is within this PDF. */
  links: CalcLink[];
  /** Pages with no text layer (pages of the calcs the engine marked `scanned`). */
  noTextPages: number[];
  /** page number -> calc key (prefixed). */
  pageOwner: Map<number, string>;
  /** Offset of this PDF's pages in the combined view used for cross-PDF edges. */
  offset: number;
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

export class Project {
  readonly inputs: ProjectInputs;
  readonly actor: string;
  readonly model: { path: string; name: string; sha256: string; format: string; project: string | null; schema: string | null };
  readonly graph: Model;
  readonly elements: EngineElement[];
  readonly elementById: Map<string, EngineElement>;
  readonly gids: Set<string>;
  readonly pdfs: PdfDoc[];
  readonly calcs: Calc[];
  readonly calcByKey: Map<string, Calc>;
  readonly pdfOfCalc: Map<string, PdfDoc>;
  readonly calcKeys: Set<string>;
  readonly rawLinks: CalcLink[];
  readonly decisions: DecisionsFile | null;
  readonly warnings: string[];
  readonly timings: Record<string, number>;

  // derived from the decisions (recompute)
  links: CalcLink[] = [];
  linksByElement = new Map<string, CalcLink[]>();
  linksByCalc = new Map<string, CalcLink[]>();
  status = new Map<string, MappingStatus>();
  counts: Record<MappingStatus, number> = { confirmed: 0, review: 0, unmapped: 0 };
  calcEdges: CalcEdgeView[] = [];
  effective = new Map<string, Decision>();
  /** Decisions whose element or calc is not in this project (carried, but not applied). */
  unappliedDecisions = 0;
  /** The log the derived state was computed from (identity), to tell when it is stale. */
  computedLog: readonly Decision[] | null = null;

  constructor(init: {
    inputs: ProjectInputs;
    model: Project["model"];
    graph: Model;
    pdfs: PdfDoc[];
    decisions: DecisionsFile | null;
    warnings: string[];
    timings: Record<string, number>;
  }) {
    this.inputs = init.inputs;
    this.actor = init.inputs.actor ?? safeUser();
    this.model = init.model;
    this.graph = init.graph;
    this.elements = init.graph.elements();
    this.elementById = new Map(this.elements.map((e) => [e.global_id, e]));
    this.gids = new Set(this.elementById.keys());
    this.pdfs = init.pdfs;
    this.calcs = init.pdfs.flatMap((p) => p.calcs);
    this.calcByKey = new Map(this.calcs.map((c) => [c.key, c]));
    this.pdfOfCalc = new Map(init.pdfs.flatMap((p) => p.calcs.map((c) => [c.key, p] as const)));
    this.calcKeys = new Set(this.calcByKey.keys());
    this.rawLinks = init.pdfs.flatMap((p) => p.links);
    this.decisions = init.decisions;
    this.warnings = init.warnings;
    this.timings = init.timings;
    this.recompute();
  }

  get log(): readonly Decision[] {
    return this.decisions?.log ?? [];
  }

  /** Apply the decision log: effective links, statuses, calc edges. */
  recompute(): void {
    const log = this.log;
    this.computedLog = log;
    this.links = effectiveLinks(this.rawLinks, log, this.gids, this.calcKeys);
    this.linksByElement = new Map();
    this.linksByCalc = new Map();
    for (const l of this.links) {
      push(this.linksByElement, l.global_id, l);
      push(this.linksByCalc, l.calc_key, l);
    }
    const st = mappingStatuses(this.elements, this.links);
    this.status = st.byElement;
    this.counts = st.counts;
    this.effective = effectiveDecisions(log);
    this.unappliedDecisions = log.filter((d) => !this.gids.has(d.global_id) || !this.calcKeys.has(d.calc_key)).length;

    const edges: CalcEdgeView[] = [];
    for (const pdf of this.pdfs) {
      const own = new Set(pdf.calcs.map((c) => c.key));
      const links = this.links.filter((l) => own.has(l.calc_key));
      for (const e of calcDependencies(pdf.calcs, pdf.pages, links)) edges.push({ ...e, cross_pdf: false });
    }
    if (this.pdfs.length > 1) {
      // combined view: page numbers offset per PDF so they are unique; links' pages offset to match
      const pages = this.pdfs.flatMap((p) => p.pages.map((pg) => ({ n: pg.n + p.offset, text: pg.text, words: pg.words })));
      const links = this.links.map((l) => {
        const p = this.pdfOfCalc.get(l.calc_key)!;
        return l.page === null ? l : { ...l, page: l.page + p.offset };
      });
      for (const e of crossReferenceDeps(this.calcs, pages, links)) {
        const a = this.pdfOfCalc.get(e.src);
        const b = this.pdfOfCalc.get(e.dst);
        if (!a || !b || a === b) continue;
        edges.push({
          ...e,
          evidence: e.evidence.map((ev) => {
            const p = this.pdfOfCalc.get(ev.calc);
            return { ...ev, page: ev.page === null || !p ? ev.page : ev.page - p.offset };
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

  decisionFor(gid: string, key: string): Decision | undefined {
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

  /** The `source` block every result carries. */
  source(opts: { pdfs?: Iterable<PdfDoc> | "all"; decisions?: boolean } = {}): Record<string, unknown> {
    const pdfs = opts.pdfs === "all" || opts.pdfs === undefined ? this.pdfs : [...new Set(opts.pdfs)].sort((a, b) => a.index - b.index);
    return {
      model: { file: this.model.name, sha256: this.model.sha256 },
      calc_pdfs: pdfs.map((p) => ({ file: p.name, sha256: p.sha256, key_prefix: p.prefix })),
      ...(opts.decisions
        ? {
            decisions: this.decisions
              ? { file: this.decisions.name, sha256: this.decisions.sha256, entries: this.decisions.log.length, exists: this.decisions.exists }
              : null,
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

const prefixed = (prefix: string, key: string) => (prefix ? `${prefix}${key}` : key);

/** Read, validate and map everything. Throws with a user-facing message on bad input. */
export async function loadProject(inputs: ProjectInputs): Promise<Project> {
  const timings: Record<string, number> = {};
  const warnings: string[] = [];
  const t0 = performance.now();

  const modelBytes = new Uint8Array(await readFile(inputs.model));
  const modelName = basename(inputs.model);
  const graph = await loadModel(modelBytes, modelName);
  timings.model_ms = Math.round(performance.now() - t0);
  warnings.push(...graph.warnings.map((w) => `model: ${w}`));
  const elements = graph.elements();
  if (!elements.length) warnings.push(`model: ${modelName} has no structural elements; nothing can be mapped`);
  else if (!elements.some((e) => e.mark)) warnings.push(`model: no element in ${modelName} has a mark, so only size / type tiers can link calcs`);

  // prefixes: main = "", others = "<stem>/" (must be unique)
  const prefixes = inputs.calcs.map((p, i) => (i === 0 ? "" : `${stemSlug(p)}/`));
  const dup = prefixes.find((p, i) => p && prefixes.indexOf(p) !== i);
  if (dup) {
    const who = inputs.calcs.filter((_, i) => prefixes[i] === dup).map((p) => basename(p));
    throw new ProjectError(`calc PDFs ${who.join(" and ")} give the same calc-key prefix "${dup}". Rename one of them (the prefix is the file stem).`);
  }

  const pdfs: PdfDoc[] = [];
  let offset = 0;
  for (const [i, path] of inputs.calcs.entries()) {
    const name = basename(path);
    const bytes = new Uint8Array(await readFile(path));
    const hash = sha256(bytes);
    const twin = pdfs.find((p) => p.sha256 === hash);
    if (twin) warnings.push(`calcs: ${name} has the same content as ${twin.name} (sha256 ${hash.slice(0, 12)})`);
    const t1 = performance.now();
    let text: Awaited<ReturnType<typeof readPdf>>;
    try {
      text = await readPdf(bytes);
    } catch (e) {
      throw new ProjectError(`calc PDF ${name} could not be read: ${(e as Error).message}`);
    }
    const readMs = Math.round(performance.now() - t1);
    const t2 = performance.now();
    const m = mapCalcs(elements, text.pages);
    const mapMs = Math.round(performance.now() - t2);
    const prefix = prefixes[i]!;
    const calcs = m.calcs.map((c) => ({ ...c, key: prefixed(prefix, c.key) }));
    const links = m.links.map((l) => ({ ...l, calc_key: prefixed(prefix, l.calc_key) }));
    // the engine's own scanned rule (segment): pages of calcs it flagged as having no text layer
    const noTextPages = calcs.filter((c) => c.scanned).flatMap((c) => c.pages);
    if (noTextPages.length === text.pages.length) {
      warnings.push(`calcs: ${name} has NO text layer on any of its ${text.pages.length} page(s) (scanned?). Nothing in it can be mapped: OCR it first.`);
    } else if (noTextPages.length) {
      warnings.push(`calcs: ${name} page(s) ${compactRanges(noTextPages)} have no text layer (scanned / handwritten); calcs on them are never mapped`);
    }
    const pageOwner = new Map<number, string>();
    for (const c of calcs) for (const n of c.pages) pageOwner.set(n, c.key);
    pdfs.push({
      index: i, path, name, sha256: hash, prefix, bytes, pages: text.pages, title: text.meta.title,
      calcs, links, noTextPages, pageOwner, offset, readMs, mapMs,
    });
    offset += Math.max(text.pages.length, ...text.pages.map((p) => p.n), 0);
    timings[`pdf_${i}_read_ms`] = readMs;
    timings[`pdf_${i}_map_ms`] = mapMs;
  }

  let decisions: DecisionsFile | null = null;
  if (inputs.decisions) {
    decisions = new DecisionsFile(inputs.decisions);
    await decisions.load();
  }
  const t3 = performance.now();
  const project = new Project({
    inputs,
    model: { path: inputs.model, name: modelName, sha256: sha256(modelBytes), format: graph.format, project: graph.project, schema: graph.schema },
    graph,
    pdfs,
    decisions,
    warnings,
    timings,
  });
  timings.review_ms = Math.round(performance.now() - t3);
  timings.total_ms = Math.round(performance.now() - t0);
  if (project.unappliedDecisions) {
    warnings.push(
      `decisions: ${project.unappliedDecisions} decision(s) name an element or calc that is not in this project; they are kept in the file but not applied`,
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
