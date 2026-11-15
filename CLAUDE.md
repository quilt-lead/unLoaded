# Project instructions

The project mission below is the source of truth for product direction. Every design, architecture, and UI decision should be consistent with it. If a request conflicts with the mission, point out the conflict before proceeding.

@mission.md

# UI skills

UI quality is a core part of the mission, so the project vendors UI skills in [.claude/skills/](.claude/skills/) (sources and licenses: [.claude/skills/SOURCES.md](.claude/skills/SOURCES.md)). Use them for any UI work:

- **frontend-design** ([SKILL.md](.claude/skills/frontend-design/SKILL.md)): load before designing a new view or restyling an existing one. Plan the tokens (color, type, layout), check the plan against the brief, then build. This is an engineering tool for structural engineers: favor clarity, density, and legibility of calculations and element data over marketing-page treatments.
- **frontend-ui-engineering** ([SKILL.md](.claude/skills/frontend-ui-engineering/SKILL.md)): load when building or changing React components. Covers component structure, state, accessibility (WCAG 2.1 AA), and loading/empty/error states.
- **react-best-practices** ([SKILL.md](.claude/skills/react-best-practices/SKILL.md)): load when writing or reviewing React code. This app is React + TypeScript on Vite, not Next.js, so skip the `server-*` rules and Next-specific advice.
- **web-design-guidelines** ([SKILL.md](.claude/skills/web-design-guidelines/SKILL.md)): run as a review pass on finished UI code before calling UI work done.

# Agent handoff notes

Before starting work, read [docs/agents/](docs/agents/README.md): findings, decisions, gotchas and the files in flight from earlier sessions. Before handing off, add or update a note there, following its conventions.
## Architecture & Recent Changes Summary

Full description: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). In short:

### 1. Frontend only, four views (`React + TypeScript + Tailwind + Three.js`)
- No server. Element Graph and Calculation Graph (`src/components/RadialGraphCanvas.tsx`), 3D model with the
  real IFC meshes via web-ifc (`src/components/Structural3DViewer.tsx`, `src/components/three/ifcViewer.ts`;
  element-graph boxes when there is no IFC), PDF calcs with highlighted evidence (`src/components/DocumentBrowser.tsx`,
  `src/components/pdf/`), and the inspector with review decisions and impact (`src/components/PropertyInspector.tsx`).

### 2. Data: one element graph, one calc engine, one merge
- Models (`.ifc`, serialized element graph, ModelInput, legacy BIM JSON via `src/loaders/legacyBimJson.ts`) become an
  `ElementGraph` (`packages/ifc-parser`, `packages/element-graph`); `src/loaders/elementGraphToBim.ts` is the only
  ElementGraph → view adapter.
- All IFC and JSON sample models and test fixtures live in `data/` (see `data/README.md`); `scripts/copy-assets.mjs`
  copies the ones **Load sample** needs into `public/samples/`.
- Calc package PDFs go through `packages/calc-mapper` in a Web Worker (`src/engine/`); `src/data/loadProject.ts` is the
  only engine → view adapter. `src/data/mergeProject.ts` joins the two by GlobalId.
- Projects live in IndexedDB (`src/data/projectStore.ts`: revisions, element graphs, extractions, mapping runs, the
  append-only decision log), with an in-memory fallback; a whole project saves to / opens from one file.

### 3. Namable Groups & Whole-Group Selection (`RadialGraphCanvas.tsx`, `PropertyInspector.tsx`)
- Multi-selected nodes (`Shift + Click`) can be clustered into visual groups (`Ctrl+G` / `Cmd+G`).
- Clicking either a group's dashed boundary hull or its header name pill selects all member elements simultaneously (with `Shift + Click` toggle support) and frames them in 3D.
- Groups can be renamed inline directly on the canvas (double-click pill or click `✎`) or from the Property Inspector.

### 4. Revision diff (`HeaderBar.tsx`, `FilterBar.tsx`, `RevisionPanel.tsx`, `Structural3DViewer.tsx`, `PropertyInspector.tsx`, `DocumentBrowser.tsx`)
- Pick a base (A) and a compare (B) model revision to enter **DIFF MODE**; **Swap A↔B** reverses it.
- The one diff is `diffGraphs` in `packages/calc-mapper` (key join on GlobalId + content hash, per-field before → after).
  Elements are `+ Added` (emerald), `~ Modified` (amber), `- Removed` (crimson) or `Unchanged` (slate) across the
  Element Graph, the 3D model (elements only in the other revision drawn as ghosts), the inspector's before → after
  cards and the PDF list badges. Legacy demo JSON goes through the same diff.
