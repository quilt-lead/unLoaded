# done — branch `feat/crossing-selection`

## Files

- `src/components/RadialGraphCanvas.tsx`
- `src/App.tsx`
- `src/utils/graphSelection.ts`
- `src/utils/graphSelection.test.ts`

## Decisions

- The element and calculation graph views share `RadialGraphCanvas`, so the same rectangle gesture serves both.
- Left-to-right selects nodes fully contained by the rectangle; right-to-left selects circles intersecting it. Shift-drag adds to the current selection. Middle/right drag remains pan, and canceling a selection gesture leaves the current selection intact.
- A calculation-graph rectangle updates the selected calculation IDs and the union of their mapped elements, keeping the inspector and linked 3D selection consistent. The last selected calculation remains the primary inspector target.
- The selection overlay uses the existing green/mint highlight palette. Noninteractive graph wires let the user start a rectangle on top of them.
- All graph-node labels use white text with a dark shadow for legibility across node fill colors.

## Verification

- `npx vitest run src`: 118 tests pass.
- `npm run typecheck` and `npm run build`: pass.
- `npm test`: app and other workspace tests pass, but `packages/mcp-server/test/server.test.ts` fails in `get_page_image returns PNG image content plus the frame and the PDF's hash` on this Node 20.9 runtime. `@unloaded/mcp-server` declares Node `>=22.18`; this is unrelated to graph selection.

## Working files

None.
