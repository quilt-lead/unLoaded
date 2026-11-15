# calcgraph-reference: offline dev tooling (not part of the app)

The app is frontend-only. The calc engine runs in the browser as `packages/calc-mapper`. This
folder holds the Python tooling that proves the engine works and keeps the repo clean. Nothing
here is served or bundled.

| Path | What |
|---|---|
| `synth/` | Deterministic synthetic fixture generator. It writes `model_rev1.ifc`, `model_rev2.ifc` (column C8 removed), `calc_package.pdf`, `calc_supplement.pdf` and `ground_truth.json` (IfcOpenShell + PyNite + PyMuPDF). The supplement covers a calc starting mid-page, one continued after a gap, a typical-group calc, a loads-only reference and a planted size mismatch; its truth is in `ground_truth.json["supplement"]`. `--check` proves it is byte-stable. |
| `scripts/build_graph.mjs` | IFC -> serialized element graph, using the packages the UI runs (`packages/ifc-parser` + `packages/element-graph`). |
| `scripts/evaluate.py` | The scorer. It builds the graphs, runs `packages/calc-mapper/scripts/run-pipeline.ts`, and scores segmentation, mapping per tier, xref, load path, calc edges, the diff, carried decisions and impact against ground truth. |
| `scripts/evaluate_all.py` | The scorecard plus the gate against `eval/baseline.json`, over the union of baseline and run keys. Gated metrics may not drop by more than 0.005; error metrics such as `uc_abs_err_p90` may not rise by more than max(25% of the baseline, 0.001) - an absolute 0.005 on a 0.0008 baseline would allow ~7x. Exact counts must match. A metric that disappears, or a new gated / exact one with no baseline, fails. A stage with a baseline that does not run fails, except a declared local-only stage in CI (below). |
| `scripts/check_no_copyrighted.py` | Copyright guard over the whole repo. It blocks PDFs, `data/sets/` and `data/labels/`, every non-text blob (images, SVG, archives, office files, unknown binaries - classified by content as well as name) and base64 payloads (data: URIs, and raw / URL-safe runs of 256+ characters) unless pinned by path + sha, and salted-hash term matches (UTF-16 / UTF-32 text is decoded first). `--range` / `--history` scan every (path, blob) a commit introduces, merge resolutions included; `--push` (CI) scans what a push introduces. Details are in its docstring. |
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

What CI gates on: `synthetic_check` and `synthetic_v1` here, and the copyright guard in its own CI job (`--self-test`, `--tracked`, then the PR range or the push). **`move_answer_key` is local-only**
(`LOCAL_ONLY` in `scripts/evaluate_all.py`): it needs `data/synthetic_v2`, whose generator designs with the
AISC shapes table, which is gitignored while its licence is undecided (decision D22). In CI it skips with
a LOCAL-ONLY banner at the top and bottom of the scorecard naming the metrics left unchecked, and a
GitHub `::warning::` annotation so the PR shows it; in the full
local run (no `--synthetic-only`) a skip of it is a regression, so run that before merging a change to
`packages/move-impact`. Any other stage that skips while it has a baseline fails CI.

Copyright guard term matching: protected terms are found as whole tokens, as camelCase / letter-digit
sub-units (`get<Term>Value`, `PRJ<number>Rev2`), and - for terms of 8 or more letters/digits - as a
substring of the file's separator-free text (`xx<term>yy`). A decimal is one number in every tier:
`1234.56` never matches a stored `123456`, and a stored `12345-6` written as `12345.6` is not found. **A term shorter
than 8 characters glued to letters or digits of the same case with no case or letter/digit boundary is
not detected: that part is mitigation, not a fix.** Below 8 characters a substring match would also hit
ordinary words and the digit runs of IFC coordinates.

Raw base64 shorter than 256 characters, or broken up by other characters, is not detected (a stated
residual). Prod's history predates the guard: it holds unpinned screenshots under
`prototyping/calc-graph/docs/screenshots/` and several `.DS_Store` versions, so `--history` on prod
fails. That history is already public and is neither rewritten nor allowlisted; CI scans what each PR
or push introduces instead (`--push`: `before..sha`, or `origin/prod..sha` for a new branch; when that
cannot be determined it scans the tree and emits a `::warning::` that the push's history was not
scanned).

Copyright guard pre-commit hook (once per clone, from the repo root):
`git config core.hooksPath tools/calcgraph-reference/scripts/git-hooks`.

The Python reference engine (the FastAPI backend: ingest, matcher, store) was retired here once the
TypeScript port matched it link for link on the synthetic package. It is in git history up to
the commit that introduced `packages/calc-mapper`.
