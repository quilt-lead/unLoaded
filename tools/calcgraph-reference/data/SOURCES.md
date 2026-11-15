# Data sources

Every file in this tooling folder that came from outside, with where it came from and its licence.
No customer file (OneDrive or elsewhere) is in this repo.

## Downloaded

Nothing. (The buildingSMART sample IFC this folder used to carry is a byte-identical duplicate of
`packages/ifc-parser/test/fixtures/Building-Structural-IFC4.ifc`, which keeps its provenance in that
folder's SOURCES.md.)

## Generated (not downloaded)

`tools/calcgraph-reference/data/synthetic/` is produced by `uv run python -m synth.generate` (run from `tools/calcgraph-reference/`;
gitignored, byte-stable for a given seed). Everything in it - model, calc package, numbers,
ground truth - is synthetic.

## Libraries (installed, not vendored)

| Tool | Use | Licence |
|---|---|---|
| IfcOpenShell 0.9 | write the synthetic IFC | LGPL-3.0 |
| PyMuPDF 2.1 | write the synthetic calc package (tooling only; not in the app) | AGPL-3.0 (commercial licence from Artifex otherwise) |
| PyNite (PyNiteFEA 3.2) | member forces for the synthetic calcs | MIT |
| matplotlib (mathtext) | Mathcad-style formula images, scanned hand-calc raster | matplotlib licence (PSF-style, BSD-compatible) |
| NumPy, Pillow | geometry maths, image noise | BSD-3 / MIT-CMU (HPND) |
| DejaVu Sans (bundled with matplotlib) | font of the rasterised hand calc | Bitstream Vera / DejaVu licence (free) |
