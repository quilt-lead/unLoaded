# Structural Calculation & Element Graph Viewer (React + TypeScript)

Visualizes **structural engineering calculations (PDFs)** and maps them bidirectionally onto **structural BIM elements** (beams, columns, slabs, shear walls, connections, fasteners/bolts, foundations) across **Element Graph**, **Calculation Graph**, **3D Structural Model**, and **PDF Revision Browser** views.

## Views & Core Capabilities
1. **Element Graph (`element-graph`):** Radial topological graph of structural elements & connectivity (`Beam <-> Connection <-> Column`, `Shift + Click` multi-select, `Ctrl+G` grouping, center-to-center wires).
2. **Calculation Graph (`calculation-graph`):** Graph of structural calculation types (`Beam Sizing Calcs`, `Column Sizing Calcs`, `Connection & Fastener Calcs`, `Slab & Punching Shear Calcs`, `Foundation & Geotech Calcs`) and PDF calculation packages—clicking any calculation node highlights its mapped structural elements in the 3D viewport and inspector.
3. **3D Structural Model (`3d` + Floating/Dockable HUD):** Synchronized Three.js WebGL building viewer with demand/capacity utilization heatmap and zoom-to-selection.
4. **PDF Calculation & Version Browser (`docs`):** Supports 1:1 calculation PDFs, multi-element PDF packages, and revision switching (`Rev A`, `Rev B`, `Rev C`, `Rev D`).
5. **Pluggable IFC & BIM Converters (`src/utils/ifcParser.ts`):** Supports direct `.ifc` (`ISO-10303-21`) STEP imports across all IFC element classes as well as `.json` BIM graphs.

## Quick Start
```bash
npm install
npm run dev
```
