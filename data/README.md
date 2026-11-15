# data/

The single home for all IFC and JSON model data: sample models you import into the app by hand
(**Import IFC / DB**, **Compare DB**) and the fixtures the tests read. Nothing here is bundled or
auto-loaded; the app starts with an empty workspace.

| File | Format | Used by |
|---|---|---|
| `Building-Structural-IFC4.ifc` | IFC4 (buildingSMART sample) | `packages/ifc-parser` tests, `src/loaders/elementGraphToBim.test.ts`, `npm run smoke`, `packages/ifc-parser/scripts/dump.ts` |
| `tiny-frame-mm.ifc` | IFC4, mm units, hand-written | `packages/ifc-parser/test/tiny.test.ts` |
| `simple-frame.json` | `ModelInput` | `packages/element-graph` tests, `src/loaders/elementGraphToBim.test.ts` |
| `bim-database.json` | legacy BIM graph (`{ projectName, nodes, links }`) | manual import sample |
| `harborview-tower-rev1-base.json` | legacy BIM graph | Diff Mode sample: load as Base (A) |
| `harborview-tower-rev2-compare.json` | legacy BIM graph | Diff Mode sample: load as Compare (B) |

Tests reference these files by path, so renaming or editing one can break them.
Calculation PDFs are git-ignored (`*.pdf`) and are not kept here.

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
