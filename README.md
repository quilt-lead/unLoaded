# Structural Calculation & Element Graph Viewer (React + TypeScript)

Visualizes **structural engineering calculations (PDFs)** and maps them bidirectionally onto **structural BIM elements** (beams, columns, slabs, shear walls, connections, fasteners/bolts, foundations) across **Element Graph**, **Calculation Graph**, **3D Structural Model**, and **PDF Revision Browser** views.

## Views & Core Capabilities
1. **Element Graph (`element-graph`):** Radial topological graph of structural elements & connectivity (`Beam <-> Connection <-> Column`, `Shift + Click` multi-select, `Ctrl+G` grouping, center-to-center wires).
2. **Calculation Graph (`calculation-graph`):** Graph of structural calculation types (`Beam Sizing Calcs`, `Column Sizing Calcs`, `Connection & Fastener Calcs`, `Slab & Punching Shear Calcs`, `Foundation & Geotech Calcs`) and PDF calculation packages—clicking any calculation node highlights its mapped structural elements in the 3D viewport and inspector.
3. **3D Structural Model (`3d` + Floating/Dockable HUD):** Synchronized Three.js WebGL building viewer with demand/capacity utilization heatmap and zoom-to-selection.
4. **PDF Calculation & Version Browser (`docs`):** Supports 1:1 calculation PDFs, multi-element PDF packages, and revision switching (`Rev A`, `Rev B`, `Rev C`, `Rev D`).
5. **Pluggable IFC & BIM Converters (`src/loaders/parsers.ts`):** `.ifc` via web-ifc, plus `.json` ModelInput, serialized element graphs and legacy BIM graphs (see below).
6. **Diff Mode:** load a Base DB (A) and a Compare DB (B) to see added / modified / removed elements across all views.

## Decoupled Data Architecture
- The application starts with an **empty workspace**—no demo model is auto-loaded at runtime.
- Click **Import IFC / DB** in the top-right header to load any `.ifc` (`ISO-10303-21` STEP) model or `.json` structural graph.
- All IFC and JSON data lives in one folder, [`data/`](data/README.md). Import any file there manually; the same files back the tests.

## Data pipeline

```
.ifc ──> @unloaded/ifc-parser ──> ModelInput ──> @unloaded/element-graph ──> ElementGraph ──> elementGraphToBim ──> BimNode/BimLink ──> UI
             (web-ifc)          (parser contract)   buildGraph + inference     (domain model)   (src/loaders)          (view model)
```

- `packages/ifc-parser` reads what the IFC states: elements, marks, profiles, materials, levels, bbox/axis geometry and explicit relations.
- `packages/element-graph` is the topology source of truth. Elements and connections are nodes. Edges are `connects` (physical), `supports` (directed load path: `a` is supported by `b`) and `part_of`. Missing connectivity is inferred from geometry and recorded as evidence.
- `src/loaders/elementGraphToBim.ts` maps it onto the UI view model: kinds become categories, column-on-column chains become column stacks, bboxes become 3D boxes (feet, Y-up), `supports` edges become directed `load-path` links that the load-path trace follows exactly, and node `links` of kind `calc` become documents.
- Legacy hand-authored BIM graphs (`{ projectName, nodes, links }`, e.g. `data/bim-database.json`) are loaded directly into the view model.

A new format (Revit, Tekla, ETABS, ...) only needs to emit a `ModelInput`. See `packages/*/README.md`.

## Quick Start
```bash
npm install      # npm workspaces; postinstall copies web-ifc.wasm into public/
npm run dev
npm test         # app adapter tests + package tests
npm run smoke    # IFC -> element graph summary in Node
```
