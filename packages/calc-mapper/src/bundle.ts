/**
 * The model bundle: ONE JSON file with an element graph and its calculation graph side by side.
 *
 *   {
 *     format: "unloaded.model-bundle", version: 1,
 *     meta: { project?, label?, demo?, createdAt? },
 *     elementGraph: <ElementGraph.serialize(), unchanged>,
 *     calcGraph: null | {
 *       source: { kind: "demo" } | { kind: "pdf", documents: [{ doc_id, name, revision, sha256, pages, page_offset }] },
 *       calcs:  [{ key, title, cat, software?, pages?, scanned?, front_matter?, title_box?, spans?, code?, rev?, date?, summary? }],
 *       edges:  [{ src, dst, rules?, evidence?, provenance? }],                  calc src feeds calc dst
 *       links:  [{ element, calc, role, review, conf?, tier?, rule?, page?, rects?, snippet?, matched_text?,
 *                  caveats?, note?, decided_by?, decided_at?, provenance? }]       element -> calc
 *     }
 *   }
 *
 * The element graph is the existing serialized format, embedded as is. Calc records use the field
 * names of the engine's export (snake_case), so an export converts to a bundle and back without
 * renaming. A demo calc graph (source.kind "demo") has no PDF behind it: its calcs carry no pages or
 * regions, and every record it yields says so in its provenance (method "estimate", rule "bundle.demo").
 * A PDF calc graph names each PDF by sha256 but does not carry the bytes.
 *
 * Two adapters join a bundle to the rest of the engine:
 *   bundleExport(graph, calcGraph, decisions)  -> Export   (what the view reads; the decision log applied)
 *   exportToCalcGraph(exp)                     -> calcGraph (save a mapped project as a bundle)
 * A link's review state is carried as a decision: a bundle link "confirmed" / "manual" becomes a decision
 * older than any in the project's log, so a reviewer's later decision on the same pair wins.
 */
import { applyDecisions } from "./decisions.ts";
import { connectivity, graphElements, loadPath, parseGraph, GraphFormatError } from "./elements.ts";
import { sha256Json, SHA256_HEX } from "./hash.ts";
import { bandOf } from "./matcher.ts";
import { statusOf } from "./project.ts";
import { inputList, producerOf, RULES, type Provenance } from "./provenance.ts";
import {
  ENGINE_VERSION, type CalcCategory, type CalcEdge, type CalcEdgeEvidence, type CalcSetDocRecord, type CalcSpan, type DecisionFields, type ElementCategory,
  type Export, type ExportInfo, type Link, type LinkEvidence, type LinkRole, type Rect, type SerializedElementGraph, type Snippet, type Tier,
  type TitleBox,
} from "./types.ts";

export const BUNDLE_FORMAT = "unloaded.model-bundle";
export const BUNDLE_VERSION = 1;

/** One PDF a calc graph rests on (the bytes are not in the bundle). Pages are numbered across the set: document page + page_offset. */
export interface BundleDocument {
  /** The calc document's id in its project; null for a one-PDF calc package. */
  doc_id: string | null;
  name: string | null;
  revision: string | number | null;
  sha256: string;
  pages: number;
  page_offset: number;
}

export type BundleCalcSource = { kind: "demo" } | { kind: "pdf"; documents: BundleDocument[] };

export interface BundleCalc {
  key: string;
  title: string;
  /** The element type the calc designs, or "Loading" ("" when it is not tied to one). */
  cat: CalcCategory | "";
  software?: string;
  /** Pages of the calc (set pages); absent for a demo calc. */
  pages?: number[];
  scanned?: boolean;
  front_matter?: boolean;
  title_box?: TitleBox | null;
  spans?: CalcSpan[];
  /** Document metadata a demo calc states (a real calc's are in its PDF). */
  code?: string;
  rev?: string;
  date?: string;
  summary?: string;
  provenance?: Provenance;
}

export interface BundleCalcEdge {
  src: string;
  dst: string;
  rules?: string[];
  evidence?: CalcEdgeEvidence[];
  provenance?: Provenance;
}

