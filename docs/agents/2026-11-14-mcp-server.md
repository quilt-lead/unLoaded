# MCP server on the calc engine (`packages/mcp-server`)

- **Status:** active (ported to calc-mapper and parity-green; not committed when written)
- **Branch:** `issy/mcp-server`, rebased onto Carl's PR #9 (`origin/cs/phase1-calc-engine`, 7a970d7). Not on `prod`.
- **Owned files:** `packages/mcp-server/**`, the `@unloaded/mcp-server` entries in `package-lock.json`, the two MCP
  references in `packages/project-file/README.md` and `packages/project-file/src/index.ts`

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
  read-only; the `--decisions` file after it (ids shifted past the file's), so a server decision wins.
- **Decisions file = calc-mapper's decision log** (JSON array of `Decision`s with `id` and human `provenance`, the
  format `run-pipeline.ts --decisions` reads). New entries come from the engine's `addDecision` (`nextDecision`),
  entries are read back through `decisionFrom` (one without provenance is accepted and never rewritten). Still
  append-only, atomic temp + rename, re-read when it changes on disk. The calc-parser-format files (no `id`) the
  previous version wrote are refused with a message; that version was never merged, so no real files exist.
- **Multi-PDF:** calc-mapper is one package per run (`packageSha256` refuses two documents), so it is NOT native.
  `mapCalcs` per PDF; main PDF plain keys, others `<stem-slug>/` (put on the package's calc keys before mapCalcs).
  Status = `statusOf` over every PDF's links; within-PDF edges = each PDF's `buildState`; cross-PDF edges =
  `inferCalcEdges` on a combined view with calcs' `pages` AND `spans` emptied (calc-mapper reads regions from `spans`
  first, so emptying `pages` alone would not switch the page-reference rule off) and page numbers offset; impact =
  `propagate` over everything; export = one `buildExport` per PDF.
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
- The local test-blocking hook also matches `npm run check`. Run `node packages/mcp-server/bin/unloaded-mcp-server.mjs
  ... --check` directly instead.

## Verification (2026-11-15, this machine)

- `--check` on synthetic `model_rev1.ifc` + `calc_package.pdf`: 459 elements, 12 calcs, 800 links, confirmed 392 /
  review 63 / unmapped 4, 13 calc edges, 40 typical groups, 0 findings.
- Parity (real CLI over stdio, every tool, vs the engine packages called directly): one model + one PDF 77/77;
  rev 1 + rev 2 + one PDF 79/79; + `calc_supplement.pdf` 81/81; project file (as CI builds it) 80/80; project file with
  a seeded decision 79/79.
- vitest suites and tsc: written for CI, not run (hook-blocked locally).

## Next steps

- Real projects with more than one distinct PDF: the synthetic pair gives no cross-PDF edge; only the byte-built test
  fixture does. Confirm the cross-PDF edges read sensibly to an engineer.
- When calc-mapper extracts calc row values, pass them to move-impact as `facts` (estimates + health band).
