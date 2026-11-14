# Structural Calculation & Element Graph Viewer (React + TypeScript)

Visualizes **structural engineering calculations (PDFs)** and maps them bidirectionally onto **structural BIM elements** (beams, columns, slabs, shear walls, connections, fasteners/bolts, foundations) across **Element Graph**, **Calculation Graph**, **3D Structural Model**, and **PDF Revision Browser** views.

## Decoupled Data Architecture
- The application starts with an **empty workspace**—no demo JSON is bundled into `public/` or auto-loaded at runtime.
- Click **Import IFC / DB** in the top-right header to manually load any `.ifc` (`ISO-10303-21` STEP) model or `.json` structural graph.
- An optional reference dataset is kept outside the bundle in `sample-data/bim-database.json` if you want a sample file to upload manually.

## Quick Start
```bash
npm install
npm run dev
```
