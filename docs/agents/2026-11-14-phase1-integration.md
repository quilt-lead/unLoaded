# Phase 1: integrate PR #4 (calc engine) with prod

- **Status:** active (PR open to `prod`, awaiting Carl's merge)
- **Branch:** `cs/phase1-calc-engine`, cut from `issy/integrate-calc-graph-engine` (PR #4). Supersedes PR #4 as the
  merge vehicle: per D31 in the calc-engine note, Issy stopped merging `prod` and handed integration to Carl.
- **Owned files:** merge resolutions only (`.gitignore`, `scripts/copy-assets.mjs`, the `data/` path updates),
  `tools/calcgraph-reference/scripts/copyright_guard.json`, `src/App.scope.test.ts`.
- **Working files:** none once merged.

## What this branch adds on top of PR #4

1. **`prod` merged in twice:** PR #5 (calc-viewer prototype) and PR #7 (all IFC / JSON data in `data/`).
   PR #4's code and docs win. Sample and fixture paths point at `data/`. `copy-assets.mjs` keeps copying what
   **Load sample** needs into `public/samples/`, but now from `data/`. That is on demand, so `prod`'s "workspace starts
   empty" still holds.
2. **Copyright guard allowlist (decided by Carl).** PR #5 put extracted Building 12 permit-set text into
   `prototyping/calc-viewer/` (data JSON, `viewers/assets/data.js`, build scripts). The guard's `--tracked` scan blocked
   it. Carl chose to allowlist rather than untrack. Entries are per path and per term id, so a new file carrying a
   protected term is still blocked. The five `prototyping/calc-graph/docs/screenshots/*.png` are pinned by blob sha
   after a visual check: they show only the synthetic sample ("JOB 2611 - SAMPLE OFFICE BUILDING").
   **Still open:** the repo is public and that data is in `prod`'s history either way. Untracking or scrubbing the
   history is the repo owner's call (see open question 4 in the calc-engine note).
3. **Two Windows-only test fixes.** `App.scope.test.ts` sliced `App.tsx` on `\n  };\n`, which never matches a CRLF
   checkout (`core.autocrlf=true`), so it now normalises line endings. A calc-mapper test expected an old `parseGraph`
   error message (`f7eedc4`, from the Phase 2 branch).

## Gotchas

- There's no system Python on this Windows machine. Run the tooling with `uv run --no-project python ...`.
  The guard's `--tracked` scan takes about 2 minutes (12 terms stored without `len` are glue-scanned).
- `npm test` stops at the first failing workspace, so one failure can hide others. Read every workspace's summary.
- The synthetic sample (`Load sample`) isn't in git. Generate it with
  `cd tools/calcgraph-reference && uv run python -m synth.generate`, then `npm run assets`.
- Phase 2 (`cs/phase2-calc-sets`, see its note) was cut from this branch before the PR #7 merge. Rebase or merge it
  after this lands. It carries its own copy of the CRLF test fix (`563feaf`), which will conflict trivially.

## Verification (2026-11-14, this machine)

- `npm run typecheck`, `npm test` (every workspace: 486 tests, 1 skipped), `npm run build`: pass.
- Copyright guard: `--self-test`, `--tracked`, `--range origin/prod..HEAD`: clean.
- Not run: the Python tooling job (`evaluate_all.py --synthetic-only`). The Phase 2 agent ran it on this base and it
  matched the baseline, except `synthetic_check.generator_byte_stable`, which fails on Windows before and after (likely CRLF).
  CI on Linux is the check.
