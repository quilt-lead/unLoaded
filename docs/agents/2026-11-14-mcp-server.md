# MCP server on the calc engine (`packages/mcp-server`)

- **Status:** active (ported to calc-mapper and parity-green; review round 1 fixed 2026-11-15, uncommitted when written)
- **Branch:** `issy/mcp-server`, rebased onto Carl's PR #9 (`origin/cs/phase1-calc-engine`, 7a970d7). Not on `prod`.
- **Owned files:** `packages/mcp-server/**`, the `@unloaded/mcp-server` entries in `package-lock.json`, the two MCP
  references in `packages/project-file/README.md` and `packages/project-file/src/index.ts`
- **Working files (review round 1):** `src/{decisions,project,tools,server,engine,check,cli}.ts`,
  `scripts/{mcp-parity,minimalPdf}.ts`, `test/{decisions,multipdf,tools,projectfile}.test.ts`, `test/{fixtures,helpers}.ts`

## Context

A local stdio MCP server so an engineer's own AI can query a project (IFC + calc PDFs, or the app's
`*.calcgraph.json`) and record review decisions. It was first built on prod's `@unloaded/calc-parser`. On PR #9
**calc-parser was retired into calc-mapper** (see `2026-11-14-phase1-integration.md`, item 4), so the server was
re-pointed: `src/engine.ts` now calls `@unloaded/calc-mapper`, `@unloaded/project-file` and `@unloaded/move-impact`
(plus `ifc-parser` / `element-graph` for models). PR #9 had also carried an older project-file-only server (the
calc-mapper hackathon design); its project-file input, findings / groups / compare / move_column tools and its
`makeProjectFile` tooling were folded into the new structure, and its other files deleted.

## Decisions

- **Engine boundary:** only `src/engine.ts` imports an `@unloaded/*` package. A test in `test/server.test.ts` enforces
  it and checks `package.json` declares exactly what `engine.ts` imports (no calc-parser).
- **Models:** the graph calc-mapper reads is what the app stores: `ElementGraph.serialize()` then `parseGraph` (so a
  non-metre graph is refused up front). Repeat `--model` oldest first; the LAST is the current model (same rule as a
  project file's head = highest id). Older revisions exist only for `compare_revisions` (`diffGraphs`).
- **Project file:** `--project` takes either a manifest or a `*.calcgraph.json` (detected by `isProjectFileFormat`).
  All model revisions load; only the head calc revision is mapped (calc revisions are versions of one package, as in
  the app). Stored extraction via `storedExtractionFor`, else re-extracted. The file's decision log is applied first,
  read-only; the `--decisions` file after it (ids shifted past the file's, for the engine only), so a server decision
  wins. **Ids shown to anyone are per origin** (`{origin: "decisions_file" | "project_file", id}`): get_element, link
  decisions, record_decision and the decisions resource all use it. The shifted ids exist only inside
  `Project.buildLog`; `Project.decisionRef` maps back. Before round 1, get_element showed shifted ids and
  record_decision raw ones.
- **Decisions file = calc-mapper's decision log** (JSON array of `Decision`s with `id` and human `provenance`, the
  format `run-pipeline.ts --decisions` reads). New entries come from the engine's `addDecision` (`nextDecision`),
  entries are read back through `decisionFrom` (one without provenance is accepted and never rewritten). Still
  append-only. The calc-parser-format files (no `id`) the previous version wrote are refused with a message; that
  version was never merged, so no real files exist.
- **Concurrency (round 1):** every append holds `<realpath>.lock` (O_EXCL, `{pid, host, token, at}`), re-reads the
  file under it, writes temp next to the REAL file, fsync, rename, dir fsync. Stale = same host + dead pid, or older
  than 30 s; live = wait up to 10 s then a message naming the lock file. Without the lock, two processes appending
  15 each kept 15 of 30 (measured against HEAD 8352c0f); with it, 30 of 30. In-process, load / refresh / append share
  one queue (a refresh asked for during an append resolves after it). The snapshot after a write comes from the bytes
  written (fstat of the temp before rename), never a stat after the rename.
- **Write tools do NOT pre-refresh** (server.ts `run(..., { write: true })`): the append re-reads under the lock, so
  `reloaded_external_changes` is true exactly when someone else appended since this server last read. It used to be
  always false over MCP because the wrapper refreshed first.
- **Malformed decisions file = a problem, not a crash:** `DecisionsFile.problem`; reads keep the last good log (or
  none), `source.decisions_warning` on every result, `project_summary.decisions.problem` + warnings, writes refused,
  file never overwritten, `--check` prints NOT READY and exits 1. A 0-byte / whitespace file is a problem too (it used
  to read as `[]`).
- **Decisions naming missing calc keys** warn loudly (recomputed with the log, so a refresh updates them) with the
  likely cause from the key's prefix. This is mitigation for the calc-key prefix scheme (keys depend on `--calcs` order
  and file stems), not a fix of the scheme.
