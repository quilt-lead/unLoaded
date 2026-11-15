# Mission readiness review

- **Status:** done (review only; identified gaps remain open)
- **Branch:** `prod`, reviewed at `56f0264` plus the existing working tree
- **Owned files:** this note and the index entry in `README.md`
- **Working files:** none
- **Scope:** `mission.md` before its work-in-progress marker. No implementation changes. The pre-existing modification to `packages/mcp-server/bin/unloaded-mcp-server.mjs` was left untouched.

## Assessment

The core architecture and single-PDF workflow are substantially implemented. A rough product judgment is 70-80% of a constrained MVP, not a measured completion percentage or an estimate of remaining effort. The full mission still needs multi-document/version workflows, more reliable interpretation of real calculations, and trustworthy detailed connectivity. Drawing ingestion, move-impact, and MCP capabilities are useful additions but do not close those mission gaps.

## Priority gaps

1. **Multiple PDFs and independent versions.** Each calc upload becomes `headCalcRev` (`src/data/projectStore.ts:382`); `projectSnapshot` maps only that PDF (`src/engine/projectService.ts:257`). Historical calc revisions only have an open-file action (`src/components/RevisionPanel.tsx:145`). `packageSha256` explicitly rejects pages from multiple documents (`packages/calc-mapper/src/segment.ts:338`). Add document identities, per-document versions, an active document collection, and historical mapped selection. A main calculation PDF and a stair PDF must coexist.
2. **Real calculation segmentation and correction.** The broad title heuristic and same-title continuation rule can misidentify or merge separate calculations (`packages/calc-mapper/src/segment.ts:74`, `:257`). A read-only extraction diagnostic on the checked-in building calculation PDF yielded 238 pages, 69 segments, and 63 without a category; the stair PDF yielded 20 pages, 11 segments, and 9 without a category. These are diagnostic counts, not error rates: no independently labeled ground truth was available. Detected titles included body text and report file headers. Two distinct sheets titled `Beam Design` were also reproduced as one calc. Provide split/merge/title/type/region corrections and a labeled real-document benchmark. Scanned pages are flagged but have no OCR path.
3. **Review validity across versions.** Decisions carry solely by element ID and title-derived calc key (`packages/calc-mapper/src/decisions.ts:41`, `:65`). Document/revision/content hashes do not invalidate them. A previously confirmed or manual link can apply to changed content without a stale-review state. Preserve intentional carry-forward only when its identity/evidence remains valid.
4. **Connectivity correctness.** Bounding-box contact can create false physical links (`packages/element-graph/src/infer/inferConnectivity.ts:288`). A read-only probe with parallel diagonal 200 mm beams, centerlines about 707 mm apart, produced a `connects` edge with `gap_m: 0` because their axis-aligned boxes overlap. Add oriented/axis-aware contact checks and review/correction of inferred edges. Preserve explicit/inferred provenance in the view model.
5. **Connectivity presentation and detailed assemblies.** The element canvas draws a category/mark hierarchy and optional support traces, while `connects`/`part_of` are inspector rows. A physical connectivity/assembly view remains useful for the central mission. Fasteners are recognized in the schema/parser, but current IFC fixtures do not demonstrate the entire fastener-to-connection-to-calculation workflow. `IfcRelAggregates` is read; `IfcRelNests` is not.
6. **UI finish and browser validation.** JSON revisions that preserve IDs but change bounding boxes can leave stale 3D fallback geometry because the update key contains only IDs (`src/components/Structural3DViewer.tsx:129`). Graph nodes are pointer-only; custom groups/layout are not persisted. IFC parsing/buildGraph still run on the main thread, so large-file responsiveness needs measurement. Existing frontend tests include static markup and source-wiring checks, not a real browser end-to-end suite.

## Verification and limits

- `npm run typecheck`: passed for app and all workspaces.
- `npm test`: **491 passed, 1 skipped**. The skip is the MCP synthetic-project test, whose generated fixtures are absent.
- `npm run build`: passed. Build warns that the synthetic sample has not been generated, so the main Load sample workflow is unavailable until generated.
- `npm run smoke`: passed, with expected warnings about an unsupported IFC type and missing geometry.
- Real PDFs are present as LFS content, not pointer files.
- Tests/build initially hit the environment's sandbox directory-read restriction; approved runs outside that restriction completed successfully. This was not a repository failure.
- No current browser visual/interaction session was run. Visual polish, actual PDF highlight alignment, WebGL interactions, and cross-browser behavior are not certified by this review.
- Python evaluation was not rerun. The checked-in synthetic baseline reports approximately 93.2% design precision and 99.6% recall; it does not establish real-package accuracy.

## Suggested acceptance test

Import a representative detailed IFC, the building and stair PDFs together, and a revised version of only one PDF. Both documents should remain active; corrected calculations and manual links should survive save/reopen; changed evidence should request re-review. Navigate element -> calculation -> exact PDF region and back. Verify a known connection and its fasteners against the IFC. Run this in a browser and turn the workflow into repeatable acceptance coverage before expanding feature scope.

## Documentation drift

`setup.md` still refers to the retired calc-parser package, and `data/README.md` still says PDFs are ignored. Earlier handoff notes describe already-merged work as awaiting merge. These should be reconciled with current code in a documentation follow-up.
