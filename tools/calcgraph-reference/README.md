# calcgraph-reference: offline dev tooling (not part of the app)

The app is frontend-only. The calc engine runs in the browser as `packages/calc-mapper`. This
folder holds the Python tooling that proves the engine works and keeps the repo clean. Nothing
here is served or bundled.

| Path | What |
|---|---|
| `synth/` | Deterministic synthetic fixture generator. It writes `model_rev1.ifc`, `model_rev2.ifc` (column C8 removed), `calc_package.pdf` and `ground_truth.json` (IfcOpenShell + PyNite + PyMuPDF). `--check` proves it is byte-stable. |
| `scripts/build_graph.mjs` | IFC -> serialized element graph, using the packages the UI runs (`packages/ifc-parser` + `packages/element-graph`). |
| `scripts/evaluate.py` | The scorer. It builds the graphs, runs `packages/calc-mapper/scripts/run-pipeline.ts`, and scores segmentation, mapping per tier, xref, load path, calc edges, the diff, carried decisions and impact against ground truth. |
| `scripts/evaluate_all.py` | The scorecard plus the gate against `eval/baseline.json`. Gated metrics may not drop. Exact counts must match. |
| `scripts/check_no_copyrighted.py` | Copyright guard over the whole repo. It blocks PDFs, unpinned images, `data/sets/` and `data/labels/`, and salted-hash term matches. Details are in its docstring. |
| `scripts/check_ifc_parity.py` | Before/after gate for an IFC writer change. |
| `data/` | `SOURCES.md` is tracked; everything else (synthetic package, eval output) is gitignored local output. |

```sh
cd tools/calcgraph-reference
uv sync                                         # Python 3.12; needs Node >= 22.18 and `npm ci` at the repo root too
uv run python -m synth.generate --check         # synthetic package -> data/synthetic (byte-stable check)
uv run python scripts/evaluate.py               # score the TypeScript engine on it
uv run python scripts/evaluate_all.py --synthetic-only   # what CI gates on
```

Copyright guard pre-commit hook (once per clone, from the repo root):
`git config core.hooksPath tools/calcgraph-reference/scripts/git-hooks`.

The Python reference engine (the FastAPI backend: ingest, matcher, store) was retired here once the
TypeScript port matched it link for link on the synthetic package. It is in git history up to
the commit that introduced `packages/calc-mapper`.
