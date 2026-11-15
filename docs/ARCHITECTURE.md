# Architecture

The app links a structural model to the calculations that design it. It runs entirely in the browser:
there is no server. Models and calc packages never leave the engineer's machine.

```
IFC / JSON model ──> packages/ifc-parser ──> ModelInput ──> packages/element-graph (buildGraph)
                                                                   │  ElementGraph (elements + connections as nodes,
                                                                   │  connects / supports / part_of edges with evidence)
                                                                   ▼
calc package PDF ──> Web Worker: packages/calc-mapper ─────────> mapping run (links, calc dependencies)
                     (pdf.js text + word boxes, segment,           │
                      matcher, calc deps, impact, diffGraphs)      ▼
                                                   src/data/projectStore.ts (IndexedDB, in-memory fallback)
                                                                   │
              ElementGraph ──> src/loaders/elementGraphToBim.ts ──> ElementTopology ─┐
              Export (calc-mapper) ──> src/data/loadProject.ts ───> CalcData ────────┤
                                                                                     ▼
                                                     src/data/mergeProject.ts (by GlobalId) ──> ProjectViewModel
                                                                                     │
                       element graph · calculation graph · 3D (real IFC meshes) · PDF + evidence · inspector
```

## 1. Elements and topology: the element graph

`packages/ifc-parser` reads an IFC with web-ifc into a format-neutral `ModelInput`; `packages/element-graph`
builds the `ElementGraph` from it, inferring connectivity and the load path from geometry and the file's own
connection records (`IfcRelConnects*`). The graph is the single source of truth for elements and topology.

Other inputs reach the same graph:
- a serialized element graph or a `ModelInput` JSON;
- a **model bundle** (below), whose element graph is the serialized one, embedded unchanged.

`src/loaders/parsers.ts` dispatches every file by content: IFC, model bundle, element graph, ModelInput, a
calc-graph export, or a project file. The retired legacy `{ projectName, nodes, links }` demo format is refused
with a pointer to `scripts/convert-legacy-demo.ts`, which turns it into a model bundle.

### The model bundle (`packages/calc-mapper/src/bundle.ts`)

One JSON file with the element graph and its calculation graph side by side:

```jsonc
{ "format": "unloaded.model-bundle", "version": 1,
  "meta": { "project", "label", "demo", "createdAt" },
  "elementGraph": { /* ElementGraph.serialize() */ },
  "calcGraph": null | {
    "source": { "kind": "demo" } | { "kind": "pdf", "documents": [{ "doc_id", "name", "revision", "sha256", "pages", "page_offset" }] },
    "calcs": [{ "key", "title", "cat", "pages"?, "spans"?, "code"?, "rev"?, "date"?, "summary"? }],
    "edges": [{ "src", "dst", "rules"? }],                              // calc feeds calc
    "links": [{ "element", "calc", "role", "review", "conf"?, "page"?, "rects"?, "note"? }] } }  // element -> calc
```

- `parseBundle` validates it in full (unique calc keys; links and edges name a node of the graph and a calc of
  the bundle; one link per pair). Calc records use the engine export's field names, so `exportToCalcGraph(exp)`
  and `bundleExport(graph, calcGraph, decisions)` convert both ways without renaming.
- A bundle added as a model revision stores the bundle file as the revision's file, so the IndexedDB store and
  the project file carry its calc graph with no schema change (`meta.format = "bundle"`, `meta.hasCalcGraph`).
- `projectSnapshot` shows the model revision's own calc graph **only when the project has no calc PDF**; once a
  PDF is added, the engine maps it and the bundle's calcs step aside. The project's decision log is applied on
  top of the review state the bundle states.
- `source.kind: "demo"` (the Harborview A/B demo in `data/`) means invented calcs with no PDF: every record they
  yield has provenance `method: "estimate"`, `rule: "bundle.demo"`, each link carries a demo caveat, the calc
  root is "Demo calcs", and the PDF pane says "DEMO DATA • NO PDF", marks each calc DEMO and shows its stated
  metadata instead of a page.
- **Project → Export model + calc graph** writes the model on screen and its calc graph (not rejected links;
  review state, evidence and provenance kept) as `*.bundle.json`. The PDFs are named by sha256, not included.

## 2. Calcs: `@unloaded/calc-mapper` in a Web Worker

`src/engine/engine.worker.ts` runs the calc engine off the main thread; `src/engine/engineClient.ts` is the
promise API, with progress messages shown in the app's toast. Operations (`src/engine/ops.ts`, the only file
that calls the package's functions):

| op | what it does |
|---|---|
| `extract` | PDF bytes → pages (pdf.js text, word boxes) → segmented calcs as spans of page regions (`extractPdf`, `segmentCalcs`) |
| `map` | element graph × calc package → auto links (role, band, weighted evidence, caveats), typical groups and their links, size-mismatch findings, calc → calc dependencies (`mapCalcs`) |
| `export` | graph + package + run + decision log → the export (elements with ranked, evidenced links) (`buildExport`) |
| `bundleExport` | a model bundle's calc graph against its element graph → the same export shape, decision log applied, no PDF or mapping run (`bundleExport`) |
| `impact` | what goes stale if an element changes / is removed (`impactOf`) |
| `diff` | **the one revision diff**: two element graphs → added / removed / changed with per-field before → after (`diffGraphs`) |

Matching tiers, confidences and evidence follow the Python reference implementation in
`tools/calcgraph-reference/` (dev and CI only), which also generates the synthetic sample and scores the TS
engine against its ground truth.

## 3. The local project store: `src/data/projectStore.ts`

IndexedDB database `unloaded-calc-graph` (falls back to memory, with a warning in the UI, when IndexedDB is
unavailable):

