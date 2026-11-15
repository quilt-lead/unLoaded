/**
 * Calc sets: a project's calcs as MANY PDFs (one large package, one PDF per calc, or any mix), each a
 * document with its own revisions. The engine maps a set exactly as it maps one package, so a set of
 * one PDF and the same PDF as a package give the same links (a test pins it).
 *
 *   CalcSetDocument  one document's head revision: a stable doc_id (survives revisions) + its CalcPackage
 *   CalcSet          every document's head, combined into ONE package the engine reads:
 *                    - calc keys become calc refs "<doc_id>#<key>" (a title slug is unique only within a PDF)
 *                    - pages get SET page numbers: document k's page n is n + page_offset(k), so every page
 *                      number in a set run (links, evidence, calc edges, findings) names one page of one PDF.
 *                      `setPageOf` / `docPageOf` convert; the first document's offset is 0.
 *
 * Page references ("see page 7") stay inside the referring document (calcdeps.ts groups pages by
 * doc_sha256); cross-references by element mark work across documents.
 */
import { RULES, ruleProvenance } from "./provenance.ts";
import { packageSha256 } from "./segment.ts";
import { SEGMENTER_VERSION, type Calc, type CalcPackage, type CalcPage, type Provenance } from "./types.ts";

/** One document of a set: its stable id, display name, the revision label, and its head package. */
export interface CalcSetDocument {
  /** Stable across revisions; must not contain "#". */
  doc_id: string;
  name: string | null;
  revision?: string | number | null;
  package: CalcPackage;
}

/** A document's place in a set (no pages / calcs: what an export or a page lookup needs). */
export interface CalcSetDoc {
  doc_id: string;
  name: string | null;
  revision: string | number | null;
  /** sha256 of the document's PDF bytes. */
  sha256: string;
  /** Set page = document page + page_offset. */
  page_offset: number;
  /** Pages in the document (its highest page number). */
  pages: number;
}

export interface CalcSet {
  docs: CalcSetDoc[];
  /** Every document's head as one package: calc refs as keys, set page numbers. */
  combined: CalcPackage;
}

export const CALC_REF_SEP = "#";

/** "<doc_id>#<key>": a calc's identity in a set. */
export function calcRef(docId: string, key: string): string {
  return `${docId}${CALC_REF_SEP}${key}`;
}

/** The (doc_id, key) of a calc ref; doc_id null for a bare key (a single-package run, or a decision made before sets). */
export function parseCalcRef(ref: string): { doc_id: string | null; key: string } {
  const i = ref.indexOf(CALC_REF_SEP);
  return i < 0 ? { doc_id: null, key: ref } : { doc_id: ref.slice(0, i), key: ref.slice(i + 1) };
}

export function isCalcSet(x: CalcPackage | CalcSet | null | undefined): x is CalcSet {
  return !!x && Array.isArray((x as CalcSet).docs) && !!(x as CalcSet).combined;
}

/**
 * Combine documents into a set. Document order is the order given (the store's document order);
 * offsets follow it. Throws on a duplicate doc_id, a doc_id with "#", or the same PDF twice.
 */
export function buildCalcSet(documents: readonly CalcSetDocument[]): CalcSet {
  const ids = new Set<string>();
  const shas = new Map<string, string>();
  const docs: CalcSetDoc[] = [];
  const pages: CalcPage[] = [];
  const calcs: Calc[] = [];
  let offset = 0;
  for (const d of documents) {
    if (!d.doc_id || d.doc_id.includes(CALC_REF_SEP)) throw new Error(`calc set doc_id must be non-empty and contain no "${CALC_REF_SEP}": ${JSON.stringify(d.doc_id)}`);
    if (ids.has(d.doc_id)) throw new Error(`calc set: duplicate doc_id ${d.doc_id}`);
    ids.add(d.doc_id);
    const sha = packageSha256(d.package.pages);
    const twin = shas.get(sha);
    if (twin) throw new Error(`calc set: documents ${twin} and ${d.doc_id} are the same PDF`);
    shas.set(sha, d.doc_id);
    const count = Math.max(...d.package.pages.map((p) => p.n));
    const shift = (n: number): number => n + offset;
    for (const p of d.package.pages) pages.push({ ...p, n: shift(p.n) });
    for (const c of d.package.calcs) {
      calcs.push({
        ...c,
        key: calcRef(d.doc_id, c.key),
        ord: calcs.length,
        pages: c.pages.map(shift),
        title_box: { ...c.title_box, page: shift(c.title_box.page) },
        spans: (c.spans ?? []).map((s) => ({ regions: s.regions.map((r) => ({ ...r, page: shift(r.page) })) })),
      });
    }
    docs.push({ doc_id: d.doc_id, name: d.name, revision: d.revision ?? null, sha256: sha, page_offset: offset, pages: count });
    offset += count;
  }
  const segmenters = [...new Set(documents.map((d) => d.package.segmenter || ""))];
  return {
    docs,
    combined: {
      source_name: documents.length === 1 ? documents[0]!.package.source_name : null,
      // the combined package is not one PDF: its document hashes are on its pages and in `docs`
      source_sha256: documents.length === 1 ? docs[0]!.sha256 : "",
      segmenter: segmenters.length === 1 ? segmenters[0]! : segmenters.join("+") || SEGMENTER_VERSION,
      pages,
      calcs,
    },
  };
}

