# Drawing evidence: the selected element boxed on its drawing

- **Status:** in review (uncommitted on `issy/drawing-tag-boxes`; Issy reviews and commits)
- **Branch:** `issy/drawing-tag-boxes` (from `origin/prod` e61b010)
- **Owned files:** `src/components/drawing/DrawingEvidence.tsx`, `src/data/drawingOccurrences.ts` (+ test),
  `src/loaders/drawingImport.test.ts`; shared, additive edits in `src/App.tsx`, `src/components/PropertyInspector.tsx`,
  `src/components/HeaderBar.tsx`, `src/components/FileDropOverlay.tsx`, `src/hooks/useFileDrop.ts`,
  `src/components/pdf/PdfPage.tsx` (two optional props), `src/engine/{protocol,ops,engineClient,projectService,hooks}.ts`,
  `src/loaders/parsers.ts`, `scripts/copy-assets.mjs`, root `package.json` / `package-lock.json` (dependency on
  `@unloaded/drawing-parser`)

## What it is

Issy's ask: clicking a 3D item should pop up the piece of the drawing relevant to it with a bounding box, the way
the calc sections pop up. A model can now be read from a structural drawing set PDF (no IFC). When an element of
such a model is selected (3D, plan, graph, inspector), the inspector shows "On the drawings (n)": a crop of the
sheet with the printed tag / schedule row boxed, sheet + kind + text below it, every occurrence listed and
steppable. Clicking the crop opens the whole sheet in a dialog, zoomed to the box (Page shows the whole sheet).

## Decisions

- **Drawings are an explicit choice, never sniffed.** A calc package is a PDF too and drawing-parser's `canParse`
  cannot tell them apart. Entry points: Project menu "Add drawing set (PDF)", the empty state's "Drawing PDF"
  tile, and a third drop zone "Drawing set (PDF)". Every other PDF path still goes to calcs (`openAnyFile`,
  plain drops, "Open file…").
- **Dedicated path, not a `BIM_PARSERS` entry.** `projectService.addDrawingRevision`: LFS / PDF header check ->
  engine op `parseDrawing` (worker; drawing-parser is dynamically imported there because it pulls in ifc-parser,
  hence web-ifc's JS) -> `importDrawingModel` (the same `fromModelInput` as IFC) -> `storeModel`. Format
  `'drawing'`, media type `application/pdf`, the blob is the drawing PDF. `modelFileUrl` stays null (it is only
  set for `application/x-step`), so 3D draws element-graph boxes.
- **The drawing PDF reaches the UI as `drawingUrls`** (file name -> object URL) on the project view query, next to
  `pdfUrls`, not in `ProjectViewModel`: no change to `mergeProject` / `types/bim.ts`. Occurrences are matched by
  their `file` (= the revision's `sourceName`); an occurrence whose file is not loaded is not shown.
- **Inspector card, not the docs view.** Plain selection already shows calc evidence in the inspector, so the
  drawing card sits there (after the identity card). The full sheet is a modal dialog owned by the card, so
  `DocumentBrowser` (calc-centric, Carl's) is untouched.
- **`PdfPage` reused, not forked:** two optional props, `minSpan` (the evidence zoom's minimum span; the default
  360 pt on a large sheet made tags ~8 px in a 310 px card) and `tools` (off for the crop, which sits inside a
  button with pointer events off). Crop = `cropAround(rect)` (pad 24, min 220 x 140 pt, aspect 1.5).
- **Sample "Dana Point Bldg 12 (drawings + calcs)"** (empty state + Project menu): copy-assets copies
  `data/sampleCalc` approved plans + calcs to `public/samples/dana-point-bldg12/` only when both start with
  `%PDF-` (never LFS stubs) and says how to fetch them otherwise; the loader's error says the same.

## Measured on the real set (Dana Point Bldg 12, headless Chromium, dev server)

- Sample load: ~9 s end to end (drawing parse ~3 s in the worker, 238-page calc extraction, mapping).
  231 elements, 69 calcs, every element "needs review" (the calcs are Enercalc printouts that name types, not
  marks: type-only matches at 30 %).
- Boxes sit on the printed text: W16x26 plan tag on S2.0.2 p55 (deep link and a real 3D click), footing F12 plan
  tag and its FOUNDATION SCHEDULE - PAD row on S2.0.1 p54. Bundle / IFC elements show no card.
- Screenshots: `/private/tmp/claude-501/drawing-shots/` (01-04, 06-08).

## Gotchas

- One headless run timed out waiting for the Dana load (300 s); three other loads, before and after, took < 10 s.
  Not reproduced; unknown cause. If it recurs, look at the worker (68 MB transfer + dynamic import).
- `src/loaders/drawingImport.test.ts` imports `packages/drawing-parser/test/helpers.ts` (pages built in code); no
  test touches the real PDFs (LFS stubs in CI).
- Tests, tsc and lint were not run locally (blocked on this machine): CI is the first run.

## Open / next

- IFC model + drawings: match drawing occurrences onto IFC elements (by grid + level + size) so an IFC element can
  show its drawing too. Today occurrences exist only on drawing-derived elements.
- Multi-PDF drawing sets (`parseDrawingSet` takes several files): one revision per file set; `drawingUrls` is
  already keyed by file name.
- The drawing set as a document in the PDF view (sheet list, like calcs), and the occurrence in the URL hash.
- Parser gaps seen on this set (not in scope here): elevations without "LINE <grid>" titles, TOS level notes,
  skewed tags.

## Working files

All the files under "Owned files" until Issy commits this branch.