/** A link a bundle states. Rejected links are not written; "manual" is a link a person made. */
export type BundleReview = "auto" | "confirmed" | "manual";

export interface BundleLink {
  /** Element graph node id (GlobalId). */
  element: string;
  /** Calc key. */
  calc: string;
  role: LinkRole;
  review: BundleReview;
  /** 0..1; default 1. */
  conf?: number;
  tier?: Tier;
  rule?: string;
  page?: number | null;
  rects?: Rect[];
  snippet?: Snippet | null;
  matched_text?: string;
  caveats?: string[];
  /** Free text shown with the link (a demo link's description). */
  note?: string;
  decided_by?: string | null;
  decided_at?: string;
  provenance?: Provenance;
}

export interface BundleCalcGraph {
  source: BundleCalcSource;
  calcs: BundleCalc[];
  edges: BundleCalcEdge[];
  links: BundleLink[];
}

export interface BundleMeta {
  project?: string;
  /** The revision this model is, e.g. "Rev 1 base". */
  label?: string;
  /** Invented data for demos: shown labelled as demo data. */
  demo?: boolean;
  createdAt?: string;
}

export interface ModelBundle {
  format: typeof BUNDLE_FORMAT;
  version: typeof BUNDLE_VERSION;
  meta: BundleMeta;
  elementGraph: SerializedElementGraph;
  calcGraph: BundleCalcGraph | null;
}

export class BundleFormatError extends Error {
  name = "BundleFormatError";
}

const CATS: readonly (CalcCategory | "")[] = ["Beam", "Column", "Slab", "Wall", "Footing", "Pile", "Brace", "Connection", "Other", "Loading", ""];
const ROLES: readonly LinkRole[] = ["design", "loads"];
const REVIEWS: readonly BundleReview[] = ["auto", "confirmed", "manual"];
const TIERS: readonly Tier[] = ["exact", "range", "loose", "family", "size", "partial", "xref", "type", "manual", "stated"];

const isObj = (v: unknown): v is Record<string, unknown> => !!v && typeof v === "object" && !Array.isArray(v);
const absent = (v: unknown): boolean => v === undefined || v === null;
const isNum = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);
const optStr = (v: unknown): boolean => v === undefined || typeof v === "string";

/** Does this JSON say it is a bundle? (`parseBundle` then validates it in full.) */
export function isBundle(d: unknown): boolean {
  return isObj(d) && d.format === BUNDLE_FORMAT;
}

function fail(msg: string): never {
  throw new BundleFormatError(msg);
}

function checkSource(s: unknown): void {
  if (!isObj(s)) fail("calcGraph.source must be an object");
  if (s.kind === "demo") return;
  if (s.kind !== "pdf") fail(`calcGraph.source.kind must be "demo" or "pdf" (got ${JSON.stringify(s.kind ?? null)})`);
  if (!Array.isArray(s.documents) || !s.documents.length) fail("calcGraph.source.documents must be a non-empty list for a pdf source");
  s.documents.forEach((d, i) => {
    const at = `calcGraph.source.documents[${i}]`;
    if (!isObj(d)) fail(`${at} must be an object`);
    if (typeof d.sha256 !== "string" || !SHA256_HEX.test(d.sha256)) fail(`${at}.sha256 must be a lowercase hex sha256`);
    if (!isNum(d.pages) || d.pages < 0) fail(`${at}.pages must be a number`);
    if (!isNum(d.page_offset)) fail(`${at}.page_offset must be a number`);
    if (!absent(d.doc_id) && typeof d.doc_id !== "string") fail(`${at}.doc_id must be a string or null`);
    if (!absent(d.name) && typeof d.name !== "string") fail(`${at}.name must be a string or null`);
  });
}

