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
uv run python -m synth.generate --check     # synthetic model + calc package + ground truth (byte-stable check)
uv run python scripts/evaluate.py           # score the full pipeline against ground truth
(cd frontend && npm install && npm run build)
uv run calc-graph serve                     # http://127.0.0.1:8000 - API + built UI
```

Then press **Load sample**. **Ingest sample rev 2** loads the model revision with column C8
removed on top. For frontend work: `uv run calc-graph serve` plus `cd frontend && npm run dev`
(http://127.0.0.1:5173, proxies `/api`). Ingest from the shell:
`uv run calc-graph ingest model.ifc calcs.pdf`. Store location: `data/store/` (override with
`CALCGRAPH_STORE`). Tests for CI live in `backend/tests/` (`uv run --extra dev pytest backend/tests`).

## Evaluate, guard, CI

- `uv run python scripts/evaluate_all.py` runs every evaluation and prints one scorecard
  (synthetic v2 ground truth first: generator self-checks and the v2 IFC through `ifc_ingest` +
  `loadpath`; then the move-a-column / registry / v2-document evaluators when they exist; the AI-step
  ratchets; the copyright guard; and the deprecated v1 + drawing-set stages, which skip when their
  local inputs are absent). It exits 1 when a gated metric drops more than 0.005 below
  `eval/baseline.json` (numbers only) or a check fails. `--synthetic-only` is what CI runs;
  `--update-baseline` accepts the current numbers. Hand labels for drawing-set slices live in the
  gitignored `data/labels/` (procedure: `scripts/label_slice.py`) and never enter git.
- **Copyright guard** - install once per clone, from the repo root:
  `git config core.hooksPath prototyping/calc-graph/scripts/git-hooks`. The pre-commit hook runs
  `scripts/check_no_copyrighted.py --staged` (blocks PDFs, images not pinned in
  `scripts/copyright_guard.json`, anything under `data/sets/` or `data/labels/`, and distinctive
  strings from the copyrighted permit set outside the per-file term allowlist), plus
  `scripts/check_llm_imports.py` and `scripts/check_ai_step.py` when calc-graph Python is staged.
  `--history` / `--range A..B` / `--tracked` scan commits or HEAD; `--self-test` proves each rule.
- **CI**: `.github/workflows/ci.yml` at the repo root (uv sync, copyright guard, AI-step ratchets,
  backend pytest, `evaluate_all --synthetic-only`, frontend build; actions pinned to SHAs).

## Layout

| Path | What |
|---|---|
| `synth/` | deterministic generator: IfcOpenShell IFC4 steel frame (459 elements, marks in psets, storeys, footings, plates as connections), PyNite member forces, PyMuPDF calc package (contents page, RAM-style tables, Mathcad-style sheets with mathtext formulas, Excel/VBA grids, one scanned hand-calc page with no text layer, cross-references), ground-truth JSON, rev 2 model |
| `backend/calcgraph/` | `ifc_ingest` (IfcOpenShell), `loadpath` (geometry contact rules), `pdf_ingest` (PyMuPDF words + spans), `segment` + `matcher` (port of the mockup's `segment()` / `runMapping()`), `calcdeps` (calc graph), `impact` (propagation), `store` (SQLite revisions), `api` (FastAPI) |
| `frontend/` | Vite + TypeScript + three.js + web-ifc port of the mockup, plus the load-path graph and impact view |
| `scripts/evaluate.py` | precision / recall per tier and per calc, load path, calc edges, revisions |
| `docs/screenshots/` | headless, timestamped captures of the running app |

## Matching rules (v1, deterministic)

Tiers as in the mockup: exact mark 0.97, mark range 0.90, mark ignoring punctuation 0.88,
mark family 0.85, section size + type (+ storey named on the line) 0.62, unique partial mark
0.50, element type only 0.30, cross-reference (mark of a different element type than the calc
designs) capped at 0.45. Contents pages and pages without a text layer are never mapped.
Two deliberate changes from the mockup: software named in a calc's title wins over software
its body cites, and the element-type fallback reads the line under the title (the mockup read
the page's second line, which is the title once a page has a running header).

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
  `GET /api/projects/1/compare?a=&b=` already return that for two model revisions (verified
  exact against ground truth: 15 removed, 12 changed for rev 1 -> rev 2). Redlines, markups and
  "effects of a change" can be layered on that plus `impact.propagate()`; the diff UI is not
  built yet.