/** The set page of a document page, or null when the set has no such document / page. */
export function setPageOf(set: Pick<CalcSet, "docs">, docId: string, page: number): number | null {
  const d = set.docs.find((x) => x.doc_id === docId);
  return d && page >= 1 && page <= d.pages ? page + d.page_offset : null;
}

/** The document and its page that a set page names, or null outside the set. */
export function docPageOf(set: Pick<CalcSet, "docs">, setPage: number): { doc_id: string; page: number } | null {
  for (const d of set.docs) {
    if (setPage > d.page_offset && setPage <= d.page_offset + d.pages) return { doc_id: d.doc_id, page: setPage - d.page_offset };
  }
  return null;
}

/** sha256 of every PDF a package or set rests on, in document order. */
export function documentShas(x: CalcPackage | CalcSet): string[] {
  return isCalcSet(x) ? x.docs.map((d) => d.sha256) : [packageSha256(x.pages)];
}

// ---------------------------------------------------------------- new upload -> which document

/** What the project already holds of a document: enough to recognise a new revision of it. */
export interface KnownDocument {
  doc_id: string;
  /** File names of its revisions (any order). */
  names: readonly (string | null)[];
  /** sha256 of every revision's PDF. */
  shas: readonly string[];
  /** Calc keys (bare, not refs) of its head revision. */
  keys: readonly string[];
}

export type RevisionTarget =
  | { kind: "duplicate"; doc_id: string; rule: string; note: string; provenance: Provenance }
  | { kind: "revision"; doc_id: string; rule: string; note: string; provenance: Provenance }
  | { kind: "new"; rule: string; note: string; provenance: Provenance };

/** Share of a new package's mapped calc keys that one document's head shares, at or above which it is a revision of it. */
export const KEY_OVERLAP_MIN = 0.6;

/**
 * A file name without its extension, revision / copy tokens, and punctuation, lower case:
 * "Column Calcs_RevB (1).pdf", "column-calcs-r2.pdf" and "COLUMN CALCS v3 2026-11-14.pdf" all give "column calcs".
 */
export function documentStem(name: string): string {
  let s = name.toLowerCase().replace(/\.[a-z0-9]{2,4}$/, "");
  s = s.replace(/\(\d+\)/g, " ");                                     // (1) copies
  s = s.replace(/\b\d{4}[-_.]?\d{2}[-_.]?\d{2}\b/g, " ");             // dates
  s = s.replace(/(^|[^a-z0-9])(rev(ision)?|r|v(er(sion)?)?)[\s._-]*([a-z]|\d{1,3})(?=$|[^a-z0-9])/g, " "); // rev B, r2, v3
  s = s.replace(/(^|[^a-z0-9])(final|issued|ifc|ifp|draft|copy|updated?|latest)(?=$|[^a-z0-9])/g, " ");
  return s.replace(/[^a-z0-9]+/g, " ").trim();
}

/**
 * Is a newly extracted package a document the project already has (same PDF), a new revision of one,
 * or a new document? Rules, first that applies:
 *   1. same sha256 as any revision of a document          -> duplicate (already loaded)
 *   2. same file-name stem as a revision of one document  -> revision of it
 *   3. >= KEY_OVERLAP_MIN of the package's mapped calc keys are in one document's head (the best one)
 *                                                         -> revision of it
 *   4. otherwise                                          -> new document
 * The answer is a SUGGESTION the app shows and the user can override.
 */