function checkCalcGraph(cg: unknown, nodeIds: Set<string>): void {
  if (!isObj(cg)) fail("calcGraph must be an object or null");
  checkSource(cg.source);
  for (const k of ["calcs", "edges", "links"]) if (!Array.isArray(cg[k])) fail(`calcGraph.${k} must be a list`);
  const keys = new Set<string>();
  (cg.calcs as unknown[]).forEach((c, i) => {
    const at = `calcGraph.calcs[${i}]`;
    if (!isObj(c) || typeof c.key !== "string" || !c.key) fail(`${at} needs a non-empty string key`);
    if (keys.has(c.key)) fail(`${at}: duplicate calc key ${JSON.stringify(c.key)}`);
    keys.add(c.key);
    if (typeof c.title !== "string") fail(`${at} (${JSON.stringify(c.key)}) needs a string title`);
    if (!CATS.includes(c.cat as CalcCategory)) fail(`${at}.cat must be one of ${CATS.map((x) => JSON.stringify(x)).join(", ")}`);
    if (!absent(c.pages) && (!Array.isArray(c.pages) || !c.pages.every(isNum))) fail(`${at}.pages must be a list of page numbers`);
    if (!absent(c.spans) && !Array.isArray(c.spans)) fail(`${at}.spans must be a list`);
    for (const f of ["software", "code", "rev", "date", "summary"]) if (!optStr(c[f])) fail(`${at}.${f} must be a string`);
  });
  (cg.edges as unknown[]).forEach((e, i) => {
    const at = `calcGraph.edges[${i}]`;
    if (!isObj(e) || !keys.has(e.src as string) || !keys.has(e.dst as string)) fail(`${at} must name two calcs of calcGraph.calcs (src, dst)`);
    if (!absent(e.rules) && (!Array.isArray(e.rules) || !e.rules.every((r) => typeof r === "string"))) fail(`${at}.rules must be a list of strings`);
  });
  const pairs = new Set<string>();
  (cg.links as unknown[]).forEach((l, i) => {
    const at = `calcGraph.links[${i}]`;
    if (!isObj(l)) fail(`${at} must be an object`);
    if (typeof l.element !== "string" || !nodeIds.has(l.element)) fail(`${at}.element ${JSON.stringify(l.element ?? null)} is not a node of elementGraph`);
    if (typeof l.calc !== "string" || !keys.has(l.calc)) fail(`${at}.calc ${JSON.stringify(l.calc ?? null)} is not a calc of calcGraph.calcs`);
    const pair = `${l.element}\u0000${l.calc}`;
    if (pairs.has(pair)) fail(`${at}: element ${JSON.stringify(l.element)} is linked to calc ${JSON.stringify(l.calc)} twice`);
    pairs.add(pair);
    if (!ROLES.includes(l.role as LinkRole)) fail(`${at}.role must be "design" or "loads"`);
    if (!REVIEWS.includes(l.review as BundleReview)) fail(`${at}.review must be "auto", "confirmed" or "manual"`);
    if (l.tier !== undefined && !TIERS.includes(l.tier as Tier)) fail(`${at}.tier must be one of ${TIERS.join(", ")}`);
    if (!absent(l.conf) && (!isNum(l.conf) || l.conf < 0 || l.conf > 1)) fail(`${at}.conf must be a number from 0 to 1`);
    if (!absent(l.page) && !isNum(l.page)) fail(`${at}.page must be a number or null`);
    if (!absent(l.rects) && !Array.isArray(l.rects)) fail(`${at}.rects must be a list`);
    for (const f of ["rule", "matched_text", "note", "decided_at"]) if (!optStr(l[f])) fail(`${at}.${f} must be a string`);
  });
}

/**
 * Validate (and parse, when given text) a model bundle. Throws BundleFormatError naming the field at
 * fault. The element graph is checked by `parseGraph` (the rules every graph reader relies on); the
 * calc graph by the rules its readers rely on: unique calc keys, edges and links that name a calc of
 * the bundle and a node of its graph, one link per (element, calc) pair, known roles and reviews.
 */
