# Harborview synthetic calc package

- **Status:** done, not committed (the user reviews first). Browser-checked; `npm test` and typecheck green.
- **Branch:** `cs/dev` (working tree; nothing committed).
- **Owned files:**
  - `tools/calcgraph-reference/synth/harborview/` (new: `model.py`, `ifc.py`, `calc_pdf.py`, `generate.py`, `legacy_params.json`)
  - `tools/calcgraph-reference/scripts/evaluate_harborview.py` (new)
  - `data/harborview/` (the two bundles moved here; everything else generated and committed, PDFs in LFS)
  - `src/engine/hooks.ts` (`useLoadHarborview`; demo paths), `src/App.tsx`, `src/components/HeaderBar.tsx` (+ test)
  - `scripts/copy-assets.mjs`
- **Also touched:**
  - `synth/shapes.py` (6 sections added)
  - `synth/ifc_common.py` (header file name, below)
  - `src/loaders/harborviewBundle.test.ts` (paths)
  - `data/README.md`, `tools/calcgraph-reference/README.md`
- **Working files:** none in flight.

## What it is

The Harborview tower as a real project: an IFC per revision and calc PDFs whose text the engine maps. It sits beside
the bundle-based **Harborview A/B demo**. Menu / empty state: **Harborview sample**. It loads:

1. rev 1 IFC + 78 per-document PDFs
2. rev 2 IFC + 19 PDFs: 12 Rev B reissues and 7 new L06 calcs, each filed as the next revision of its document by file name
3. Diff Mode A→B

The engine scores 100% on rev 1 (`evaluate_harborview.py`):

- 98/98 calcs
- design links 420/420, no false links
- load references 275/275
- calc edges 199/199
- the planted size mismatch found

## Decisions

- **Source = the bundles + `legacy_params.json`.** The bundles dropped per-element demand / utilisation, so they were
  extracted once from the legacy JSON at `410a100`. Element GlobalId = uuid5(element id), stable across revs.
- **Space-free marks** (the user chose this): `Cap A1` → `PC-A1`, `Pile P-A1` → `P-A1`, `Slab L01` → `SL-L01`,
  `Core N-L01` → `SW-N-L01`, `Brace A-L01` → `BR-A-L01`. The old label is the IFC Name. The matcher reads a mark as one token.
- **S-102 is two calcs in one PDF** (pile cap, caisson). The engine takes a calc's type from its title (first `CAT_WORDS`
  match). "Pile Cap & Caisson" reads as Footing, so the caissons would be xref (loads), not design.
- **Two titles changed on the page** so `segment.ts TITLE_KW` sees a calc title:
  - "S-405 Column Base Plate & Anchor Rod Package" → "... Design"
  - "S-31x Lxx Composite Infill Beams (W16x31)" → "... Design"
- **No section sizes on girder or column schedule rows.** The matcher's size tier links a size on a mark row to every
  element of that size on the storey that the calc didn't already claim. Girder line 1's rows linked lines 2–4, and
  each stack linked every other stack: 1476 false links, design precision 22%. Infill and brace rows keep their sizes,
  because every same-size element on the storey is in that calc. Arguably an engine weakness worth raising.
- **The demo summaries name sections** ("check for W21x62"). A size on a line with no mark is a typical-group link, so
  the scope line replaces them.
- **Numbers:** steel beam capacity from the section (0.9 Fy Zx × 1.35 composite), demand = utilisation × capacity.
  Columns, connections, plates, caps and walls take demand from the demo kN, with capacity = demand / utilisation.
  Plausible, not a design.
- **Calc edges come only from cross-type "from" lines** (xref → calcdeps rule 2):
  - slab → infill, girder, core wall, braced frame
  - girder → connection
  - connection and braced frame → column stack
  - column stack → base plate → pile cap → caisson
  - Same-type mentions (beam → beam) would not make an edge, so there are none.
- **Rev B / L06 follow the bundle's `rev` field exactly.** 16 column stacks stay Rev A in rev 2 without their new L06
  segment, so those L06 columns have no designing calc in rev 2. That is the demo's own data; it is a realistic "calc
  not yet updated" case.
- **Per-document PDFs, not the combined package, in the app.** A Rev B upload matches ≥ 60% of the package's calc keys
  (calcset.ts rule 3) and would become a revision of the whole package. `calcs/harborview-calcs-rev1.pdf` is for the
  evaluator and for anyone who wants the one-large-PDF case.

## The earlier preview (another session, merged from prod)

`tools/calcgraph-reference/synth/harborview_preview.py` writes `data/harborview/harborview-demo-calcs-preview.pdf`:
a cover and four calc sheets (A1 pile cap, L01 grid line 1 girders, C-01 stack, base plates). It has no demands or checks,
and is tested by `packages/calc-mapper/test/harborview-preview.test.ts`. It was built from this note's planning version
and is superseded by the full sample. It keeps the model's spaced marks and writes them without whitespace in the PDF
(`CapA1`), where the full sample renames the marks (`PC-A1`). It moved into `data/harborview/` with the bundles at the
merge; delete it and its test if nobody needs it.

## Gotchas

- **No `&` in served file names.** Vite's static server does not decode `%26` (it answers index.html). File names use
  " and "; the PDF titles keep "&".
- **IFC byte-stability on Windows.** `ifc_common.py` wrote `path.rsplit("/")` into the IFC header, i.e. the whole
  backslash path. Now `os.path.basename`. Bytes are unchanged on Linux. This is likely the real cause of v1's
  `synthetic_check.generator_byte_stable` failing on Windows (the phase 2 note guessed CRLF). Not re-verified for v1.
- Regenerating rewrites `data/harborview/` except the bundles. Run `npm run assets` afterwards; `copy-assets.mjs`
  copies what `manifest.json` lists and warns when PDFs are LFS pointer stubs.

## Next steps

- Browser pass done (headless Chrome on `vite`):
  - Warm dev server: Diff Mode is on ~9 s after the click and the full view ~10 s later; no main-thread stall over 0.75 s.
  - It opens with +70 / ~29 / −2 elements, 105 calcs, 470 mapped, 18 without a calc (the L06 segments of the Rev A
    stacks), and one finding (the planted one).
  - Each PDF is read once at upload (worker `extractPlaced`); views reuse the stored extraction.
  - Not checked in the browser: PDF highlight click-through.
- **Cold `vite` makes it look slow.** The first load after a dev-server start (or `--force`) took 45–90 s: Vite
  pre-bundles and transforms the PDF, IFC and 3D modules on first use. A production build does not have that cost.
  The "stuck" busy text seen then was the same cold start.
- The diff chip reads "Rev 1 → 80": revision ids count calc revisions too (as in the A/B demo's chip, pre-existing).
- Optional realism from the v1 supplement: a scanned hand-calc page, a calc continued after a gap.
- `evaluate_all.py` stage for Harborview (reported) once a baseline is agreed.
- Tell Noah the demo bundles moved to `data/harborview/`.
