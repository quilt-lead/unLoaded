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
| [2026-11-15-plan-view.md](2026-11-15-plan-view.md) | in review | 2D plan tab in the model panel: framing plan per floor level (SVG from element geometry), level stepping, shared 3D/plan emphasis rules |
| [2026-11-15-default-panel-docking.md](2026-11-15-default-panel-docking.md) | done | Inspector defaults to the left dock and 3D model to the right dock; navbar shadow no longer overlaps filters |
| [2026-11-15-theme-aware-favicon.md](2026-11-15-theme-aware-favicon.md) | done | Adds light/dark SVG favicons selected by the operating system color preference |
| [2026-11-15-graph-controls-and-upward-trace.md](2026-11-15-graph-controls-and-upward-trace.md) | done | Restores type/review/confidence coloring and the data-gated utilization heatmap, removes the top-right reset control, and makes upward traces exhaustive |
| [2026-11-15-harborview-synthetic-calcs.md](2026-11-15-harborview-synthetic-calcs.md) | active | Harborview sample: generator (IFC rev 1+2, 97 calc PDFs, ground truth) from the demo bundles, all Harborview files in data/harborview/, a "Harborview sample" menu entry; engine scores 100% on it |
| [2026-11-15-selection-dimming.md](2026-11-15-selection-dimming.md) | done | Refreshes 3D material shaders when transparency changes so deselected elements reliably dim |
| [2026-11-15-model-bundle.md](2026-11-15-model-bundle.md) | done | `unloaded.model-bundle`: element graph + calc graph in one JSON; Harborview demo converted (demo calcs now in the Calculation Graph, superseding D19); legacy JSON loader retired to a converter script; Export model + calc graph |
| [2026-11-15-current-ui-prod-integration.md](2026-11-15-current-ui-prod-integration.md) | blocked | Repairs the UI merge onto prod's project/revision model while retaining the latest palette, selection, and workspace-view behavior; branch pushed, PR creation needs authenticated GitHub access |
| [2026-11-15-mission-readiness-review.md](2026-11-15-mission-readiness-review.md) | done | Mission gap review: multi-PDF/version workflows, real-document segmentation, connectivity reliability, and UI acceptance coverage |
| [2026-11-14-parser-graph-merge.md](2026-11-14-parser-graph-merge.md) | done | Merged the IFC parser and element-graph packages into the React UI via an adapter |
| [2026-11-14-calc-engine-integration.md](2026-11-14-calc-engine-integration.md) | active | Merges the hackathon calc engine (frontend only: calc-mapper, move-impact, provenance contract) and extraction ideas into main; decision log D1-D27 |
| [2026-11-14-font-update.md](2026-11-14-font-update.md) | done | Switched the app to Apercu across the global styles and canvas text overrides |
| [2026-11-14-3d-controls.md](2026-11-14-3d-controls.md) | done | Direct camera navigation, reliable drag detection, and interruptible Fit/Reset transitions |
| [2026-11-14-ui-review.md](2026-11-14-ui-review.md) | done | Inspector visibility, panel/graph gestures, honest missing data, document filters/revisions, and keyboard controls |
| [2026-11-14-column-stack-tracing.md](2026-11-14-column-stack-tracing.md) | done | Trace load paths through legacy column stacks to their lower supports |
| [2026-11-14-node-color-palette.md](2026-11-14-node-color-palette.md) | done | Unique graph category colors, a gray center node, and matching 3D base colors |
| [2026-11-14-data-consolidation.md](2026-11-14-data-consolidation.md) | done | All IFC and JSON app data (samples + test fixtures) moved into one `data/` folder |
| [2026-11-14-drag-drop-import.md](2026-11-14-drag-drop-import.md) | done | Drop a model, calc PDF or project file anywhere on the window to add it; or onto the Compare target to diff a new model revision against the current one |
| [2026-11-14-git-lfs-setup.md](2026-11-14-git-lfs-setup.md) | done | PDFs moved to Git LFS; `setup.md` added with clone/LFS/install instructions |
| [2026-11-14-phase1-integration.md](2026-11-14-phase1-integration.md) | done | Integrates PR #4 with prod (PR #5, #7, #8, #10 + LFS PDFs merges; calc-parser retired into calc-mapper; copyright guard removed (PDFs allowed); Windows test fixes) |
| [2026-11-14-phase2-calc-sets.md](2026-11-14-phase2-calc-sets.md) | active | Calc sets: one large PDF, one PDF per calc, or a mix; per-document revisions, placement of uploads, calc revision diff |
| [2026-11-14-mcp-server.md](2026-11-14-mcp-server.md) | in review | Local stdio MCP server (`packages/mcp-server`) on calc-mapper: query tools, findings / groups / revision compare / move_column, project files (v2 calc sets), append-only calc-mapper decision log, several PDFs as one calc set, engine boundary in `src/engine.ts` |
