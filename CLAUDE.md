# Project instructions

The project mission below is the source of truth for product direction. Every design, architecture, and UI decision should be consistent with it. If a request conflicts with the mission, point out the conflict before proceeding.

@mission.md

## Architecture & Recent Changes Summary

### 1. Dual-Graph & Multi-View Structural Workspace (`React + TypeScript + Tailwind + Three.js`)
- **Element Graph (`src/App.tsx`, `src/components/RadialGraphCanvas.tsx`):** Radial topological visualization of structural BIM elements (`IfcBeam`, `IfcColumn`, `IfcSlab`, `IfcWall`, `IfcMember`, `IfcFastener`, `IfcFooting`, `IfcPile`) with center-to-center spline wiring, physical connectivity inspection (`getDirectConnectivityNeighbors`), and load-path tracing.
- **Calculation Graph (`buildCalculationGraph` in `src/utils/graphEngine.ts`):** Synthesizes a parallel graph grouping engineering calculations by type (`Beam Sizing Calcs`, `Column Sizing Calcs`, `Connection & Fastener Calcs`, `Slab & Punching Shear Calcs`, `Shear Wall & Lateral Calcs`, `Foundation & Geotech Calcs`) and linking each PDF calculation package bidirectionally to its physical structural elements.
- **3D Structural Model (`src/components/Structural3DViewer.tsx`):** Synchronized Three.js WebGL building viewer with demand/capacity utilization heatmaps, zoom-to-selection, and floating/dockable HUD panels (`src/components/DockableHudPanel.tsx`).
- **PDF Calculation & Revision Browser (`src/components/DocumentBrowser.tsx`):** Supports 1:1 calculation PDFs, multi-element PDF packages, multi-version revision tabs (`Rev A`, `Rev B`, etc.), and one-click jumps back to mapped elements in the graphs and 3D model.

### 2. Decoupled Manual Data Ingestion (`src/utils/ifcParser.ts`)
- Removed auto-loaded demo JSON from `public/data/` so the workspace starts clean (`No Model Loaded`) until the user manually imports a file.
- Pluggable `BIM_PARSERS` registry supports direct `.ifc` (`ISO-10303-21`) STEP files as well as `.json` structural BIM graphs (reference sample datasets are stored outside the app bundle in `sample-data/`).

### 3. Namable Groups & Whole-Group Selection (`RadialGraphCanvas.tsx`, `PropertyInspector.tsx`)
- Multi-selected nodes (`Shift + Click`) can be clustered into visual groups (`Ctrl+G` / `Cmd+G`).
- Clicking either a group's dashed boundary hull or its header name pill selects all member elements simultaneously (with `Shift + Click` toggle support) and frames them in 3D.
- Groups can be renamed inline directly on the canvas (double-click pill or click `✎`) or from the Property Inspector.

### 4. Dual-Database Diff Comparison & Model Swap (`graphEngine.ts`, `HeaderBar.tsx`, `FilterBar.tsx`, `Structural3DViewer.tsx`, `PropertyInspector.tsx`, `DocumentBrowser.tsx`)
- Users can load a **Base Database (DB A)** via **Import IFC / DB** and a **Compare Database (DB B)** via **Compare DB** to enter **DIFF MODE**, with a **Swap A↔B** button in the header to reverse comparison direction at any time.
- `computeDatabaseDiff()` classifies elements into `+ Added` (emerald), `~ Modified` (amber — tracking section profile, material strength, axial load, utilization, floor level, and mapped PDF revision changes), `- Removed` (crimson), and `Unchanged` (slate), synchronized across the Element Graph, 3D Model (with translucent crimson ghosts for removed members), field-by-field `Before → After` Inspector cards, and PDF revision badges.
