# @unloaded/mcp-server

A local [MCP](https://modelcontextprotocol.io) server that lets an engineer's own AI (Claude Desktop, Claude Code,
Cursor, ...) query a structural project and record review decisions on it. A project is an IFC model mapped to one or
more calc-package PDFs.

- **Local only.** The server runs over stdio. It opens no port and makes no network request. It reads your files,
  answers your AI client, and writes only to the decisions file you name.
- **No AI inside.** Every answer comes from the unLoaded engine packages on prod, called the way the app calls them:
  `@unloaded/ifc-parser`, `@unloaded/element-graph` (connectivity and load path) and `@unloaded/calc-parser` (calcs,
  links, calc graph, impact, review). The engine is deterministic. Every result carries a `source` block with the
  model and calc PDFs (file name and sha256), the decisions file when it is relevant, and the engine version.

## Quick start

Node >= 22.18 is required. The packages ship TypeScript, which Node runs directly. From the repo root:

```sh
npm install
node packages/mcp-server/bin/unloaded-mcp-server.mjs \
  --model /abs/path/model.ifc --calcs /abs/path/calcs.pdf \
  --decisions /abs/path/decisions.json --actor "Jane Engineer" --check
```

`--check` loads everything, prints a summary to stderr and exits. The summary covers elements by kind, connections,
supports edges, the calcs in each PDF, links by tier, confirmed / review / unmapped counts, calc edges, decisions, the
sha256 of each input, timings and warnings. It exits 0 on success and non-zero on failure. Run it once before you add
the server to a client: a bad input then fails in your terminal instead of silently inside the client.

On the repo's fixture:

```sh
npm run check -w @unloaded/mcp-server
```

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
        "--project", "/ABS/PATH/project/project.json"
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
unloaded-mcp-server --model <model> --calcs <main.pdf> [--calcs <more.pdf> ...]
                    [--decisions <decisions.json>] [--actor "<name>"] [--check] [--verbose]
