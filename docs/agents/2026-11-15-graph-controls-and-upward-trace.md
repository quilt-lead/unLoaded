# done — branch `prod`

## Files

- `src/App.tsx`
- `src/components/HeaderBar.tsx`
- `src/components/HeaderBar.test.tsx`
- `src/components/FilterBar.tsx`
- `src/utils/graphEngine.ts`
- `src/utils/graphEngine.test.ts`
- `src/utils/colors.ts`
- `src/utils/colors.test.ts`
- `src/engine/projectService.ts`
- `src/engine/projectService.test.ts`
- `src/engine/engineClient.ts`
- `docs/ARCHITECTURE.md`

## Findings

The original header exposed Type, Review, Confidence, and Heatmap modes. Restore those against the current project view model rather than reviving the earlier demo header. Utilization coloring remains unavailable until `view.hasUtilization` is true; this reflects the real-data constraint in architecture decision D8.

The trace depth control applies to the selected direction: Up limits the upward branch, Down limits the downward branch, and Up & Down caps both branches at the same depth. The default ALL setting lets a pile or other base support reveal its full connected superstructure.

The top-right Reset View control had no independent consumer. Its button and handler were removed.

The unmapped status was using a pink-red hue (`#e11d48`), easily confused with the separate no-data
pink. Review mode now uses a true red (`#ef4444`) for “No calc found”; missing status remains distinct.

PDFs in the checkout may be Git LFS pointer text rather than PDF bytes; checking the header before
worker dispatch now reports that exact setup issue. Header sniffing also accommodates a spec-compliant
PDF header anywhere in the first 1024 bytes. Both worker extraction operations transfer their byte
buffer to avoid cloning large PDFs.

## Verification

- Pending targeted tests and typecheck.

## Working files

None.