export function parseBundle(input: string | unknown): ModelBundle {
  let d: unknown = input;
  if (typeof input === "string") {
    try {
      d = JSON.parse(input);
    } catch (e) {
      fail(`bundle is not valid JSON: ${(e as Error).message}`);
    }
  }
  if (!isObj(d)) fail("bundle must be a JSON object");
  if (d.format !== BUNDLE_FORMAT) fail(`bundle format must be ${JSON.stringify(BUNDLE_FORMAT)} (got ${JSON.stringify(d.format ?? null)})`);
  if (d.version !== BUNDLE_VERSION) fail(`bundle version ${JSON.stringify(d.version ?? null)} is not supported (this engine reads version ${BUNDLE_VERSION})`);
  if (!absent(d.meta)) {
    if (!isObj(d.meta)) fail("bundle.meta must be an object");
    for (const f of ["project", "label", "createdAt"]) if (!optStr(d.meta[f])) fail(`bundle.meta.${f} must be a string`);
    if (d.meta.demo !== undefined && typeof d.meta.demo !== "boolean") fail("bundle.meta.demo must be true or false");
  }
  let graph: SerializedElementGraph;
  try {
    graph = parseGraph(d.elementGraph);
  } catch (e) {
    if (e instanceof GraphFormatError) fail(`elementGraph: ${e.message}`);
    throw e;
  }
  if (!absent(d.calcGraph)) checkCalcGraph(d.calcGraph, new Set(graph.nodes.map((n) => n.id)));
  return { ...(d as unknown as ModelBundle), meta: (d.meta ?? {}) as BundleMeta, calcGraph: (d.calcGraph ?? null) as BundleCalcGraph | null };
}

/** A bundle of a graph and (optionally) its calc graph. */
export function makeBundle(elementGraph: SerializedElementGraph, calcGraph: BundleCalcGraph | null, meta: BundleMeta = {}): ModelBundle {
  return { format: BUNDLE_FORMAT, version: BUNDLE_VERSION, meta, elementGraph, calcGraph };
}

// ---------------------------------------------------------------- bundle -> export

/** The caveat every demo link carries (not written back to a bundle: the source says it). */
export const DEMO_CAVEAT = "Demo data: invented calc, no PDF behind it";
/** Link evidence kind of a bundle link's `note`. */
const NOTE_EVIDENCE = "note";

const pdfShas = (s: BundleCalcSource): string[] => (s.kind === "pdf" ? s.documents.map((d) => d.sha256) : []);

/** Provenance of a record the bundle states (its own, when it carries one). */
function statedProvenance(source: BundleCalcSource, rule: string, inputs: string[], own: Provenance | undefined): Provenance {
  if (own) return own;
  return source.kind === "demo"
    ? { producer: producerOf("bundle"), rule: RULES.bundle.demo, method: "estimate", inputs }
    : { producer: producerOf("bundle"), rule, method: "rule", inputs };
}

/** The bundle's links as engine links (status "auto"; review state is carried by `bundleDecisions`). Manual links are decisions only. */
function bundleLinks(cg: BundleCalcGraph, inputs: string[]): Link[] {
  const demo = cg.source.kind === "demo";
  return cg.links
    .filter((l) => l.review !== "manual")
    .map((l): Link => {
      const conf = l.conf ?? 1;
      const page = l.page ?? null;
      const rects = l.rects ?? [];
      const rule = l.rule ?? (demo ? "Demo data: stated by the demo file" : "Stated by the bundle file");
      const evidence: LinkEvidence[] = [{ kind: "tier", weight: conf, note: rule, page, rects }];
      if (l.note) evidence.push({ kind: NOTE_EVIDENCE, weight: 0, note: l.note, page: null, rects: [] });
      return {
        global_id: l.element, calc_key: l.calc, conf, tier: l.tier ?? "stated", rule, page, token: l.matched_text ?? "", span: null,
        snippet: l.snippet ?? null, rects, status: "auto", role: l.role, band: bandOf(conf), evidence,
        caveats: [...(l.caveats ?? []).filter((c) => c !== DEMO_CAVEAT), ...(demo ? [DEMO_CAVEAT] : [])],
        provenance: statedProvenance(cg.source, RULES.bundle.link, inputs, l.provenance),
      };
    });
}

/**
 * The review state a bundle states, as decisions older than any project decision (ids below 0), so
 * the project's own log is applied after them and wins on the same pair.
 */
