# Default panel docking

- **Status:** done
- **Branch:** `cs/ui-default-docking`
- **Owned files:** `src/App.tsx`, `src/components/HeaderBar.tsx`

## Decisions

- Match the supplied workspace reference using the existing docking system: inspector on the left, graph in the center, and 3D model on the right. Keep the existing 340px / 360px dock widths and manual resize / undock controls.
- Initial app state uses the docked layout. Manual docking choices still last for the current session; no persisted layout preference or migration is introduced. The latest `prod` removes Reset All; that removal is preserved.
- Work is isolated in `.worktrees/ui-default-docking`, rebased onto `prod` at `02cc934` for the pull request. Uncommitted work in the original checkout is not included.
- Remove the navbar's outer drop shadow so it no longer darkens the filter bar below it; keep its bottom border and the existing control/menu shadows.

## Verification

- After rebasing, all 142 application tests passed, including the docking and header tests. Vitest was invoked with a temporary Vite filesystem allowance for the dependencies shared with the original checkout.
- `npm run typecheck`: passed for the app and all workspaces after rebasing.
- `npm run build` and `git diff --check`: passed. The worktree links the existing web-ifc dependency locally for the asset-copy script; the optional generated synthetic sample remains absent.
- No browser interaction or rendered-layout check was performed; the existing dock rendering was reviewed in code.

## Working files

None.
