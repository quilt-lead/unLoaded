# Ctrl+Click jump to calc, Shift+Click in the calc graph, Alt+Left/Right view history

- **Status:** done (typecheck + unit tests pass; not exercised in a browser)
- **Branch:** cs/dev
- **Files:** `src/App.tsx` (`applyView` / `changeView` / `stepView`, `handleOpenNode`, `handleSelectCalcNode`),
  `src/components/RadialGraphCanvas.tsx` (`onOpenNode` prop, hint footer)

## Behaviour

- **Ctrl / Cmd + Click** a graph node (`onOpenNode`, checked before selection/drag in `handleNodePointerDown`):
  - element → `showElementCalcs` (its top non-rejected link's evidence); a toast if it has no linked calc
  - calc → selects it and opens `calcTarget(c)` in the PDF view
  - mapped-element satellite → `linkTarget(link, calc)` with the element selected
  - anything else (root, categories) → a hint toast
- **Shift + Click** in the Calculation Graph now toggles the node in the calc selection. The canvas
  always sent `toggleMulti`, but App wrapped the handler as `(id) => handleSelectCalcNode(id)`, dropping it.
  Toggling goes through `handleSelectCalcNodes`, so linked elements follow the calc selection.
  `preserveMulti` (pressing on a member of a multi-selection to drag it) keeps the selection.
- **Alt+Left / Alt+Right**: back / forward through workspace views, browser convention. `changeView`
  is the one entry point: it pushes the view being left onto `back` (cap 50) and clears `forward`;
  `stepView` moves between the stacks via `applyView` (which holds the old calc-graph filter-clearing rule).
  The keydown handler always `preventDefault`s Alt+Left/Right, or the browser navigates away from the app.

## Decisions / open questions

- History holds views only, not selection or PDF target: selection is shared across views, so going
  back to the graph after a jump still shows the node selected.
- The user described "Alt+Right to get back" after a jump; implemented as Alt+Left = back (browser
  convention). Flip the two keys in the keydown handler if they want it the other way.
- Element Graph Shift+Click: the code path (`toggleMulti` → `handleSelectElementNode`) reads correctly
  and was not changed. If it is still reported broken, reproduce in a browser first.
- Mac: Ctrl+Click is the context menu there, so Cmd+Click also triggers the jump.

## 3D model

`Structural3DViewer` takes an `onOpenNode(gid)` prop: Ctrl / Cmd + click on a picked mesh calls it
instead of selecting. App resolves the GlobalId through `elementById` and reuses `handleOpenNode`, so
the 3D model, Element Graph and Calculation Graph share one jump path (and the same no-calc toast).
Ctrl isn't bound to any navigation in `Structural3DControls`, so it does not conflict with orbit / pan.

## Trace Up/Down dead at pile caps (fixed in element-graph inference)

Symptom: the Trace Down / Up / Up & Down buttons did nothing on pile caps and piles. The buttons and
`computeLoadPathTrace` were fine; the load path was missing the foundation link. On Harborview every
cap had `supports` from its base-plate connection above, but only a `connects` (bbox contact) to its
pile below. No rule made a footing bear on a pile (`columnBase` covers column/wall bottoms only).

Fix: new rule `footingOnPile` in `packages/element-graph/src/infer/inferConnectivity.ts` (after
`columnBase`, documented in the package README). Footing supports-> pile when the pile head is at the
footing underside or embedded in it, the pile extends below it, and the head is inside the footing in
plan. Harborview rev 1: 20/20 caps on their piles, no cycles or conflicts. Test:
`packages/element-graph/test/footing-on-pile.test.ts`.

Gotcha: projects already in IndexedDB keep the element graph built at import. Re-add the IFC (or
reload the sample) to get the new edges.
