# Graph workspace comments

- **Status:** done (in review)
- **Branch:** cs/graph-comments (from prod)
- **Files:** `src/components/GraphCommentNote.tsx` (new), `src/components/RadialGraphCanvas.tsx`, `src/App.tsx`
  (comment state + handlers, toast action button), `src/types/bim.ts` (`GraphComment`), `src/utils/graphSelection.ts`
  (`selectRectsInBox`)

## What it does

Sticky-note comments on the Element Graph and the Calculation Graph. **Comment** in the canvas toolbar adds one at the
view centre, **C** adds one under the pointer. A new comment opens for editing; Ctrl+Enter or clicking away saves,
Escape cancels (a new empty comment is discarded). Double-click or Enter on a focused comment edits it.

Comments behave like nodes: click selects, Shift+Click toggles, box selection (both directions) includes them, and
dragging any selected item drags the whole selection, nodes and comments together. Arrow keys nudge selected
comments (Shift for bigger steps). Delete / Backspace removes selected comments, with **Undo** in the toast.

## Decisions

- Comments are rendered in a `foreignObject` inside the camera transform, so they pan and zoom with the graph and
  wrap text natively. Each note measures its own height (ResizeObserver; `offsetHeight` is untransformed, so it is in
  graph units) and reports it to the canvas for box selection.
- One `comments` list in App, each tagged `graph: 'element' | 'calc'`; one `selectedCommentIds` set, cleared on view
  change so Delete can't hit comments on the hidden graph. Comment selection is separate from node selection; a plain
  click on a node or group clears it, a plain click on a comment clears node selection.
- Comments are project-scoped like groups and moved nodes: cleared in `enterScope`, kept across revisions.
- The toast gained an optional action button (`showToast(msg, isError, { label, run })`) for Undo.
- Comments never dim with selection/filter highlighting: they are annotations, not data.

## Not done / next

- **Not persisted**: comments are lost on reload, same as groups and node positions. The natural home is the project
  in IndexedDB (`src/data/projectStore.ts`) and the project file, together with groups and positions.
- Comments are free-floating; they don't attach to a node (an anchor that follows the node would be a follow-up).
- On the Calculation Graph on prod, nodes aren't draggable (`onMoveNodes` is a no-op), so dragging a mixed selection
  there moves only the comments.
- The "N Selected" pill counts nodes only.