export function bundleDecisions(cg: BundleCalcGraph, at = "1970-01-01T00:00:00.000Z"): DecisionFields[] {
  const reviewed = cg.links.filter((l) => l.review !== "auto");
  return reviewed.map((l, i) => ({
    id: i - reviewed.length,
    global_id: l.element,
    calc_key: l.calc,
    action: l.review === "manual" ? "manual" : "confirm",
    actor: l.decided_by ?? null,
    note: l.note ?? null,
    at: l.decided_at ?? at,
  }));
}

/**
 * The export of a bundle's graph and calc graph (the shape `buildExport` writes for a mapped project),
 * with the bundle's review state and then `decisions` (the project's log) applied. Async: every record
 * names the element graph it rests on by sha256 (and, for a PDF calc graph, each PDF).
 */
export async function bundleExport(
  graph: SerializedElementGraph, cg: BundleCalcGraph, decisions: readonly DecisionFields[] = [], info: ExportInfo = {},
): Promise<Export & { calc_source: BundleCalcSource }> {
  const graphSha = await sha256Json(graph);
  const inputs = inputList([graphSha, ...pdfShas(cg.source)]);
  const rows = graphElements(graph);
  const keys = new Set(cg.calcs.map((c) => c.key));
  const links = applyDecisions(bundleLinks(cg, inputs), [...bundleDecisions(cg), ...decisions], new Set(rows.map((r) => r.global_id)), keys);
  const perEl = new Map<string, Link[]>();
  for (const l of links) (perEl.get(l.global_id) ?? perEl.set(l.global_id, []).get(l.global_id)!).push(l);
  const title = new Map(cg.calcs.map((c) => [c.key, c.title]));
  const docs = cg.source.kind === "pdf" ? cg.source.documents : [];
  const set = docs.filter((d): d is BundleDocument & { doc_id: string } => typeof d.doc_id === "string");
  return {
    model: info.model ?? graph.meta?.source?.file ?? null,
    model_revision: info.model_revision ?? null,
    calc_package: info.calc_package ?? (cg.source.kind === "demo" ? "Demo calcs (no PDF)" : docs.length === 1 ? docs[0]!.name : `${docs.length} calc documents`),
    calc_revision: info.calc_revision ?? null,
    engine: ENGINE_VERSION,
    producers: {
      model: { element_graph: { format: graph.format, version: graph.version, source: graph.meta?.source ?? null } },
      mapping: { "calc-mapper": ENGINE_VERSION },
      bundle: { format: BUNDLE_FORMAT, version: BUNDLE_VERSION, source: cg.source.kind },
      inputs,
    },
    calcs: cg.calcs.map((c) => {
      const meta = Object.fromEntries((["code", "rev", "date", "summary"] as const).filter((f) => c[f]).map((f) => [f, c[f]!]));
      return {
        key: c.key, title: c.title, software: c.software ?? "", element_type: c.cat, pages: c.pages ?? [], scanned: Boolean(c.scanned),
        front_matter: Boolean(c.front_matter), title_box: c.title_box ?? null, spans: c.spans ?? [],
        provenance: statedProvenance(cg.source, RULES.bundle.calc, inputs, c.provenance),
        ...(Object.keys(meta).length ? { meta } : {}),
      };
    }),
    calc_edges: cg.edges.map((e): CalcEdge => ({
      src: e.src, dst: e.dst, rules: e.rules ?? [], evidence: e.evidence ?? [],
      provenance: statedProvenance(cg.source, RULES.bundle.edge, inputs, e.provenance),
    })),
    load_path: loadPath(graph).map((e) => ({ src: e.src, dst: e.dst, rule: e.rule })),
    connectivity: connectivity(graph),
    elements: rows.map((e) => {
      const ls = perEl.get(e.global_id) ?? [];
      return {
        global_id: e.global_id, ifc_type: e.ifc_type, mark: e.mark, storey: e.storey, size: e.profile, status: statusOf(ls),
        calcs: [...ls].sort((p, q) => q.conf - p.conf).map((l) => ({
          calc: l.calc_key, title: title.get(l.calc_key) ?? l.calc_key, page: l.page, confidence: Math.round(l.conf * 100) / 100,
          tier: l.tier, rule: l.rule, matched_text: l.token, review: l.status,
          evidence: { page: l.page, span: l.span, rects: l.rects, snippet: l.snippet },
          role: l.role, band: l.band, reasons: l.evidence, caveats: l.caveats,
          provenance: l.provenance, ...(l.review_provenance ? { review_provenance: l.review_provenance } : {}),
        })),
      };
    }),
    groups: [], group_links: [], findings: [],
    ...(set.length === docs.length && set.length > 0
      ? { documents: set.map((d): CalcSetDocRecord => ({ doc_id: d.doc_id, name: d.name, revision: d.revision, sha256: d.sha256, page_offset: d.page_offset, pages: d.pages })) }
      : {}),
    calc_source: cg.source,
  };
}

