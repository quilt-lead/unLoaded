# Status: done
# Branch: prod
# Files: src/index.css, tailwind.config.js, src/components/RadialGraphCanvas.tsx

## Summary
Switched the app's primary UI font from IBM Plex Sans to Apercu and made the change consistent across the global stylesheet, Tailwind font tokens, and the SVG canvas text overrides.

## Why
Apercu is the design default for the product, and the previous IBM Plex stack was hard-coded in the main stylesheet and a few canvas-specific inline styles. Keeping the font change at the global layer makes it easier to maintain and ensures the UI remains visually consistent across graph and panel surfaces.

## Notes
- Apercu WOFF2 faces are bundled from the user's supplied archive and loaded locally; no external font CDN is required.
- The supplied archive did not include a separate font license file.
- Monospace styling remains on IBM Plex Mono so code-like labels and numeric annotations preserve their technical contrast.
- No structural logic was changed; this is a presentation-only update.
