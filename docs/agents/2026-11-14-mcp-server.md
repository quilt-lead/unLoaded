# MCP server on the calc engine (`packages/mcp-server`)

- **Status:** in review. Carl merged an earlier snapshot (8352c0f) into prod and ported it to calc sets (6d0cd77,
  "PR from `cs/mcp-server`"). The later work on this branch (review rounds 1-4: decisions lock, per-origin ids,
  malformed-file handling) was merged with `origin/prod` (cc04749) on 2026-11-15 for a PR `issy/mcp-server` -> `prod`.
- **Branch:** `issy/mcp-server`, merged with `prod` (merge commit on this branch; prod's calc-set design won every
  multi-PDF conflict).
- **Owned files:** `packages/mcp-server/**`, the `@unloaded/mcp-server` entries in `package-lock.json`, the two MCP
  references in `packages/project-file/README.md` and `packages/project-file/src/index.ts`
- **Working files:** none in flight (everything committed and pushed).

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
  read-only; the `--decisions` file after it (ids shifted past the file's, for the engine only), so a server decision
  wins. **Ids shown to anyone are per origin** (`{origin: "decisions_file" | "project_file", id}`): get_element, link
  decisions, record_decision and the decisions resource all use it. The shifted ids exist only inside
  `Project.buildLog` (which also turns a bare key into `d1#key`, as prod's `log` getter did); `Project.decisionRef`
  maps back. Before round 1, get_element showed shifted ids and record_decision raw ones.
- **Decisions file = calc-mapper's decision log** (JSON array of `Decision`s with `id` and human `provenance`, the
  format `run-pipeline.ts --decisions` reads). New entries come from the engine's `addDecision` (`nextDecision`),
  entries are read back through `decisionFrom` (one without provenance is accepted and never rewritten). Still
  append-only, atomic temp + rename, re-read when it changes on disk, under the lock below. The calc-parser-format files (no `id`) the
  previous version wrote are refused with a message; that version was never merged, so no real files exist.
- **Concurrency (round 1):** every append holds `<realpath>.lock` (O_EXCL, `{pid, host, token, at}`), re-reads the
  file under it, writes temp next to the REAL file, fsync, rename, dir fsync. Stale = same host + dead pid, or older
  than 30 s; live = wait up to 10 s then a message naming the lock file. Without the lock, two processes appending
  15 each kept 15 of 30 (measured against HEAD 8352c0f); with it, 30 of 30. In-process, load / refresh / append share
  one queue (a refresh asked for during an append resolves after it). The snapshot after a write comes from the bytes
  written (fstat of the temp before rename), never a stat after the rename.
- **Concurrency (round 2, replaces the stale/break rules above):** `withFileLock` in decisions.ts. The holder
  heartbeats (futimes on its own fd, 1 s). Stale = same hostname + dead pid, OR the lock's observation key (dev, ino,
  mtime, size, content, read from one fd) unchanged for 5 s on the WAITER's monotonic clock; wait 15 s. No clock of
  another machine is compared. Every unlink of the lock (break AND release) runs under `<lock>.guard` (O_EXCL, held
  for one re-read + one unlink) and only if the lock still matches (key for a break, token for a release); the old
  move-aside + link-back is gone (no hard links needed). Every loop turn that does not acquire goes through one
  deadline + backoff point: an unreadable / unremovable lock fails with the lock path, never a busy loop (it used to
  wedge the in-process queue). Guard staleness is by observation only, same window as the lock (5 s; it was 3 s until
  review round 3 showed a breaker stalled 3 s inside the guard could unlink a live lock); the guard holds a token and
  its holder re-checks it immediately before unlinking the lock and before releasing the guard (a guard whose token
  write failed is removed only if the path is still the file it created). The guard's stale window IS the lock's
  `staleMs` (passed through `removeLock`; round 4: a fixed 5 s guard window meant short custom timings could never
  clear a crash-left guard). Residuals: any process frozen > staleMs holding the lock or the guard can have it taken;
  two processes clearing a crash-left guard at the same moment can both proceed, and then one can remove a lock taken
  meanwhile (the lock is matched when re-read, not at the unlink). `DecisionsFile.log` keeps its identity while the bytes are unchanged, so
  `Project.computedLog !== fileLog` means "really changed"; `recordDecisions` validates under the lock with
  `Project.effectiveOver` (effectiveDecisions only, no buildState) and recomputes after release: once, or twice when
  someone else had appended (the extra one gives an honest `link_before`). A decisions file without W_OK is refused.
