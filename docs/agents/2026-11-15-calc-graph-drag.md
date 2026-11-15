# Calculation Graph node dragging

- **Status:** done
- **Branch:** cs/dev
- **Files:** `src/App.tsx` (calc graph `calcMoved` state, `handleMoveCalcNodes`, `calcGraph` memo)

## What changed

`RadialGraphCanvas` already supported dragging for both graphs; the Calculation Graph was passed a
no-op `onMoveNodes`. App now keeps a separate `calcMoved` map for calc graph nodes, reset with the
other project-scoped state in `enterScope`.

## Decisions

- Calc moves are stored as **cumulative offsets** (`dx`, `dy`), not absolute positions like the element
  graph's `moved`. The mapped-element satellites from `withMappingSatellites` are laid out around the
  anchor calc each render, so offsetting the anchor before that call makes its fan follow it. A dragged
  satellite gets its own offset applied after the layout.
- Satellite ids are `map:<calcKey>:<elementId>`, so a satellite's offset is remembered per calc anchor.
- Offsets survive revision changes within a project (same as element-graph `moved`), and are cleared on
  project change.

## Not done

- Calc graph has no groups, so the canvas's group drag expansion is a no-op there.
- Positions are not persisted to IndexedDB / project files (neither are element-graph moves).

## Dependency wires only on selection

`RadialGraphCanvas` draws `calc-dependency` edges (dashed indigo arrows) only when one end is in
`selectedNodeIds`. Drawn always, the ~hundreds of wires buried the graph. Calc-mapping edges already
appear only for the anchor calc (`withMappingSatellites`).
