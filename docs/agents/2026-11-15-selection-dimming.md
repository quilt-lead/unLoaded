# 3D selection dimming

- **Status:** done
- **Branch:** prod
- **Owned files:** `src/components/three/ifcViewer.ts`, `src/components/three/ifcViewer.test.ts`

## Cause and decision

Selecting Connections correctly selects its descendants and produces no load-path trace, but some
previously opaque meshes stayed bright. Three.js caches an `OPAQUE` shader variant that forces alpha
to 1; changing `material.transparent` does not automatically invalidate that program. The visible
leftovers depended on which meshes had already rendered with that variant.

Invalidate the material only when transparency mode changes. Ordinary opacity, color, and glow updates
keep the cached program. Selection membership and load-path behavior do not need changes.

## Verification

- The new regressions failed before the fix and pass after it: opaque/dim transitions, repeated
  selection changes, multiple meshes per element, and no shader invalidation within the same mode.
- `npx vitest run src`: 249 tests passed, including 126 app tests and 123 discovered in the existing
  `.claude/worktrees/set-linking-port` checkout. `npm run build` passed.
- Chromium/WebGL pixel check using the real `IfcViewer.style`: with invalidation suppressed (old
  behavior), opacity 0.06 still produced alpha 255; with the fix, alpha was 15. Selecting again
  restored alpha 255; dimming again to 0.07 produced alpha 18. This was a focused renderer check,
  not a full app interaction test; no browser dependencies were added.
- Vite/esbuild needed normal filesystem access because the sandbox blocked ancestor directories.

## Working files

None.
