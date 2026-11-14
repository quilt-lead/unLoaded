# Data sources

Every file in this repo that came from outside, with where it came from and its licence.
No customer file (OneDrive or elsewhere) is in this repo.

## Downloaded

| File | Source | Licence | Fetched |
|---|---|---|---|
| `data/open/Building-Structural-IFC4.ifc` | buildingSMART Sample-Test-Files, `IFC 4.0.2.1 (IFC 4 ADD2 TC1)/Simple-Scene/Building-Structural.ifc`, commit `8832bddc04d8597d69e6a414e5f67a65e8b3b626` - https://github.com/buildingSMART/Sample-Test-Files | CC BY 4.0, (C) buildingSMART International Ltd. (repo LICENSE file) | 2026-11-14 12:39 PM ET, sha256 `903b5a005901397aa2b235daf6a60f46c099eae286cb01c815abf0a341707432` |

Used as a smoke test that the backend ingests a third-party IFC (14 elements, 10 load-path
edges inferred). It has no marks and no matching calc package, so it is not scored.

## Generated (not downloaded)

`data/synthetic/` is produced by `uv run python -m synth.generate` (gitignored, byte-stable for
a given seed). Everything in it - model, calc package, numbers, ground truth - is synthetic.

## Libraries (installed, not vendored)

| Tool | Use | Licence |
|---|---|---|
| IfcOpenShell 0.9 | write the synthetic IFC; read IFC semantics, psets, storeys, geometry | LGPL-3.0 |
| PyMuPDF 2.1 | write the synthetic calc package; read text + word boxes; render evidence pages | AGPL-3.0 (commercial licence from Artifex otherwise) |
| PyNite (PyNiteFEA 3.2) | member forces for the synthetic calcs | MIT |
| matplotlib (mathtext) | Mathcad-style formula images, scanned hand-calc raster | matplotlib licence (PSF-style, BSD-compatible) |
| FastAPI / Starlette / uvicorn | API | MIT / BSD-3 / BSD-3 |
| NumPy, Pillow | geometry maths, image noise | BSD-3 / MIT-CMU (HPND) |
| three.js 0.170 | 3D viewer | MIT |
| web-ifc 0.0.66 | IFC geometry in the browser | MPL-2.0 |
| Vite 6, TypeScript 5.6 | frontend build | MIT / Apache-2.0 |
| DejaVu Sans (bundled with matplotlib) | font of the rasterised hand calc | Bitstream Vera / DejaVu licence (free) |
