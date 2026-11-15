# done — branch `prod`

## Files

- `src/utils/colors.ts`
- `src/utils/colors.test.ts`
- `src/components/Structural3DViewer.tsx`

## Findings

Structural graph categories use the supplied bright swatches `#FF1493`, `#FF5E7E`, `#FF8A00`, `#FFAE42`, `#A3D900`, and `#00AEEF`, plus three equal OKLab interpolation steps between each adjacent pair. The six anchors are assigned first in a high-contrast order; the derived colors are then interleaved by contrast to give 21 distinct category colors. The supplied light gray `#D8D3D8` is reserved for the center node; the dark charcoal `#2F2F2F` is not used as a node fill.

The same graph-color resolver supplies element colors in the radial graph, inspector, and 3D model in base, heatmap, diff, and selection states. Selection uses emissive emphasis and white wireframes without replacing the element fill; dimming lowers opacity without turning elements gray. Selected graph wires are white rather than mint.

## Verification

`npx vitest run src` passes (55 tests), `npm run build` passes, and `git diff --check` is clean. Browser review with the 420-element Harborview model confirmed the gray center, distributed category colors, neutral selector, and matching graph/3D colors.

## Working files

None.
