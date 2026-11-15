# Drag & drop import

- **Status:** done (not yet verified with a real OS drag in a browser, see below)
- **Branch:** `cs/drag-drop-import`
- **Owns:** `src/hooks/useFileDrop.ts`, `src/components/FileDropOverlay.tsx`; small wiring in `src/App.tsx` (`handleDropFiles`, `<FileDropOverlay>`), empty-state copy in `RadialGraphCanvas.tsx`

## What it does

Dragging an OS file over the window shows a full-window overlay. With no model loaded there is one
target (loads as DB A). With DB A loaded there are two: **Replace Base Model** (DB A) and
**Compare Against DB A** (DB B → Diff Mode). Dropping outside a target defaults to DB A. Every import
goes through the existing `handleUploadFile`, so toasts, state resets and diff logic are identical to
the header buttons.

## Decisions

- **Window-level listeners, not a canvas `onDrop`.** The 3D/inspector HUD panels float over the
  canvas; a canvas-only target would let a drop on a panel fall through to the browser, which opens
  the file and navigates away from the app.
- **Only drags whose `dataTransfer.types` includes `Files` are handled.** In-app node/panel drags use
  pointer events and never trigger the overlay.
- **Slot detection via `data-drop-slot` + `closest()`** on the drop target instead of per-zone
  handlers, so all drop logic lives in one hook.
- **Extension filtering happens on drop, not on dragover.** Browsers don't expose file names during
  dragover, so the overlay can't reject a bad file early. Unsupported files get an error toast. The list
  comes from `ACCEPTED_EXTENSIONS`, so new parsers in `BIM_PARSERS` are picked up automatically.
- **One file per drop, by user decision.** If several are dropped, the first supported one is imported
  and the rest are logged to the console. Two files → A + B in one drop was offered and declined. Don't
  add it unless asked.

## Open / next steps

- There's no DOM test environment (no jsdom/testing-library), so the hook has no unit tests. Verify
  manually: drag a `.ifc` from `data/` onto an empty app, then a second one onto the "Compare" target,
  then a `.txt` (expect an error toast).
- There's no in-progress import state. A drop during a slow IFC parse starts a second import.

## Update: ported onto the calc-engine integration (PR #9)

The DB A / DB B slots don't exist after PR #4. A and B are model revisions of one project. In `App.tsx`:
- a drop anywhere goes through `handleOpenFile`, the header's open-by-content path: a model or calc PDF becomes the
  newest revision, and a project file opens as a project;
- the Compare zone, shown once a model is loaded, runs `addRevisionFile('model', f, { compareWithHead: true })`.

Drops accept `.pdf` too. The overlay copy was reworded to match.
