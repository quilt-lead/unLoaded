# blocked — branch `feat/current-ui-integration`

## Files

- `src/App.tsx`
- `src/components/`
- `src/index.css`
- `src/loaders/`
- `src/utils/`

## Findings

The `prod` project/revision model is the source of truth: IFC topology comes from the element-graph adapter, calculation data from the calc-mapper, and both feed the current `ProjectViewModel`. Keep that architecture rather than restoring the older demo graph or PDF-mapping implementation.

The current UI changes are reapplied to that model: the shared color resolver keeps graph and 3D fills aligned, selection emphasizes without replacing the element fill, the project root alone is gray, selected wires are white, and the workspace-view indicator is neutral. Escape remains a single global action even when focus is in an input. Legacy stacked-column tracing is covered through the current adapter.

The obsolete `buildCalculationGraph` assertion was removed from `documents.test.ts`; the test itself documents that API as not ported to this branch.

## Verification

- `npx vitest run src`: 18 files, 124 tests passed.
- `npm run build`: passed.
- Browser review at `http://localhost:5173/`: Harborview demo loaded; graph colors, gray root, and 3D model colors were visually checked.
- `git diff --check`: clean.
- Full `npm test` reaches all workspaces but the MCP server's `get_page_image` test fails on Node 20.9.0. That package requires Node `>=22.18`; other workspace tests pass. The synthetic sample build assets are also absent, so the build reports that the optional “Load sample” dataset was not generated.

## Blocker

The branch is pushed, but the PR is not open: the available GitHub integration is read-only and the browser session is signed out. Open the comparison page while authenticated to create the PR against `prod`: https://github.com/quilt-lead/unLoaded/compare/prod...feat/current-ui-integration?expand=1

## Working files

None.
