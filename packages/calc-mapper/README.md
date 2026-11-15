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
const run = await mapCalcs(graph, pkg);                  // auto links (status "auto") + calc dependency edges
let decisions = addDecision([], { global_id, calc_key, action: "confirm" }, { inputs: run.inputs });
const exp = buildExport(graph, pkg, run, decisions);     // the retired backend's /export (+ connectivity)
const imp = await impactOf(graph, pkg, run, decisions, gid, "remove");
const cmp = diffGraphs(graphRev1, graphRev2);            // the retired backend's /compare
```

The output shapes are the retired Python backend's, with snake_case kept (`src/types.ts`). They
cover `/export`, `/compare`, `/impact`, the `/state` pieces (`buildState`) and the decision
records.

## Auditability contract (`src/types.ts`)

Ported from the reference schema (`calcgraph/schema/{models,units,frames}.py`). Every addition is a
new field; no field of the export was renamed or removed.

- **Provenance is required** (`provenance.ts`) on every `Link`, `GroupLink`, `CalcEdge`, `Calc`,
  `Finding`, `Impact` and `Decision`: `{ producer: "calc-mapper@<version>/<module>", rule, method,
  inputs }`. `method` is `"rule"`, `"human"` (decisions, hand links: plus `actor` and `at`) or
  `"estimate"`. `inputs` are the sha256 of the documents the record rests on. A record built without
  provenance does not type-check, and `inputList` throws on anything that is not a sha256.
  - Rule ids: `segment.calc-title | scanned-run | front-matter | untitled-start`, `matcher.tier.<tier>`,
    `matcher.typical-group`, `matcher.finding.size-mismatch`,
    `calcdeps.page-reference.input | output`, `calcdeps.cross-reference` (joined with "+" when an
    edge has both), `impact.propagate.<mode>`, `decision.<action>`.
  - A link a person confirmed / rejected keeps the matcher's provenance and gains
    `review_provenance` (the decision's).
  - A decision read back from a store or file may lack provenance (`DecisionFields`).
    `buildState`, `buildExport` and `impactOf` accept those and pass each through `decisionFrom`,
    which states the provenance from the decision's own fields.
  - `PACKAGE_VERSION` is the version in every producer string; a test pins it to `package.json`.
- **Document hashes** (WebCrypto `crypto.subtle.digest`, in browsers, workers and Node >= 20):
  - `extractPdf` hashes the PDF's bytes once, and every page carries the hash (`doc_sha256`).
  - `mapCalcs` hashes the graph's canonical JSON.
  - `MappingRun.producers` and `Export.producers` hold the producers (`calc-mapper@<version>`, the
    graph's `<format>@<version>`) and both hashes. `MappingRun.inputs` is `[graph, pdf]`.
  - So `mapCalcs` and `impactOf` are async.
- **Units** (`units.ts`): `Quantity { value, unit }`. `Unit` is units.py's fixed set of 57 canonical
  units. `convert()` uses the same table.
  - An unknown unit throws `UnknownUnit`, and a literal one is a type error. Mixed dimensions
    throw `UnitMismatch`.
  - The engine reports the load-path `gap` as `Quantity<"m">` (beside `gap_m`).
  - A graph whose `meta.units` is not metres is refused.
  - Section designations stay strings.
- **Frames** (`frames.ts`): every rect is a `SheetRect` (PDF points on one page). Graph geometry is
  `ModelPointM` (world metres). `BuildingPointFt` is declared for drawing-set ingest. The brands
  are type-level only, so JSON stays plain arrays.

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
    "scanned" calc, which is never mapped. "Scanned" describes those pages and nothing else.
  - A page with front-matter evidence is front matter and is never mapped: 3 or more dot-leader
    entries, or a contents / index / cover heading line among its first lines (`FRONT_HEADING`).
    Having no title is not front-matter evidence.
  - A calc-like title on a page starts a new calc, unless it is the current calc's title or an
    earlier calc's (that calc continues after a gap), also right after a scanned run or front matter.
  - A page (part) with text but no title continues the most recent calc that has text (after a
    scanned sketch or an inserted contents page, as a new span). With none yet (a cover with no title
    keyword) it starts "Untitled (from page N)" (`segment.untitled-start`), mapped like any calc.
  - Calc keys are unique by construction (`uniqueKeys`): a repeated slug gets the first `-<n>` no
    calc has taken, so "Beam Design 2" and a second "Beam Design" never share `beam-design-2`.
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
  - Calc text and marks are read through one fold (`text.ts`): upper case, the Unicode dashes
    U+2010-U+2015 as "-", one UTF-16 unit per character so spans stay exact. "SL‐2" (U+2010)
    matches the mark SL-2.
  - Section sizes in calc text come from a calc-text grammar (`profile.ts` `CALC_SECTION_PATTERNS`), not
    the parser's: the parser reads fields known to hold a profile, a calc is mostly arithmetic, grids
    and tags. A designation must be complete: a family prefix with every dimension the family needs,
    no spaces inside a generic NxN, no commas ("MU = 45 X 12", "GRID 12 X 14", "HD12", "S 2 X 4",
    "HEA200,240" are not sizes). Or it is exactly a profile the model carries that has a digit and a
    letter (`isDesignation`; a ProfileName "Beam" is never a size, nor the model's size in a
    comparison). IPE 300, HEA 200, 457X191X67 UB, 533X210X92UB, 310UB40.4, C10X15.3, L4X4X1/2,
    HSS6X6X.375 and W12X53 are found. A token that is a model mark is never a size.
  - A line names a storey only as a whole word ("LEVEL 10" does not name Level 1, "ROOFING" not Roof),
    in the size rule and in the evidence alike.
- **Calcs as spans of page regions** (`segment.ts`):
  - A page is cut at a mid-page heading that reads as a calc title (set at least 1.2x the page's
    median line height and about as large as the page's own title). So a calc can start or end
    mid-page. Body lines that merely contain "design" or "bracing" are not headings.
  - A part titled like an EARLIER calc (e.g. "... (cont.)" after another calc) continues that calc.
    Each calc carries `spans: [{regions: [{page, rect, start, end}]}]`. A region that picks up where
    the last stopped continues the span; a gap starts a new one. `pages` is kept.
  - The matcher and calc edges read only inside a calc's own regions.
- **Link role, evidence and confidence** (`matcher.ts`):
  - Every link has `evidence[]` of `{kind, weight, note, page, rects}`. Item 1 is always the tier,
    so tier metrics still compute. Then the matched line adds:
    - storey: +0.05 if it names the element's storey, -0.15 if it names a different one;
    - size: +0.05 if it names the model's size, -0.20 if a mark line names a different size.
  - `conf` is the sum, clamped to [0, 1]. Bands: high >= 0.75, medium >= 0.5, low otherwise.
    `caveats[]` explain the doubts in plain words.
  - Role is "design" or "loads". An xref is always loads. Otherwise a link is design when any hit
    sits on a line without a load cue (reactions, loads, from, carried, end moments, punching,
    supporting, designed separately, see).
  - Element status counts design links only: a loads-only element is "unmapped" (not designed).
  - Which hit a link keeps is still decided by the tier confidence, as in the reference engine, so
    pages, spans and calc edges are unchanged.
- **Typical groups**: a group is the elements of one kind, storey and size. A size on a line that
  names no mark ("Level 3 typical beams W18X35") links the calc to the group ONCE
  (`group_links[]`). Members keep a per-element size link marked `via_group`. A size beside a mark
  keeps the reference engine's plain per-element size links.
- **Size-mismatch findings**: a design-role line that names the mark (exact or range tier) and a
  different size than the model gives a finding: element, calc, model size, calc size, location.
  Sizes on both sides go through one normaliser (`profile.ts`, a port of packages/ifc-parser's
  `normaliseProfile`; a test pins the two together) and are found by the one grammar above.
- **Calc edges** (`calcdeps.ts`): page references ("see page 7"; a "to" cue reverses the
  direction) and cross-references.
  - A page number is not a reference (`pageReferences`): "Page 7 of 40", "Page 2/5", or a page
    mention on a running header / footer - a line in the top or bottom 3 lines of a page that recurs
    in the same band on another page with only its page number changed (`runningLines`, detected per
    document). Every other page mention is a reference, cue word or not ("max end reaction: page 7").
  - A cross-reference points at the element's designer (`designerOf`): a design-role link beats a
    loads-role one, then the higher tier confidence, then the smaller calc key.
- **Impact** (`impact.ts`): walks the graph's `supports` edges. Connection nodes pass load through,
  so waves count depth the way `ElementGraph.loadPathDown` does.
- **Diff** (`diff.ts`):
  - Elements are keyed by GlobalId. An element counts as changed when its content hash differs.
    The hash covers ifc_type, mark, name, type_name, profile, storey, params and the bbox to 1 mm.
  - Each change lists the before and after value of every changed field. The hash and the field
    comparison read one field list (`diffFields`), so a changed element always lists at least one
    field (a rename lists `name`) and float noise under 1 mm is neither a change nor "moved".
  - Load-path edges are compared too, giving the edges added and removed.
- **Decisions** (`decisions.ts`):
  - The log is append-only and keyed by (global_id, calc_key), not by revision.
  - The latest decision for a pair wins, and "undo" clears it.
  - Decisions carry forward to later revisions while both keys exist.

## Versions that key stored results (`types.ts`)

- `SEGMENTER_VERSION` is recorded on every `CalcPackage` (`segmenter`). project-file's
  `storedExtractionFor` reuses a stored extraction only when it matches, so a segmenter change reaches
  existing projects.
- `ENGINE_VERSION` = `<MAPPER_VERSION>+<SEGMENTER_VERSION>` keys stored mapping runs (the app's run
  cache, `MappingRun.engine`), so a matcher or a segmenter bump makes every stored run stale.
- `test/review-round2.test.ts` pins a fingerprint of segment / runMapping / inferCalcEdges output on a
  realistic fixture next to each version: a behaviour change that keeps the version fails there.
- `parseGraph` accepts exactly what the engine reads (numbers in text fields read as text; coordinate
  lists of any length, null for a NaN JSON could not carry) and throws `GraphFormatError` otherwise.
- `calcPackageProblem(x)` names what in a stored calc package the engine could not read (null if none).

## Proof it is at least as good as the reference

`scripts/run-pipeline.ts` (Node >= 22.18) runs the engine on a graph and a PDF and writes JSON. The
scorer, `tools/calcgraph-reference/scripts/evaluate.py`, grades that JSON against the synthetic
ground truth. CI gates on `tools/calcgraph-reference/eval/baseline.json`: precision, recall and F1,
exact link counts per tier, xref, calc edges, segmentation, the rev 1 -> rev 2 diff and the C8
impact, plus role accuracy, group-link precision and findings. A small second synthetic package
(`calc_supplement.pdf`) adds what the main one lacks: a calc starting mid-page, a calc continued
after a gap, a typical-group calc, a loads-only reference and a planted size mismatch. It is scored on
span boundaries, roles, group links and mismatch precision and recall.

```
node packages/calc-mapper/scripts/run-pipeline.ts --graph g.json --pdf calcs.pdf --out out.json \
  [--decisions d.json] [--compare-to g2.json] [--impact <GlobalId>:remove]
```

## Scripts

```
npx tsc -p packages/calc-mapper/tsconfig.json
npx vitest run --root packages/calc-mapper
```