unloaded-mcp-server --project <project.json> [--decisions <file>] [--actor "<name>"] [--check]
```

| Option | Meaning |
|---|---|
| `--model` | `.ifc` (parsed with web-ifc, then connectivity is inferred by `buildGraph`), a serialized element graph `.json` (`format: "unloaded.element-graph"`), or a ModelInput `.json`. The importer dispatches exactly like the app's `src/loaders/parsers.ts`. |
| `--calcs` | A calc-package PDF. Repeat the flag for several. The first is the main package. |
| `--decisions` | The review decisions file. Optional. It is created on the first recorded decision. Without it the server is read-only. |
| `--actor` | Name recorded on decisions. Default: your OS user name. |
| `--project` | A manifest `{"model": "...", "calcs": ["...", ...], "decisions": "...", "actor": "..."}`, with paths relative to the manifest. `--decisions` and `--actor` on the command line override it. |
| `--check` | Load, print the summary, exit. |
| `--verbose` | Also print web-ifc's parser messages and pdf.js warnings. Both are counted and hidden by default. |

Everything is validated before the server starts. The checks catch a missing file, a PDF passed as the model, a file
that is not IFC or PDF, the same PDF given twice, a manifest with the wrong shape, a malformed decisions file and a
missing directory for the decisions file. A PDF with no text layer (scanned) produces a warning: the engine never maps
those pages, so OCR the PDF first.

### Several calc PDFs: the calc-key rule

Calc PDFs are either one calc per file or one large package, and a project can have several. The engine runs
`mapCalcs` **per PDF**, so page numbers always belong to one PDF: a "page 7" reference never resolves into another
file. Calc keys must be unique across the set and stable for the decisions file:

- The **first** `--calcs` PDF keeps calc-parser's plain keys (`floor-beam-girder-design-ram-structural-system`). A
  single-PDF decisions file is therefore exactly calc-parser's format.
- Every **further** PDF's keys are prefixed with a slug of its file stem: `Supplement A.pdf` gives
  `supplement-a/floor-beam-girder-design-ram-structural-system`. If two PDFs give the same prefix, the server refuses
  to start and asks you to rename one.

Keep the order of `--calcs` stable. Swapping the main PDF changes which keys are plain.

Every calc records its source PDF (name and sha256) and its page numbers within that PDF.

**Calc edges across PDFs.** Edges within one PDF are calc-parser's `inferCalcDeps` on that PDF alone (page references
and cross-references). Edges between PDFs come from the engine's cross-reference rule only. The server calls
`inferCalcDeps` on a combined view: every calc, every page with its page number offset so numbers are unique, and every
link. Each calc is passed with no pages, which switches off the page-reference rule. It keeps only edges whose two calcs
are in different PDFs, and maps evidence page numbers back to their own PDF. Example: a supplement calc that mentions a
beam designed in the main package gets a `main calc -> supplement calc` edge with the mention as evidence. No new
matching rule is involved. For this rule the "designer" of an element is its strongest non-xref link across all PDFs,
so when several PDFs design the same element, the cross-PDF edge points at the strongest one. Like the Python
reference, calc edges are recomputed from the *effective* links: a rejected cross-reference stops feeding an edge, and a
manual link counts as a designer.

## Tools

| Tool | What it returns |
|---|---|
| `project_summary` | Model counts (kinds, categories, storeys, connections, edges by kind), each PDF (pages, calcs, prefix, pages with no text layer), every calc, links by tier and review status, status counts, calc edges (within / across PDFs), decisions file, warnings. |
| `search_elements` | Elements filtered by text query, mark, name, kind, category, profile, storey, status or linked calc; paginated. |
| `get_element` | Node data, status, links sorted by confidence (tier, conf, rule, page, token, snippet, rects, PDF, decision who / when / note), connectivity with edge evidence, one hop of the load path. |
| `list_calcs` | Calcs across PDFs, filtered by PDF, category, software or text; paginated. |
| `get_calc` | One calc: PDF, pages, linked elements with tiers, calc edges in and out with evidence, and optionally its page text, paginated by page. |
| `search_calc_text` | Full-text search over every page of every PDF. Each hit has its pdf, page, calc, span, snippet and rects. |
| `trace_load_path` | Multi-hop `loadPathDown` / `loadPathUp` with depth and `max_depth`, plus the supports edges walked. |
| `calc_dependencies` | The calc graph, or one calc's neighbourhood to a depth, with rules and evidence. Cross-PDF edges are flagged. |
| `impact_of_change` | `propagateImpact` (change / remove): removed and hit elements with waves and reasons, and stale calcs with reasons and PDFs. |
| `review_status` | Status counts, elements needing review, unmapped elements, unreviewed links under a confidence threshold; paginated. |
| `export_mapping` | calc-parser's `exportMapping` report (elements pageable). |
| `get_page_image` | A PDF page as PNG (MCP image content). It can highlight a link's words, a text span (`rectsForSpan`), calc-edge evidence or raw rects, and crop to the evidence with padding. |
| `record_decision` | **Writes.** Appends one decision (confirm / reject / manual / undo) to the decisions file. |
| `record_decisions` | **Writes.** Batch version, all or nothing. |

Read tools are annotated `readOnlyHint: true`. The two write tools are `readOnlyHint: false`, `idempotentHint: false`.
Resources: `unloaded://project/summary` and `unloaded://project/decisions`.

Elements can be named by GlobalId or by a mark that names exactly one element. The write tools require the exact
GlobalId; if you pass a mark, the error message names its GlobalId.

## The decisions file

A JSON array of calc-parser `Decision`s, oldest first:

```json
[
  {
    "global_id": "0CvnE_Gs1IsA$admCFuTp2",
    "calc_key": "column-design-ram-structural-system",
    "action": "confirm",
    "at": "2026-11-14T15:02:11.512Z",
    "actor": "Jane Engineer",
    "note": "checked p.13"
  }
]
```

- `action` is one of: `confirm` or `reject` (an automatic link must exist), `manual` (link any element to any calc
  by hand), `undo` (clear the latest decision on that pair; there must be one).
- The latest decision per (GlobalId, calc key) wins (`effectiveDecisions`). Decisions are keyed by GlobalId and calc
  key, so they carry forward to a new model or calc revision as long as both still exist. Decisions naming something
  that is not in the current project are kept and reported, but not applied.
- **Append-only.** The server never rewrites or drops an entry. It re-reads the file whenever it changed on disk
  (size / mtime, then sha256), so a colleague's or a script's edits show up in the next answer and are kept by the
  next append. It writes the whole array to a temp file in the same directory and renames it over the original. A
  batch is validated as a whole: one bad entry means nothing is written.
