# Status: done
# Branch: prod
# Files: public/unloaded-logo.svg, src/components/HeaderBar.tsx, src/components/FilterBar.tsx, src/components/DockableHudPanel.tsx, src/utils/colors.ts, src/index.css, src/App.tsx

## Summary
Replaced the header's network glyph with the supplied CalcMap SVG wordmark, kept the existing project title and header layout, and gave the image intrinsic dimensions and descriptive alt text. The header now omits the IFC schema badge and graph-flow tagline. Chrome and workspace backgrounds use quieter neutral graphite, and the Added diff state uses the logo green (#14AE5C). The Inspector cannot be closed or hidden in graph/3D views; it remains absent in the PDF view.

## Verification
- `npm run typecheck`, `npm test`, and `npm run build` passed for the logo update before the subsequent cleanup changes.
- Confirmed the SVG is served by Vite and visually checked it in the header.

## Working files

None.
