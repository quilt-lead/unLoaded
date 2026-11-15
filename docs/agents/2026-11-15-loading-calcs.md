# Loading calcs (gravity, wind, seismic, combinations) in the Calculation Graph

- **Status:** done, not committed (the user reviews first). `npm test`, typecheck, generator `--check` and
  `evaluate_harborview.py` all green; browser-checked on the Harborview sample.
- **Branch:** `cs/dev` (working tree).
- **Owned files:**
  - `packages/calc-mapper/src/{types,segment,calcdeps,provenance,bundle,index}.ts`, `test/loading.test.ts` (new),
    `test/review-round2.test.ts` (ratchet re-pinned), `README.md`
  - `tools/calcgraph-reference/synth/harborview/loading.py` (new), `calc_pdf.py`, `model.py`, `generate.py`
  - `data/harborview/**` (regenerated), `src/data/loadProject.ts`, `src/utils/colors.ts` (+ tests)
- **Working files:** none in flight.

## What it is

The user asked for calcs that link to other calcs rather than elements (gravity, wind, seismic loading), with
synthetic data on the Harborview sample and a new "Loading" section in the Calculation Graph.

- Harborview gets four loading calcs, one PDF each: S-001 Gravity Load Criteria, S-002 Wind Load Analysis,
  S-003 Seismic Load Analysis, S-004 Load Combination Criteria. They are Rev A in rev 1 and Rev B in rev 2,
  because the L06 addition adds a floor, height and seismic weight.
- Numbers come from the model's slab extents and heights: 122 × 92 ft plan, ASCE 7-22, Exposure D, SDC C,
  OCBF R = 3.25. They are plausible, not a design.
- Edges (111 in rev 1):
  - S-001 → S-003 and S-004; S-002 and S-003 → S-004.
  - S-001 → slab, girder, infill and column stack calcs.
  - S-002 and S-003 → slab (diaphragm), brace and core wall calcs.
  - S-004 → brace, core wall, base plate, pile cap and caisson calcs.
  - Connections take loads only from the beams, as before.
- Evaluator: 102/102 calcs, 310/310 calc edges, design links and load references still 100%, no stray links.

## Decisions

- **Calcs cite a sheet number, so the engine got a rule for it.** The rules that existed could not join a
  loading calc:
  - Page references stay inside one PDF, and the sample loads one PDF per calc.
  - Cross-references need an element that the cited calc designs.
  - New rule 3 in `calcdeps.ts`, `calc reference`: a calc names another calc's sheet number (the hyphenated
    token its title starts with). It resolves only if exactly one calc has that sheet. The twenty S-102
    caps resolve to nothing, and "L01" is never a sheet.
  - Direction is by cue word, as for page references.
- **`CalcCategory = ElementCategory | "Loading"`**, kept apart from `ElementCategory`, because no element is
  ever "Loading".
  - The category is read only from the title, and only when the title names no element type:
    "Column Load Takedown" stays Column.
  - The matcher needs no change. A Loading calc has no CAT_WORDS entry, so its type tier is skipped. The
    sample PDFs name no marks or sizes, so they link nothing.
- **Versions bumped:** `segment-v3`, `mapper-v1.3`. Stored extractions and runs re-run. The ratchet fixture
  now has two loading pages and a sheet citation, and both fingerprints were re-pinned.
- **Bundle format** accepts `cat: "Loading"`.
- **UI:**
  - The section is labelled "Loading", not "Loading calcs".
  - Its description says it designs no element.
  - Color `GRAPH_NODE_PALETTE[3]` (`LOADING_COLOR`). No element kind uses it; the element graph uses it
    only for site / building / storey.

## Gotchas / open

- No `to` before a sheet number on a citation line: it would reverse the edge.
- Loading text must not contain element marks, sizes or "page N". They would make links or page references.
- The inspector's calc subtitle shows the document name of the first revision ("… - Rev A") in rev 2 too.
  This was already the case before this change, for every reissued document.
- White label text on the orange (and the existing yellow / lime) category nodes is low contrast.
- The A/B bundle demo (`harborview-tower-*.bundle.json`) has no loading calcs. Only the IFC + PDF sample does.