| store | key | holds |
|---|---|---|
| `projects` | id | name, head model revision, head calc revision |
| `revisions` | auto id | kind (`model` / `calcs`), seq, label, source file name, media type, meta |
| `blobs` | revision id | the original IFC / JSON / PDF |
| `graphs` | revision id | model revisions: `ElementGraph.serialize()`, built once at import (never re-parsed) |
| `extractions` | revision id | calc revisions: extracted pages + segmented calcs |
| `runs` | auto id | one mapping run per (model revision, calc revision, engine version) |
| `decisions` | auto id | the append-only review log keyed by (GlobalId, calc key); latest wins; carries across revisions |

Every added file becomes the head of its kind. **Save project file** writes the whole project (files base64,
graphs, extractions, decision log) as one JSON document (`*.calcgraph.json`, format
`unloaded.calc-graph-project`); opening it creates a new project. The format is declared once, in
`packages/project-file` (type, `parseProjectFile` validator, base64 codec, head rule): the app's writer
(`exportProject`) and reader (`parsers.ts` → `importProject`) and the MCP server (`packages/mcp-server`) all use
it, so a file one writes the others read. An opened file is validated field by field before anything is
imported, and the error names the field at fault. JSON was chosen over a zip: no dependency,
it goes through the same content-dispatching importer as every other file, and it stays inspectable; base64
costs ~33 % on files of a few MB. A plain calc-graph export JSON also opens, read-only.

`src/engine/projectService.ts` composes store + engine (add revisions, the head mapping run, the export with
decisions applied, impact, compare, project files, samples); `src/engine/hooks.ts` exposes it to React with
TanStack Query and hands components view data only.

## 4. The view model: two adapters, one merge

- `src/loaders/elementGraphToBim.ts` is the only ElementGraph → view code: project → kind category → column
  stack / mark family → element; storeys; load path (`supports`); connectivity; element-graph boxes for the 3D
  fallback; demo documents.
- `src/data/loadProject.ts` is the only engine → view code: calcs, the calc graph, each element's links with
  confidence / tier / rule / evidence / review status, impact, the revision diff, the revision list.
- `src/data/mergeProject.ts` joins them by GlobalId (`mergeProject`) and lays a revision diff over the result
  (`applyModelDiff`; elements only in the other revision become ghost nodes).

Components (`src/components/*`) read `src/types/bim.ts` only. Utilisation stays empty until a real source
exists, so the heatmap toggle is disabled with an explanation. Load-path tracing applies its depth
setting in the selected direction; the default ALL setting lets upward traces follow connected
supports through the full structure.
PDF intake checks the header before starting extraction and identifies Git LFS pointer files with
instructions to fetch their contents.

## 5. Views

- **Element graph** (`RadialGraphCanvas`): the hierarchy, review-status rings, traced load path, impact and
  diff colouring, namable groups, and directional box selection (left-to-right encloses; right-to-left crosses;
  Shift adds). Escape cancels an active box selection and clears the shared selection in the graph and 3D views.
- **Calculation graph**: calcs by the element type they design, calc → calc dependencies, and the selected
  calc's linked elements with edges styled by review state.
- **3D** (`Structural3DViewer`, `three/ifcViewer.ts`): the head revision's real IFC meshes via web-ifc, keyed by
  GlobalId; element-graph boxes when there is no IFC; diff ghosts from the other revision.
- **2D plan** (`PlanView2D`, `plan/`, slicing in `utils/planSlice.ts`): the model panel's second tab. One floor
  level at a time as a framing plan: slab outline, beams at their section width, braces dashed, columns and walls
  cut just below the level, columns that start on it dashed, footings, connections. Drawn as SVG from the element
  graph's bbox / centreline / section (never the meshes), so it works without an IFC. Levels are the storeys plus
  any slab no storey sits on. Membership is geometric because IFC puts a floor's beams in the storey below. Styling
  and selection share `utils/elementEmphasis.ts` with the 3D view.
- **PDF calcs** (`DocumentBrowser`, `pdf/PdfPage.tsx`): the original page with the matched evidence
  highlighted; each calc stepped through by its regions (a calc can start or end mid-page; the region is
  outlined); calc dependencies side by side (`pdf/EvidenceCompare.tsx`); tabs for **typical groups** (elements of
  one size on one storey that a size-only calc links to once) and **findings** (the calc sizes an element
  differently from the model; click jumps to the page and selects the element).
- **Inspector**: links ranked by confidence with their role (**design** = the calc sizes the element; **loads
  only** = it takes loads from / mentions it), confidence band, caveats, "via typical group", and an expandable
  "why" listing the weighted evidence the confidence is the sum of (each item can be shown on its page);
  confirm / reject / undo / link by hand; size-mismatch findings; impact, load path, connectivity, parameters, the
  diff's before → after, demo documents labelled as such. An element's mapping status and colour follow its best
  **design** link: loads-only elements count as unmapped.
- **Provenance** (auditability): each link's "why" also shows who made it (producer `calc-mapper@<version>/<module>`,
  rule id, method, sha256 of its input documents) and, once reviewed, who decided it and when. The mapping summary
  shows the run's producer records: engine version, the element graph's source and sha256, the calc PDF's name and
  sha256. Calc extractions stored before the provenance contract are re-read from the stored PDF on first use, and
  mapping runs are keyed by engine version, so older runs recompute.

## Running it

```bash
npm install          # also copies web-ifc.wasm and the samples into public/ (scripts/copy-assets.mjs)
npm run dev
```

**Load sample** (and **Revisions → Add sample calc supplement**, which exercises roles, a typical group and a size
mismatch) needs the synthetic package generated once:
`cd tools/calcgraph-reference && uv run python -m synth.generate`, then `npm run assets`. Until then the app
says the sample is not generated. The Harborview A/B demo (two model bundles in `data/`) needs nothing extra.
