# Project instructions

The project mission below is the source of truth for product direction. Every design, architecture, and UI decision should be consistent with it. If a request conflicts with the mission, point out the conflict before proceeding.

@mission.md

# UI skills

UI quality is a core part of the mission, so the project vendors UI skills in [.claude/skills/](.claude/skills/) (sources and licenses: [.claude/skills/SOURCES.md](.claude/skills/SOURCES.md)). Use them for any UI work:

- **frontend-design** ([SKILL.md](.claude/skills/frontend-design/SKILL.md)): load before designing a new view or restyling an existing one. Plan the tokens (color, type, layout), check the plan against the brief, then build. This is an engineering tool for structural engineers: favor clarity, density, and legibility of calculations and element data over marketing-page treatments.
- **frontend-ui-engineering** ([SKILL.md](.claude/skills/frontend-ui-engineering/SKILL.md)): load when building or changing React components. Covers component structure, state, accessibility (WCAG 2.1 AA), and loading/empty/error states.
- **react-best-practices** ([SKILL.md](.claude/skills/react-best-practices/SKILL.md)): load when writing or reviewing React code. This app is React + TypeScript on Vite, not Next.js, so skip the `server-*` rules and Next-specific advice.
- **web-design-guidelines** ([SKILL.md](.claude/skills/web-design-guidelines/SKILL.md)): run as a review pass on finished UI code before calling UI work done.

# Setup

Before cloning, installing, running tests, or adding data files, read [setup.md](setup.md). PDFs are stored in Git LFS: a checkout without LFS has pointer stubs instead of PDFs, and the calc-parser tests fail.

# Agent handoff notes

Before starting work, read [docs/agents/](docs/agents/README.md): findings, decisions, gotchas and the files in flight from earlier sessions. Before handing off, add or update a note there, following its conventions.
## Architecture & Recent Changes Summary

### 1. Dual-Graph & Multi-View Structural Workspace (`React + TypeScript + Tailwind + Three.js`)
- **Element Graph (`src/App.tsx`, `src/components/RadialGraphCanvas.tsx`):** Radial topological visualization of structural BIM elements (`IfcBeam`, `IfcColumn`, `IfcSlab`, `IfcWall`, `IfcMember`, `IfcFastener`, `IfcFooting`, `IfcPile`) with center-to-center spline wiring, physical connectivity inspection (`getDirectConnectivityNeighbors`), and load-path tracing.
- **Calculation Graph (`buildCalculationGraph` in `src/utils/graphEngine.ts`):** Synthesizes a parallel graph grouping engineering calculations by type (`Beam Sizing Calcs`, `Column Sizing Calcs`, `Connection & Fastener Calcs`, `Slab & Punching Shear Calcs`, `Shear Wall & Lateral Calcs`, `Foundation & Geotech Calcs`) and linking each PDF calculation package bidirectionally to its physical structural elements.
- **3D Structural Model (`src/components/Structural3DViewer.tsx`):** Synchronized Three.js WebGL building viewer with demand/capacity utilization heatmaps, zoom-to-selection, and floating/dockable HUD panels (`src/components/DockableHudPanel.tsx`).
- **PDF Calculation & Revision Browser (`src/components/DocumentBrowser.tsx`):** Supports 1:1 calculation PDFs, multi-element PDF packages, multi-version revision tabs (`Rev A`, `Rev B`, etc.), and one-click jumps back to mapped elements in the graphs and 3D model.

### 2. Decoupled Manual Data Ingestion (`src/loaders/parsers.ts`)
- Removed auto-loaded demo JSON (previously in `public/data/`) so the workspace starts clean (`No Model Loaded`) until the user manually imports a file.
- Async `BIM_PARSERS` registry: `.ifc` goes through `packages/ifc-parser` (web-ifc) → `packages/element-graph` → `src/loaders/elementGraphToBim.ts`; `.json` is dispatched on content (serialized element graph, ModelInput, or legacy BIM graph via `src/loaders/legacyBimJson.ts`). All IFC and JSON data (samples and test fixtures) lives in one folder, `data/` (see `data/README.md`), outside the app bundle. Details: `docs/agents/2026-11-14-parser-graph-merge.md`.

### 3. Namable Groups & Whole-Group Selection (`RadialGraphCanvas.tsx`, `PropertyInspector.tsx`)
- Multi-selected nodes (`Shift + Click`) can be clustered into visual groups (`Ctrl+G` / `Cmd+G`).
- Clicking either a group's dashed boundary hull or its header name pill selects all member elements simultaneously (with `Shift + Click` toggle support) and frames them in 3D.
- Groups can be renamed inline directly on the canvas (double-click pill or click `✎`) or from the Property Inspector.

### 4. Dual-Database Diff Comparison & Model Swap (`graphEngine.ts`, `HeaderBar.tsx`, `FilterBar.tsx`, `Structural3DViewer.tsx`, `PropertyInspector.tsx`, `DocumentBrowser.tsx`)
- Users can load a **Base Database (DB A)** via **Import IFC / DB** and a **Compare Database (DB B)** via **Compare DB** to enter **DIFF MODE**, with a **Swap A↔B** button in the header to reverse comparison direction at any time.
- `computeDatabaseDiff()` classifies elements into `+ Added` (emerald), `~ Modified` (amber — tracking section profile, material strength, axial load, utilization, floor level, and mapped PDF revision changes), `- Removed` (crimson), and `Unchanged` (slate), synchronized across the Element Graph, 3D Model (with translucent crimson ghosts for removed members), field-by-field `Before → After` Inspector cards, and PDF revision badges.
