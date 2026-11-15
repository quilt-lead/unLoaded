# @unloaded/calc-mapper

The calc engine, in the browser. Reads a calc package PDF, splits it into calcs, maps them onto a
serialized element graph (`@unloaded/element-graph`, `ElementGraph.serialize()`), infers which
calc feeds which, and answers "what goes stale if this element changes or is removed". It also
diffs two model revisions and keeps the human decision log. Pure TypeScript with no server. The
only runtime dependency is `pdfjs-dist` 4.10.38, the version the app already renders with.

```ts
import { extractPdf, segmentCalcs, mapCalcs, buildExport, impactOf, diffGraphs, addDecision } from "@unloaded/calc-mapper";

const text = await extractPdf(pdfBytes);                 // pages: text + word boxes + spans; scanned flag
const pkg = segmentCalcs(text.pages, "calcs.pdf");       // calcs: key, title, software, element type, pages
const run = mapCalcs(graph, pkg);                        // auto links (status "auto") + calc dependency edges
let decisions = addDecision([], { global_id, calc_key, action: "confirm" });
const exp = buildExport(graph, pkg, run, decisions);     // the retired backend's /export (+ connectivity)
const imp = impactOf(graph, pkg, run, decisions, gid, "remove");
const cmp = diffGraphs(graphRev1, graphRev2);            // the retired backend's /compare
```

The output shapes are the retired Python backend's, with snake_case kept (`src/types.ts`). They
cover `/export`, `/compare`, `/impact`, the `/state` pieces (`buildState`) and the decision
records.

## What it does (rules unchanged from the reference engine)

- **PDF** (`pdf.ts`): pdf.js text items are split into words the way MuPDF splits them. They split
  on whitespace. An item that continues the previous one on the same baseline with no gap is glued
  to it. Words are grouped into rows by their bottom edge (within 3 pt) and joined with " " and "\n".
  Every word keeps its box (PDF points, top-left origin) and its span in the page text.
  On the synthetic package the page text, word counts and spans are identical to the PyMuPDF
  reference. The boxes are approximate: pdf.js gives no per-glyph widths.
  - **Browser:** pdf.js needs its worker configured (`GlobalWorkerOptions.workerSrc`), as
    `src/components/pdf/pdf.ts` already does. Inside a Web Worker, set `workerPort` or
    `workerSrc` the same way.
  - **Node:** pass the legacy build,
    `extractPdf(bytes, { pdfjs: await import("pdfjs-dist/legacy/build/pdf.mjs") })`.
- **Segmentation** (`segment.ts`):
  - A page with fewer than 25 characters has no text layer. A run of such pages becomes one
    "scanned" calc, which is never mapped.
  - A page with 3 or more dot-leader entries is front matter and is never mapped.
  - A calc-like title on a page starts a new calc.
  - Software named in the title wins over software the body only cites.
  - The element type falls back to the line under the title.
- **Mapping** (`matcher.ts`), strongest tier first:

  | Tier | Confidence | When |
  |---|---|---|
  | exact | 0.97 | the element's mark appears |
  | range | 0.90 | the mark falls inside a written range |
  | loose | 0.88 | the mark matches ignoring punctuation |
  | family | 0.85 | a token names a mark family |
  | size | 0.62 | section size and element type (and storey, if the line names one) |
  | partial | 0.50 | the token is the tail of exactly one mark |
  | type | 0.30 | the calc names no marks or sizes |

  A mark tier whose element type differs from the calc's becomes an **xref**, capped at 0.45.
  Every link keeps its page, span, snippet, highlight rects and rule.
- **Calc edges** (`calcdeps.ts`): page references ("see page 7"; a "to" cue reverses the
  direction) and cross-references.
- **Impact** (`impact.ts`): walks the graph's `supports` edges. Connection nodes pass load through,
  so waves count depth the way `ElementGraph.loadPathDown` does.
- **Diff** (`diff.ts`):
  - Elements are keyed by GlobalId. An element counts as changed when its content hash differs.
    The hash covers ifc_type, mark, name, type_name, profile, storey, params and the bbox to 1 mm.
  - Each change lists the before and after value of every changed field.
  - Load-path edges are compared too, giving the edges added and removed.
- **Decisions** (`decisions.ts`):
  - The log is append-only and keyed by (global_id, calc_key), not by revision.
  - The latest decision for a pair wins, and "undo" clears it.
  - Decisions carry forward to later revisions while both keys exist.

## Proof it is at least as good as the reference

`scripts/run-pipeline.ts` (Node >= 22.18) runs the engine on a graph and a PDF and writes JSON. The
scorer, `tools/calcgraph-reference/scripts/evaluate.py`, grades that JSON against the synthetic
ground truth. CI gates on `tools/calcgraph-reference/eval/baseline.json`: precision, recall and F1,
exact link counts per tier, xref, calc edges, segmentation, the rev 1 -> rev 2 diff and the C8
impact.

```
node packages/calc-mapper/scripts/run-pipeline.ts --graph g.json --pdf calcs.pdf --out out.json \
  [--decisions d.json] [--compare-to g2.json] [--impact <GlobalId>:remove]
```

## Scripts

```
npx tsc -p packages/calc-mapper/tsconfig.json
npx vitest run --root packages/calc-mapper
```
