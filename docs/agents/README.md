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
| [2026-11-14-calc-engine-integration.md](2026-11-14-calc-engine-integration.md) | active | Merges the hackathon calc engine (frontend only: calc-mapper, move-impact, provenance contract) and extraction ideas into main; decision log D1-D27 |
| [2026-11-14-font-update.md](2026-11-14-font-update.md) | done | Switched the app to Apercu across the global styles and canvas text overrides |
| [2026-11-14-3d-controls.md](2026-11-14-3d-controls.md) | done | Direct camera navigation, reliable drag detection, and interruptible Fit/Reset transitions |
| [2026-11-14-ui-review.md](2026-11-14-ui-review.md) | done | Inspector visibility, panel/graph gestures, honest missing data, document filters/revisions, and keyboard controls |
| [2026-11-14-data-consolidation.md](2026-11-14-data-consolidation.md) | done | All IFC and JSON app data (samples + test fixtures) moved into one `data/` folder |
| [2026-11-14-phase1-integration.md](2026-11-14-phase1-integration.md) | active | Integrates PR #4 with prod (PR #5 + #7 merges, copyright allowlist, Windows test fixes) for merge into prod |
