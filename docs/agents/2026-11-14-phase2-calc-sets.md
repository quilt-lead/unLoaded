# Phase 2: calc sets (many PDFs) and per-document revisions

- **Status:** done (steps 1-5); PR open to `prod`. Follow-ups below.
- **Branch:** `cs/phase2-calc-sets`, cut from `cs/phase1-calc-engine`; `prod` (with PR #9 merged) merged in on 2026-11-15.
- **Owned files:** `packages/calc-mapper/src/{types,project,package,calcset}.ts` (calcset.ts new), `packages/project-file/`,
  `src/engine/{ops,projectService,hooks}.ts`, `src/data/{projectStore,loadProject,mergeProject}.ts`, `src/components/RevisionPanel.tsx`,
  the calc-upload path in `src/loaders/parsers.ts` / `HeaderBar.tsx`.
- **Working files:** none in flight. Also touched: `src/components/{CalcDocumentsSection,RevisionPanel,DocumentBrowser,HeaderBar}.tsx`, `src/App.tsx`, `src/types/bim.ts`, `packages/mcp-server/`.

## Why

The mission says calcs arrive either as **one large PDF** or **one PDF per calc**, and that **each PDF may have several
versions**. PR #4's engine supports exactly one calc PDF per project at a time:

- `packageSha256` / `segmentCalcs` refuse pages from more than one document (`segment.ts`).
- `Calc.key` is a slug of the title, unique only within one package. `Link`, `CalcEdge`, `Decision` and impact all key on it.
- `MappingRun.inputs` is `[graph, pdf]`; the project file / store keep one head `calcs` revision (`headOf`).

So a folder of 40 one-calc PDFs can't be loaded, and "Rev B of the column calcs" replaces the whole calc set.

## Model

- **CalcDocument**: one logical PDF in the project, with a stable `doc_id` (not the sha: it survives revisions).
  Holds an ordered list of **document revisions** (each one PDF file → one `CalcPackage`, as today).
- **CalcSet**: the head revision of every document in the project. This is what mapping runs over.
- **Calc identity** is `(doc_id, key)`. Serialized as a single string `calc_ref = "<doc_id>#<key>"` everywhere a key is
  used today (links, edges, decisions, impact, export), so downstream code that treats keys as opaque strings keeps working.
- **Backward compatibility:** always use `calc_ref`, even with a single document (no special case), and migrate
  old decisions on read (`calc_key` without `#` → the project's first document). One rule, no special case. Old project
  files and stored decisions must still open; add a test with a pre-Phase-2 project file.

## Matching a new upload to an existing document

When a PDF is added, decide whether it is a **new document** or a **new revision of an existing one**:

1. Same sha256 as an existing revision → already loaded, no-op (tell the user).
2. Same normalized file name ignoring revision tokens (`_RevB`, `-r2`, `(1)`, `v3`, dates) → revision of that document.
3. Calc-key overlap: ≥ 60% of the new package's non-front calc keys match one document's head keys → revision of it.
4. Otherwise a new document.

The decision is a **suggestion** shown in the upload UI ("Added as Rev C of *Column calcs*" with a "make it a new
document instead" / "pick document" override). Record the rule used with provenance (`calcset.match.<rule>`).

## Engine changes (`packages/calc-mapper`)

- `calcset.ts` (new): `CalcSet` type, `buildCalcSet(docs)`, `resolveRevisionTarget(set, newPkg, fileName)` (rules above),
  `calcRef(doc_id, key)` / `parseCalcRef`.
- `mapCalcs(graph, set)` accepts a `CalcSet` (keep a `CalcPackage` overload that wraps it as a one-document set).
  Page numbers are per document: anything carrying `page` (Link, Snippet, rects, page references in `calcdeps`) also needs
  `doc_id`. Calc → calc dependency edges may now cross documents (cross-references by title work across files;
  page references stay within one document).
- `inputs` becomes `[graph sha, ...every document head sha]`, sorted for stable run keys.
- `diffCalcSets(before, after)`: per document, calcs added / removed / changed (`content_hash`) / pages moved; documents
  added / removed. This is the calc-revision diff the app is missing.
- Bump `ENGINE_VERSION` (cached runs recompute) and keep `PACKAGE_VERSION` in step.
- **Gate:** the synthetic evaluation baseline must not move. Single-PDF synthetic run through the set path must score
  identically. Add a synthetic split-per-calc case (split the synthetic package into one PDF per calc in the test, or
  compose `CalcPage[]` per calc) and require the same mapping P/R/F1 as the single PDF.

## Storage (`packages/project-file`, `src/data/projectStore.ts`)

- Calc revisions gain `docId`. Head is per document (`headOf(revisions, "calcs", docId)`), and the set head is every
  document's head. Documents can be **removed** from the set (soft: a tombstone revision), since a calc can be withdrawn.
- Project-file format version bump; the reader accepts the old version (no `docId` → one document) and the writer writes
  the new one. Store DB version bump with an upgrade that assigns existing calc revisions to one document.
- Decisions: `calcRev` stays (the revision the decision was made against); `calc_key` becomes a `calc_ref`.

## App

- Upload: accept multiple PDFs at once (file picker `multiple`, drag-drop of many). Show per-file progress and the
  new-document / new-revision decision for each, overridable.
- Revision panel: documents listed with their revision tabs (Rev A, Rev B...) instead of one global calc revision list.
- Compare calc revisions: pick a document (or "whole set") and two revisions → `diffCalcSets` output in the inspector,
  and badges on calc nodes in the calc graph (added / changed / removed, same colours as the model diff).
- Calc graph: calcs grouped by category as now; the PDF viewer opens the right document at the right page.
- Follow the project's UI skills (frontend-ui-engineering, react-best-practices, then web-design-guidelines review).

## Order of work

1. calc-mapper: `calcset.ts`, `calc_ref` through types / matcher / calcdeps / impact / export, `diffCalcSets`. Tests + gate.
2. project-file + store: doc ids, per-document heads, migration of old files / DB. Tests.
3. engine ops / projectService / hooks.
4. UI: multi-upload, revision panel, calc diff.
5. Browser smoke (headless) on the synthetic sample: one PDF, then split into per-calc PDFs, then a Rev B of one document.

## Open questions

- Should a revision be allowed to **split or merge** documents (Rev B combines two Rev A PDFs)? Proposed: not in Phase 2;
  the user removes the old documents and adds the new one, and decisions follow `calc_ref` by key match only within a document.
- Do decisions carry across documents when a calc moves from one PDF to another? Proposed: no (identity includes doc_id).

## Progress

| Step | State | Commit |
|---|---|---|
| 1. calc-mapper: calc sets, calc refs, per-document page refs, revision targets, calc diff | done | `b4fd0c5` |
| 2. project-file v2 + store: documents, per-document heads, legacy reads | done | `b383394` |
| 3. engine ops / projectService / hooks + MCP server on the set | done | `e9a1b0d` |
| 4a. View shows each PDF's own pages; calc opens in its document's PDF; multi-PDF upload | done | `b267967` |
| 4b. Calc documents in the revision panel: revisions, move, withdraw, calc diff | done | `f56cd92` |
| 5. Browser smoke (headless Chromium on the dev server) | done | see below |

Also on this branch, not Phase 2 but needed for green tests (cherry-pick into Phase 1): `f7eedc4` (stale parseGraph
test message), `563feaf` (App.scope test failed on a Windows CRLF checkout).

**Gate:** `evaluate_all.py --synthetic-only` before and after step 1: identical on every metric (design P/R/F1
93.2/99.6/96.3, calc edges 84.6/91.7, load path 100/100, segmentation 12/12, impact C8 15/36/8). One check,
`synthetic_check.generator_byte_stable`, fails on this Windows machine before and after (not caused by this work; likely
CRLF in the generated files, the same cause as `563feaf`). MCP parity on the synthetic project file: 35/35.

## Decisions

- **One combined package, set page numbers** (not per-document runs merged after). The matcher's type-only tier
  ("calc covers beams but names no marks") only claims elements no other calc claimed; run per document, a one-calc
  PDF would claim every beam. Combining keeps one claim pass, so one PDF per calc maps exactly as one large PDF (test).
  Document k's page n is set page n + offset(k); offsets follow document order. Every page number in a set run,
  export and view is a set page; `docPageOf` / `setPageOf` (engine) and `pageOffsets` (snapshot) convert.
- **Page references resolve inside the referring PDF.** calcdeps groups pages by `doc_sha256` and takes each
  document's offset from its lowest page, so a single PDF behaves exactly as before. Running headers / footers are found
  per document.
- **The package path is unchanged.** `mapCalcs(graph, CalcPackage)` still gives bare keys, so the Python gate, the CLI
  and `run-pipeline.ts` are untouched. Only the set path gives refs. No MAPPER_VERSION bump: no output of the package
  path changed, and the app's run cache is now keyed by set (`calcSetKey`), so old cached runs are never reused anyway.
- **`RunProducers.calc_package` is optional**: present when the run rests on one PDF; `calc_set` / `Export.documents`
  describe a set. A fake combined hash was rejected (provenance hashes must name real bytes).
- **No IndexedDB version bump.** Records are schemaless; old ones read through project-file rules (`LEGACY_DOC_ID = "d1"`
  for calc revisions without `docId`; bare decision keys → `d1#key`). Nothing is migrated in place, so an older build of the
  app can still open the same database.
- **Project file version 2**, reader accepts 1 and 2. A document must have at least one revision (the store drops a
  document a move leaves empty; the reader refuses an empty one).
- **Placement rules** (`resolveRevisionTarget`): same sha256 → duplicate (not added); same file-name stem (revision /
  copy / date tokens dropped) as exactly one document → its revision; ≥ 60 % of the new PDF's non-front calc keys in one
  document's head → its revision; else new. It is a suggestion: `addCalcRevision(target)` and `moveCalcRevision` override.
- **A document whose PDF cannot be read is left out of the set**, named in `calcError`; the others still map (was: the
  whole calc view dropped).
- **MCP:** default view = the head set; `calc_revision` = that revision alone as a one-document set; `get_calc` accepts a
  bare key when only one document has it; `get_page_image` needs `calc_revision` when there are several documents (it
  takes a page of ONE PDF; descriptions say how to convert set pages).
- **Open questions in the plan, answered as proposed:** no split / merge of documents across revisions; decisions do not
  follow a calc into another document (identity includes doc_id).

- **View pages are each PDF's own** (not set pages): `toCalcData` converts once, by the document of the calc each page
  belongs to (every page in the view belongs to a calc); view calcs carry `docId` / `docName`; DocumentBrowser picks the
  PDF from `pdfUrls[docId]`.

## Browser smoke (2026-11-15)

Headless Chromium (playwright-core from another session's scratchpad, not a project dependency) on `vite --port 5191`:
Load sample -> 1 document; Add sample supplement -> toast "added as a new calc document, calc_supplement (revision #3)",
2 documents, 15 calcs; the supplement's PT SLAB TENDON PROFILE CHECK opens the supplement PDF at its own page 2 (sheet
"SUPPLEMENT S-2 OF 3"), title highlighted; adding calc_package.pdf again adds nothing. One console 404 (pre-existing
favicon, per the parser-merge note). Not exercised in the browser: one PDF per calc (covered by the calc-mapper test),
move / withdraw / calc diff clicks (store + engine tests cover them).

## Left / follow-ups

- Calc diff badges on the calc graph nodes (the diff shows in the revision panel only).
- Rename a calc document from the UI (`updateDocument({ name })` exists; no control yet).
- `generator_byte_stable` fails on Windows checkouts only (Linux CI passes it; CRLF).
- Done 2026-11-15: merged `prod` after PR #9. The only conflicts were the duplicate CRLF test fix and `App.tsx`, where drag & drop
  met the calc-document handlers. A drop of calc PDFs alone is now one calc-set upload (`handleUpload('calcs', pdfs)`,
  placed per document like **Add calc PDFs**). Anything else still opens one file at a time.
- Direction (Carl, 2026-11-15): TypeScript is the reference, not the Python prototype. Equivalence checks belong in
  TS tests (the one-PDF-per-calc test is one), not in the Python gate.
