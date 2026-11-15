# Harborview synthetic calc package

- **Status:** active (planning; open questions below need an answer before step 1)
- **Branch:** not cut yet (proposed `cs/harborview-calcs` from `prod`)
- **Owned files (planned):** `tools/calcgraph-reference/synth/harborview/` (new), `tools/calcgraph-reference/data/harborview/`
  (generated, gitignored), `scripts/copy-assets.mjs` (sample list), the **Load sample** entry point in the app.
- **Working files:** none yet.

## Goal

A calc package (PDFs) that matches the Harborview tower in `data/harborview-tower-rev{1,2}-*.json`, so the calc graph,
element ↔ calc links and PDF evidence can be demoed on the same building as the Diff Mode demo. Today Harborview's calcs are
only `documents` stubs (shown as "demo data", `DEMO_DOCUMENT_LINK`); the only real calc sample is the unrelated v1
synthetic building (`tools/calcgraph-reference/synth/`, 3 storeys, metric grid).

## Why PDFs are required

The calc graph only exists as output of `packages/calc-mapper`, whose input is PDF text (`CalcPage[]`: text + word boxes).
Segmentation (`segment.ts`) splits pages into calcs by title; the matcher (`matcher.ts`) links elements by finding their
marks as tokens in calc text. Writing a mapping run directly into a project file would bypass the engine and leave the
PDF view empty, so it was rejected.

## What the Harborview data gives us

- Rev 1: 420 element instances on a 5×4 grid (A–E × 1–4), L01–L05 plus foundation. 20 pile caps, 20 piles,
  100 connections (20 base plates, 80 shear tabs), 5 slabs, 10 core walls, 10 braces, 100 column segments (20 stacks
  × 5), 155 beams (40 W18x46 girders, 40 W21x62 girders, 75 W16x31 infill).
- 78 calc stubs (sheet number, title, code, rev, page count, summary), 664 claimed pages in total. Grouping varies:
  one per grid (S-102 pile cap + caisson), one per stack (S-501), one per level (S-20x slabs, S-40x connections,
  S-312.. infill), one per grid line per level (S-302 girders), one for all 20 base plates (S-405), one each for core walls
  (S-601) and braces (S-605).
- Rev 2: adds L06 (70 elements), removes girder `G-B2C2-L02` and its connection, changes loads on 60 elements.
  Calc stubs: 6 go to Rev B (S-601, S-605, three S-302 grid-line-2 calcs, S-204) and 7 are new (L06 calcs).
- Marks are unique, but 65 contain a space (`Cap A1`, `Pile P-A1`, `Slab L01`, `Core N-L01`, `Brace A-L01`). The matcher's
  token regex (`[A-Z0-9]+(?:[-./][A-Z0-9]+)*`) splits these, so they never match exactly. See open question 1.
- Sizes not in the v1 `synth/shapes.py` table: W14x132, W18x46, W21x62, HSS8x8x1/2. Add them as nominal values, the
  same as the existing table (the full AISC table is gitignored under D22).

## Plan

1. **Building from JSON** (`synth/harborview/building.py`): read the two Harborview JSONs and produce the v1 `El` model.
   Element key = legacy `id` (stable across revs, so GlobalIds stay stable via uuid5). `design_calc` = the stub's doc id.
   Load path from the JSON links plus grid topology. No analysis: forces and utilisations come from the JSON
   (`axialLoadKn`, `utilization`), so calc numbers match what the inspector shows.
2. **IFC writer** (if question 2 = yes): reuse `synth/ifc_common.py` to write `harborview_rev1.ifc` / `harborview_rev2.ifc`
   from `pos3d` / `size3d` (feet → metres, the same transform as `legacyBimJson.ts geometryOf`), with Mark, section and
   grade psets. Joints and pile caps as boxes, members as extruded profiles.
3. **Calc templates** (`synth/harborview/calc_pdf.py`), one per calc family (pile cap/caisson, slab/diaphragm, girder line,
   infill, connections per level, base plates, column stack, core wall, braced frame). Each calc page carries the sheet
   header, the stub's title (which must pass `segment.ts TITLE_KW`), the design code, a member/joint schedule naming every
   mark it designs with its size and demand/capacity, plus load-cue lines ("reactions from G-B2C2-L02") naming the members
   it only takes loads from. This gives a calc graph with real calc → calc edges (slab → infill → girder → connection →
   column stack → base plate → pile cap).
4. **Package layout:** write per-calc PDFs and one combined PDF from the same pages (the mission allows both), plus
   Rev B PDFs for the 6 revised docs and new PDFs for the 7 L06 docs.
5. **Ground truth** (`ground_truth.json`, same schema as v1): design calc and ref calcs per GlobalId, calc edges, rev2 diff.
   This lets `scripts/evaluate.py` score the engine on Harborview (reported, not gated, until a baseline is agreed).
6. **Byte-stable `--check`**, the same as v1.
7. **App wiring:** `copy-assets.mjs` copies the Harborview sample; **Load sample** loads the rev1 IFC plus the calc set
   (and optionally the Rev 2 IFC plus Rev B PDFs as the comparison).
8. **Verify:** run `evaluate.py` on the new data, then a browser pass: element → calc → highlighted PDF region and back,
   Diff Mode A/B with calc revisions.

## Decisions (defaults unless an open question changes them)

- Numbers come from the JSON, not a PyNite analysis: the demo must agree with the inspector, and the JSON already carries
  demand and utilisation. The calcs are plausible, not a design.
- 1–3 pages per calc, not the stubs' 664. Stub page counts are dropped; titles, codes and revs are kept.
- The v1 synthetic stays as the CI gate (`synthetic_v1`, `synthetic_check`). Harborview is added, not a replacement.
- A few realism features from the v1 supplement (a scanned hand-calc page, one deliberate size mismatch, a calc continued
  after a gap) are worth adding at the end so the demo shows findings. Low priority.

## Open questions

1. Marks with spaces: rename to space-free marks in the IFC/PDFs (e.g. `PC-A1`, `P-A1`, `SL-L01`, `SW-N-L01`,
   `BR-A-L01`, keeping the old label as the element Name), or teach the matcher multi-word marks?
2. Generate a Harborview IFC (real GlobalIds, 3D meshes, a full Load sample project), or PDFs only against the legacy JSON?
3. Should the Harborview sample replace the v1 sample behind **Load sample**, or sit next to it?
4. Rev 2 scope: generate the Rev B and L06 PDFs in the first pass, or Rev 1 only first?
