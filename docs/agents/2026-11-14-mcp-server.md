# MCP server on the calc engine (`packages/mcp-server`)

- **Status:** in review (merged with prod and ported to calc sets on 2026-11-15; PR from `cs/mcp-server` into `prod`)
- **Branch:** `issy/mcp-server` (Issy's work, on 7a970d7), merged with `prod` (bd02afd) on `cs/mcp-server`.
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
  All model revisions load; the calcs mapped are the app's calc set: every live document at its head revision
  (`documentHeads`; v1 files read as one document `d1`). Stored extraction via `storedExtractionFor`, else re-extracted. The file's decision log is applied first,
  read-only; the `--decisions` file after it (ids shifted past the file's), so a server decision wins.
- **Decisions file = calc-mapper's decision log** (JSON array of `Decision`s with `id` and human `provenance`, the
  format `run-pipeline.ts --decisions` reads). New entries come from the engine's `addDecision` (`nextDecision`),
  entries are read back through `decisionFrom` (one without provenance is accepted and never rewritten). Still
  append-only, atomic temp + rename, re-read when it changes on disk. The calc-parser-format files (no `id`) the
  previous version wrote are refused with a message; that version was never merged, so no real files exist.
- **Multi-PDF = the calc set (2026-11-15, replaces the per-PDF design).** When Issy wrote the server, calc-mapper
  mapped one package per run, so it ran `mapCalcs` per PDF with `<stem>/` key prefixes and composed cross-PDF edges
  itself. Prod has since added calc sets (`2026-11-14-phase2-calc-sets.md`): `buildCalcSet` maps many PDFs as one,
  and the app and project file v2 key calcs as calc refs `"<docId>#<key>"`. Keeping the per-PDF scheme would have
  made the server's keys, links and decision log differ from the app's, so `src/project.ts` now builds ONE calc set
  (doc ids `d1, d2, ...` in `--calcs` order, or the project file's documents), runs `mapCalcs` / `buildState` once on
  it, and keys every calc by its calc ref (a bare key resolves when one PDF has it; a bare key in a decisions file
  reads as `d1#key`, as in the app). The engine numbers pages across the set; `Project` converts every page in
  links, link evidence, group links, findings and calc-edge evidence back to the record's own PDF (`- page_offset`),
  so the tool contract "pages are pages of the named PDF" held and the tools barely changed. `export_mapping` is the
  one exception: it returns the app's `buildExport` on the set unchanged (set pages) plus `calc_documents` offsets.
  `crossReferenceEdges` and `stemSlug` are gone. The same PDF given twice is mapped once (warning), as the app does.
- **Tools added vs the calc-parser version:** `list_findings`, `list_typical_groups`, `compare_revisions`,
  `move_column`. Links now carry role / band / reasons / caveats / provenance; status counts design links only (high
  band 0.75, not 0.8). `export_mapping` is `buildExport` on the calc set (was calc-parser `exportMapping`).
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
- The source files came from Issy's machine with CRLF; the port rewrote the touched ones with LF (git normalises on
  commit, `core.autocrlf=true`). Harmless, but a whole-file diff in an editor is the line endings.
- `make-project-file.ts --doc d2 --calcs x.pdf` puts a PDF in a second calc document; without `--doc`, every PDF is a
  revision of `d1` (so only the last is mapped).

## Verification after the prod merge + calc-set port (2026-11-15, Windows, Node 24)

- vitest: 50/50 (6 files). Three assertions in `test/inputs.test.ts` assumed POSIX paths / a space before `units`;
  fixed (the suites had never run before this). `npm run typecheck` (repo-wide) clean.
- Parity (real CLI over stdio): CI's project file (rev 1 + calcs + rev 2) 81/81; same + a seeded decision 80/80;
  project file with a second calc document (`--doc d2`) 86/86; `--two-pdf` on the CLI 85/85 (CLI and project file
  give the same 843 links).
- `--check` on `model_rev1.ifc` + both synthetic PDFs: `[d1]` 12 calcs, `[d2]` 3 calcs, 883 live links, 13 calc edges,
  confirmed 392 / review 63 / unmapped 4.

## Verification before the merge (Issy, 2026-11-15)

- `--check` on synthetic `model_rev1.ifc` + `calc_package.pdf`: 459 elements, 12 calcs, 800 links, confirmed 392 /
  review 63 / unmapped 4, 13 calc edges, 40 typical groups, 0 findings.
- Parity (real CLI over stdio, every tool, vs the engine packages called directly): one model + one PDF 77/77;
  rev 1 + rev 2 + one PDF 79/79; + `calc_supplement.pdf` 81/81; project file (as CI builds it) 80/80; project file with
  a seeded decision 79/79.
- vitest suites and tsc: written for CI, not run (hook-blocked locally).

## Next steps

- Real projects with more than one distinct PDF: the synthetic pair gives no cross-PDF edge; only the byte-built test
  fixture does. Confirm the cross-PDF edges read sensibly to an engineer.
- Calc revision diff (`diffCalcSets`) and older calc revisions are not exposed as tools yet; the app has them.
- When calc-mapper extracts calc row values, pass them to move-impact as `facts` (estimates + health band).
