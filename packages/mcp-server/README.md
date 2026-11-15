# @unloaded/mcp-server

A local [MCP](https://modelcontextprotocol.io) server that lets an engineer's own AI (Claude Desktop, Claude Code,
Cursor, ...) query a structural project and record review decisions on it. A project is an IFC model mapped to one or
more calc-package PDFs, optionally with older model revisions to compare against, or a `*.calcgraph.json` project file
saved from the app.

- **Local only.** The server runs over stdio. It opens no port and makes no network request. It reads your files,
  answers your AI client, and writes only to the decisions file you name.
- **No AI inside.** Every answer comes from the unLoaded engine packages, called the way the app calls them:
  `@unloaded/ifc-parser` and `@unloaded/element-graph` (model, connectivity, load path), `@unloaded/calc-mapper` (calcs,
  links with role / weighted evidence / provenance, calc graph, typical groups, size-mismatch findings, review state,
  export, impact, revision diff, decision log), `@unloaded/project-file` (the app's project file) and
  `@unloaded/move-impact` (move / remove a column). The engine is deterministic. Every result carries a `source` block
  with the model and calc PDFs (file name and sha256), the element graph's sha256, the project file when there is one,
  the decisions file when it is relevant, and the engine version.

## Quick start

Node >= 22.18 is required. The packages ship TypeScript, which Node runs directly. From the repo root:

```sh
npm install
node packages/mcp-server/bin/unloaded-mcp-server.mjs \
  --model /abs/path/model.ifc --calcs /abs/path/calcs.pdf \
  --decisions /abs/path/decisions.json --actor "Jane Engineer" --check
```

`--check` loads everything, prints a summary to stderr and exits. The summary covers elements by kind, connections,
supports edges, model revisions, the calcs in each PDF, links by tier / role / band, confirmed / review / unmapped
counts, calc edges, typical groups, findings, decisions, the sha256 of each input, timings and warnings. It exits 0 on
success and non-zero on failure (including a decisions file that cannot be read: the report ends `NOT READY`). Run it once before you add the server to a client: a bad input then fails in your
terminal instead of silently inside the client.

On the synthetic package (generated, not committed: `cd tools/calcgraph-reference && uv run python -m synth.generate`):

```sh
node packages/mcp-server/bin/unloaded-mcp-server.mjs \
  --model tools/calcgraph-reference/data/synthetic/model_rev1.ifc \
  --calcs tools/calcgraph-reference/data/synthetic/calc_package.pdf --check
```

(`npm run check -w @unloaded/mcp-server` runs the same.)

## Client configuration

Use absolute paths everywhere. `node` must be Node >= 22.18. If your client cannot find the right `node`, put its
absolute path in `command` (find it with `which node`).

### Claude Desktop

Edit `claude_desktop_config.json` (macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`, Windows:
`%APPDATA%\Claude\claude_desktop_config.json`), then restart Claude Desktop:

```json
{
  "mcpServers": {
    "unloaded": {
      "command": "node",
      "args": [
        "/ABS/PATH/unLoaded/packages/mcp-server/bin/unloaded-mcp-server.mjs",
        "--model", "/ABS/PATH/project/model.ifc",
        "--calcs", "/ABS/PATH/project/calcs-main.pdf",
        "--calcs", "/ABS/PATH/project/calcs-supplement.pdf",
        "--decisions", "/ABS/PATH/project/decisions.json",
        "--actor", "Jane Engineer"
      ]
    }
  }
}
```

### Claude Code

```sh
claude mcp add unloaded -- node /ABS/PATH/unLoaded/packages/mcp-server/bin/unloaded-mcp-server.mjs \
  --model /ABS/PATH/project/model.ifc --calcs /ABS/PATH/project/calcs-main.pdf \
  --decisions /ABS/PATH/project/decisions.json --actor "Jane Engineer"
```

Add `--scope project` to share it through the repo's `.mcp.json`, or write `.mcp.json` yourself:

```json
{
  "mcpServers": {
    "unloaded": {
      "command": "node",
      "args": [
        "/ABS/PATH/unLoaded/packages/mcp-server/bin/unloaded-mcp-server.mjs",
        "--project", "/ABS/PATH/project/tower.calcgraph.json",
        "--decisions", "/ABS/PATH/project/decisions.json"
      ]
    }
  }
}
```

### Cursor

`.cursor/mcp.json` in the workspace (or `~/.cursor/mcp.json` for every workspace):

```json
{
  "mcpServers": {
    "unloaded": {
      "command": "node",
      "args": [
        "/ABS/PATH/unLoaded/packages/mcp-server/bin/unloaded-mcp-server.mjs",
        "--model", "/ABS/PATH/project/model.ifc",
        "--calcs", "/ABS/PATH/project/calcs-main.pdf",
        "--decisions", "/ABS/PATH/project/decisions.json"
      ]
    }
  }
}
```

## Inputs

```
unloaded-mcp-server --model <model> [--model <newer revision> ...] --calcs <main.pdf> [--calcs <more.pdf> ...]
                    [--decisions <decisions.json>] [--actor "<name>"] [--check] [--verbose]
unloaded-mcp-server --project <project.calcgraph.json | project.json> [--decisions <file>] [--actor "<name>"] [--check]
```

| Option | Meaning |
|---|---|
| `--model` | `.ifc` (parsed with web-ifc, then connectivity is inferred by `buildGraph`), a serialized element graph `.json` (`format: "unloaded.element-graph"`), or a ModelInput `.json`. The importer dispatches like the app's `src/loaders/parsers.ts`, and the graph is what the app stores (`ElementGraph.serialize()`, read back by calc-mapper's `parseGraph`; a graph not in metres is refused). **Repeat it** to add older revisions, oldest first: the **last** `--model` is the current model, the one the calcs are mapped onto (as in a project file, where the head is the highest revision id). `compare_revisions` diffs any two. |
| `--calcs` | A calc-package PDF. Repeat the flag for several. The first is the main package. |
| `--project` | Either the app's saved project file (`*.calcgraph.json`, format `unloaded.calc-graph-project`), or a manifest `{"model": "..." \| ["older", "current"], "calcs": ["...", ...], "decisions": "...", "actor": "..."}` with paths relative to it. `--decisions` and `--actor` on the command line override the manifest's. |
| `--decisions` | The review decisions file. Optional. It is created on the first recorded decision. Without it the server is read-only. |
| `--actor` | Name recorded on decisions. Default: your OS user name. |
| `--check` | Load, print the summary, exit. |
| `--verbose` | Also print web-ifc's parser messages and pdf.js warnings. Both are counted and hidden by default. |

Everything is validated before the server starts. The checks catch a missing file, a PDF passed as the model, a file
that is not IFC or PDF, a Git LFS pointer in place of a PDF, the same model or PDF given twice, a project file passed as
`--model`, a manifest with the wrong shape and a missing directory for the decisions file. A decisions file that cannot
be read (not JSON, a bad entry, empty) does not stop the server: see [The decisions file](#the-decisions-file).
A PDF with no text layer (scanned) produces a warning: the engine never maps those pages, so OCR the PDF first.

### A project file (`*.calcgraph.json`)

The app's **Save project** writes one file through `@unloaded/project-file`; the server reads it through the same
package. It holds every revision's original file, each model revision's element graph, each calc revision's
extraction and the app's decision log.

- **Model revisions:** all of them, oldest first. The head (highest id) is the current model. Revision numbers in
  `project_summary.model_revisions` and `compare_revisions` are the file's revision ids.
- **Calc package:** the head calc revision (calc revisions are versions of one package; older ones are listed in a
  warning, not mapped). Its stored extraction is used when `storedExtractionFor` (the app's rule) accepts it for the
  PDF in the file; otherwise the PDF is re-extracted, and `calc_pdfs[].extraction` / `extraction_note` say why.
- **Decisions:** the file's decision log is applied first (read-only: the project file is never written), then the
  `--decisions` file, so a later decision recorded through the server wins.

### Several calc PDFs: the calc-key rule

Calc PDFs are either one calc per file or one large package, and a project can have several. calc-mapper maps **one
calc package (one PDF) per run**: `packageSha256` refuses pages from two documents, and the app keeps one head calc
package. So multiple PDFs are not native to the engine. The server runs `mapCalcs` **per PDF**, and page numbers always
belong to one PDF: a "page 7" reference never resolves into another file. Calc keys must be unique across the set and
stable for the decisions file:

- The **first** `--calcs` PDF keeps calc-mapper's plain keys (`floor-beam-girder-design-ram-structural-system`). A
  single-PDF project is therefore exactly the engine's output.
- Every **further** PDF's keys are prefixed with a slug of its file stem: `Supplement A.pdf` gives
  `supplement-a/connection-design-check`. The prefix is put on the package's calc keys before `mapCalcs`, so every
  record the engine makes carries it. If two PDFs give the same prefix, the server refuses to start and asks you to
  rename one.

Keep the order of `--calcs` stable. Swapping the main PDF changes which keys are plain.

Across PDFs, everything is still an engine call:

- **Element status:** calc-mapper's `statusOf` over the element's links from every PDF (design links only).
- **One designer per element.** A cross-reference edge runs from the calc that designs an element to a calc that
  mentions it. That designer is calc-mapper's `designerOf` over the effective links of **every** PDF, for every edge,
  within a PDF or across two. An element designed in two PDFs therefore still has one designer (design role first,
  then the higher tier confidence, then the smaller calc key), and a mention of it gets one fed-by edge.
- **Calc edges within one PDF:** `inferCalcEdges` on that PDF's calcs, pages and effective links, with the other PDFs'
  links passed in only as designer candidates (their page nulled, so none is read as a mention on this PDF's pages).
  Edges whose two calcs are both in that PDF are kept. Page-reference edges always come from here: the page-reference
  rule only ever sees one PDF, so "page 7" is that PDF's page 7. With one PDF this is exactly `buildState`'s call.
- **Calc edges between PDFs:** the cross-reference rule only. The server calls `inferCalcEdges` on a combined view:
  every calc with its pages and regions emptied (this switches off the page-reference rule), every page with its page
  number offset so numbers are unique (a mention's cue word, such as "carried **to**", is read on its own PDF's page),
  and every effective link. It keeps only edges whose two calcs are in different PDFs, and maps evidence page numbers
  back to their own PDF. Example: a supplement calc that takes a beam's reactions from the main package gets a
  `main beam calc -> supplement calc` edge with the mention as evidence.
- **Impact:** calc-mapper's `propagate` over the load path, every effective link and every calc edge.
- **Export:** one `buildExport` per PDF (each is one engine run).

## Tools

| Tool | What it returns |
|---|---|
| `project_summary` | Model counts (kinds, categories, storeys, connections, edges by kind), model revisions, each PDF (pages, calcs, prefix, pages with no text layer, extraction), every calc, links by tier / role / band / review status, status counts, calc edges (within / across PDFs), typical groups, findings, decisions, warnings. |
| `search_elements` | Elements filtered by text query, mark, name, kind, category, profile, storey, status or linked calc; paginated. |
| `get_element` | Node data, status, links sorted by confidence with every engine field (tier, conf, band, role, reasons = weighted evidence, caveats, rule, page, token, snippet, rects, provenance, review provenance, PDF, decision who / when / note), typical groups and their group links, findings, decisions, connectivity with edge evidence, one hop of the load path. |
| `list_calcs` | Calcs across PDFs, filtered by PDF, category, software or text; paginated. |
| `get_calc` | One calc: PDF, pages, page regions, title box, provenance, linked elements with tier / role / band / caveats, group links, findings, calc edges in and out with evidence, and optionally its page text with the ranges that belong to it, paginated by page. |
| `search_calc_text` | Full-text search over every page of every PDF. Each hit has its pdf, page, calc (the calc whose region holds the hit; null when none or more than one does), span (offsets in the page text as extracted), snippet and rects. |
| `trace_load_path` | Multi-hop `loadPathDown` / `loadPathUp` with depth and `max_depth`, each element's best calc, plus the supports edges walked (with gap). |
| `calc_dependencies` | The calc graph, or one calc's neighbourhood to a depth, with rules, evidence and provenance. Cross-PDF edges are flagged. |
| `impact_of_change` | The engine's impact (change / remove): removed and hit elements with waves and reasons, stale calcs with reasons and PDFs, provenance. |
| `review_status` | Status counts, elements needing review, unmapped elements (with loads-only links), unreviewed links under a confidence threshold (default 0.75, the high band); paginated. |
| `list_findings` | Size-mismatch findings (model size, calc size, page, span, rects, snippet, provenance) with the element and calc, minus those on rejected links; filter by calc, element or PDF. |
| `list_typical_groups` | Typical groups (`group:<category>:<storey>:<profile>`, members with marks) and the group links of size-only calcs; filter by kind, storey, profile, linked only. |
| `compare_revisions` | `diffGraphs` between two model revisions (removed / added / changed elements with per-field before / after, load-path edges removed / added), plus the calcs linked to an element in the diff. Default: the current model against the revision before it. |
| `move_column` | `@unloaded/move-impact` on the current model and the reviewed links: move a column by dx / dy metres or remove it. Elements on the path with reasons, the geometric screen, re-framing, clashes, notes, assumptions, stale calcs. No calc values are read yet, so no utilisation estimates or health band. |
| `export_mapping` | calc-mapper's `buildExport`, one report per calc PDF (elements pageable). |
| `get_page_image` | A PDF page as PNG (MCP image content). It can highlight a link's words, a text span (`rectsForSpan`), calc-edge evidence or raw rects, and crop to the evidence with padding. |
| `record_decision` | **Writes.** Appends one decision (confirm / reject / manual / undo) to the decisions file. Returns the decision (`origin: "decisions_file"` and its id in the file), the link and status before / after, and `reloaded_external_changes`. |
| `record_decisions` | **Writes.** Batch version, all or nothing. |

Read tools are annotated `readOnlyHint: true`. The two write tools are `readOnlyHint: false`, `idempotentHint: false`.
Resources: `unloaded://project/summary` and `unloaded://project/decisions`.

Every result's `source` names the calc PDFs whose calcs it returns or whose sha256 its provenance cites (impact and
`move_column` rest on every PDF's links, so they name all of them). When the decisions file cannot be read, every
`source` also carries `decisions_warning`.

Elements can be named by GlobalId or by a mark that names exactly one element. The write tools require the exact
GlobalId; if you pass a mark, the error message names its GlobalId.

## The decisions file

calc-mapper's decision log: a JSON array of `Decision`s, oldest first. It is the format calc-mapper's own CLI reads
(`packages/calc-mapper/scripts/run-pipeline.ts --decisions`). Each entry is made by the engine's `addDecision`:

```json
[
  {
    "id": 1,
    "global_id": "0CvnE_Gs1IsA$admCFuTp2",
    "calc_key": "column-design-ram-structural-system",
    "action": "confirm",
    "actor": "Jane Engineer",
    "note": "checked p.13",
    "at": "2026-11-14T15:02:11.512Z",
    "model_rev": "model.ifc",
    "calc_rev": "calcs-main.pdf",
    "provenance": {
      "producer": "calc-mapper@0.1.0/decisions",
      "rule": "decision.confirm",
      "method": "human",
      "inputs": ["<sha256 of the element graph>", "<sha256 of the calc PDF>"],
      "actor": "Jane Engineer",
      "at": "2026-11-14T15:02:11.512Z"
    }
  }
]
```

- `action` is one of: `confirm` or `reject` (an automatic link must exist), `manual` (link any element to any calc
  by hand), `undo` (clear the pair back to its automatic state; the pair must have a decision in effect).
- `id` orders the log: the latest decision per (GlobalId, calc key) wins (`effectiveDecisions`), and `undo` clears the
  pair: the link goes back to its automatic state, a hand link is removed, and earlier decisions on the pair are NOT
  restored (confirm, then reject, then undo leaves the link unreviewed, not confirmed). Decisions are keyed by GlobalId
  and calc key, not by revision, so they carry forward to a new model or calc revision as long as both still exist.
  Decisions naming something that is not in the current project are kept, not applied, and reported as a warning in
  `project_summary` and `--check`. A missing calc key gets its likely cause: a non-main PDF's prefix that no loaded PDF
  has (renamed or dropped supplement), a PDF that no longer has that calc (calcs renamed, split or reordered), or a main
  PDF without it (the `--calcs` order changed). Keep the `--calcs` order and the file names stable.
- **Decision ids are per origin.** Every tool and the `unloaded://project/decisions` resource name a decision by
  `origin` + `id`: `"decisions_file"` ids are the ids in this file (what `record_decision` returns), and
  `"project_file"` ids number a project file's own decision log 1..n in file order. The engine is handed one log with
  this file's ids shifted past the project file's (an id only orders decisions), but no tool shows a shifted id.
- `model_rev` / `calc_rev` record what the decision was made against: file names, or the revision ids with a project
  file. `provenance.inputs` are the sha256 of the element graph and of the calc's PDF.
- An entry without `provenance` (written by hand or by an older tool) is accepted: the engine states it from the
  entry's own fields (`decisionFrom`). The server never adds it to an existing entry.
- **Append-only.** The server never rewrites or drops an entry. Read tools re-read the file whenever it changed on
  disk (size / mtime, then sha256), so a colleague's or a script's edits show up in the next answer. A batch is
  validated as a whole: one bad entry means nothing is written.
- **Several writers.** Two servers can share one file (Claude Desktop and Claude Code on the same `--decisions`).
  Every append takes an exclusive lock, `<file>.lock` next to the real file (created with `O_EXCL`; it holds the
  writer's pid, host, a token and the time). Under the lock it re-reads the file, validates the batch against what is
  really there, numbers it after the last id in the file, writes the whole array to a temp file next to the real file,
  fsyncs it, renames it over the original (atomic on POSIX file systems) and fsyncs the directory. The holder refreshes
  the lock's mtime every second while it holds it. A lock is broken when its writer is on this machine (same hostname)
  and no longer running, or when nothing about it has changed for 5 s as watched by the waiting server on its own
  clock (clocks of different machines are never compared). A live lock is waited for up to 15 s, then the write fails
  with a message naming the lock file; so does a lock file that cannot be read or removed. Removing a lock (breaking a
  stale one, or releasing one's own) happens under a second short-lived file, `<file>.lock.guard`, and only while that
  guard is still the server's own, so a server removes only the exact lock it judged stale, not one another writer has
  just taken (short of the residual below). `reloaded_external_changes` is
  true when the file held decisions this server had not seen; they are kept. Within one server, reads and appends go
  through one queue, so a read can never land after an append and roll the answer back.
- **What the file system has to provide.** On a local disk (APFS, ext4, NTFS) the above holds. On a network file
  system, `O_EXCL` creation must be atomic: true on NFSv3 and later and on SMB, not on NFSv2, and not on folder-sync
  tools (Dropbox, OneDrive, iCloud Drive), which can lose an append. Two machines with the same hostname are taken
  to be one machine. No hard links are needed. Not prevented: staleness is judged by time, so a server that freezes
  for more than 5 s (suspended process, long pause) while holding the lock or the guard can lose it to another writer
  and, in a narrow window, write alongside it; two servers removing a guard file left by a crash at the same moment
  can both proceed. A crash can leave `<file>.lock`, `<file>.lock.guard` or a `.<file>.<pid>.<hex>.tmp`
  file: all are harmless (the lock and guard are cleared automatically; the temp file is never read and can be
  deleted).
- **Writes replace the file** (temp file + rename). The file's mode is kept, but its owner can change (to the user
  the server runs as), a hard link to it stops seeing new entries, and ACLs and extended attributes are not carried
  over. A file the server may not write (for example `chmod 444`) is refused with a message and left untouched, even
  though its directory would allow the rename.
- **A symlinked `--decisions` path** is resolved once: the real file is read, locked and written, so the link stays a
  link. The file's mode is kept.
- **A file that cannot be read** (not JSON, a bad entry, an empty or whitespace-only file) does not stop the server.
  Answers use the last good copy of the log (none, if it was never readable), every result's `source` carries
  `decisions_warning`, `project_summary` lists it under `warnings`, and `record_decision` is refused until the file is
  fixed. The server never overwrites it. `--check` reports it as `NOT READY` and exits 1. An empty file is not read as
  an empty log: write `[]` into it, or delete it and the server creates it on the first decision.
- Writes go to this file only. The IFC, the PDFs and a project file are never modified.

## Architecture

```
bin/unloaded-mcp-server.mjs   Node version check, console -> stderr, then src/cli.ts
src/cli.ts                    arguments -> loadProject -> --check report or stdio server
src/inputs.ts                 CLI + manifest parsing and up-front validation
src/engine.ts                 THE ENGINE BOUNDARY (see below)
src/project.ts                the loaded project: model revisions, per-PDF mapping, key prefixes, cross-PDF edges, decisions applied
src/decisions.ts              the decisions file: validation, change detection, cross-process lock, atomic append
src/tools.ts                  tool bodies (lookups, filters, pagination over engine output)
src/server.ts                 MCP registration: schemas, descriptions, annotations, resources
src/pageImage.ts              page PNG rendering (pdf.js legacy + @napi-rs/canvas)
src/check.ts                  the --check report
scripts/makeProjectFile.ts    a project file in the app's format without the browser (tooling, CI, tests)
scripts/make-project-file.ts  its CLI
scripts/minimalPdf.ts         a minimal PDF written byte by byte (vitest fixtures, parity --two-pdf)
scripts/mcp-parity.ts         end-to-end parity over stdio
```

**Engine boundary.** `src/engine.ts` is the only module in `src/` that imports an `@unloaded/*` package
(`ifc-parser`, `element-graph`, `calc-mapper`, `project-file`, `move-impact`). It exposes a narrow interface:
`loadModel` / `modelFromRevision` (a read-only `Model` with the serialized graph calc-mapper reads, its sha256, the
element rows, load path, connectivity and the element-graph queries), `readCalcPackage`, `storedCalcPackage`,
`mapCalcs`, `buildState`, `buildExport`, `calcEdgesOfPdf`, `crossReferenceEdges`, `designerOf`, `calcRegions`,
`statusOf`, `rectsForSpan`, `propagateImpact`,
`diffGraphs`, `moveColumn`, `nextDecision`, `decisionFrom`, `effectiveDecisions`, the project-file readers
(`isProjectFile`, `parseProjectFile`, `headRevision`, `revisionBytes`, `projectFileDecisions`), `ENGINE_VERSION`,
`ENGINE_PRODUCERS`, `CONFIDENCE_BANDS` and `DECISION_ACTIONS`. The data types the rest of the server uses are
re-exported from it. Each function is a direct engine call; the three thin compositions (`calcEdgesOfPdf`,
`crossReferenceEdges`, `projectFileDecisions`) are documented in the file. A test (`test/server.test.ts`, "engine boundary") fails if any
other file in `src/` imports an engine package, and checks `package.json` declares exactly what `engine.ts` imports.

## Not included, and why

- **Calc revisions as a history.** A project file's older calc revisions are not mapped: the app shows the head, and
  calc-mapper has no calc-package diff. Pass a different PDF version with `--calcs` to look at it.
- **Utilisation estimates and the health band in `move_column`.** move-impact derives them from calc facts (the values
  a calc row prints); calc-mapper does not extract row values yet, so they would have to be invented.
- **Legacy `{nodes, links}` BIM JSON models.** They have no GlobalIds, so calcs and decisions cannot be keyed to their
  elements. The server refuses them with a message.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `needs Node >= 22.18` | Install a newer Node, or point `command` at it by absolute path. |
| The client shows the server as failed with no detail | Run the same command with `--check` in a terminal. Every input error is printed there. |
| `--model ... is a PDF` / `--calcs ... is not a PDF` | The model goes in `--model`, calc packages go in `--calcs`. |
| `is a Git LFS pointer, not the PDF` | The repo keeps PDFs in Git LFS. Run `git lfs install && git lfs pull`. |
| `no "ISO-10303-21" STEP header` | The file is not an IFC, or it is `.ifczip`. Unzip it. |
| `legacy BIM graph JSON` | Use the source `.ifc`, or an element graph saved from the app. |
| `is a calc-graph project file: pass it with --project` | A `*.calcgraph.json` goes in `--project`. |
| `graph.meta.units must be "m"` | The element graph is not in metres; rebuild it from the IFC. |
| `same calc-key prefix` | Two non-main PDFs share a file stem. Rename one. |
| `has NO text layer` warning / calcs marked scanned | The PDF pages are images. OCR them, then run again. |
| `decisions_warning` / `the decisions file cannot be read: ...` | Fix what it names (`must be a JSON array`, `entry N: ...`, `is not valid JSON`, `is empty`), or point `--decisions` at a new file. Answers meanwhile use the last good log; writes are refused. |
| `is locked by another writer` | Another server or tool is writing the decisions file. If none is, delete the `.lock` file it names. |
| `cannot be read` / `cannot be removed` (lock file) | The `.lock` path is not a regular file or its directory is not writable. Fix or delete the path it names. |
| `is not writable by this server` | The decisions file's permissions forbid writing it. Make it writable (`chmod u+w`) to record decisions. |
| `name N calc key(s) that are not in this project` | Decisions recorded against PDFs that are not loaded, or loaded in another order / under another name. The warning names the likely cause; restore the `--calcs` order and names. |
| `This server is read-only` from `record_decision` | Add `--decisions /abs/path/decisions.json` to the args and restart the server. |
| `no automatic link ... use manual` | `confirm` and `reject` act on engine links only. Use `manual` to link by hand. |
| `compare needs two model revisions` | Repeat `--model` with the older revision first, or use a project file with several. |
| Hundreds of `[WEB-IFC]` lines | Hidden by default. `--verbose` shows them. They are web-ifc parser notices and harmless. |

## Development

```sh
npm run typecheck -w @unloaded/mcp-server     # tsc
npm test -w @unloaded/mcp-server              # vitest: tools vs the engine, multi-PDF, project file, decisions, inputs, MCP surface

# end-to-end parity: spawn the real CLI over stdio, call every tool, compare with the engine packages called directly
node packages/mcp-server/scripts/mcp-parity.ts                 # synthetic: model rev 1 + rev 2 (current), calc_package.pdf
node packages/mcp-server/scripts/mcp-parity.ts --two-pdf       # + a supplement generated on the synthetic marks (cross-PDF edges, one designer)
node packages/mcp-server/scripts/mcp-parity.ts --model a.ifc [--model b.ifc] --calcs x.pdf [--calcs y.pdf]

# a project file in the app's format (no browser), then parity on it (what CI runs)
node tools/calcgraph-reference/scripts/build_graph.mjs \
  tools/calcgraph-reference/data/synthetic/model_rev1.ifc tools/calcgraph-reference/data/synthetic/model_rev1.graph.json \
  tools/calcgraph-reference/data/synthetic/model_rev2.ifc tools/calcgraph-reference/data/synthetic/model_rev2.graph.json
node packages/mcp-server/scripts/make-project-file.ts --out /tmp/synthetic.calcgraph.json --name "Synthetic" \
  --model tools/calcgraph-reference/data/synthetic/model_rev1.graph.json \
  --calcs tools/calcgraph-reference/data/synthetic/calc_package.pdf \
  --model tools/calcgraph-reference/data/synthetic/model_rev2.graph.json
node packages/mcp-server/scripts/mcp-parity.ts /tmp/synthetic.calcgraph.json
```

The vitest suites use committed fixtures only: `test/fixtures.ts` writes two element-graph revisions and two small calc
PDFs byte by byte (the supplement cross-references a beam the main package designs), so nothing generated is needed.
The parity script runs on the synthetic package (`cd tools/calcgraph-reference && uv run python -m synth.generate`;
its output is gitignored). It writes decisions to a temp file only, and checks that the inputs' sha256 did not change.
Its oracle is the engine called directly and never a copy of the server's multi-PDF composition: with one PDF every
result must equal the engine's; with several, the calc edges are checked against invariants (each PDF's page-reference
edges are the engine's on that PDF alone, one designer per element, every mention has its edge in the direction the
engine gives it on its own PDF, evidence pages within their own PDF). It also checks the decisions file end to end: an
append by someone else between two `record_decision` calls is kept and reported, and earlier entries stay byte for byte.
CI (`.github/workflows/ci.yml`) runs the project-file parity in the `tooling` job and every workspace's typecheck and
vitest in the `frontend` job.
