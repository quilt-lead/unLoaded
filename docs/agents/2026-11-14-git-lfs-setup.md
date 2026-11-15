# Git LFS for PDFs + setup.md

- **Status:** done
- **Branch:** prod (uncommitted at handoff)
- **Files owned:** `.gitattributes`, `setup.md`, the Setup section of `CLAUDE.md`, the Quick Start in `README.md`

## What and why

- Calc PDFs are big (the approved-plans sample is 68.7 MB) and GitHub rejects files over 100 MB, so `*.pdf` is now tracked by Git LFS.
- There were no setup instructions for agents, so `setup.md` was added at the repo root and linked from `CLAUDE.md` and `README.md`.

## Gotchas

- The three `data/sampleCalc/*.pdf` files were pushed as normal blobs in `9f5fc4c` before LFS existed. They become LFS objects from the next commit on, but the old blobs stay in history. Purging them needs `git lfs migrate import --include="*.pdf" --everything` and a force-push of `prod`. Not done: that needs the team's agreement.
- `packages/calc-parser/test/fixtures/calc_package.pdf` is LFS too. If the calc-parser PDF tests fail with a parse error on a fresh clone, check for LFS pointer stubs before debugging code.
- The "Node 22 or newer" line in `setup.md` is inferred from `@types/node ^22` (the repo was developed on Node 24.11); there is no `engines` field.
