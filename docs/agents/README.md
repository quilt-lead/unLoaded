# Agent handoff notes

This is a shared workspace where agents (and people) leave findings for the next session.
Read it before starting work. Write to it before handing off.

## Conventions

- **One file per topic or workstream**: `YYYY-MM-DD-<topic>.md`, e.g. `2026-11-14-parser-graph-merge.md`.
  Update an existing note when you continue the same work. Don't start a parallel one.
- **Each note starts with a header**: status (`active` / `done` / `blocked`), branch, and the files it owns.
- **Record what the code doesn't say**: why something was decided, what was rejected,
  gotchas, open questions, and the next steps. Don't restate code or git history.
- **Working files**: list the files you are actively changing under "Working files" so the
  next agent knows what is in flight and what to avoid touching.
- **Keep it current**: when a note is no longer true, fix or delete it. Stale notes are worse than none.

## Index

| Note | Status | Summary |
|---|---|---|
| [2026-11-14-parser-graph-merge.md](2026-11-14-parser-graph-merge.md) | done | Merged the IFC parser and element-graph packages into the React UI via an adapter |
| [2026-11-14-font-update.md](2026-11-14-font-update.md) | done | Switched the app to Apercu across the global styles and canvas text overrides |
| [2026-11-14-calcmap-logo.md](2026-11-14-calcmap-logo.md) | done | Replaced the header glyph with the CalcMap SVG wordmark |
| [2026-11-14-3d-controls.md](2026-11-14-3d-controls.md) | done | Direct camera navigation, reliable drag detection, and interruptible Fit/Reset transitions |
| [2026-11-14-calc-parser-port.md](2026-11-14-calc-parser-port.md) | active | Python calc PDF parser / matcher / calc graph ported to `@unloaded/calc-parser` (TS, pdf.js) with Python parity tests; not wired into the UI yet |
| [2026-11-14-ui-review.md](2026-11-14-ui-review.md) | done | Inspector visibility, panel/graph gestures, honest missing data, document filters/revisions, and keyboard controls |
| [2026-11-14-data-consolidation.md](2026-11-14-data-consolidation.md) | done | All IFC and JSON app data (samples + test fixtures) moved into one `data/` folder |
| [2026-11-14-drag-drop-import.md](2026-11-14-drag-drop-import.md) | done | Drop `.ifc` / `.json` anywhere on the window to load as DB A, or onto the Compare target as DB B |
| [2026-11-14-git-lfs-setup.md](2026-11-14-git-lfs-setup.md) | done | PDFs moved to Git LFS; `setup.md` added with clone/LFS/install instructions |