- **Write tools do NOT pre-refresh** (server.ts `run(..., { write: true })`): the append re-reads under the lock, so
  `reloaded_external_changes` is true exactly when someone else appended since this server last read. It used to be
  always false over MCP because the wrapper refreshed first.
- **Malformed decisions file = a problem, not a crash:** `DecisionsFile.problem`; reads keep the last good log (or
  none), `source.decisions_warning` on every result, `project_summary.decisions.problem` + warnings, writes refused,
  file never overwritten, `--check` prints NOT READY and exits 1. A 0-byte / whitespace file is a problem too (it used
  to read as `[]`).
- **Decisions naming missing calc refs** warn loudly (`Project.checkDecisionKeys`, recomputed with the log, so a
  refresh updates them) with the likely cause: a doc id no loaded PDF has (PDF dropped or `--calcs` reordered), a
  document without that calc, and which other document has a calc with that key (a bare key reads as `d1#key`, so a
  hand-written bare key for a d2 calc lands here). Re-derived at the merge from the round-1 prefix warning: calc refs
  depend only on doc ids (`--calcs` order / the project file's documents), not on file stems, so the prefix-collision
  refusal and stem-based causes are gone.
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
- **Superseded at the prod merge: the per-PDF composition (round 1, e2211c2).** Before calc sets the server ran
  `mapCalcs` per PDF with `<stem>/` prefixes and composed cross-PDF edges itself; round 1 added one `designerOf` over
  every PDF (`calcEdgesOfPdf`, `crossReferenceEdges` with pages AND spans emptied, page offsets for cue words). All of
  it, its tests and the parity's `edgeProblems` invariants and generated supplement were dropped: on one calc set the
  engine does all three itself. Checked on the CROSS_* fixture (B-101 designed in both PDFs, "see page 2", "carried
  to"): one designer, the page reference stays in its PDF, the cue is read on its own page
  (`test/multipdf.test.ts`, "cross-PDF cases on the calc set").
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
- **Parity oracle must stay independent.** `scripts/mcp-parity.ts` is prod's calc-set rebuild: the reference is
  `buildCalcSet` + one `mapCalcs` / `buildState` called directly, compared for equality. Round 1's `edgeProblems`
  invariants and generated `xref_supplement.pdf` (needed while the server composed cross-PDF edges itself; the engine
  caps edge evidence at 6 items, which once hid a wrong extra designer) were dropped at the prod merge, because there
  is no server-side composition left to check. Don't put a copy of project.ts's code into it.
- The local test-blocking hook also matches `npm run check`. Run `node packages/mcp-server/bin/unloaded-mcp-server.mjs
  ... --check` directly instead.
- The source files came from Issy's machine with CRLF; the port rewrote the touched ones with LF (git normalises on
  commit, `core.autocrlf=true`). Harmless, but a whole-file diff in an editor is the line endings.
- `make-project-file.ts --doc d2 --calcs x.pdf` puts a PDF in a second calc document; without `--doc`, every PDF is a
  revision of `d1` (so only the last is mapped).

## Verification after merging prod into issy/mcp-server (2026-11-15, this machine, Node 22)

- Parity (real CLI over stdio): default (rev 1 + rev 2 + calc_package.pdf) 83/83; `--two-pdf` (calc_supplement.pdf
  again) 88/88; CI's project file 84/84; project file with two seeded decisions 84/84 (incl. "seeded decision: origin
  project_file, id 1"); project file with a second calc document (`--doc d2`) 89/89. New parity checks vs prod's:
  record_decision origin + id, external append kept AND reported (`reloaded_external_changes` true) with raw-byte
  prefix, decisions-not-applied warning only when warranted, search hit count by an independent window compare.
- `--check` rev 1 + rev 2 + both PDFs: OK, `[d1]` 12 calcs, `[d2]` 3 calcs, 843 live links; a malformed decisions
  file: NOT READY, exit 1. Two processes x 15 appends (lockcheck/check2.mjs): 30 entries, ids 1..30.
- vitest and tsc not run locally (hook-blocked); CI runs them.

## Verification of Carl's prod merge + calc-set port (6d0cd77; 2026-11-15, Windows, Node 24)

- vitest: 50/50 (6 files). Three assertions in `test/inputs.test.ts` assumed POSIX paths / a space before `units`;
  fixed (the suites had never run before this). `npm run typecheck` (repo-wide) clean.
- Parity (real CLI over stdio): CI's project file (rev 1 + calcs + rev 2) 81/81; same + a seeded decision 80/80;
  project file with a second calc document (`--doc d2`) 86/86; `--two-pdf` on the CLI 85/85 (CLI and project file
  give the same 843 links).
- `--check` on `model_rev1.ifc` + both synthetic PDFs: `[d1]` 12 calcs, `[d2]` 3 calcs, 883 live links, 13 calc edges,
  confirmed 392 / review 63 / unmapped 4.

## Verification, review rounds 2-4 + real-world testing (2026-11-15 overnight, this machine + CI; before the prod merge)

Per-PDF material below (stem prefixes, generated supplement, cross-PDF designer) is superseded by calc sets.

- Rounds (Opus, high, each on the previous fix delta): R2 6 findings (0 high; 2 medium lock defects: unbounded wait
  that wedged the server, move-aside/link-back break race; plus 30 s age breaking live holders, recompute under the
  lock, chmod 444 overwritten, undocumented FS assumptions); R3 3 (1 medium: a breaker stalled inside the guard could
  unlink a live lock, reproduced); R4 3 lows, no behavioural defect. Stopped on severity: R4 found wording and a
  latent custom-timing limit only. Commits 3198f02, f72f711 (TS narrowing, CI typecheck), 2300d3a, fea40ca.
- CI green on each fix head after f72f711 (mcp-server vitest 74 -> 76 -> 77 tests, none skipped).
- Parity after every wave: default 82/82, --two-pdf 85/85, project file 83/83, + seeded decision 82/82, one model +
  one PDF 80/80, rev1 + rev2 + main + supplement 82/82. Two processes x 15 appends: 30/30, ids 1..30.
- Synthetic seeds 1, 2, 3, 42, 1234: --check OK and parity 82/82 each. NOTE: `synth.generate --seed` only varies the
  scanned page's noise; the IFC is byte-identical across seeds, so seeds give no structural variety.
- Bad inputs (all fail with a clear message and non-zero exit, or warn): duplicate stem slug, same PDF twice,
  truncated PDF, LFS pointer, IFC passed as PDF and vice versa, missing model, malformed / wrong-shape / empty
  decisions (NOT READY), decisions dir missing, no --calcs, unknown flag, manifest with an unknown key; a manifest
  with spaces and relative paths, 3 PDFs with spaces, and an identical-content supplement (warned) all load.
- End to end: `claude mcp add` (local scope, scratch dir) -> Connected; two `claude -p` sessions called
  project_summary, search_elements, get_element, record_decision (confirm, undo), record_decisions (2 rejects),
  get_page_image (crop with the highlight), compare_revisions and the decisions resource; the decision persisted
  across a restart and the file is calc-mapper's log format with the right actor. Ergonomic nit: the client first
  passed `element` to get_element (its parameter is `id`; other tools use `global_id` / `element` / `column`).

## Verification, review round 1 (2026-11-15, this machine; per-PDF parts superseded by calc sets)

- Parity, all modes green: default (rev 1 + rev 2 + calc_package.pdf) 82/82; `--two-pdf` (generated supplement)
  85/85 with 2 cross-PDF edges; project file as CI builds it 83/83; project file with a seeded decision 82/82;
  `--model rev1.ifc --calcs calc_package.pdf` 80/80; rev 1 + rev 2 + calc_package + calc_supplement 82/82.
- Negative controls run against HEAD 8352c0f's src (temporary copy, deleted): the new `--two-pdf` parity fails 5
  checks (second designer, origin ids, reloaded_external_changes); two processes x 15 appends kept 15 of 30.
- vitest and tsc not run locally (hook-blocked); new tests were read against the old code to confirm they fail there.

## Verification before the merge (Issy, 2026-11-15, before review round 1)

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
- calc-mapper's own `addDecision` computes the next id with `Math.max(0, ...log.map(...))`: a RangeError past ~150k
  decisions. Engine package, not changed here.
- When calc-mapper extracts calc row values, pass them to move-impact as `facts` (estimates + health band).
