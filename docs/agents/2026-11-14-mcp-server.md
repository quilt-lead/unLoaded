# MCP server on prod's engine (`packages/mcp-server`)

- **Status:** active (built and parity-green; not committed when written)
- **Branch:** `issy/mcp-server` (from `origin/prod`)
- **Owned files:** `packages/mcp-server/**`, the `@unloaded/mcp-server` entries in `package-lock.json`

## Context

A local stdio MCP server so an engineer's own AI can query a project (IFC + calc PDFs) and record review
decisions. An earlier design lived on the calc-mapper branch (`git show 0fd9aa9:packages/mcp-server/...`). This one
is rebuilt on prod's packages (ifc-parser, element-graph, calc-parser). It reuses that design's wiring, page renderer,
bin shim and parity-script approach.

## Decisions

- **Engine boundary:** only `src/engine.ts` imports the engine packages, so the server can be re-pointed to another
  port (e.g. calc-mapper) later. A test in `test/server.test.ts` enforces it.
- **The server writes decisions** (the user decided), and nothing else. The decisions file is a JSON array of
  calc-parser `Decision`s, append-only, written atomically, re-read when it changes on disk.
- **Multi-PDF:** `mapCalcs` runs per PDF. The main PDF keeps plain keys; the others get a `<stem-slug>/` prefix.
  Cross-PDF calc edges come from `inferCalcDeps` on a combined view with calcs' `pages` emptied (this switches off
  the page-reference rule). Only edges spanning two PDFs are kept.
- **Calc edges use effective links**, like Python's `pipeline.state` (rejected xrefs drop edges, manual links count as
  designers). With no decisions this equals `mapCalcs`' own edges (the parity script checks it).
- Left out: revision compare (no model diff in prod's packages), legacy `{nodes,links}` JSON (no GlobalIds),
  typical groups / findings / move_column (calc-mapper only).

## Gotchas

- web-ifc's wasm logs to **stdout** through `console.log`. That would corrupt the MCP channel. The bin shim reroutes
  console to stderr *before* the CLI (and therefore web-ifc) is imported. Don't add static imports of engine code to
  the bin shim.
- pdf.js prints `Warning: ... standardFontDataUrl` during `readPdf`. calc-parser's `readPdf` doesn't take
  getDocument options. The warnings are harmless, and they are counted and hidden unless `--verbose`.
- No pdf-lib in the tree, so the multi-PDF tests pass the fixture PDF twice under two temp names.
- prod has no `.github/workflows`: the vitest suites here run only when someone runs `npm test`.
- The local test-blocking hook also matches `npm run check` (the package's `--check` shortcut). Run
  `node packages/mcp-server/bin/unloaded-mcp-server.mjs ... --check` directly instead.

## Next steps

- Real projects with more than one distinct PDF: confirm the cross-PDF edges read sensibly to an engineer.
- If the app adopts calc-parser decisions, keep the file format identical so the app and the server share one log.
