# calcgraph-reference: offline dev tooling (not part of the app)

The app is frontend-only. The calc engine runs in the browser as `packages/calc-mapper`. This
folder holds the Python tooling that proves the engine works and keeps the repo clean. Nothing
here is served or bundled.

| Path | What |
|---|---|
| `synth/` | Deterministic synthetic fixture generator. It writes `model_rev1.ifc`, `model_rev2.ifc` (column C8 removed), `calc_package.pdf`, `calc_supplement.pdf` and `ground_truth.json` (IfcOpenShell + PyNite + PyMuPDF). The supplement covers a calc starting mid-page, one continued after a gap, a typical-group calc, a loads-only reference and a planted size mismatch; its truth is in `ground_truth.json["supplement"]`. `--check` proves it is byte-stable. |
| `scripts/build_graph.mjs` | IFC -> serialized element graph, using the packages the UI runs (`packages/ifc-parser` + `packages/element-graph`). |
| `scripts/evaluate.py` | The scorer. It builds the graphs, runs `packages/calc-mapper/scripts/run-pipeline.ts`, and scores segmentation, mapping per tier, xref, load path, calc edges, the diff, carried decisions and impact against ground truth. |
| `scripts/evaluate_all.py` | The scorecard plus the gate against `eval/baseline.json`, over the union of baseline and run keys. Gated metrics may not drop (error metrics such as `uc_abs_err_p90` may not rise). Exact counts must match. A metric that disappears, or a new gated / exact one with no baseline, fails. A stage with a baseline that does not run fails, except a declared local-only stage in CI (below). |
| `scripts/check_no_copyrighted.py` | Copyright guard over the whole repo. It blocks PDFs, `data/sets/` and `data/labels/`, every non-text blob (images, SVG, archives, office files, unknown binaries - classified by content as well as name) and embedded base64 payloads unless pinned by path + sha, and salted-hash term matches (UTF-16 / UTF-32 text is decoded first). `--range` / `--history` scan every (path, blob) a commit introduces, merge resolutions included. Details are in its docstring. |
| `scripts/check_ifc_parity.py` | Before/after gate for an IFC writer change. |
| `data/` | `SOURCES.md` is tracked; everything else (synthetic package, eval output) is gitignored local output. |

```sh
cd tools/calcgraph-reference
uv sync                                         # Python 3.12; needs Node >= 22.18 and `npm ci` at the repo root too
uv run python -m synth.generate --check         # synthetic package -> data/synthetic (byte-stable check)
uv run python scripts/evaluate.py               # score the TypeScript engine on it
uv run python scripts/evaluate_all.py --synthetic-only   # what CI gates on
uv run python scripts/evaluate_all.py                    # the full local run: every stage must run
```

What CI gates on: `synthetic_check`, `synthetic_v1` and `copyright`. **`move_answer_key` is local-only**
(`LOCAL_ONLY` in `scripts/evaluate_all.py`): it needs `data/synthetic_v2`, whose generator designs with the
AISC shapes table, which is gitignored while its licence is undecided (decision D22). In CI it skips with
a LOCAL-ONLY banner at the top and bottom of the scorecard naming the metrics left unchecked; in the full
local run (no `--synthetic-only`) a skip of it is a regression, so run that before merging a change to
`packages/move-impact`. Any other stage that skips while it has a baseline fails CI.

Copyright guard term matching: protected terms are found as whole tokens, as camelCase / letter-digit
sub-units (`get<Term>Value`, `PRJ<number>Rev2`, `12345.6` for a stored `12345-6`), and - for terms of 8 or
more letters/digits - as a substring of the file's separator-free text (`xx<term>yy`). **A term shorter
than 8 characters glued to letters or digits of the same case with no case or letter/digit boundary is
not detected: that part is mitigation, not a fix.** Below 8 characters a substring match would also hit
ordinary words and the digit runs of IFC coordinates.

Copyright guard pre-commit hook (once per clone, from the repo root):
`git config core.hooksPath tools/calcgraph-reference/scripts/git-hooks`.

The Python reference engine (the FastAPI backend: ingest, matcher, store) was retired here once the
TypeScript port matched it link for link on the synthetic package. It is in git history up to
the commit that introduced `packages/calc-mapper`.
