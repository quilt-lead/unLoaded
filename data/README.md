# data/

The single home for IFC and JSON model data, plus selected sample calculation PDFs. Model samples can
be imported into the app by hand (**Import IFC / DB**, **Compare DB**); nothing here is bundled or
auto-loaded, and the app starts with an empty workspace.

| File | Format | Used by |
|---|---|---|
| `Building-Structural-IFC4.ifc` | IFC4 (buildingSMART sample) | `packages/ifc-parser` tests, `src/loaders/elementGraphToBim.test.ts`, `npm run smoke`, `packages/ifc-parser/scripts/dump.ts` |
| `tiny-frame-mm.ifc` | IFC4, mm units, hand-written | `packages/ifc-parser/test/tiny.test.ts` |
| `simple-frame.json` | `ModelInput` | `packages/element-graph` tests, `src/loaders/elementGraphToBim.test.ts` |
| `harborview/harborview-tower-rev1-base.bundle.json` | model bundle (`unloaded.model-bundle`): element graph + demo calc graph | **Harborview A/B demo** (rev A), `src/loaders/harborviewBundle.test.ts`, the Harborview sample generator |
| `harborview/harborview-tower-rev2-compare.bundle.json` | model bundle | **Harborview A/B demo** (rev B), same test, same generator |
| `harborview/harborview-rev{1,2}.ifc`, `harborview/calcs/**.pdf` | IFC4 + calc PDFs (generated, committed; PDFs in Git LFS) | **Harborview sample** (rev 1 IFC + 82 calc PDFs incl. 4 loading calcs, rev 2 IFC + 23 reissued / new PDFs), listed in `harborview/manifest.json` |
| `harborview/ground_truth.json` | what the calc engine should find in the sample | `tools/calcgraph-reference/scripts/evaluate_harborview.py` |
| `harborview/harborview-demo-calcs-preview.pdf` | synthetic five-page calc preview (superseded by the Harborview sample) | `packages/calc-mapper/test/harborview-preview.test.ts` |

Tests reference these files by path, so renaming or editing one can break them.

The Harborview bundles are **demo data**: their calcs are invented (no PDF behind them) and the app labels
them so. `harborview-demo-calcs-preview.pdf` is an earlier four-calculation preview with matching model marks; whitespace in marks is
removed in PDF tokens (for example `CapA1`) so the current matcher recognizes the full mark. Category
differences can still lower a match to a cross-reference. The PDF deliberately
contains no design loads, capacities, code checks, or engineering conclusions. It is not for design,
construction, permitting, or reliance. Regenerate it with
`python -m synth.harborview_preview` from `tools/calcgraph-reference/` (requires the declared PyMuPDF dependency).

The bundles were converted from Noah's legacy `{ projectName, nodes, links }` JSON with
`node scripts/convert-legacy-demo.ts <legacy.json> <out.bundle.json> "<revision label>"`; the legacy files are
in git history (`git log --all -- data/harborview-tower-rev1-base.json`). The app no longer opens the legacy format.
The bundle format is described in `packages/calc-mapper/src/bundle.ts`.

The **Harborview sample** is the same tower with a real model and real (synthetic) calcs: every file in
`harborview/` except the two bundles is generated from the bundles by
`cd tools/calcgraph-reference && uv run python -m synth.harborview.generate` (byte-stable; `--check` proves it). Regenerate
it after changing a bundle or the generator, then run `npm run assets`. PDFs are stored in Git LFS (`.gitattributes`).

All PDFs are managed by Git LFS (`.gitattributes`); only intentionally selected samples belong in this folder.

## Provenance

### Building-Structural-IFC4.ifc

- Source: buildingSMART Sample-Test-Files, `IFC 4.0.2.1 (IFC 4 ADD2 TC1)/Simple-Scene/Building-Structural.ifc`
- Repository: https://github.com/buildingSMART/Sample-Test-Files
- Licence: CC BY 4.0, (c) buildingSMART International Ltd.
- Copied unchanged from `prototyping/calc-graph/data/open/Building-Structural-IFC4.ifc`.

### tiny-frame-mm.ifc

Hand-written for this repo (no third-party content). IFC4, millimetre units, one storey at 3000 mm,
an HEA 200 column, a 200x400 rectangular beam, an IfcPlate ("Shear tab", no geometry), property sets
with marks, a typed column with a type-level pset, one IfcRelConnectsElements.
