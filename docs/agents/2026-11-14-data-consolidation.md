# Data consolidation into `data/`

- **Status**: done (PR open against `prod`)
- **Branch**: `cs/consolidate-data` (worktree `../unLoaded-data`)
- **Files owned**: `data/`, `scripts/copy-assets.mjs`, test fixture paths

## What changed and why

All IFC and JSON model data now lives in one flat folder, `data/` (index + provenance in `data/README.md`).
Before, the same files were spread over `data/`, `sample-data/`, `public/data/` (three byte-identical copies of
`bim-database.json`, two of each Harborview file), `fixtures/` and `packages/ifc-parser/test/fixtures/`.

- Package tests now reach up to the repo root (`../../../data/...`). `element-graph` already did this for
  `fixtures/`, so the packages were never self-contained; this keeps one copy instead of two.
- `scripts/copy-assets.mjs` no longer copies samples into `public/samples/`. Nothing in `src/` fetched them; they
  only existed as an upload convenience, and `data/` serves that now. It still copies `web-ifc.wasm`.
  `public/samples/` stays in `.gitignore` so stale local copies don't get committed.

## Left alone

- `prototyping/` keeps its own data (`calc-graph/data/open/*.ifc`, `calc-viewer/data/*.json`). Those are
  self-contained prototypes with their own loaders, not app data.

## Gotchas

- Existing checkouts still have a stale `public/samples/`; delete it by hand if it confuses you.
- Tests read `data/` by path: renaming a file there needs the test references updated (listed in `data/README.md`).
