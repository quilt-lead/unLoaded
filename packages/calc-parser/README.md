# @unloaded/calc-parser

Calc package PDF → calcs → element ↔ calc links → calc dependency graph → change impact.
Pure TypeScript, so it runs in the browser (pdf.js) and in Node, with no backend.

This is a port of the Python prototype in `prototyping/calc-graph/backend/calcgraph`:

| Python | Here | What |
|---|---|---|
| `pdf_ingest.py` (PyMuPDF) | `pdf.ts` (pdf.js) | Page text rebuilt from word boxes; every word keeps its span and box |
| `segment.py` | `segment.ts` | Split the package into calcs (scanned, front matter, title changes), software, element type |
| `matcher.py` | `matcher.ts` | Mark / range / loose / family / size / partial / xref / type tiers with confidence and evidence |
| `calcdeps.py` | `calcdeps.ts` | Calc → calc edges from page references and cross-references |
| `impact.py` | `impact.ts` | Change / remove propagation down the load path and the calc graph |
| `pipeline.py`, `store.py` (review parts) | `review.ts` | Human decisions (confirm / reject / manual / undo), element status, export report |
| `ifc_ingest.py` (IfcOpenShell) | `elements.ts` | Adapter from `@unloaded/ifc-parser` elements, plus `catOf` / `profileFrom` |

Not ported, because the app already covers them: `loadpath.py` (use `@unloaded/element-graph`'s
`supports` edges), the SQLite store, FastAPI, and server-side page PNGs (render with pdf.js in the browser).

## Use

```ts
import * as pdfjs from 'pdfjs-dist';
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url';
import { readPdf, mapCalcs, toCalcElements } from '@unloaded/calc-parser';

pdfjs.GlobalWorkerOptions.workerSrc = workerUrl;
const pkg = await readPdf(bytes, pdfjs);                          // { pages, meta }
const elements = toCalcElements(model.elements, levelNamesById);  // from @unloaded/ifc-parser
const { calcs, links, calcEdges } = mapCalcs(elements, pkg.pages);
```

In Node (tests), pass `pdfjs-dist/legacy/build/pdf.mjs`. `readPdf(..., { countImages: false })`
skips the per-page operator list, which is noticeably faster on large scanned packages.

## Parity with Python

`test/fixtures/` holds the synthetic package (`synth.generate --seed 7`) and the Python
pipeline's outputs on it (`golden/`, written by `golden/dump_golden.py`). The tests check:

- the rule modules, given Python's own pages and elements, return **identical** calcs, links (all 800,
  including confidence, span, snippet and rects), calc edges and impact results
- pdf.js rebuilds the **same page text** as PyMuPDF on every page, and the links from pdf.js pages match
- the whole TS pipeline (web-ifc + pdf.js) returns the same links as the whole Python pipeline

Known, intended differences:

- Word boxes are approximate (pdf.js gives run widths, not glyph positions): x p95 0.6 pt, max ~3 pt.
  They're only used for highlight rectangles.
- `@unloaded/ifc-parser` keeps HSS fractions (`HSS6X6X3/8`). Python's IFC regex cut them to `HSS6X6X3`,
  so Python could never size-match an HSS member. It also derives `<depth>X<width>` sizes for plates and footings.
- `test_matcher_units.py` expected `2B1` to link by range. It's also named outright, so both
  implementations link it as exact. The Python test only ran in CI and was wrong.

To regenerate the fixtures after a rule change in Python:

```sh
cd prototyping/calc-graph
uv run python -m synth.generate --out <tmp>/synth --seed 7
uv run python ../../packages/calc-parser/test/fixtures/golden/dump_golden.py "$PWD" <tmp>/synth ../../packages/calc-parser/test/fixtures/golden
cp <tmp>/synth/{calc_package.pdf,model_rev1.ifc,ground_truth.json} ../../packages/calc-parser/test/fixtures/
```