- **Multi-PDF:** calc-mapper is one package per run (`packageSha256` refuses two documents), so it is NOT native.
  `mapCalcs` per PDF; main PDF plain keys, others `<stem-slug>/` (put on the package's calc keys before mapCalcs).
  Status = `statusOf` over every PDF's links. ONE designer per element for every cross-reference edge: `designerOf`
  over every PDF's effective links (round 1: within-PDF edges used to take each PDF's own buildState designer, so an
  element designed in two PDFs had two designers and extra edges). Within-PDF edges = `calcEdgesOfPdf` (engine.ts:
  inferCalcEdges on one PDF, other PDFs' links passed with `page: null` as designer candidates only), keeping edges
  with both calcs in that PDF; with one PDF it is exactly buildState's call. Cross-PDF edges = `inferCalcEdges` on a
  combined view with calcs' `pages` AND `spans` emptied (calc-mapper reads regions from `spans` first, so emptying
  `pages` alone would not switch the page-reference rule off) and page numbers offset (the cue word of a mention is
  read on its own page); impact = `propagate` over everything; export = one `buildExport` per PDF (per-run designer,
  documented as per-run).
- **Tools added vs the calc-parser version:** `list_findings`, `list_typical_groups`, `compare_revisions`,
  `move_column`. Links now carry role / band / reasons / caveats / provenance; status counts design links only (high
  band 0.75, not 0.8). `export_mapping` is `buildExport` per PDF (was calc-parser `exportMapping`).
- **move_column without calc facts:** calc-mapper extracts no calc row values yet, so move-impact gets the graph and
  the reviewed links only: no utilisation estimates, no health band (said in the result).

## Gotchas

- web-ifc's wasm logs to **stdout** through `console.log`. That would corrupt the MCP channel. The bin shim reroutes
  console to stderr *before* the CLI (and therefore web-ifc) is imported. Don't add static imports of engine code to
  the bin shim. The parity script filters those lines from its own direct `parseIfc`.
- pdf.js prints `Warning: ... standardFontDataUrl` during extraction. Counted and hidden unless `--verbose`.
- `makeProjectFile` lives in `scripts/` (not `src/`) because it imports engine packages; CI's `tooling` job runs
  `scripts/make-project-file.ts` then `scripts/mcp-parity.ts <file>`. Don't rename either without updating
  `.github/workflows/ci.yml`.
- The Building 12 PDFs in `data/sampleCalc/` are Git LFS pointers on this machine (no `git-lfs` installed); the CLI
  says so instead of "not a PDF". No PDF was added to git.
- No committed calc PDF fixture exists on this branch (calc-parser's went with it; calc-mapper's golden fixtures are
  JSON). The vitest suites build theirs byte by byte in `test/fixtures.ts`; parity runs on the generated synthetic
  package (`uv run python -m synth.generate`, gitignored).
- **Parity oracle must stay independent.** `scripts/mcp-parity.ts` used to re-implement the server's multi-PDF edge
  composition (a tautology). It now checks invariants (`edgeProblems`): per-PDF page-reference edges == the engine on
  that PDF alone, every cross-reference evidence item's other end == designerOf over all links, every live mention has
  its edge oriented as the engine orients it on its own PDF, cross_pdf flag, evidence pages in range. Don't put a
  copy of project.ts's composition back into it.
- **The engine caps edge evidence at 6 items.** A wrong extra designer can hide behind the cap (on synthetic data the
  supplement first won the designer tie by key order and the stray main-PDF edge's evidence was capped away, so the
  invariants passed against the old code). The --two-pdf supplement is therefore named `xref_supplement.pdf` so the
  main calc wins a tie, and the parity asserts that the supplement's mention is fed by exactly one designer.
- The local test-blocking hook also matches `npm run check`. Run `node packages/mcp-server/bin/unloaded-mcp-server.mjs
  ... --check` directly instead.

## Verification, review round 1 (2026-11-15, this machine)

- Parity, all modes green: default (rev 1 + rev 2 + calc_package.pdf) 82/82; `--two-pdf` (generated supplement)
  85/85 with 2 cross-PDF edges; project file as CI builds it 83/83; project file with a seeded decision 82/82;
  `--model rev1.ifc --calcs calc_package.pdf` 80/80; rev 1 + rev 2 + calc_package + calc_supplement 82/82.
- Negative controls run against HEAD 8352c0f's src (temporary copy, deleted): the new `--two-pdf` parity fails 5
  checks (second designer, origin ids, reloaded_external_changes); two processes x 15 appends kept 15 of 30.
- vitest and tsc not run locally (hook-blocked); new tests were read against the old code to confirm they fail there.

## Verification (2026-11-15, this machine, before review round 1)

- `--check` on synthetic `model_rev1.ifc` + `calc_package.pdf`: 459 elements, 12 calcs, 800 links, confirmed 392 /
  review 63 / unmapped 4, 13 calc edges, 40 typical groups, 0 findings.
- Parity (real CLI over stdio, every tool, vs the engine packages called directly): one model + one PDF 77/77;
  rev 1 + rev 2 + one PDF 79/79; + `calc_supplement.pdf` 81/81; project file (as CI builds it) 80/80; project file with
  a seeded decision 79/79.
- vitest suites and tsc: written for CI, not run (hook-blocked locally).

## Next steps

- Real projects with more than one distinct PDF: the synthetic calc_supplement.pdf gives no cross-PDF edge; the
  byte-built fixtures and the parity's generated supplement do. Confirm the cross-PDF edges read sensibly to an engineer.
- The calc-key scheme itself (prefix = file stem, plain keys for the first `--calcs`) is fragile by design; round 1
  only made breakage loud. A stable key (e.g. by PDF sha256 or a manifest-declared id) would be the structural fix.
- calc-mapper's own `addDecision` computes the next id with `Math.max(0, ...log.map(...))`: a RangeError past ~150k
  decisions. Engine package, not changed here.
- When calc-mapper extracts calc row values, pass them to move-impact as `facts` (estimates + health band).
