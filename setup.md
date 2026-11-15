# Setup

How to get a working checkout. Agents: read this before cloning, running tests, or adding data files.

## Prerequisites

- **Node.js 22 or newer** (with npm) — the repo uses npm workspaces (`packages/*`).
- **Git LFS** — all PDFs are stored in Git LFS. Install it from <https://git-lfs.com> (it ships with Git for Windows), then run once per machine:

  ```bash
  git lfs install
  ```

## First-time setup

```bash
git clone https://github.com/quilt-lead/unLoaded.git
cd unLoaded
git lfs pull     # only needed if LFS was installed after cloning
npm install      # postinstall copies web-ifc.wasm into public/
```

Check that the PDFs came down as real files, not LFS pointer stubs:

```bash
git lfs ls-files   # each PDF should be listed with a `*` (content present), not `-`
```

A pointer stub is a ~130-byte text file starting with `version https://git-lfs.github.com/spec/v1`.
If you see those, Git LFS was not installed when you cloned; run `git lfs install && git lfs pull`.

## Day-to-day commands

```bash
npm run dev        # Vite dev server
npm test           # app adapter tests + package tests
npm run typecheck
npm run smoke      # IFC -> element graph summary in Node
```

## Large files (Git LFS)

`.gitattributes` routes every `*.pdf` through LFS:

```
*.pdf filter=lfs diff=lfs merge=lfs -text
```

- **Adding a PDF:** just `git add` it. LFS handles it automatically; confirm with `git lfs ls-files`.
- **Adding another large binary type** (e.g. big `.ifc` models): `git lfs track "*.ext"`, then commit `.gitattributes` together with the files.
- **Why:** GitHub rejects any file over 100 MB unless it is in LFS, and every non-LFS binary bloats every clone forever.
- **Quota:** GitHub's free LFS allowance is about 1 GB storage and 1 GB download per month. Prefer a representative sample over every revision of every calc package.
- **Tests depend on LFS:** `packages/calc-parser/test/fixtures/calc_package.pdf` is an LFS file. Without LFS the calc-parser PDF tests read a pointer stub and fail with a PDF parse error. That is a setup problem, not a code bug.
- **Older history still holds full PDFs:** the sample calcs in `data/sampleCalc/` were first pushed before LFS was set up, so those blobs remain in history. Removing them requires `git lfs migrate import --include="*.pdf" --everything` plus a force-push of `prod`. Only do that with the team's agreement.

## Data

All IFC, JSON and sample PDF data lives in [`data/`](data/README.md), outside the app bundle. The app starts empty; import files manually.
