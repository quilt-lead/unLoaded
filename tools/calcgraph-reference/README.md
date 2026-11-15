# calcgraph-reference: offline dev tooling (not part of the app)

The app is frontend-only. The calc engine runs in the browser as `packages/calc-mapper`. This
folder holds the Python tooling that proves the engine works and keeps the repo clean. Nothing
here is served or bundled.

| Path | What |
|---|---|
| `synth/` | Deterministic synthetic fixture generator. It writes `model_rev1.ifc`, `model_rev2.ifc` (column C8 removed), `calc_package.pdf`, `calc_supplement.pdf` and `ground_truth.json` (IfcOpenShell + PyNite + PyMuPDF). The supplement covers a calc starting mid-page, one continued after a gap, a typical-group calc, a loads-only reference and a planted size mismatch; its truth is in `ground_truth.json["supplement"]`. `--check` proves it is byte-stable. |
| `synth/harborview/` | The Harborview sample generator. It reads the demo model bundles in `data/harborview/` (plus `legacy_params.json`: per-element demand and utilisation the bundles dropped) and writes, into `data/harborview/` (committed): `harborview-rev{1,2}.ifc`, one calc PDF per calc document (`calcs/rev1/`, 82: 78 design + 4 loading, `synth/harborview/loading.py`), the same pages as one package, the rev 2 reissues and new L06 calcs (`calcs/rev2/`, 23), `ground_truth.json` and the app's `manifest.json`. `--check` proves it is byte-stable. |
| `scripts/evaluate_harborview.py` | Scores the engine on the Harborview sample: segmentation, design links, load references, calc edges, the planted size mismatch. Reported, not gated. |
| `scripts/build_graph.mjs` | IFC -> serialized element graph, using the packages the UI runs (`packages/ifc-parser` + `packages/element-graph`). |
| `scripts/evaluate.py` | The scorer. It builds the graphs, runs `packages/calc-mapper/scripts/run-pipeline.ts`, and scores segmentation, mapping per tier, xref, load path, calc edges, the diff, carried decisions and impact against ground truth. |
| `scripts/evaluate_all.py` | The scorecard plus the gate against `eval/baseline.json`, over the union of baseline and run keys. Gated metrics may not drop by more than 0.005; error metrics such as `uc_abs_err_p90` may not rise by more than max(25% of the baseline, 0.001) - an absolute 0.005 on a 0.0008 baseline would allow ~7x. Exact counts must match. A metric that disappears, or a new gated / exact one with no baseline, fails. A stage with a baseline that does not run fails, except a declared local-only stage in CI (below). |
| `scripts/check_ifc_parity.py` | Before/after gate for an IFC writer change. |
| `data/` | `SOURCES.md` is tracked; everything else (synthetic package, eval output) is gitignored local output. |

```sh
cd tools/calcgraph-reference
uv sync                                         # Python 3.12; needs Node >= 22.18 and `npm ci` at the repo root too
uv run python -m synth.generate --check         # synthetic package -> data/synthetic (byte-stable check)
uv run python scripts/evaluate.py               # score the TypeScript engine on it
uv run python scripts/evaluate_all.py --synthetic-only   # what CI gates on
uv run python scripts/evaluate_all.py                    # the full local run: every stage must run
uv run python -m synth.harborview.generate --check      # Harborview sample -> data/harborview (then npm run assets)
uv run python scripts/evaluate_harborview.py            # score the engine on it
```

What CI gates on: `synthetic_check` and `synthetic_v1` here. **`move_answer_key` is local-only**
(`LOCAL_ONLY` in `scripts/evaluate_all.py`): it needs `data/synthetic_v2`, whose generator designs with the
AISC shapes table, which is gitignored while its licence is undecided (decision D22). In CI it skips with
a LOCAL-ONLY banner at the top and bottom of the scorecard naming the metrics left unchecked, and a
GitHub `::warning::` annotation so the PR shows it; in the full
local run (no `--synthetic-only`) a skip of it is a regression, so run that before merging a change to
`packages/move-impact`. Any other stage that skips while it has a baseline fails CI.

The Python reference engine (the FastAPI backend: ingest, matcher, store) was retired here once the
TypeScript port matched it link for link on the synthetic package. It is in git history up to
the commit that introduced `packages/calc-mapper`.