// ---------------------------------------------------------------- export -> bundle

/** The calc source of an export: the bundle's it came from, else the PDFs the engine mapped (by sha256). */
function sourceOf(exp: Export): BundleCalcSource {
  if (exp.calc_source) return exp.calc_source;
  const pkg = exp.producers.calc_package;
  const documents: BundleDocument[] = exp.documents?.length
    ? exp.documents.map((d) => ({ doc_id: d.doc_id, name: d.name, revision: d.revision, sha256: d.sha256, pages: d.pages, page_offset: d.page_offset }))
    : pkg
      ? [{ doc_id: null, name: pkg.name, revision: exp.calc_revision, sha256: pkg.sha256, pages: pkg.pages, page_offset: 0 }]
      : fail("the export names no calc PDF (no documents and no calc_package producer): it cannot be saved as a PDF calc graph");
  return { kind: "pdf", documents };
}

/**
 * The calc graph of a project's export: its calcs, calc edges and every link that is not rejected,
 * with evidence, review state and provenance kept. The PDFs are named by sha256 (from the export's
 * documents, else its calc package record); their bytes are not included. An export made from a
 * bundle keeps that bundle's source (a demo stays a demo). Typical groups, group links and findings
 * are derived again by the engine from the PDF, so they are not written.
 */
export function exportToCalcGraph(exp: Export): BundleCalcGraph {
  const source = sourceOf(exp);
  const links: BundleLink[] = [];
  for (const e of exp.elements) {
    for (const l of e.calcs ?? []) {
      if (l.review === "rejected") continue;
      const decided = l.review_provenance;
      const note = (l.reasons ?? []).find((r) => r.kind === NOTE_EVIDENCE)?.note;
      const caveats = (l.caveats ?? []).filter((c) => c !== DEMO_CAVEAT);
      links.push({
        element: e.global_id, calc: l.calc, role: l.role ?? "design",
        review: l.review === "manual" ? "manual" : l.review === "confirmed" ? "confirmed" : "auto",
        conf: l.confidence, tier: l.tier, rule: l.rule, page: l.evidence?.page ?? l.page, rects: l.evidence?.rects ?? [],
        snippet: l.evidence?.snippet ?? null, matched_text: l.matched_text, caveats,
        ...(note ? { note } : {}),
        ...(decided?.actor !== undefined ? { decided_by: decided.actor } : {}),
        ...(decided?.at ? { decided_at: decided.at } : {}),
        // a demo record's provenance is derived again on load (it says "demo"); a mapped one is the run's
        ...(source.kind === "pdf" ? { provenance: l.provenance } : {}),
      });
    }
  }
  return {
    source,
    calcs: exp.calcs.map((c) => ({
      key: c.key, title: c.title, cat: c.element_type, software: c.software, pages: c.pages, scanned: c.scanned,
      front_matter: c.front_matter, title_box: c.title_box, spans: c.spans, ...(c.meta ?? {}),
      ...(source.kind === "pdf" ? { provenance: c.provenance } : {}),
    })),
    edges: exp.calc_edges.map((e) => ({
      src: e.src, dst: e.dst, rules: e.rules, evidence: e.evidence, ...(source.kind === "pdf" ? { provenance: e.provenance } : {}),
    })),
    links,
  };
}
