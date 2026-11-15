#!/usr/bin/env python3
"""Every staged calc-graph .py / .ts / .tsx must PARSE as it will be committed.

Reads the STAGED blob (`git show :<path>`), never the working tree. Why: a commit made by staging
only some hunks (`git apply --cached`, `git add -p`) while another session has uncommitted edits in
the same file can land hunks at the wrong offsets. The working tree is still correct, so a local
build passes, and the committed tree does not parse (331a5ee..76fc4cc: MovePage.tsx and api.ts
failed tsc in CI for 30 commits).

- .py: compile() in-process
- .ts / .tsx: one esbuild run over all staged blobs (syntax only: no bundling, no type check)

Usage: python scripts/check_staged_parse.py        (exit 1 and name every file that does not parse)
Wired into scripts/git-hooks/pre-commit.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile

PREFIX = "prototyping/calc-graph/"
TS = (".ts", ".tsx")


def git(*args: str, top: str) -> bytes:
    return subprocess.run(["git", "-C", top, *args], check=True, capture_output=True).stdout


def main() -> int:
    top = subprocess.run(["git", "rev-parse", "--show-toplevel"], check=True, capture_output=True, text=True).stdout.strip()
    names = git("diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z", top=top).decode().split("\0")
    paths = [p for p in names if p.startswith(PREFIX) and (p.endswith(".py") or p.endswith(TS))]
    if not paths:
        return 0
    bad: list[str] = []
    ts: list[tuple[str, bytes]] = []
    for p in paths:
        blob = git("show", f":{p}", top=top)   # ":<path>" = the index entry, path from the repo root
        if p.endswith(".py"):
            try:
                compile(blob, p, "exec", dont_inherit=True)
            except SyntaxError as e:
                bad.append(f"{p}:{e.lineno}: {e.msg}")
        else:
            ts.append((p, blob))
    if ts:
        esbuild = os.path.join(top, PREFIX, "frontend", "node_modules", ".bin", "esbuild")
        if not os.path.exists(esbuild):
            print(f"check_staged_parse: {len(ts)} staged .ts/.tsx file(s) but no esbuild at {esbuild}; "
                  f"run `npm --prefix {PREFIX}frontend ci` once", file=sys.stderr)
            return 1
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "src")
            files = []
            for p, blob in ts:
                f = os.path.join(src, p)
                os.makedirs(os.path.dirname(f), exist_ok=True)
                with open(f, "wb") as fh:
                    fh.write(blob)
                files.append(p)
            # run from the temp tree with repo-relative paths, so errors name the real file
            r = subprocess.run([esbuild, *files, f"--outdir={os.path.join(tmp, 'out')}",
                                "--log-level=error", "--log-limit=0", "--color=false"], capture_output=True, text=True, cwd=src)
            if r.returncode != 0:
                bad.append((r.stderr or r.stdout).strip())
    if bad:
        print("check_staged_parse: the STAGED content does not parse (the working tree may be fine - check what\n"
              "`git diff --cached` would commit, e.g. hunks staged with `git apply --cached` at the wrong offsets):",
              file=sys.stderr)
        for b in bad:
            print(b, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
