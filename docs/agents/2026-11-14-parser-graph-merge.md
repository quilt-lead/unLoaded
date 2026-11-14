# Parser + element graph merged into the React UI

- **Status:** done (PR from `cs/dev` into `prod`)
- **Owned files:** `src/loaders/*`, `packages/element-graph`, `packages/ifc-parser`, `scripts/copy-assets.mjs`,
  the load-path part of `src/utils/graphEngine.ts`

## Context

Two independent lines of work existed:

1. **`prod` (React UI, "reactified")**: a single Vite app in `src/`. The view model is `BimNode` / `BimLink`
   (`src/types/bim.ts`): Project (level 0) → Category (1) → ColumnStack (1.5) → Instance (2). Nodes carry
   radial layout coords, 3D boxes and documents. The load path was *guessed*: `orientLoadLink` ranks by
   `floorNum`, then by id/parent prefixes (`cat-col`, `beam-`, ...). The IFC import was a regex STEP reader
   with a fake grid layout and random utilization.
2. **`cs/dev` stash**: an npm-workspaces monorepo. `packages/ifc-parser` (web-ifc → `ModelInput`) and
   `packages/element-graph` (`ElementGraph`: connections are nodes, `connects` / `supports` / `part_of`
   edges with evidence, geometric inference). Plus `apps/graph-viewer`, a cytoscape prototype UI.

The user's instruction: **the React UI is the source of truth**, so merge the parser and graph into it.

## Decisions

- **Two layers, one adapter.** `ElementGraph` is the domain model and the source of truth for topology.
  `BimGraphData` stays the UI view model. `src/loaders/elementGraphToBim.ts` is the only place they meet.
  The UI components were not changed to consume `ElementGraph` directly.
- **Category ids reuse prod's ids** (`cat-beam`, `cat-col`, `cat-slab`, `cat-conn`, `cat-wall`, `cat-footing`, ...),
  because `CATEGORY_PALETTE`, `getStructuralGravityRank`, `classifyCalcCategory` and the 3D slab check key on them.
- **Direction conventions match.** In element-graph, `supports` means `a` is supported by `b` (load flows a → b).
  In prod, a load-path `BimLink` flows source → target. The adapter emits `{source: a, target: b, relation: 'load-path'}`.
  `computeLoadPathTrace` uses only `load-path` links, unoriented, whenever any exist. Otherwise it falls
  back to the old heuristic (the demo DB has none: its links use a `rel` key, not `relation`).
- **Column stacks** are derived with union-find over column → column `supports` edges, following through a
  `connection` node (splices). They are only emitted if at least one stack has 2 or more segments.
  `computeRadialLayout` only places columns that sit under a stack once any stack exists, so either all columns are stacked or none are.
- **3D frame:** bbox (m, Z-up) → feet, Y-up: `three = (x, z, -y)`. Recentred in plan, with the lowest point at y = 0.
  The viewer has no rotation support, so boxes are axis-aligned bboxes.
- **No fake engineering data.** Utilization and axial load are left undefined for imported models.
- **Calc mapping hook:** `ElementNode.links` entries with `kind: 'calc'` become `BimNode.documents`
  (`target` = doc id, `data` = title / rev / pages / ...). Nothing populates these yet.
- **Dropped:** the regex STEP parser (superseded) and `apps/graph-viewer` (it duplicated the prod UI).
  Prod's legacy JSON importer survives as `src/loaders/legacyBimJson.ts`.

## Gotchas

- `web-ifc.wasm` must be served from `public/wasm/`. `scripts/copy-assets.mjs` copies it on postinstall, predev and prebuild
  (git-ignored). web-ifc is lazy-imported, so it is a ~3 MB chunk that loads only when an `.ifc` is opened.
  `optimizeDeps.exclude: ['web-ifc']` is required.
- web-ifc's meshes are already in metres and Y-up. The parser converts back to IFC Z-up, so don't convert twice.
- The packages use `.ts` import extensions, so the app tsconfig needs `allowImportingTsExtensions` (it already has it).
- `src/vite-env.d.ts` is needed for `import.meta.env`.
- The JSON importer dispatches on content (serialized graph → ModelInput → `{nodes}`), not on a byte sniff, because a
  ModelInput's `elements` key can be well past the first KB.
- Many IFC elements have no storey. The adapter assigns the highest level at or below `bbox.min.z + 5 cm`.

## Verification

- `npm test`: 8 adapter tests (`src/loaders/elementGraphToBim.test.ts`, simple-frame + real IFC end to end) + 60 package tests.
- `npm run build` passes. `npm run smoke` prints an IFC → graph summary in Node.
- Headless Chromium (Playwright from a scratch dir, not a project dependency): the demo DB loads, then importing
  `public/samples/Building-Structural-IFC4.ifc` populates the graph, Inspector and 3D view with no console errors.
  The only 404 is `/favicon.ico`, which predates this work.

## Open items / next steps

- Hold the `ElementGraph` instance in app state (`ImportResult.elementGraph` is returned but discarded) so the UI
  can edit topology, export `.element-graph.json`, and show edge evidence (the dropped graph-viewer had an evidence
  inspector worth porting).
- Populate calc links (PDF ↔ element mapping) on `ElementNode.links`.
- The 3D default camera is hard-coded for the 168 ft demo tower. Fit to the model bounds on load.
- The Inspector shows "0 kN" when `axialLoadKn` is undefined. Show "—" instead.
- Oriented boxes for diagonal members (needs rotation support in `Structural3DViewer`).
- Run IFC parsing in a Web Worker for large files.
