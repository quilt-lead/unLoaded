# @unloaded/mcp-server

Point your own AI (Claude Desktop, Claude Code, Cursor, any MCP client) at a calc-graph project, and
ask it about the model, the calcs, the links between them, the evidence and the impact of a change.

**It runs on your machine, over your own file.** The server is a local process your AI client starts.
It talks to that client over stdin/stdout (MCP stdio). It opens no port and makes no network request.
It reads the project file you name and never writes to it. Nothing leaves your machine except what your
AI client sends to its model provider, which includes the tool results it asks for (text, numbers and
page images from your project). The app has no server for this, and doesn't get one.

## Input: a project file saved from the app

In the app, **Save project** writes one `*.calcgraph.json` file (`src/data/projectStore.ts`
`exportProject`, format `unloaded.calc-graph-project` v1). The format is declared once, in
`@unloaded/project-file`, which both the app and this server read and write it through. It holds every revision's original file
base64-encoded, each model revision's element graph (built in the browser at import), each calc PDF's
extraction, and the decision log. The server reads exactly that file:

- **Revisions.** The head of each kind is the revision with the highest id, the same rule the app's
  importer uses. Tools default to the heads (what the app shows). Pass `model_revision` /
  `calc_revision` to ask about others.
- **Same engine as the app.** For a (model, calc) pair, the server runs `@unloaded/calc-mapper`
  in-process: `mapCalcs`, then `buildState` and `buildExport` with the decision log, then `impactOf` and
  `diffGraphs`. These are the same calls the app's worker makes, with the same arguments. There is no
  second implementation.
- **Stored extraction.** It is used when its document hash matches the PDF in the file. Otherwise the
  PDF is re-read with `extractPdf` + `segmentCalcs`, so every provenance hash names the PDF that is
  actually there. `source.calc_revision.extraction` says which happened.
- **Caching.** Results are cached in memory per sha256 of the file's bytes. Save a new version from the
  app over the same path and the next call picks it up.

## Tools

All tools are read-only and annotated so. Every result carries the engine's own records untouched:
links with `role`, `band`, `caveats`, `reasons` (weighted evidence) and `provenance` (producer, rule,
method, input sha256s), calc edges, findings, impact. Every result also has a `source` block: the
project file and its sha256, the revisions, the engine version and the run's producer records.

| Tool | Input | Returns |
|---|---|---|
| `project_summary` | `model_revision?`, `calc_revision?` | project, revisions, counts (elements by kind / storey / status, links by review / role, calc edges, load-path and connectivity edges, groups, findings, decisions), calc list |
| `search_elements` | `mark?`, `kind?`, `storey?`, `size?`, `grid?`, `status?`, `limit?` (50, max 500) | `{count, returned, elements: [{global_id, mark, kind, storey, size, grid, status, calcs: [{calc, role, band, confidence, review}]}]}` |
| `get_element` | `id` (GlobalId or mark) | the element row (params, geometry in metres), every calc link (export shape, with provenance and review provenance), typical groups and group links, findings, load path (`bears_on` / `carries`), connectivity, decisions |
| `get_calc` | `key` (or exact title), `include_text?`, `max_chars?` | the calc (title, software, element type, pages, spans, title box, provenance), linked elements with their link evidence, group links, findings, calc edges (`feeds` / `fed_by`), optionally the calc's own text |
| `impact_of_change` | `id`, `mode?` (`change` / `remove`) | calc-mapper's `Impact` (removed, hit -> wave, why, stale calcs, provenance), plus hit elements with marks and stale calcs with titles |
| `list_revisions` | none | model and calc revisions with head flags, decision count |
| `compare_revisions` | `a?`, `b?` (model revision ids; default head and the one before) | `diffGraphs` output (removed / added / changed with per-field before/after, load-path edges) plus counts |
| `list_findings` | `calc?`, `element?`, `limit?` | size-mismatch findings (minus those on rejected links, as in the app), with mark / title labels |
| `list_typical_groups` | `kind?`, `storey?`, `size?`, `linked_only?`, `limit?` | groups (`group:<cat>:<storey>:<profile>`, members) with member marks and their group links |
| `get_page_image` | `page`, `rect?`, `highlight?`, `width?` (200-3000 px), `calc_revision?` | the calc PDF page as PNG image content, cropped to `rect` and outlining `highlight` (PDF points, top-left origin, the frame of every rect the other tools return), plus a text block with the page size, area, scale and the PDF's sha256 |
| `move_column` | `column`, `dx?`, `dy?` (metres), `remove?` | `@unloaded/move-impact` on the head graph and the reviewed links: elements on the path with reasons, the geometric screen, re-framing, clashes, stale calcs. No calc values are read yet, so there are no utilisation estimates and no health band |

