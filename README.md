# Structural BIM & IFC Radial Graph Viewer

Interactive 2D radial dependency graph, synchronized 3D structural WebGL frame viewer, and structural engineering document/PDF browser.

## Repository Structure

```text
structural-bim-graph-viewer/
├── index.html                 # Main application (Radial Graph + 3D BIM Viewport + Document Browser)
├── data/
│   └── bim-database.json      # Reference 14-story reinforced concrete flat-plate BIM database (IFC 4.3)
├── docs/
│   └── ARCHITECTURE.md        # Data schema, load-path tracing & interaction guide
└── README.md
```

## Quick Start

1. **Run via local HTTP server** (so `fetch('./data/bim-database.json')` loads automatically):
   ```bash
   python3 -m http.server 8080
   ```
   Then open `http://localhost:8080`.
2. **Or open `index.html` directly** (`file://`) and click **Upload DB** in the top-right header to load `data/bim-database.json` (or any custom BIM JSON database).

## Key Features

- **Radial Hierarchy & Infinite Zoom:** Multi-ring radial graph with smooth G2 radial-tangent splines, auto-fitted white node labels, and unrestricted zoom (`Wheel` to zoom, `MMB`/`RMB` drag to pan).
- **Multi-Select & Grouping (`Ctrl+G` / `Cmd+G`):** `Shift + Click` multiple nodes to move them simultaneously, or press `Ctrl+G` to cluster them into a dashed group hull (`GROUP N`).
- **Load Path Tracing & Utilization Heatmap:** Trace upstream/downstream gravity load paths with hop-depth limiting and toggle demand/capacity utilization heatmap coloring across both 2D and 3D views.
- **3D Structural Frame & Document Browser:** Synchronized Three.js 3D structural model (`RMB` orbit, `MMB` pan, `FIT` zoom-to-selection) and mapped engineering calculation/PDF repository.
