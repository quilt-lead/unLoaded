# Data sources

Every file in this repo that came from outside, with where it came from and its licence.
No customer file (OneDrive or elsewhere) is in this repo.

## Downloaded

| File | Source | Licence | Fetched |
|---|---|---|---|
| `data/open/Building-Structural-IFC4.ifc` | buildingSMART Sample-Test-Files, `IFC 4.0.2.1 (IFC 4 ADD2 TC1)/Simple-Scene/Building-Structural.ifc`, commit `8832bddc04d8597d69e6a414e5f67a65e8b3b626` - https://github.com/buildingSMART/Sample-Test-Files | CC BY 4.0, (C) buildingSMART International Ltd. (repo LICENSE file) | 2026-11-14 12:39 PM ET, sha256 `903b5a005901397aa2b235daf6a60f46c099eae286cb01c815abf0a341707432` |

Used as a smoke test that the backend ingests a third-party IFC (14 elements, 10 load-path
edges inferred). It has no marks and no matching calc package, so it is not scored.

### AISC shapes subset (committed, not MIT)

| File | Source | Licence | Fetched |
|---|---|---|---|
| `synth/v2/data/aisc_v16_subset.csv` | Subset (W8..W36 and square HSS 4..12; 300 shapes, sha256 `2c4090e1cb6987a7364634335c96e94f89177cf43a1b94c9c595a10ed1b6a54e`) of the AISC Shapes Database v16.0, obtained via `data/aisc-v16.csv` in https://github.com/cmccomb/structural-shapes | AISC data, (C) American Institute of Steel Construction - NOT MIT. The MIT licence in that repository covers only the repository author's code, not the AISC data. Redistribution terms are AISC's, not an open licence; kept committed by project decision (public hackathon repo) | committed with the synth v2 designed building (595bd7c) |

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

## API specifications (codegen inputs for the mock platform adapters)

`backend/calcgraph/platforms/` serves SYNTHETIC data only; these specs give its raw objects their
field names and types. Regenerate with `uv run python scripts/gen_platform_models.py [--refresh]`
(openapi-python-client 0.29.1, MIT; optional dependency group `codegen`). The full Procore document
is cached in `data/store/specs/` (gitignored); only the extracted subset and the generated models are
in the repo.

| Spec | Source | Licence | Fetched | Used for |
|---|---|---|---|---|
| Procore REST API OpenAPI 3.0 ("Procore Rest API Documentation" v2.0, x-created-at 2026-11-13T21:00:38.939Z, 2,305 paths, 63,517,031 bytes, sha256 `bb8e062a7f8edb06d95f95dc9a26b64a57f59aff1b2b57375f74a586b9e2ef4d`) | https://developers.procore.com/api/v1/resource_groups/full_oas?version=1 (the "download OAS" endpoint of developers.procore.com) | No licence stated in the document; governed by Procore's developer terms (developers.procore.com). Only an 8-schema subset (`platforms/generated/procore_subset.openapi.json`, examples stripped) and the models generated from it are committed | 2026-11-14 3:31 PM ET | `platforms/generated/procore_rest/` (models + types only, no HTTP client): Submittal, Rfi, ChangeEvent, ChangeOrderPackage, BudgetLineItem, CostCode, Task, Drawing |
| Autodesk APS OpenAPI specs | https://github.com/autodesk-platform-services/aps-sdk-openapi | Apache-2.0 | checked 2026-11-14 (not downloaded) | Nothing: the repo has no ACC Submittals, RFIs, Cost Management or Sheets spec, so `autodesk_build.py` keeps hand shapes from the APS reference pages |
