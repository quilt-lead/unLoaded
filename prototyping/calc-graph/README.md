# calc-graph

Hackathon v1 (2026-11-14). Maps a structural BIM model's **element graph** (beams, columns,
slabs, braces, footings and connections as typed nodes, with load-path edges) to a calc
package's **calc graph** (calcs, with "output feeds input" edges), keeps the evidence for
every link, and shows which calcs go stale when an element changes or is removed. Every
upload is stored as a revision so a Git-style diff / redline feature can be built on top.

## Run it

Needs `uv` and Node 22.

```sh
cd ~/Documents/calc-graph
uv sync                                     # Python 3.12 deps
uv run python -m synth.v2.generate --check  # the Harbor View building: IFC, drawings, specs, calc package + ground truth
uv run python scripts/evaluate_all.py       # score everything against that ground truth (scorecard below)
uv run calc-graph ingest-set --sid synthetic-v2 --name "Harbor View Office (synthetic v2)" \
  --plans data/synthetic_v2/drawings.pdf --calcs data/synthetic_v2/calc_package.pdf \
  --model data/synthetic_v2/model.ifc       # the drawing-set view's data (data/sets/synthetic-v2 + the store)
(cd frontend && npm install && npm run build)
uv run calc-graph serve                     # http://127.0.0.1:8000 - API + built UI
```

