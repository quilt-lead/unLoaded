# Calc parser ported from Python to TypeScript

- **Status:** active (engine done, not wired into the UI yet)
- **Branch:** `prod` (uncommitted when written)
- **Owned files:** `packages/calc-parser/**`

## Context

The calc ↔ element mapping only existed as a Python FastAPI prototype (`prototyping/calc-graph`, PyMuPDF +
IfcOpenShell). The app is a static React app with the IFC parser in TS. The user chose to port the calc
side to TS ("fewer moving pieces"), with no loss of functionality.

## Decisions

- **New workspace package `@unloaded/calc-parser`**, framework-agnostic like `ifc-parser` / `element-graph`.
  Field names (`global_id`, `calc_key`, `conf`, ...) are kept from Python on purpose: the golden JSON compares
  one-to-one, and the prototype's data stays readable. Convert at the UI adapter, not in the engine.
- **pdf.js is injected** (`readPdf(bytes, pdfjs)`), so the package doesn't pick the build: the app passes `pdfjs-dist`
  with a Vite `?url` worker, tests pass the legacy build. Pinned to 4.10.38 (the mockup's version).
- **Python `re` semantics:** `pyRe()` rewrites `\b` to Unicode-aware lookarounds. Don't write raw `\b` in rule regexes.
- **Not ported:** `loadpath.py` (use element-graph `supports` edges as `LoadEdge`s), the SQLite store and API.
  Decisions are plain data; persisting them is the app's job (`effectiveLinks` takes the log).
- The Python prototype is left in place. Deleting it is the user's call.

## Gotchas

- Python's tests "only run in CI" (a hook blocks local runners), and `test_tiers` was actually failing. Verified by
  calling it directly with `uv run python -c ...`. Don't treat Python tests as ground truth without running them.
- pdf.js returns runs, not words. Word x positions are interpolated with Helvetica widths (monospace split evenly),
  and touching runs are joined. Ascent/descent (0.93 / 0.31) were measured against MuPDF on the fixture.
- pdf.js detaches the buffer it is given. `readPdf` passes a copy.

## Next steps

- Wire into the app: a "Import calcs (PDF)" action that runs `readPdf` + `mapCalcs` against the loaded model and writes
  `kind: 'calc'` links onto `ElementNode.links` (the hook in `elementGraphToBim.ts`), feeding the Document Browser
  and the Calculation Graph. Show highlights from `rects` with a pdf.js page render.
- Review UI (confirm / reject / manual) persisting the decision log, and the impact view (`propagateImpact`).
- Run `readPdf` in a Web Worker for large packages.