## Setup

The workspace packages ship TypeScript sources, which Node runs directly. This needs **Node >= 22.18**.
From the repo root:

```sh
npm install
node packages/mcp-server/bin/unloaded-mcp-server.mjs ~/Projects/tower.calcgraph.json --check   # loads it, prints a summary
# inside the repo the bin is also on npx:
npx @unloaded/mcp-server ~/Projects/tower.calcgraph.json --check
```

Use absolute paths in client configs. Clients don't start servers from the repo directory.

**Claude Desktop**: `claude_desktop_config.json` (Settings > Developer > Edit Config):

```json
{
  "mcpServers": {
    "calc-graph": {
      "command": "node",
      "args": [
        "/absolute/path/to/unLoaded/packages/mcp-server/bin/unloaded-mcp-server.mjs",
        "/absolute/path/to/tower.calcgraph.json"
      ]
    }
  }
}
```

**Claude Code**:

```sh
claude mcp add calc-graph -- node /absolute/path/to/unLoaded/packages/mcp-server/bin/unloaded-mcp-server.mjs /absolute/path/to/tower.calcgraph.json
# add --scope user to use it from every directory; `claude mcp list` checks it started
```

**Cursor**: the same `mcpServers` block as Claude Desktop, in `~/.cursor/mcp.json` or a project's
`.cursor/mcp.json`.

The file can also come from `UNLOADED_PROJECT_FILE` instead of the argument.

Then ask, for example: *"Which beams on Level 3 are only linked to a calc by size, and what are the
caveats?"*, *"Show me the evidence for the link between 2B13 and the floor beam calc"*, *"What goes stale
if column C8 is removed?"*, *"What changed between the two model revisions?"*

## Dependencies

| Package | Version | Why |
|---|---|---|
| `@modelcontextprotocol/sdk` | 1.32.2 (2026-10-23) | the official MCP TypeScript SDK: server, stdio transport |
| `zod` | 4.6.7 (2026-10-12) | the SDK's peer dependency for tool input schemas |
| `@napi-rs/canvas` | 0.1.100 | page rendering. It is the canvas pdf.js itself loads in Node (its `NodeCanvasFactory`; an optional dependency of `pdfjs-dist`, already in the lockfile at this version). It ships prebuilt binaries per platform and needs no system libraries. Pinned here so rendering doesn't depend on an optional install |
| `pdfjs-dist` | 4.10.38 | the version calc-mapper and the app use (legacy build in Node) |
| `@unloaded/calc-mapper`, `@unloaded/element-graph`, `@unloaded/move-impact` | workspace | the engine |

## Scripts

```sh
# a project file from element graphs + calc PDFs, in the app's format (no browser needed)
node packages/mcp-server/scripts/make-project-file.ts --out sample.calcgraph.json --name "Sample" \
  --model tools/calcgraph-reference/data/synthetic/model_rev1.graph.json \
  --calcs tools/calcgraph-reference/data/synthetic/calc_package.pdf \
  --model tools/calcgraph-reference/data/synthetic/model_rev2.graph.json

# end-to-end parity: launches the CLI over stdio with the MCP client, calls every tool, and compares
# each result with calc-mapper / move-impact called directly on the same file (exit 1 on a mismatch)
node packages/mcp-server/scripts/mcp-parity.ts sample.calcgraph.json

npx tsc -p packages/mcp-server/tsconfig.json
npx vitest run --root packages/mcp-server
```

The tests build a small project in memory: two element-graph revisions and a two-page calc PDF
written byte by byte. No generated PDF is committed. `test/synthetic.test.ts` also runs on the
synthetic package when `tools/calcgraph-reference/data/synthetic/` has been generated. It is skipped
otherwise.