Every view runs on the one synthetic building, Harbor View Office (`synth/v2`, fictional): `/v2`
(move a column), `/set` (its drawings and calc package read as documents, its IFC in 3D) and `/ifc`
(its IFC mapped to its calc package; press **Load Harbor View documents** once - the project is the
same revision-store project `/v2` applies moves to, so an applied move is a new model revision there).
The Dana Point permit set and the synthetic v1 building were retired on 2026-11-14 (tag
`pre-v2-cleanup` has them). For frontend work: `uv run calc-graph serve` plus `cd frontend && npm run dev`
(http://127.0.0.1:5173, proxies `/api`). Ingest from the shell:
`uv run calc-graph ingest model.ifc calcs.pdf`. Store location: `data/store/` (override with
`CALCGRAPH_STORE`). `data/synthetic_v2/` is SOURCE data, written only by the generator (`synth/v2`);
evaluation results and other derived outputs (move_eval, registry_eval / registry_ingested, platforms.json,
the ETABS .e2k export, the scorecard) go under `data/eval/` (override with `CALCGRAPH_DERIVED`), ETABS jobs
under the store - all resolved in `backend/calcgraph/store_root.py`, whose audit hook refuses any other
write into the source dir (and `evaluate_all.py` fails `source_data_unchanged` if one gets through). Tests for CI live in `backend/tests/` (`uv run --extra dev pytest backend/tests`).

## Evaluate, guard, CI

- `uv run python scripts/evaluate_all.py` runs every evaluation and prints one scorecard
  (synthetic v2 ground truth first: generator self-checks and the v2 IFC through `ifc_ingest` +
  `loadpath`; then the move-a-column / registry / v2-document evaluators when they exist; the AI-step
  ratchets; the copyright guard; the IFC path's mapping score on v2 (`v2_ifc_mapping`); and, when the
  Harbor View set is built locally, its coverage and the strict provenance audit (`schema_strict`:
  `scripts/schema_audit.py --strict`, every fact's rule id / version / engine / confidence from its
  producer)). It exits 1 when a gated metric drops more than 0.005 below
  `eval/baseline.json` (numbers only) or a check fails. `--synthetic-only` is what CI runs;
  `--update-baseline` accepts the current numbers.
- **IFC writers** - every IFC calc-graph writes (synth v2, including `/api/v2/apply` revisions) goes through
  `backend/calcgraph/ifc_common.py` on `ifcopenshell.api`; the v2 file also carries the structural
  analysis model (`ifc_structural.py`, from the ETABS-style analysis objects). Contracts are IDS files
  in `backend/calcgraph/ids/`; `scripts/validate_ifc.py` checks every IFC we produce against them
  (ifctester + schema validation + GlobalId stability; evaluate_all stage `ifc_contract`).
  `scripts/check_ifc_parity.py A.ifc B.ifc` is the before/after gate for a writer change (elements,
  GlobalIds, psets, storeys, bounding boxes within 1 mm). `calcgraph.ifc_diff` is the ifcdiff revision
  diff; `scripts/compare_revision_diffs.py` runs it against the store's key-join diff.
- **Copyright guard** - install once per clone, from the repo root:
  `git config core.hooksPath prototyping/calc-graph/scripts/git-hooks`. The pre-commit hook runs
  `scripts/check_no_copyrighted.py --staged` (blocks PDFs, images not pinned in
  `scripts/copyright_guard.json`, anything under `data/sets/` or `data/labels/`, and distinctive
  strings from the copyrighted (retired) Dana Point permit set outside the per-file term allowlist), plus
  `scripts/check_llm_imports.py` and `scripts/check_ai_step.py` when calc-graph Python is staged.
  `--history` / `--range A..B` / `--tracked` scan commits or HEAD; `--self-test` proves each rule.
- **CI**: `.github/workflows/ci.yml` at the repo root, on PRs and pushes to main / issy-prototype (uv sync,
  copyright guard, AI-step ratchets, type check, backend pytest, `evaluate_all --synthetic-only`, frontend
  build; actions pinned to SHAs).
- **Type check**: `scripts/check_types.py` runs pyright (`pyrightconfig.json`, standard mode, version pinned in
  the script) as a ratchet against the committed `eval/pyright_baseline.json`, which only ever shrinks: a new
  (file, rule, message) fails, an allowed error that no longer occurs fails (commit the shrunk baseline CI
  uploads, or `--tighten-from` the downloaded `pyright_current.json`), and a count above any earlier committed
  version fails - and requires `scripts/typecheck_canary.py`'s dict-where-a-Move-is-required calls to stay
  errors. CI only (type checkers are blocked on the dev Mac).

## Layout

| Path | What |
|---|---|
| `synth/v2/` | deterministic generator of the Harbor View building: designed steel frame (AISC 360 / ASCE 7, PyNite), IFC4 with the analytical model, drawing set, spec book, calc package (RAM / RISA / Enercalc / Mathcad styles, one scanned page), registry truth, move scenarios - see `docs/2026-11-14-move-a-column-notes.md` |
| `backend/calcgraph/` | `ifc_ingest` (IfcOpenShell), `loadpath` (geometry contact rules), `pdf_ingest` (PyMuPDF words + spans), `calcpkg_ingest` (the one profile-driven calc-package reader) + `segment` (its sub-calc groups as the IFC path's calcs) + `matcher` (port of the mockup's `runMapping()`), `calcdeps` (calc graph), `impact` (propagation), `drawing_ingest` / `set_graph` / `calc_records` / `connections` / `set_integrate` (drawing-set path), `registry_ingest` (element registry from the documents), `store` + `revstore` (SQLite revisions), `api` (FastAPI) |
| `frontend/` | Vite + React 18 + TypeScript app (React Router, TanStack Query, React Flow + dagre, pdf.js, three.js + web-ifc via `src/viewer.ts`). Shared components in `src/components/`, help registry + glossary in `src/help/` (ratchet `scripts/check-help.mjs` runs in `npm run build`), gallery at `/dev/components`. |
| `scripts/evaluate_all.py` | the scorecard (stages above), `eval/baseline.json` |

## Matching rules (IFC path, deterministic)

Tiers as in the mockup: exact mark 0.97, mark range 0.90, mark ignoring punctuation 0.88,
mark family 0.85, section size + type (+ storey named on the line) 0.62, unique partial mark
0.50, element type only 0.30, cross-reference (mark of a different element type than the calc
designs) capped at 0.45. Contents pages, pages before the first profile sheet id (a cover) and
pages without a text layer are never mapped. A calc is one sub-calc group of `calcpkg_ingest`
(consecutive pages of one section with the same title; sheet ids, titles and software from the set
profile); its element type comes from its title, else its table titles.

Calc edges: page references ("page 7", "pages 5-8") with direction from the nearest cue word
on the line ("to" = output, else input), plus cross-references (a calc mentioning an element
another calc designs takes that calc's output).

## How revisions are stored (for the diff / redline feature)

**Store v2 (F2): one SQLite revision store for both paths** (`backend/calcgraph/store.py`,
`revstore.py`, `data/store/`, gitignored). Shared tables: `project` (IFC projects and drawing
sets, `slug` = set id), `document` (every source file content-addressed by sha256, bytes in
`blobs/`), `revision` (IFC: `model` / `calcs`; drawing sets: `set` / `records` / `connections` /
`integrated`; `producer_json` records the code that built it as `module@<source hash>` plus
declared rule ids / confidence), `revision_doc`, `head`, `artifact` (each build's output files,
content-addressed - the drawing-set API serves these), `fact` (the `calcgraph.schema` facts of
each revision or mapping run keyed by stable id, provenance stored with every fact,
`body_hash` / `content_hash`, so a diff is a key join: `GET /api/store/diff?a=&b=`),
`calibration`, and the append-only `decision` log. The IFC path's native tables below are kept
unchanged. A v1 store migrates in place on open (backup `calcgraph.sqlite.pre-f2.bak`);
`uv run calc-graph migrate-store` also backfills facts and imports `data/sets/*` outputs
(which set builders still write as a working copy). Schema-shaped endpoints:
`/api/store/projects`, `/api/store/projects/{pid}/bundle`, `/api/store/sets/{sid}/bundle`,
`/api/store/revisions/{rid}[/bundle]`, `/api/store/runs/{id}/bundle`, `/api/store/diff`. The v1
responses are unchanged (`scripts/check_store_parity.py`); `/export` additionally carries the
evidence boxes, calc title boxes, calc-edge evidence and producer records.

v1 detail (still true for the IFC path's native rows):

- Every upload is an immutable `revision` row (`kind` model or calcs, `parent_id` = previous
  head of that kind, `seq`, label, source file name, sha256). The raw file is kept
  content-addressed in `data/store/blobs/<sha256>.<ext>`, so any revision can be re-read or
  re-rendered later. `project.head_model_rev` / `head_calc_rev` point at the current pair.
- **Model revisions** store a full parameter snapshot per element keyed by
  `(revision_id, GlobalId)`: mark, type, size, storey, the open `params_json` (every pset
  flattened to `Pset.Prop`, so bolted / welded connection fields arrive with no schema change),
  geometry summary, and a `content_hash`. Load-path edges are stored per revision too.
- **Calc revisions** store pages (text + word boxes) and calcs keyed by a stable `calc_key`
  (slug of the title) with a `content_hash` of title + text.
- **Mapping runs** are stored per (model rev, calc rev) pair with the engine version; each run
  keeps every auto link with its evidence (page, character span, snippet, highlight boxes, rule).
- **Human decisions** (confirm, reject, link by hand, undo) are an append-only log keyed by
  `(GlobalId, calc_key)`, not by revision, so they carry forward to every later revision while
  both keys still exist. The latest decision per pair wins; nothing is overwritten.
- A diff is therefore a key join: elements by GlobalId + `content_hash` (added / removed /
  changed with per-field before and after), edges by `(src, dst)`, calcs by `calc_key` +
  `content_hash`, links by run. `Store.compare_models(a, b)` and
  `GET /api/projects/{pid}/compare?a=&b=` already return that for two model revisions (on Harbor
  View, `/api/v2/compare` checks it against ifcdiff). Redlines, markups and
  "effects of a change" can be layered on that plus `impact.propagate()`; the diff UI is not
  built yet.