- Writes go to this file only. The IFC and the PDFs are never modified.

## Architecture

```
bin/unloaded-mcp-server.mjs   Node version check, console -> stderr, then src/cli.ts
src/cli.ts                    arguments -> loadProject -> --check report or stdio server
src/inputs.ts                 CLI + manifest parsing and up-front validation
src/engine.ts                 THE ENGINE BOUNDARY (see below)
src/project.ts                the loaded project: per-PDF mapping, key prefixes, cross-PDF edges, decisions applied
src/decisions.ts              the decisions file: validation, change detection, atomic append
src/tools.ts                  tool bodies (lookups, filters, pagination over engine output)
src/server.ts                 MCP registration: schemas, descriptions, annotations, resources
src/pageImage.ts              page PNG rendering (pdf.js legacy + @napi-rs/canvas)
src/check.ts                  the --check report
```

**Engine boundary.** `src/engine.ts` is the only module that imports `@unloaded/ifc-parser`,
`@unloaded/element-graph` or `@unloaded/calc-parser`. It exposes a narrow interface: `loadModel`, `readPdf`,
`mapCalcs`, `calcDependencies`, `crossReferenceDeps`, `effectiveDecisions`, `effectiveLinks`, `mappingStatuses`,
`statusOf`, `propagateImpact`, `exportMapping`, `rectsForSpan` and `ENGINE_VERSION`, plus a read-only `Model` with the
element-graph queries. The data types the rest of the server uses are re-exported from it. To point the server at
another port of the same engine (for example calc-mapper from PR #4), rewrite this one file. A test
(`test/server.test.ts`, "engine boundary") fails if any other file in `src/` imports an engine package.

## Not included, and why

- **Revision compare.** Prod's engine packages have no model diff. The app's diff works on the legacy JSON graph
  (`src/utils/graphEngine.ts`), which has no GlobalIds. A second implementation here would break the
  "engine output only" rule.
- **Legacy `{nodes, links}` BIM JSON models.** They have no GlobalIds, so calcs and decisions cannot be keyed to their
  elements. The server refuses them with a message.
- **Typical groups, size-mismatch findings, move-column what-ifs.** These came from the old calc-mapper design. They
  are not in prod's packages.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `needs Node >= 22.18` | Install a newer Node, or point `command` at it by absolute path. |
| The client shows the server as failed with no detail | Run the same command with `--check` in a terminal. Every input error is printed there. |
| `--model ... is a PDF` / `--calcs ... is not a PDF` | The model goes in `--model`, calc packages go in `--calcs`. |
| `no "ISO-10303-21" STEP header` | The file is not an IFC, or it is `.ifczip`. Unzip it. |
| `legacy BIM graph JSON` | Use the source `.ifc`, or an element graph saved from the app. |
| `same calc-key prefix` | Two non-main PDFs share a file stem. Rename one. |
| `has NO text layer` warning / calcs marked scanned | The PDF pages are images. OCR them, then run again. |
| `decisions file must be a JSON array` / `entry N: ...` | Fix the named entry, or point `--decisions` at a new file. |
| `This server is read-only` from `record_decision` | Add `--decisions /abs/path/decisions.json` to the args and restart the server. |
| `no automatic link ... use manual` | `confirm` and `reject` act on engine links only. Use `manual` to link by hand. |
| Hundreds of `[WEB-IFC]` lines | Hidden by default. `--verbose` shows them. They are web-ifc parser notices and harmless. |

## Development

```sh
npm run typecheck -w @unloaded/mcp-server     # tsc
npm test -w @unloaded/mcp-server              # vitest: tools vs the engine, multi-PDF, decisions, inputs, MCP surface
npm run parity -w @unloaded/mcp-server        # spawn the real CLI over stdio, call every tool, compare with direct engine calls
node packages/mcp-server/scripts/mcp-parity.ts --two-pdf               # same, with the fixture PDF twice
node packages/mcp-server/scripts/mcp-parity.ts --model m.ifc --calcs a.pdf --calcs b.pdf
```

The tests and the parity script use calc-parser's fixture (`packages/calc-parser/test/fixtures/model_rev1.ifc` and
`calc_package.pdf`) in place. The parity script writes decisions to a temp file only, and checks that the inputs'
sha256 did not change.