export function resolveRevisionTarget(known: readonly KnownDocument[], pkg: CalcPackage, fileName: string | null): RevisionTarget {
  const sha = packageSha256(pkg.pages);
  const prov = (rule: string): Provenance => ruleProvenance("calcset", rule, [sha]);
  const dup = known.find((d) => d.shas.includes(sha));
  if (dup) return { kind: "duplicate", doc_id: dup.doc_id, rule: RULES.calcset.duplicate, note: "the same PDF is already loaded", provenance: prov(RULES.calcset.duplicate) };
  const stem = fileName ? documentStem(fileName) : "";
  if (stem) {
    const byName = known.filter((d) => d.names.some((n) => n && documentStem(n) === stem));
    if (byName.length === 1) {
      return { kind: "revision", doc_id: byName[0]!.doc_id, rule: RULES.calcset.name, note: `same file name (${stem})`, provenance: prov(RULES.calcset.name) };
    }
  }
  const keys = pkg.calcs.filter((c) => !c.front && !c.scanned).map((c) => c.key);
  if (keys.length) {
    let best: { d: KnownDocument; share: number } | null = null;
    for (const d of known) {
      const have = new Set(d.keys);
      const share = keys.filter((k) => have.has(k)).length / keys.length;
      if (share >= KEY_OVERLAP_MIN && (!best || share > best.share)) best = { d, share };
    }
    if (best) {
      return {
        kind: "revision", doc_id: best.d.doc_id, rule: RULES.calcset.keys,
        note: `${Math.round(best.share * 100)}% of its calcs are in this document`, provenance: prov(RULES.calcset.keys),
      };
    }
  }
  return { kind: "new", rule: RULES.calcset.new, note: "no document with this name or these calcs", provenance: prov(RULES.calcset.new) };
}

// ---------------------------------------------------------------- calc revision diff

export interface CalcDiffEntry {
  doc_id: string;
  key: string;
  ref: string;
  title: string;
}

export interface CalcSetDiff {
  docs_added: string[];
  docs_removed: string[];
  added: CalcDiffEntry[];
  removed: CalcDiffEntry[];
  /** Same key, different title + text (`content_hash`). */
  changed: (CalcDiffEntry & { before_title: string })[];
  /** Same content, different document pages. */
  moved: (CalcDiffEntry & { before_pages: number[]; after_pages: number[] })[];
  unchanged: number;
}

/**
 * Calcs added / removed / changed / moved between two sets of documents (each document's package in
 * its OWN page numbers - the CalcSetDocument inputs, not the combined set). Front matter is ignored.
 * Documents are matched by doc_id, calcs within a document by key.
 */
export function diffCalcSets(before: readonly CalcSetDocument[], after: readonly CalcSetDocument[]): CalcSetDiff {
  const out: CalcSetDiff = { docs_added: [], docs_removed: [], added: [], removed: [], changed: [], moved: [], unchanged: 0 };
  const byId = (ds: readonly CalcSetDocument[]) => new Map(ds.map((d) => [d.doc_id, d]));
  const a = byId(before), b = byId(after);
  const entry = (doc_id: string, c: Calc): CalcDiffEntry => ({ doc_id, key: c.key, ref: calcRef(doc_id, c.key), title: c.title });
  const live = (p: CalcPackage | undefined) => new Map((p?.calcs ?? []).filter((c) => !c.front).map((c) => [c.key, c]));
  for (const id of new Set([...a.keys(), ...b.keys()])) {
    const da = a.get(id), db = b.get(id);
    if (!da) out.docs_added.push(id);
    if (!db) out.docs_removed.push(id);
    const ca = live(da?.package), cb = live(db?.package);
    for (const [k, c] of cb) {
      const o = ca.get(k);
      if (!o) out.added.push(entry(id, c));
      else if (o.content_hash !== c.content_hash) out.changed.push({ ...entry(id, c), before_title: o.title });
      else if (o.pages.join(",") !== c.pages.join(",")) out.moved.push({ ...entry(id, c), before_pages: o.pages, after_pages: c.pages });
      else out.unchanged += 1;
    }
    for (const [k, c] of ca) if (!cb.has(k)) out.removed.push(entry(id, c));
  }
  const byRef = (p: CalcDiffEntry, q: CalcDiffEntry) => (p.ref < q.ref ? -1 : p.ref > q.ref ? 1 : 0);
  for (const l of [out.added, out.removed, out.changed, out.moved]) l.sort(byRef);
  out.docs_added.sort();
  out.docs_removed.sort();
  return out;
}
