# @unloaded/project-file

The whole-project file, `*.calcgraph.json` (format `unloaded.calc-graph-project`, version 1). This package
is the only place the format is declared. Every reader and writer goes through it:

| | writes | reads |
|---|---|---|
| app | `src/data/projectStore.ts` `exportProject` | `src/loaders/parsers.ts` (`parseProjectFile`) → `importProject` |
| MCP server | `packages/mcp-server/src/makeProjectFile.ts` (tooling, tests) | `packages/mcp-server/src/project.ts` `loadProject` |

What it holds: every revision's original file base64-encoded (`blob`), each model revision's element graph
(`graph`, required), each calc revision's extraction (`extraction`, optional: readers re-extract from the PDF
when it is missing or stale), and the append-only decision log, oldest first.

- `ProjectFile`, `ProjectFileRevision`, `ProjectFileRevisionFields`, `ProjectFileDecision`: the types. The app's
  store records extend the field types, so the store and the file cannot drift. Decision actions are
  calc-mapper's `DECISION_ACTIONS`.
- `parseProjectFile(data)`: validates every field a reader relies on (including each model graph, via
  calc-mapper's `parseGraph`, and that each decision's revisions exist in the file with the right kind).
  Throws `ProjectFileError` naming the first field at fault.
- `isProjectFileFormat(data)`: routing only ("does this JSON claim to be a project file?").
- `encodeBase64` / `decodeBase64`: one codec for the browser and Node.
- `headOf(revisions, kind)`: the head of a kind is the highest id, which is what importing leaves as head.

Tests: `test/projectFile.test.ts` (round trip, codec against Node's encoder, every rejection); the app's
writer → reader → importer round trip is `src/data/projectStore.test.ts`.
